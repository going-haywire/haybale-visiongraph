"""
Tracker node — assigns stable tracking ids to detections across frames.

Wraps a visiongraph tracker (Centroid / Flate / Motpy), whose
``process(ResultList) -> ResultList`` matches detections frame-to-frame and stamps
each with a ``tracking_id`` (see notes.md Q11). The tracker keeps the *original*
result objects (``t.reference``), so a pose passed in comes back as the same pose
with its joints intact, even though visiongraph types the return as
``ResultList[ObjectDetectionResult]``.

Because haywire ports are statically typed, a **``result_type`` setting** chooses
which subtype this node's inlet and outlet carry (notes.md Q12):

- default ``DETECTION_RESULT`` — the common case;
- ``POSE_RESULT`` / ``SEGMENTATION_RESULT`` — for tracking those subtypes.

Changing it ``rejig``s both the ``result`` inlet and the ``tracked`` outlet to the
chosen type. Edges that no longer fit the narrowed type are dropped by the
framework exactly when the subtype relationship genuinely fails — the setting
can't produce an inconsistent graph.

Every knob is a ``setting()``; ``backend`` and ``result_type`` are *seeded* to
config ports in ``init()``, and both are ``Promotable.CONFIG`` — an edge-driven
inlet would let the graph retype ports mid-run. Each backend's tuning knobs
live in their own bag, hidden while another backend is selected.

Tracking is detection-level (it matches on bounding box + class), so it requires
``DETECTION_RESULT`` or a subtype; the base ``VISION_RESULT`` is intentionally not
offered.
"""

import time
from typing import TYPE_CHECKING, Any, Optional

from haywire.core.execution.execution_context import ExecutionContext
from haywire.core.node import node, BaseNode, NodeType
from haywire.core.settings import NodeSettings, Promotable, UiState, setting
from haywire.core.types.enums import PortType
from haywire.barn.builtin.types import BOOL, CHOICES, FLOAT, INT


# Tracking backends — plain constructors with sensible defaults (no .create()).
# They DO have setup(), and it is required: see hb_ensure_tracker's docstring.
# Motpy needs visiongraph's `mot` extra (filterpy) — declared in pyproject.
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


# Which bag belongs to which backend, and which of its fields the backend
# consumes in setup() rather than per frame (verified against visiongraph
# 1.2.0). Flate reads all of its knobs inside track(); Motpy hands every one of
# its seven to MultiObjectTracker(...) in setup(); Centroid builds its Tracker
# from max_lost in setup() but reads `enabled` per frame.
_BACKEND_BAGS = {
    "Flate": ("flate", frozenset()),
    "Centroid": ("centroid", frozenset({"max_lost"})),
    "Motpy": (
        "motpy",
        frozenset(
            {
                "delta_time",
                "min_iou",
                "multi_match_min_iou",
                "min_steps_alive",
                "max_staleness_to_positive_ratio",
                "max_staleness",
                "use_predicted_bounding_box",
            }
        ),
    ),
}


class TrackerChoiceSettings(NodeSettings):
    """The two structural choices. Both `Promotable.CONFIG`.

    `result_type` drives `rejig`, which destroys and rebuilds the result inlet
    and tracked outlet: an edge-driven inlet could retype those ports mid-run
    and drop the very edges feeding it. `backend` rebuilds the tracker, so an
    edge would imply live switching it cannot deliver. A pinless config port —
    a face widget, no edge — is exactly right for both.
    """

    backend = setting[CHOICES](
        "Flate",
        label="Backend",
        category="Tracker",
        description="Which tracker implementation to use. Changing this rebuilds the tracker.",
        widget_config={"options": list(_TRACKERS.keys())},
        promotable=Promotable.CONFIG,
    )
    result_type = setting[CHOICES](
        "Detection",
        label="Result Type",
        category="Tracker",
        description="Which result subtype the inlet and outlet carry. Changing this retypes both ports.",
        widget_config={"options": list(_RESULT_TYPES.keys())},
        promotable=Promotable.CONFIG,
    )


class FlateSettings(NodeSettings):
    """FlateTracker. Every field is read inside ``track()`` — all live."""

    max_cost = setting[FLOAT](
        0.5,
        min=0.0,
        max=5.0,
        label="Max Cost",
        category="Flate",
        description="Largest distance still accepted as a match.",
    )
    min_alive = setting[INT](
        0,
        min=0,
        max=100,
        label="Min Alive",
        category="Flate",
        description="Frames a track must survive before it is reported.",
    )
    max_lost = setting[INT](
        5,
        min=0,
        max=300,
        label="Max Lost",
        category="Flate",
        description="Frames a track may go unseen before it is dropped.",
    )
    include_stale = setting[BOOL](
        False,
        label="Include Stale",
        category="Flate",
        description="Also report tracks that were not matched this frame.",
    )
    class_aware = setting[BOOL](
        False,
        label="Class Aware",
        category="Flate",
        description="Only match detections of the same class.",
    )


class CentroidSettings(NodeSettings):
    """CentroidTracker. ``max_lost`` is consumed by ``setup()``; ``enabled`` is live."""

    enabled = setting[BOOL](
        True,
        label="Enabled",
        category="Centroid",
        description="When off, detections pass through untracked.",
    )
    max_lost = setting[INT](
        0,
        min=0,
        max=300,
        label="Max Lost",
        category="Centroid",
        description="Frames a track may go unseen. Applied when the tracker is built.",
        promotable=Promotable.CONFIG,
    )


class MotpySettings(NodeSettings):
    """MotpyTracker. Every field is consumed by ``setup()`` — all rebuild-category."""

    delta_time = setting[FLOAT](
        0.1,
        min=0.001,
        max=1.0,
        label="Delta Time",
        category="Motpy",
        description="Kalman filter time step. Applied when the tracker is built.",
        promotable=Promotable.CONFIG,
    )
    min_iou = setting[FLOAT](
        0.1,
        min=0.0,
        max=1.0,
        label="Min IoU",
        category="Motpy",
        description="Smallest overlap accepted as a match. Applied when the tracker is built.",
        promotable=Promotable.CONFIG,
    )
    multi_match_min_iou = setting[FLOAT](
        1.0,
        min=0.0,
        max=2.0,
        label="Multi-match Min IoU",
        category="Motpy",
        description="Above 1.0 disables multi-matching. Applied when the tracker is built.",
        promotable=Promotable.CONFIG,
    )
    min_steps_alive = setting[INT](
        -1,
        min=-1,
        max=100,
        label="Min Steps Alive",
        category="Motpy",
        description="Steps before a track is reported; -1 leaves it unset.",
        promotable=Promotable.CONFIG,
    )
    max_staleness_to_positive_ratio = setting[FLOAT](
        3.0,
        min=0.0,
        max=20.0,
        label="Staleness Ratio",
        category="Motpy",
        description="Applied when the tracker is built.",
        promotable=Promotable.CONFIG,
    )
    max_staleness = setting[FLOAT](
        12.0,
        min=0.0,
        max=100.0,
        label="Max Staleness",
        category="Motpy",
        description="Applied when the tracker is built.",
        promotable=Promotable.CONFIG,
    )
    use_predicted_bounding_box = setting[BOOL](
        False,
        label="Use Predicted Box",
        category="Motpy",
        description="Report the Kalman prediction rather than the detection.",
        promotable=Promotable.CONFIG,
    )


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

    if TYPE_CHECKING:
        choice: TrackerChoiceSettings
        flate: FlateSettings
        motpy: MotpySettings
        centroid: CentroidSettings
    else:
        choice = TrackerChoiceSettings
        flate = FlateSettings
        motpy = MotpySettings
        centroid = CentroidSettings

    def init(self):
        from haywire.barn.builtin.types import STRING
        from haybale_core.types import EXEC
        from haywire.barn.builtin.widgets import SimpleLabelWidget

        # Control in.
        self.add(EXEC.as_inlet("execute", label="Run"))

        # Status display — a read-only label, never a setting.
        self.add(
            STRING.as_config("status", default="Idle", label="Status", widget=SimpleLabelWidget.config())
        )

        # Control out.
        self.add(EXEC.as_outlet("tracked_ready", label="Tracked Ready"))

        # Typed result ports built from the current result_type.
        self._build_result_ports()

        # Seeded promotions: this node's default face. In init(), NOT post_init
        # — post_init also runs on graph load (after promotions are restored),
        # so promoting there would undo a user's demotion on every load.
        self.choice.promote("backend", PortType.CONFIG)
        self.choice.promote("result_type", PortType.CONFIG)

    def _result_type_cls(self) -> Any:
        """Resolve the chosen result_type label to its ``@type`` class."""
        from haybale_visiongraph.types import result_type as rt

        attr = _RESULT_TYPES.get(str(self.choice.result_type), "DETECTION_RESULT")
        return getattr(rt, attr)

    def _build_result_ports(self):
        """Add the ``result`` inlet and ``tracked`` outlet at the current type."""
        result_type = self._result_type_cls()
        self.add(result_type.as_inlet("result", label="Result"))
        self.add(result_type.as_outlet("tracked", label="Tracked"))

    def hb_on_result_type_change(self, value=None, old=None):
        """Retype the result inlet + tracked outlet to the chosen subtype (Q12).

        Driven from a ``subscribe_field`` callback rather than a config port's
        ``on_change=`` (retired for settings, ADR 0013). Note that callback
        exceptions are caught and logged by the subscription adapter, so a
        failure here would leave the ports stale rather than raising — see
        tests/core/test_settings/test_rejig_from_subscription.py.
        """
        with self.rejig(include=r"^(result|tracked)$"):
            self._build_result_ports()

    def post_init(self):
        """Initialise the tracker cache and wire setting subscriptions."""
        self.hb_tracker: Optional[Any] = None
        self.hb_loaded_backend: Optional[str] = None

        self.choice.subscribe_field("backend", self.hb_on_backend_change)
        self.choice.subscribe_field("result_type", self.hb_on_result_type_change)
        for accessor, _rebuild in _BACKEND_BAGS.values():
            bag = getattr(self, accessor, None)
            if bag is not None:
                bag.subscribe(self.hb_on_bag_field_changed)

        self.hb_refresh_bag_visibility()

    def on_shutdown(self, context: ExecutionContext):
        """Release the tracker when the flow stops."""
        self.hb_release()

    def on_teardown(self):
        """Release the tracker when the node is destroyed."""
        self.hb_release()

    def hb_release(self):
        """Release the cached tracker, if any."""
        if self.hb_tracker is not None:
            try:
                self.hb_tracker.release()
            except Exception:
                pass
            self.hb_tracker = None
            self.hb_loaded_backend = None

    def hb_on_backend_change(self, value=None, old=None):
        """A backend change drops the cached tracker AND re-gates the panel."""
        self.hb_release()
        self.hb_refresh_bag_visibility()
        self.hb_update_status("Backend changed")

    def hb_on_bag_field_changed(self, name=None, value=None, old=None):
        """Release only if the current backend consumes that field at build time."""
        _, rebuild_fields = _BACKEND_BAGS.get(str(self.choice.backend), ("", frozenset()))
        if name in rebuild_fields:
            self.hb_release()

    def hb_refresh_bag_visibility(self):
        """Hide the tuning bags that do not belong to the selected backend."""
        active, _ = _BACKEND_BAGS.get(str(self.choice.backend), ("", frozenset()))
        for accessor, _rebuild in _BACKEND_BAGS.values():
            bag = getattr(self, accessor, None)
            if bag is not None:
                bag.set_ui_state_all(UiState.NORMAL if accessor == active else UiState.HIDDEN)

    def hb_ensure_tracker(self) -> Optional[Any]:
        """Lazily build + ``setup()`` the chosen tracker backend.

        ``setup()`` is NOT optional, despite the plain constructors: both
        ``CentroidTracker`` and ``MotpyTracker`` leave ``self.tracker = None``
        in ``__init__`` and only build the underlying tracker in ``setup()``,
        so skipping it makes them raise on the first frame. ``FlateTracker``
        survives without it only because its ``setup()`` merely resets
        counters. (``create()`` is what trackers don't have — not ``setup()``.)

        Build-time settings are applied in the window between construction and
        ``setup()``, which is what makes them reachable at all.
        """
        backend = str(self.choice.backend)
        if self.hb_tracker is not None and self.hb_loaded_backend == backend:
            return self.hb_tracker

        # Backend changed or first use — drop any stale tracker first.
        self.hb_release()

        entry = _TRACKERS.get(backend)
        if entry is None:
            self.hb_update_status(f"Unknown backend: {backend}")
            return None

        module_path, cls_name = entry
        try:
            import importlib

            mod = importlib.import_module(module_path)
            tracker = getattr(mod, cls_name)()
            self.hb_apply_settings(tracker, backend, build_time=True)
            tracker.setup()
            self.hb_tracker = tracker
            self.hb_loaded_backend = backend
        except Exception as e:
            self.hb_update_status(f"Tracker error: {e}")
            self.hb_tracker = None
            self.hb_loaded_backend = None
            return None
        return self.hb_tracker

    def hb_apply_settings(self, tracker: Any, backend: str, build_time: bool):
        """Push this backend's bag onto the tracker.

        ``build_time=True`` writes only the fields the backend consumes in
        ``setup()``; ``False`` writes only the live ones, and runs per frame.
        """
        accessor, rebuild_fields = _BACKEND_BAGS.get(backend, ("", frozenset()))
        bag = getattr(self, accessor, None)
        if bag is None:
            return
        for name in type(bag)._property_settings():
            if (name in rebuild_fields) is build_time:
                setattr(tracker, name, getattr(bag, name))

    def worker(self, context: ExecutionContext, result=None) -> Optional[str]:
        """Run the tracker over one frame's results."""
        if result is None:
            self.hb_update_status("No result")
            return None

        tracker = self.hb_ensure_tracker()
        if tracker is None:
            return None

        # Live knobs, pushed per frame: a handful of attribute writes against
        # a tracking pass, and the tracker can never drift from the panel.
        self.hb_apply_settings(tracker, str(self.choice.backend), build_time=False)

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
        # Carry the producer's overlay colour through: a Tracker sits BETWEEN
        # the estimator that chose the colour and the Annotate node that reads
        # it, so dropping it here would silently un-colour any tracked branch.
        self.out("tracked", result_type(results=tracked, color=getattr(result, "color", "")))
        count = len(tracked) if tracked is not None else 0
        self.hb_update_status(f"{count} tracked · {elapsed_ms:.0f}ms")
        return "tracked_ready"

    def hb_update_status(self, status: str):
        """Update the status label."""
        try:
            self.ports["status"].set_value(status)
        except Exception:
            pass
