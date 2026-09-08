"""
Shared base for vision **estimator** nodes (object detection, segmentation, pose).

Every estimator family shares the identical lifecycle (notes.md Q6):

    create(Config.VARIANT) -> setup() -> process(frame) -> ResultList -> release()

Only two things differ per family: the output ``@type`` and the curated map of
selectable models. So all the machinery lives here once; a concrete family node is
a thin subclass that sets just two class attributes::

    class ObjectDetectorNode(BaseEstimatorNode):
        RESULT_TYPE = DETECTION_RESULT
        MODELS = {"YOLOv8-N": ModelSpec(...), ...}

Design decisions realised here:

- **Image inlet ``RGB_FRAME``** (Q4) — gray auto-adapts; depth is refused.
- **Lazy ``setup()`` on first frame** (Q7) — the estimator is a transform, not a
  device. The built estimator is cached; changing ``model`` — or any field a
  spec lists in ``rebuild_fields`` — releases it so the next frame rebuilds.
- **Synchronous ``process()``** in ``worker()`` (Q8) — the upstream camera thread
  self-throttles to inference speed; frame->result ordering is trivially correct.
- **Status label** (Q9) — "Loading model…" before the slow first-frame setup, then
  a rolling "N results · Xms" after each inference.
- **Heavy backends are lazy-imported inside ``build()``** (Q13) — only the chosen
  model's module is imported, and only when a frame actually flows.
- **Settings-first** (sixth inquisition) — every knob is a ``setting()``;
  ``model`` and ``min_score`` are *seeded* to config ports in ``init()`` so the
  node keeps its familiar face, and the user may demote them.
- **Per-backend bags, hidden by model** — the backends behind one ``model``
  dropdown have disjoint knobs, so each gets its own bag and the irrelevant
  ones are hidden rather than left visible and inert. See ``estimator_settings``.
"""

import importlib
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Optional

from haywire.core.execution.execution_context import ExecutionContext
from haywire.core.node import BaseNode
from haywire.core.settings import UiState
from haywire.core.types.enums import PortType

from .estimator_settings import UNSET, InferenceSettings, OverlaySettings, SelectionSettings


@dataclass(frozen=True)
class ModelSpec:
    """
    A lazily-resolvable estimator model.

    Declared with *strings* so a family node can list its models without importing
    any heavy backend at module/registration time. The backend is imported and the
    config variant resolved only on first frame, inside ``hb_ensure_estimator``.

    Attributes:
        module: Dotted module path of the estimator class
            (e.g. ``"visiongraph.estimator.spatial.YOLOv8Detector"``).
        cls_name: Estimator class name within that module (e.g. ``"YOLOv8Detector"``).
        config_cls_name: Config enum class name (e.g. ``"YOLOv8Config"``).
        variant: Config enum member name (e.g. ``"YOLOv8_N"``).
        bags: Accessor names of the per-backend settings bags this model uses.
            Everything else is hidden in the panel while it is selected.
        rebuild_fields: Field names that this backend consumes when the model is
            BUILT rather than per frame. Changing one releases the cached
            estimator so the next frame rebuilds it. The set is per-spec because
            liveness is per-backend: ``min_score`` is read inside ``process()``
            by Ultralytics/MoveNet/SSD/MaskRCNN but inside ``setup()`` by
            MediaPipe, so only MediaPipe's specs list it.
    """

    module: str
    cls_name: str
    config_cls_name: str
    variant: str
    bags: frozenset = field(default_factory=frozenset)
    rebuild_fields: frozenset = field(default_factory=frozenset)

    def build(self) -> Any:
        """Import the backend, resolve the config variant, and ``create()`` it."""
        mod = importlib.import_module(self.module)
        estimator_cls = getattr(mod, self.cls_name)
        config_cls = getattr(mod, self.config_cls_name)
        config_variant = getattr(config_cls, self.variant)
        return estimator_cls.create(config_variant)


# NOTE: intentionally NOT decorated with @node. The NodeRegistry only registers
# classes carrying ``class_identity`` (set by @node), so an undecorated BaseNode
# subclass is never offered in the menu — exactly what we want for a shared base.
# The concrete family subclasses each carry their own @node(...).
class BaseEstimatorNode(BaseNode):
    """
    Abstract base for image-in / result-out estimator nodes.

    Subclass contract (class attributes):
        MODELS: ``{label: ModelSpec(...)}`` — the curated models, declared as
            *strings* so the heavy backend module is imported only on first
            frame, never at library load or node-add (Q13).
        Backend bags: alias whichever bags this family's MODELS reference, under
            the accessor names ``ModelSpec.bags`` uses.

    Inputs:
        execute: Control flow in (pulse per frame).
        frame: The image to run inference on (RGB_FRAME).

    Settings:
        model / min_score: seeded to config ports — the node's default face.
        color: overlay colour stamped on the emitted result (see OverlaySettings).
        per-backend bags: shown only while a model that uses them is selected.

    Outputs:
        result_ready: Control flow out (pulsed after inference).
        result: The estimator's result list (typed by the subclass).
        count: Number of results.
    """

    # --- Subclass contract -------------------------------------------------
    MODELS: "dict[str, ModelSpec]" = {}

    if TYPE_CHECKING:
        # mypy view: the bags are bound instances, not the aliased classes.
        inference: InferenceSettings
        overlay: OverlaySettings
        selection: SelectionSettings
    else:
        inference = InferenceSettings
        overlay = OverlaySettings
        # Each family node overrides this with `selection_bag(MODELS)` so the
        # dropdown carries its own labels; the base's is empty on purpose.
        selection = SelectionSettings

    def hb_result_type(self) -> Any:
        """Return the ``@type`` class this node outlets. Subclasses override with
        an in-method import (the result types are light — notes.md Q13)."""
        raise NotImplementedError

    def init(self):
        from haywire.barn.builtin.types import STRING, INT
        from haybale_core.types import EXEC
        from haywire.barn.builtin.widgets import SimpleLabelWidget
        from haybale_visiongraph.types.frame_type import RGB_FRAME

        # Control in.
        self.add(EXEC.as_inlet("execute", label="Run"))

        # Image in.
        self.add(RGB_FRAME.as_inlet("frame", label="Frame"))

        # Status display — a read-only label, never a setting.
        self.add(
            STRING.as_config("status", default="Idle", label="Status", widget=SimpleLabelWidget.config())
        )

        # Control out.
        self.add(EXEC.as_outlet("result_ready", label="Result Ready"))

        # Result out (typed by the subclass) + convenience count.
        result_type = self.hb_result_type()
        self.add(result_type.as_outlet("result", label="Result"))
        self.add(INT.as_outlet("count", label="Count"))

        # Seeded promotions: this node's default face. In init(), NOT post_init
        # — post_init also runs on graph load, after promotions have been
        # restored, so promoting there would undo a user's demotion on every
        # load. init() runs only on a fresh drop.
        self.selection.promote("model", PortType.CONFIG)
        self.inference.promote("min_score", PortType.CONFIG)

    def post_init(self):
        """Initialise the lazy-estimator cache and wire setting subscriptions."""
        self.hb_estimator: Optional[Any] = None
        self.hb_loaded_model: Optional[str] = None

        # on_change='method' string dispatch was retired for settings (ADR
        # 0013), so both of these are subscribe_field callbacks now.
        self.selection.subscribe_field("model", self.hb_on_model_change)
        self.inference.subscribe_field("min_score", self.hb_on_maybe_rebuild_field)
        for accessor in self.hb_backend_bags():
            bag = getattr(self, accessor, None)
            if bag is not None:
                bag.subscribe(self.hb_on_bag_field_changed)

        self.hb_refresh_bag_visibility()

    # --- model / bag plumbing ----------------------------------------------

    def hb_current_spec(self) -> Optional[ModelSpec]:
        """The ModelSpec for the currently selected model label."""
        return type(self).MODELS.get(str(self.selection.model))

    @classmethod
    def hb_backend_bags(cls) -> frozenset:
        """Every per-backend bag accessor any of this family's models uses."""
        return frozenset().union(*(spec.bags for spec in cls.MODELS.values())) if cls.MODELS else frozenset()

    def hb_refresh_bag_visibility(self):
        """Hide the per-backend bags the selected model does not use.

        Cross-checking against the *spec* rather than a hand-kept list means a
        new model added to MODELS carries its own answer. Uses the bulk form,
        which walks each bag's own declared fields, so no field names live here.
        """
        spec = self.hb_current_spec()
        active = spec.bags if spec is not None else frozenset()
        for accessor in self.hb_backend_bags():
            bag = getattr(self, accessor, None)
            if bag is not None:
                bag.set_ui_state_all(UiState.NORMAL if accessor in active else UiState.HIDDEN)

    def hb_on_model_change(self, value=None, old=None):
        """A model change invalidates the estimator AND re-gates the panel."""
        self.hb_release()
        self.hb_refresh_bag_visibility()
        self.hb_update_status("Model changed — will load on next frame")

    def hb_on_maybe_rebuild_field(self, value=None, old=None):
        """Release the estimator only if THIS backend builds with that field.

        ``min_score`` is live for Ultralytics/MoveNet/SSD/MaskRCNN (read inside
        ``process()``) but rebuild-category for MediaPipe (consumed by
        ``setup()`` as ``min_pose_detection_confidence``). Reloading a model on
        every slider step would be unusable on the backends where it is live,
        so the spec decides.
        """
        spec = self.hb_current_spec()
        if spec is not None and "min_score" in spec.rebuild_fields:
            self.hb_release()

    def hb_on_bag_field_changed(self, name=None, value=None, old=None):
        """A per-backend field changed; release if this backend builds with it."""
        spec = self.hb_current_spec()
        if spec is not None and name in spec.rebuild_fields:
            self.hb_release()

    # --- estimator lifecycle ------------------------------------------------

    def on_shutdown(self, context: ExecutionContext):
        """Release the estimator when the flow stops."""
        self.hb_release()

    def on_teardown(self):
        """Release the estimator when the node is destroyed."""
        self.hb_release()

    def hb_release(self):
        """Release the cached estimator, if any."""
        if getattr(self, "hb_estimator", None) is not None:
            try:
                self.hb_estimator.release()
            except Exception:
                pass
            self.hb_estimator = None
            self.hb_loaded_model = None

    def hb_ensure_estimator(self) -> Optional[Any]:
        """
        Lazily build + ``setup()`` the estimator for the current model choice.

        Rebuild-category settings are applied in the window BETWEEN ``create()``
        and ``setup()`` — that is what makes them reachable at all, since
        ``create()`` takes only the config variant. (``engine`` is the one knob
        that stays unreachable: ``__init__`` consumes the enum into an engine
        object immediately, so there is no window for it.)
        """
        model_label = str(self.selection.model)
        if self.hb_estimator is not None and self.hb_loaded_model == model_label:
            return self.hb_estimator

        # Model changed or first use — drop any stale estimator first.
        self.hb_release()

        spec = type(self).MODELS.get(model_label)
        if spec is None:
            self.hb_update_status(f"Unknown model: {model_label}")
            return None

        self.hb_update_status(f"Loading model: {model_label}…")
        try:
            estimator = spec.build()
            self.hb_apply_build_settings(estimator, spec)
            estimator.setup()
        except Exception as e:
            self.hb_update_status(f"Load error: {e}")
            self.hb_estimator = None
            self.hb_loaded_model = None
            return None

        self.hb_estimator = estimator
        self.hb_loaded_model = model_label
        return estimator

    def hb_apply_build_settings(self, estimator: Any, spec: ModelSpec):
        """Push rebuild-category settings onto a freshly-created estimator."""
        estimator.min_score = float(self.inference.min_score)
        for accessor in spec.bags:
            bag = getattr(self, accessor, None)
            if bag is None:
                continue
            for name in type(bag)._property_settings():
                if name in spec.rebuild_fields:
                    self.hb_assign(estimator, name, getattr(bag, name))

    def hb_apply_live_settings(self, estimator: Any, spec: ModelSpec):
        """Push live settings onto the running estimator, before ``process()``.

        Done per frame rather than through a subscription: these are a handful
        of attribute writes against an inference call costing tens of
        milliseconds, and it removes any chance of the estimator drifting out
        of sync with the panel.
        """
        if "min_score" not in spec.rebuild_fields:
            estimator.min_score = float(self.inference.min_score)
        for accessor in spec.bags:
            bag = getattr(self, accessor, None)
            if bag is None:
                continue
            for name in type(bag)._property_settings():
                if name not in spec.rebuild_fields:
                    self.hb_assign(estimator, name, getattr(bag, name))

    @staticmethod
    def hb_assign(estimator: Any, name: str, value: Any):
        """Write one setting onto the estimator, translating where the shapes differ.

        The NMS fields live on a nested ``nms_options`` dataclass rather than on
        the estimator, and its ``eta``/``top_k`` are ``Optional`` — which a
        settings field cannot express, hence the UNSET sentinel.
        """
        if name in ("enabled", "score_threshold", "nms_threshold", "eta", "top_k", "batch_mode"):
            options = getattr(estimator, "nms_options", None)
            if options is None:
                return
            if name in ("eta", "top_k"):
                setattr(options, name, None if value == UNSET else value)
            elif name == "batch_mode":
                from visiongraph.model.NMSOptions import NMSBatchMode

                setattr(options, name, NMSBatchMode[str(value)])
            else:
                setattr(options, name, value)
            return
        setattr(estimator, name, value)

    # --- execution ----------------------------------------------------------

    def worker(self, context: ExecutionContext, frame=None) -> Optional[str]:
        """Run inference on one frame, synchronously (Q8)."""
        from haybale_visiongraph.types.frame_type import BaseFrame

        if frame is None or not isinstance(frame, BaseFrame) or not frame.is_valid():
            self.hb_update_status("No valid frame")
            return None

        estimator = self.hb_ensure_estimator()
        if estimator is None:
            return None

        spec = self.hb_current_spec()
        if spec is not None:
            self.hb_apply_live_settings(estimator, spec)

        try:
            t0 = time.time()
            results = estimator.process(frame.data)
            elapsed_ms = (time.time() - t0) * 1000.0
        except Exception as e:
            self.hb_update_status(f"Inference error: {e}")
            return None

        # min_score is applied by the estimator itself now, not post-filtered
        # here. The old Python filter could only ever REMOVE results the
        # backend had already kept at its own default (0.3/0.5), so lowering
        # this below that default did nothing.
        result_type = self.hb_result_type()
        self.out("result", result_type(results=results, color=str(self.overlay.color)))
        count = len(results) if results is not None else 0
        self.out("count", count)
        self.hb_update_status(f"{count} results · {elapsed_ms:.0f}ms")
        return "result_ready"

    def hb_update_status(self, status: str):
        """Update the status label (re-renders the bound widget live)."""
        try:
            self.ports["status"].set_value(status)
        except Exception:
            pass
