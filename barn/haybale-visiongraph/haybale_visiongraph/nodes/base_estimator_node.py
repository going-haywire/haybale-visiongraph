"""
Shared base for vision **estimator** nodes (object detection, segmentation, pose).

Every estimator family shares the identical lifecycle (notes.md Q6):

    build from local files -> setup() -> process(frame) -> ResultList -> release()

Only two things differ per family: the output ``@type`` and the curated map of
selectable models, which are catalog entries. So all the machinery lives here once; a concrete family node is
a thin subclass that sets just two class attributes::

    class ObjectDetectorNode(BaseEstimatorNode):
        RESULT_TYPE = DETECTION_RESULT
        FAMILY = "object-detection"
        MODELS = {"haybale-visiongraph:catalog:yolov8n": ModelSpec(...), ...}

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
- **Models come from haybale-models** — the ``model`` port takes a catalog entry; a
  model not on this machine is listed as needed, and nothing downloads here.
- **Settings-first** (sixth inquisition) — every other knob is a ``setting()``;
  ``min_score`` is *seeded* to a config port in ``init()`` so the node keeps its
  familiar face, and the user may demote it.
- **Per-backend bags, hidden by model** — the backends behind one ``model``
  dropdown have disjoint knobs, so each gets its own bag and the irrelevant
  ones are hidden rather than left visible and inert. See ``estimator_settings``.
"""

import importlib
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from haywire.core.execution.execution_context import ExecutionContext
from haywire.core.node import BaseNode
from haywire.core.node.node_warning import NodeWarning
from haywire.core.settings import UiState, bag, settings_fields

from haybale_models.consumer import KIND, resolve_port
from haybale_models.resolver import ModelMissing
from haybale_models.value.model_ref import ModelRef

from .estimator_settings import InferenceSettings, OverlaySettings


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

    def build(self, files: dict[str, Path]) -> Any:
        """Import the backend and construct it from local files, as its ``create()`` would.

        ``create()`` itself would hand the backend repository assets that download by themselves.

        Args:
            files: The resolved files by name inside the resource; ``""`` for a single file.
        """
        from visiongraph.data.Asset import Asset

        mod = importlib.import_module(self.module)
        estimator_cls = getattr(mod, self.cls_name)
        value = getattr(getattr(mod, self.config_cls_name), self.variant).value
        items = value if isinstance(value, tuple) else (value,)
        assets = [_local(item, files) for item in items if isinstance(item, Asset)]
        rest = [item for item in items if not isinstance(item, Asset)]
        if not rest:
            return estimator_cls(task=assets[0])
        if isinstance(rest[0], bool):
            return estimator_cls(*assets, multi_pose=rest[0])
        if len(assets) == 1:
            return estimator_cls(assets[0], labels=rest[0])
        return estimator_cls(*assets, rest[0])


def _local(asset: Any, files: dict[str, Path]) -> Any:
    """Return *asset*'s resolved file as a local asset."""
    from visiongraph.data.LocalAsset import LocalAsset

    return LocalAsset(files[asset.name] if asset.name in files else files[""])


# NOTE: intentionally NOT decorated with @node. The NodeRegistry only registers
# classes carrying ``class_identity`` (set by @node), so an undecorated BaseNode
# subclass is never offered in the menu — exactly what we want for a shared base.
# The concrete family subclasses each carry their own @node(...).
class BaseEstimatorNode(BaseNode):
    """
    Abstract base for image-in / result-out estimator nodes.

    Subclass contract (class attributes):
        FAMILY: The ``purpose`` of the catalog entries this node lists.
        MODELS: ``{catalog key: ModelSpec(...)}`` — the curated models, declared as
            *strings* so the heavy backend module is imported only on first
            frame, never at library load or node-add (Q13).
        Backend bags: alias whichever bags this family's MODELS reference, under
            the accessor names ``ModelSpec.bags`` uses.

    Inputs:
        execute: Control flow in (pulse per frame).
        frame: The image to run inference on (RGB_FRAME).

    Settings:
        model: Port taking a catalog entry of this family; starts empty.
        min_score: seeded to a config port — the node's default face.
        color: overlay colour stamped on the emitted result (see OverlaySettings).
        per-backend bags: shown only while a model that uses them is selected.

    Outputs:
        result_ready: Control flow out (pulsed after inference).
        result: The estimator's result list (typed by the subclass).
        count: Number of results.
    """

    # --- Subclass contract -------------------------------------------------
    FAMILY: str = ""
    MODELS: "dict[str, ModelSpec]" = {}

    inference = bag(InferenceSettings)
    overlay = bag(OverlaySettings)

    def hb_result_type(self) -> Any:
        """Return the ``@type`` class this node outlets. Subclasses override with
        an in-method import (the result types are light — notes.md Q13)."""
        raise NotImplementedError

    def hb_add_model_port(self):
        """Add the ``model`` port: a catalog entry of this family, chosen in the picker."""
        from haybale_models.types.model_ref import MODEL_REF

        self.add(
            MODEL_REF.as_inlet(
                "model",
                label="Model",
                description="Which backend + weights to run. Changing this reloads the model.",
                on_change="hb_on_model_change",
                widget_config={"properties": {"catalog_only": True, "filter": {"purpose": [self.FAMILY]}}},
            )
        )

    def hb_replace_stale_model_port(self):
        """Give a node from an older graph the current ``model`` port, empty.

        A loaded node's ports come from its saved file, so one saved with the model dropdown has a
        string port here instead. Its label is dropped: the node asks for a model.
        """
        from haybale_models.types.model_ref import MODEL_REF

        current = self.ports.get("model")
        if current is not None and current.type_cls is MODEL_REF and "selection.model" not in self.ports:
            return
        with self.rejig(include=["model", "selection.model"]):
            self.hb_add_model_port()

    def init(self):
        from haywire.barn.builtin.types import STRING, INT
        from haywire.barn.builtin.types import EXEC
        from haywire.barn.builtin.widgets import SimpleLabelWidget
        from haybale_visiongraph.types.frame_type import RGB_FRAME

        # Control in.
        self.add(EXEC.as_inlet("execute", label="Run"))

        # Image in.
        self.add(RGB_FRAME.as_inlet("frame", label="Frame"))

        self.hb_add_model_port()

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

    def post_init(self):
        """Initialise the lazy-estimator cache and wire setting subscriptions."""
        self.hb_estimator: Optional[Any] = None
        self.hb_loaded_model: Optional[str] = None
        self.hb_failed_load: Optional[str] = None
        self.hb_failed_status: str = ""
        self.hb_replace_stale_model_port()

        # on_change='method' string dispatch was retired for settings (ADR
        # 0013), so this is a subscribe_field callback.
        self.inference._subscribe_field("min_score", self.hb_on_maybe_rebuild_field)
        for accessor in self.hb_backend_bags():
            bag = getattr(self, accessor, None)
            if bag is not None:
                bag._subscribe(self.hb_on_bag_field_changed)

        self.hb_refresh_bag_visibility()

    # --- model / bag plumbing ----------------------------------------------

    def hb_current_ref(self) -> ModelRef:
        """The reference on the ``model`` port."""
        value = self.ports["model"].get_value()
        if isinstance(value, ModelRef):
            return value
        return ModelRef.from_dict(value) if isinstance(value, dict) else ModelRef()

    def hb_current_spec(self) -> Optional[ModelSpec]:
        """The ModelSpec of the chosen catalog entry; ``None`` for no model or a foreign one."""
        return type(self).MODELS.get(self.hb_current_ref().catalog or "")

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
                bag._set_ui_state_all(UiState.NORMAL if accessor in active else UiState.HIDDEN)

    def hb_on_model_change(self, port=None, value=None):
        """A model change invalidates the estimator AND re-gates the panel."""
        self.hb_release()
        self.hb_failed_load = None
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
            self.hb_failed_load = None

    def hb_on_bag_field_changed(self, name=None, value=None, old=None):
        """A per-backend field changed; release if this backend builds with it."""
        spec = self.hb_current_spec()
        if spec is not None and name in spec.rebuild_fields:
            self.hb_release()
            self.hb_failed_load = None

    # --- estimator lifecycle ------------------------------------------------

    def on_shutdown(self, context: ExecutionContext):
        """Release the estimator when the flow stops; the next start tries a failed load again."""
        self.hb_release()
        self.hb_failed_load = None

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
        Lazily build + ``setup()`` the estimator for the chosen model.

        Rebuild-category settings are applied in the window BETWEEN construction
        and ``setup()`` — that is what makes them reachable at all. (``engine`` is
        the one knob that stays unreachable: ``__init__`` consumes the enum into an
        engine object immediately, so there is no window for it.)

        Returns ``None`` when no model is chosen, its files are not on this machine,
        the entry is not one of this node's, or it fails to load.
        """
        ref = self.hb_current_ref()
        chosen = ref.catalog or ""
        if self.hb_estimator is not None and self.hb_loaded_model == chosen:
            return self.hb_estimator

        # Model changed or first use — drop any stale estimator first.
        self.hb_release()

        try:
            resolved = resolve_port(self, "model")
        except ModelMissing:
            # The file a load failed on is gone; another one may arrive under the same digest.
            self.hb_failed_load = None
            self.hb_update_status("Model not downloaded" if chosen else "Choose a model")
            return None

        spec = type(self).MODELS.get(chosen)
        if spec is None:
            message = "This node cannot run this model"
            self.wrapper.replace_warnings(
                KIND, [NodeWarning(message=message, source_version=None, kind=KIND)]
            )
            self.hb_update_status(message)
            return None

        # A failed load fails the same way every frame until something it depends on changes.
        if self.hb_failed_load == resolved.key:
            self.hb_update_status(self.hb_failed_status)
            return None

        self.hb_update_status(f"Loading model: {chosen.rsplit(':', 1)[-1]}…")
        try:
            estimator = spec.build(resolved.files)
            self.hb_apply_build_settings(estimator, spec)
            estimator.setup()
        except Exception as e:
            self.hb_failed_status = f"Load error: {e}"
            self.hb_update_status(self.hb_failed_status)
            self.hb_estimator = None
            self.hb_loaded_model = None
            self.hb_failed_load = resolved.key
            return None

        self.hb_estimator = estimator
        self.hb_loaded_model = chosen
        self.hb_failed_load = None
        return estimator

    def hb_apply_build_settings(self, estimator: Any, spec: ModelSpec):
        """Push rebuild-category settings onto a freshly-created estimator."""
        estimator.min_score = float(self.inference.min_score)
        for accessor in spec.bags:
            bag = getattr(self, accessor, None)
            if bag is None:
                continue
            for name in settings_fields(bag):
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
            for name in settings_fields(bag):
                if name not in spec.rebuild_fields:
                    self.hb_assign(estimator, name, getattr(bag, name))

    @staticmethod
    def hb_assign(estimator: Any, name: str, value: Any):
        """Write one setting onto the estimator, translating where the shapes differ.

        The NMS fields live on a nested ``nms_options`` dataclass rather than on
        the estimator. Its ``eta``/``top_k`` are ``Optional`` and the settings
        fields are ``OPTIONAL[...]``, so the value already IS ``None`` when the
        user cleared it — no per-name sentinel translation to keep in sync with
        the declarations in ``estimator_settings``.
        """
        if name in ("enabled", "score_threshold", "nms_threshold", "eta", "top_k", "batch_mode"):
            options = getattr(estimator, "nms_options", None)
            if options is None:
                return
            if name == "batch_mode":
                from visiongraph.model.NMSOptions import NMSBatchMode

                setattr(options, name, NMSBatchMode[str(value)])
            else:
                setattr(options, name, value)
            return
        setattr(estimator, name, value)

    # --- execution ----------------------------------------------------------

    def worker(self, context: ExecutionContext, frame=None, model=None) -> Optional[str]:
        """Run inference on one frame, synchronously (Q8)."""
        from haybale_visiongraph.types.frame_type import BaseFrame

        if frame is None or not isinstance(frame, BaseFrame) or not frame.is_valid():
            self.hb_update_status("No valid frame")
            return None

        estimator = self.hb_ensure_estimator()
        if estimator is None:
            self.out("result", self.hb_result_type()(results=[], color=str(self.overlay.color)))
            self.out("count", 0)
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
