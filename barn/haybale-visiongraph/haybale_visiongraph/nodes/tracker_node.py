"""
Tracker node — assigns stable tracking ids to detections across frames.

Wraps a visiongraph tracker (Centroid / Flate / Motpy), whose
``process(ResultList) -> ResultList`` matches detections frame-to-frame and stamps
each with a ``tracking_id`` (see notes.md Q11). The tracker keeps the *original*
result objects (``t.reference``), so a pose passed in comes back as the same pose
with its joints intact, even though visiongraph types the return as
``ResultList[ObjectDetectionResult]``.

Because haywire ports are statically typed, a **``result_type`` config** chooses
which subtype this node's inlet and outlet carry (notes.md Q12):

- default ``DETECTION_RESULT`` — the common case;
- ``POSE_RESULT`` / ``SEGMENTATION_RESULT`` — for tracking those subtypes.

Changing it ``rejig``s both the ``result`` inlet and the ``tracked`` outlet to the
chosen type. Edges that no longer fit the narrowed type are dropped by the
framework exactly when the subtype relationship genuinely fails — the config can't
produce an inconsistent graph.

Tracking is detection-level (it matches on bounding box + class), so it requires
``DETECTION_RESULT`` or a subtype; the base ``VISION_RESULT`` is intentionally not
offered.
"""

import time
from typing import Any, Optional

from haywire.core.execution.execution_context import ExecutionContext
from haywire.core.node import node, BaseNode, NodeType


# Tracking backends — plain constructors with sensible defaults (no .create()).
_TRACKERS = {
    "Flate": ("visiongraph.tracker.FlateTracker", "FlateTracker"),
    "Centroid": ("visiongraph.tracker.CentroidTracker", "CentroidTracker"),
    "Motpy": ("visiongraph.tracker.MotpyTracker", "MotpyTracker"),
}

# result_type label -> result_type module attribute name.
_RESULT_TYPES = {
    "Detection": "DETECTION_RESULT",
    "Pose": "POSE_RESULT",
    "Segmentation": "SEGMENTATION_RESULT",
}


@node(
    label="Tracker",
    description="Assign stable tracking ids to detections across frames",
    menu="vision/process",
    search_tags=["tracker", "tracking", "track", "centroid", "flate", "motpy", "id"],
    node_type=NodeType.CONTROL,
)
class TrackerNode(BaseNode):
    """
    Frame-to-frame tracker.

    Inputs:
        execute: Control flow in (pulse per frame).
        result: The result list to track (typed by ``result_type``).
        backend: Which tracker implementation to use.
        result_type: Which result subtype the inlet/outlet carry.

    Outputs:
        tracked_ready: Control flow out.
        tracked: The same results, stamped with tracking ids (typed by ``result_type``).
    """

    def init(self):
        from haybale_core.types import EXEC, STRING
        from haybale_core.widgets.basic_widgets import SelectWidget, SimpleLabelWidget

        # Control in.
        self.add(EXEC.as_inlet("execute", label="Run"))

        # Backend selection.
        self.add(
            STRING.as_config(
                "backend",
                default="Flate",
                label="Backend",
                widget=SelectWidget.config(properties={"options": list(_TRACKERS.keys())}),
                on_change="hb_on_backend_change",
            )
        )

        # Result-type selection — drives the inlet/outlet type via rejig (Q12).
        self.add(
            STRING.as_config(
                "result_type",
                default="Detection",
                label="Result Type",
                widget=SelectWidget.config(properties={"options": list(_RESULT_TYPES.keys())}),
                on_change="hb_on_result_type_change",
            )
        )

        # Status display.
        self.add(
            STRING.as_config("status", default="Idle", label="Status", widget=SimpleLabelWidget.config())
        )

        # Control out.
        self.add(EXEC.as_outlet("tracked_ready", label="Tracked Ready"))

        # Typed result ports built from the current result_type.
        self._build_result_ports()

    def _result_type_cls(self) -> Any:
        """Resolve the chosen result_type label to its ``@type`` class."""
        from haybale_visiongraph.types import result_type as rt

        attr = _RESULT_TYPES.get(self.value("result_type"), "DETECTION_RESULT")
        return getattr(rt, attr)

    def _build_result_ports(self):
        """Add the ``result`` inlet and ``tracked`` outlet at the current type."""
        result_type = self._result_type_cls()
        self.add(result_type.as_inlet("result", label="Result"))
        self.add(result_type.as_outlet("tracked", label="Tracked"))

    def hb_on_result_type_change(self, port=None, *args):
        """Retype the result inlet + tracked outlet to the chosen subtype (Q12)."""
        with self.rejig(include=r"^(result|tracked)$"):
            self._build_result_ports()

    def post_init(self):
        """Initialise the tracker cache."""
        self.hb_tracker: Optional[Any] = None
        self.hb_loaded_backend: Optional[str] = None

    def hb_on_backend_change(self, port=None, *args):
        """A backend change drops the cached tracker (rebuilt next frame)."""
        self.hb_tracker = None
        self.hb_loaded_backend = None
        self.hb_update_status("Backend changed")

    def hb_ensure_tracker(self) -> Optional[Any]:
        """Lazily build the chosen tracker backend (plain constructor)."""
        backend = self.value("backend")
        if self.hb_tracker is not None and self.hb_loaded_backend == backend:
            return self.hb_tracker

        entry = _TRACKERS.get(backend)
        if entry is None:
            self.hb_update_status(f"Unknown backend: {backend}")
            return None

        module_path, cls_name = entry
        try:
            import importlib

            mod = importlib.import_module(module_path)
            self.hb_tracker = getattr(mod, cls_name)()
            self.hb_loaded_backend = backend
        except Exception as e:
            self.hb_update_status(f"Tracker error: {e}")
            self.hb_tracker = None
            self.hb_loaded_backend = None
            return None
        return self.hb_tracker

    def worker(self, context: ExecutionContext, result=None) -> Optional[str]:
        """Run the tracker over one frame's results."""
        if result is None:
            self.hb_update_status("No result")
            return None

        tracker = self.hb_ensure_tracker()
        if tracker is None:
            return None

        result_list = getattr(result, "results", None)
        if result_list is None:
            self.hb_update_status("Empty result")
            return None

        try:
            t0 = time.time()
            tracked = tracker.process(result_list)
            elapsed_ms = (time.time() - t0) * 1000.0
        except Exception as e:
            self.hb_update_status(f"Tracking error: {e}")
            return None

        result_type = self._result_type_cls()
        self.out("tracked", result_type(results=tracked))
        count = len(tracked) if tracked is not None else 0
        self.hb_update_status(f"{count} tracked · {elapsed_ms:.0f}ms")
        return "tracked_ready"

    def hb_update_status(self, status: str):
        """Update the status label."""
        try:
            self.ports["status"].set_value(status)
        except Exception:
            pass
