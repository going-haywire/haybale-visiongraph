"""
Shared base for vision **estimator** nodes (object detection, segmentation, pose).

Every estimator family shares the identical lifecycle (notes.md Q6):

    create(Config.VARIANT) -> setup() -> process(frame) -> ResultList -> release()

Only two things differ per family: the output ``@type`` and the curated map of
selectable models. So all the machinery lives here once; a concrete family node is
a thin subclass that sets just two class attributes::

    class ObjectDetectorNode(BaseEstimatorNode):
        RESULT_TYPE = DETECTION_RESULT
        MODELS = {"YOLOv8-N": (YOLOv8Detector, YOLOv8Config.YOLOv8_N), ...}

Design decisions realised here:

- **Image inlet ``RGB_FRAME``** (Q4) — gray auto-adapts; depth is refused.
- **Lazy ``setup()`` on first frame** (Q7) — the estimator is a transform, not a
  device. The built estimator is cached; changing the ``model`` config releases it
  so the next frame rebuilds. No load/unload control ports.
- **Synchronous ``process()``** in ``worker()`` (Q8) — the upstream camera thread
  self-throttles to inference speed; frame->result ordering is trivially correct.
- **Status label** (Q9) — "Loading model…" before the slow first-frame setup, then
  a rolling "N results · Xms" after each inference. No mid-``process()`` progress:
  a synchronous worker has no yield point.
- **Heavy backends are lazy-imported inside ``setup()``** (Q13) — only the chosen
  model's module is imported, and only when a frame actually flows.

Subclasses provide their model classes/configs in ``MODELS``; this base never
imports a backend itself.
"""

import importlib
import time
from dataclasses import dataclass
from typing import Any, Optional

from haywire.core.execution.execution_context import ExecutionContext
from haywire.core.node import BaseNode


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
    """

    module: str
    cls_name: str
    config_cls_name: str
    variant: str

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
        RESULT_TYPE: the ``@type`` class this node outlets (e.g. ``DETECTION_RESULT``).
        MODELS: ``{label: ModelSpec(...)}`` — the curated models, declared as
            *strings* (module path / class / config class / variant) so the heavy
            backend module is imported only on first frame, never at library load
            or node-add (Q13).

    Inputs:
        execute: Control flow in (pulse per frame).
        frame: The image to run inference on (RGB_FRAME).
        model: Which model/backend to use (dropdown over ``MODELS``).
        min_score: Drop results below this confidence.

    Outputs:
        result_ready: Control flow out (pulsed after inference).
        result: The estimator's result list (typed by ``RESULT_TYPE``).
        count: Number of results.
    """

    # --- Subclass contract -------------------------------------------------
    MODELS: "dict[str, ModelSpec]" = {}

    def hb_result_type(self) -> Any:
        """Return the ``@type`` class this node outlets. Subclasses override with
        an in-method import (the result types are light — notes.md Q13)."""
        raise NotImplementedError

    def init(self):
        from haybale_core.types import EXEC, STRING, INT, FLOAT
        from haybale_core.widgets.basic_widgets import (
            SelectWidget,
            NumberWidget,
            SimpleLabelWidget,
        )
        from haybale_visiongraph.types.frame_type import RGB_FRAME

        # Control in.
        self.add(EXEC.as_inlet("execute", label="Run"))

        # Image in.
        self.add(RGB_FRAME.as_inlet("frame", label="Frame"))

        # Model selection — a curated dropdown over this family's MODELS.
        model_labels = list(type(self).MODELS.keys())
        default_model = model_labels[0] if model_labels else ""
        self.add(
            STRING.as_config(
                "model",
                default=default_model,
                label="Model",
                widget=SelectWidget.config(properties={"options": model_labels}),
                on_change="hb_on_model_change",
            )
        )

        # Confidence threshold — frequently reached for, so a config (Q14).
        self.add(
            FLOAT.as_config(
                "min_score",
                default=0.0,
                label="Min Score",
                widget=NumberWidget.config(properties={"min": 0.0, "max": 1.0, "step": 0.05}),
            )
        )

        # Status display.
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
        """Initialise the lazy-estimator cache."""
        self.hb_estimator: Optional[Any] = None
        self.hb_loaded_model: Optional[str] = None

    def on_shutdown(self, context: ExecutionContext):
        """Release the estimator when the flow stops."""
        self.hb_release()

    def on_teardown(self):
        """Release the estimator when the node is destroyed."""
        self.hb_release()

    def hb_on_model_change(self, port=None, *args):
        """A model change invalidates the cached estimator (rebuilt next frame)."""
        self.hb_release()
        self.hb_update_status("Model changed — will load on next frame")

    def hb_release(self):
        """Release the cached estimator, if any."""
        if self.hb_estimator is not None:
            try:
                self.hb_estimator.release()
            except Exception:
                pass
            self.hb_estimator = None
            self.hb_loaded_model = None

    def hb_ensure_estimator(self) -> Optional[Any]:
        """
        Lazily build + ``setup()`` the estimator for the current model choice.

        Returns the cached estimator, building it on first use or after a model
        change. Heavy backend modules are imported only here (Q13). Returns
        ``None`` if the model can't be resolved.
        """
        model_label = self.value("model")
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
            estimator.setup()
        except Exception as e:
            self.hb_update_status(f"Load error: {e}")
            self.hb_estimator = None
            self.hb_loaded_model = None
            return None

        self.hb_estimator = estimator
        self.hb_loaded_model = model_label
        return estimator

    def worker(self, context: ExecutionContext, frame=None) -> Optional[str]:
        """Run inference on one frame, synchronously (Q8)."""
        from haybale_visiongraph.types.frame_type import BaseFrame

        if frame is None or not isinstance(frame, BaseFrame) or not frame.is_valid():
            self.hb_update_status("No valid frame")
            return None

        estimator = self.hb_ensure_estimator()
        if estimator is None:
            return None

        try:
            t0 = time.time()
            results = estimator.process(frame.data)
            elapsed_ms = (time.time() - t0) * 1000.0
        except Exception as e:
            self.hb_update_status(f"Inference error: {e}")
            return None

        results = self.hb_apply_min_score(results)

        result_type = self.hb_result_type()
        self.out("result", result_type(results=results))
        count = len(results) if results is not None else 0
        self.out("count", count)
        self.hb_update_status(f"{count} results · {elapsed_ms:.0f}ms")
        return "result_ready"

    def hb_apply_min_score(self, results):
        """Filter results below the ``min_score`` config, preserving list type."""
        min_score = self.value("min_score") or 0.0
        if min_score <= 0.0 or results is None:
            return results
        from visiongraph.result.ResultList import ResultList

        return ResultList([r for r in results if getattr(r, "score", 1.0) >= min_score])

    def hb_update_status(self, status: str):
        """Update the status label (re-renders the bound widget live)."""
        try:
            self.ports["status"].set_value(status)
        except Exception:
            pass
