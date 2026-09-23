"""The settings-first node conversion (sixth inquisition).

Covers the parts of the sixth-inquisition conversion that fail *silently* if
they regress:

- the seeded promotions that give each node its default face (a missed one
  just means a knob quietly vanishes from the node card);
- per-backend bag gating (a bag left visible for a model that ignores it is
  the flat-union-bag failure the design exists to avoid);
- `rebuild_fields` being per-spec, which is the whole reason `min_score` can
  stay a live slider on five backends while MediaPipe reloads for it.

The framework monorepo symlinks this package into its own ``barn/``, but its
suite does not run these: the symlink is local-only, so CI there has no
``haybale_visiongraph`` to import.
"""

import pytest

from haywire.core.settings import UiState

pytestmark = [pytest.mark.unit]


class _StubWrapper:
    graph = None
    state = None

    def mark_as_structuraly_dirty(self):
        pass


def _families():
    from haybale_visiongraph.nodes.object_detector_node import ObjectDetectorNode
    from haybale_visiongraph.nodes.pose_estimator_node import PoseEstimatorNode
    from haybale_visiongraph.nodes.segmentation_node import SegmentationNode

    return [ObjectDetectorNode, SegmentationNode, PoseEstimatorNode]


def _build(cls):
    node = cls(node_id="test-node", wrapper=_StubWrapper())
    node.init()
    # Mirrors NodeWrapper._initialize: promoted ports (including the ones a
    # setting(promote_default=...) seeded at bag construction) are realised
    # here, by the same call the load path makes.
    node._regenerate_promoted_ports()
    node.post_init()
    return node


def _bag_state(node, accessor):
    """NORMAL / HIDDEN for a whole bag, or the mixed set if it disagrees."""
    bag = getattr(node, accessor)
    states = {bag._effective_ui_state(f) for f in type(bag)._settings_descriptors()}
    return states.pop() if len(states) == 1 else states


@pytest.mark.parametrize("cls", _families(), ids=lambda c: c.__name__)
def test_model_and_min_score_are_seeded_to_config_ports(library_system, cls):
    """The node's default face. Seeded in init(), so a fresh drop has them."""
    node = _build(cls)

    # A promoted port's id is the setting's storage_key (`<accessor>.<field>`),
    # never the bare field name. This is also why an unmigrated graph shows the
    # old `min_score` config port AND the new `inference.min_score` side by
    # side rather than one silently shadowing the other.
    assert "selection.model" in node.ports
    assert "inference.min_score" in node.ports
    assert node.selection._get_promoted_direction("model").value == "config"
    assert node.inference._get_promoted_direction("min_score").value == "config"


@pytest.mark.parametrize("cls", _families(), ids=lambda c: c.__name__)
def test_every_model_names_only_bags_the_node_declares(library_system, cls):
    """A ModelSpec naming a bag the node forgot to alias would gate nothing."""
    declared = set(cls._settings_bags)
    for label, spec in cls.MODELS.items():
        assert spec.bags <= declared, f"{cls.__name__}/{label} references undeclared bags"


@pytest.mark.parametrize("cls", _families(), ids=lambda c: c.__name__)
def test_selecting_a_model_shows_its_bags_and_hides_the_rest(library_system, cls):
    node = _build(cls)
    backend_bags = cls.hb_backend_bags()

    for label, spec in cls.MODELS.items():
        node.selection.model = label
        for accessor in backend_bags:
            expected = UiState.NORMAL if accessor in spec.bags else UiState.HIDDEN
            assert _bag_state(node, accessor) is expected, (
                f"{cls.__name__}: with model={label!r}, bag {accessor!r} should be {expected.name}"
            )


def test_mediapipe_rebuilds_for_min_score_but_movenet_does_not(library_system):
    """The per-spec split that a single node-level rebuild list could not express."""
    from haybale_visiongraph.nodes.pose_estimator_node import PoseEstimatorNode

    node = _build(PoseEstimatorNode)

    node.selection.model = "MediaPipe Pose (Full)"
    assert "min_score" in node.hb_current_spec().rebuild_fields

    node.selection.model = "MoveNet MultiPose"
    assert "min_score" not in node.hb_current_spec().rebuild_fields


def test_min_score_change_releases_the_estimator_only_when_rebuild_bound(library_system):
    """A slider drag must not reload the model on backends where it is live."""
    from haybale_visiongraph.nodes.pose_estimator_node import PoseEstimatorNode

    node = _build(PoseEstimatorNode)
    sentinel = object()

    node.selection.model = "MoveNet MultiPose"
    node.hb_estimator = sentinel
    node.hb_loaded_model = "MoveNet MultiPose"
    node.inference.min_score = 0.42
    assert node.hb_estimator is sentinel, "live backend reloaded on a min_score change"

    node.selection.model = "MediaPipe Pose (Full)"
    node.hb_estimator = sentinel
    node.hb_loaded_model = "MediaPipe Pose (Full)"
    node.inference.min_score = 0.55
    assert node.hb_estimator is None, "MediaPipe did not reload for a build-time field"


@pytest.mark.parametrize("cls", _families(), ids=lambda c: c.__name__)
def test_changing_model_drops_the_cached_estimator(library_system, cls):
    node = _build(cls)
    labels = list(cls.MODELS)
    node.hb_estimator = object()
    node.hb_loaded_model = labels[0]

    node.selection.model = labels[-1] if len(labels) > 1 else labels[0]

    assert node.hb_estimator is None


@pytest.mark.parametrize("cls", _families(), ids=lambda c: c.__name__)
def test_overlay_colour_is_carried_on_the_emitted_result(library_system, cls):
    """Q6B: the estimator stamps its colour, AnnotateNode reads it back."""
    node = _build(cls)
    node.overlay.color = "#ff8800"

    result = node.hb_result_type()(results=[], color=str(node.overlay.color))

    assert result.color == "#ff8800"


# --- the other converted nodes ------------------------------------------------


def _tracker():
    from haybale_visiongraph.nodes.tracker_node import TrackerNode

    return _build(TrackerNode)


def test_tracker_seeds_backend_and_result_type_as_config_only(library_system):
    """Both drive rebuilds/rejig, so neither may become an edge-driven inlet."""
    from haywire.core.node.promotion import eligible_promotion_directions

    node = _tracker()
    fields = type(node.choice)._settings_descriptors()

    assert "choice.backend" in node.ports
    assert "choice.result_type" in node.ports
    for name in ("backend", "result_type"):
        directions = {d.value for d in eligible_promotion_directions(fields[name])}
        assert directions == {"config"}, f"{name} should be config-only, got {directions}"


def test_tracker_shows_only_the_selected_backend_bag(library_system):
    from haybale_visiongraph.nodes.tracker_node import _BACKEND_BAGS

    node = _tracker()
    for backend, (accessor, _rebuild) in _BACKEND_BAGS.items():
        node.choice.backend = backend
        for other_accessor, _r in _BACKEND_BAGS.values():
            expected = UiState.NORMAL if other_accessor == accessor else UiState.HIDDEN
            assert _bag_state(node, other_accessor) is expected, (
                f"backend={backend!r}: bag {other_accessor!r} should be {expected.name}"
            )


def test_tracker_result_type_retypes_both_ports(library_system):
    """rejig driven from a subscribe_field callback — the Q10 assumption."""
    node = _tracker()
    assert node.ports["result"].registry_id == "DETECTION_RESULT"

    node.choice.result_type = "Pose"

    assert node.ports["result"].registry_id == "POSE_RESULT"
    assert node.ports["tracked"].registry_id == "POSE_RESULT"


def test_frame_event_seeds_the_three_stream_toggles(library_system):
    from haybale_visiongraph.nodes.numpy_frame_event_node import NumpyFrameEventNode

    node = _build(NumpyFrameEventNode)

    for name in ("enable_rgb", "enable_depth", "enable_ir"):
        assert f"streams.{name}" in node.ports
        assert node.streams._get_promoted_direction(name).value == "config"


def test_frame_event_toggle_rebuilds_stream_outlets(library_system):
    """The other rejig-from-subscribe_field site."""
    from haybale_visiongraph.nodes.numpy_frame_event_node import NumpyFrameEventNode

    node = _build(NumpyFrameEventNode)
    assert "rgb" in node.ports
    assert "depth" not in node.ports

    node.streams.enable_depth = True
    assert "depth" in node.ports

    node.streams.enable_rgb = False
    assert "rgb" not in node.ports
    assert "depth" in node.ports, "unrelated stream outlet was swept up"


def test_frame_event_queue_mode_reaches_the_callback_event(library_system):
    """ADR 0010's knob was hardcoded to DROP/1; it is the user's choice now."""
    from haywire.core.execution.scheduler import QueueMode
    from haybale_visiongraph.nodes.numpy_frame_event_node import NumpyFrameEventNode

    node = _build(NumpyFrameEventNode)
    assert node.event_subscription.queue_mode is QueueMode.DROP
    assert node.event_subscription.max_queue_size == 1

    node.dispatch.queue_mode = "Block (every frame)"
    node.dispatch.max_queue_size = 16
    node.post_init()  # rebuild-category: applies on next start

    assert node.event_subscription.queue_mode is QueueMode.BLOCK
    assert node.event_subscription.max_queue_size == 16


def test_webcam_seeds_camera_index_and_frame_skip_only(library_system):
    """Open-time knobs stay panel-only so the busiest card stops being crowded."""
    from haybale_visiongraph.nodes.web_cam_node import WebCameraNode

    node = _build(WebCameraNode)

    assert "capture.camera_index" in node.ports
    assert "capture.frame_skip" in node.ports
    for name in ("width", "height", "fps", "capture_backend"):
        assert f"capture.{name}" not in node.ports


def test_webcam_zero_size_keeps_the_camera_default(library_system):
    """BaseInput seeds 640x480, so a saved 0 must NOT be assigned through."""
    from haybale_visiongraph.nodes.web_cam_node import WebCameraNode

    node = _build(WebCameraNode)
    node.capture.width = 0
    node.capture.height = 0

    cam = node.hb_build_input()

    assert (cam.width, cam.height) == (640, 480), "0 was written through as a 0x0 request"


def test_webcam_image_settings_reach_the_input(library_system):
    import cv2
    from haybale_visiongraph.nodes.web_cam_node import WebCameraNode

    node = _build(WebCameraNode)
    cam = node.hb_build_input()
    assert cam.rotate is None
    assert cam.flip is None
    assert cam.crop is None

    node.image.rotate = "90"
    node.image.flip = "h"
    node.image.crop_width = 0.5
    node.hb_apply_image_settings(cam)

    assert cam.rotate == cv2.ROTATE_90_CLOCKWISE
    assert cam.flip == 1
    assert cam.crop is not None


# --- the two nodes nothing else instantiates ---------------------------------
#
# AnnotateNode and OakDCameraNode had no test that built them, which is how a
# batch of broken `bag.promote(...)` / `bag.subscribe(...)` calls survived the
# namespace-separation refactor: mypy could not see them (untyped bodies) and
# no test executed them. These two tests close that hole.


def test_annotate_node_builds_and_seeds_its_face(library_system):
    from haybale_visiongraph.nodes.annotate_node import AnnotateNode

    node = _build(AnnotateNode)

    assert "style.min_score" in node.ports
    assert "style.show_info" in node.ports
    assert node.style._get_promoted_direction("min_score").value == "config"


def test_oak_node_builds_and_seeds_its_device_picker(library_system):
    from haybale_visiongraph.nodes.oak_d_camera_node import OakDCameraNode

    node = _build(OakDCameraNode)

    assert "device.mxid" in node.ports
    assert node.device._get_promoted_direction("mxid").value == "config"


def test_oak_stream_gating_still_runs(library_system):
    """Exercises the set_ui_state_all calls that were left un-renamed."""
    from haywire.core.settings import UiState
    from haybale_visiongraph.nodes.oak_d_camera_node import OakDCameraNode

    node = _build(OakDCameraNode)
    node.hb_refresh_stream_status_indication()

    # No subscriber wants anything, so every stream bag is hidden.
    assert _bag_state(node, "depth") is UiState.HIDDEN
    assert _bag_state(node, "ir") is UiState.HIDDEN
    assert _bag_state(node, "color") is UiState.HIDDEN
