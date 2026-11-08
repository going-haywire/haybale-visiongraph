"""Visiongraph's nodes on image values: cameras wrap, consumers read, nothing is copied by accident."""

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import numpy as np
import pytest
from haybale_image.types.image import IMAGE_RGB
from haybale_image.value import ChannelOrder, DepthValue, ImageMetadata, ImageValue, Layout
from test_estimator_models import _build, _families

from haywire.barn.builtin.types import CARRIER, FLOAT, INT
from haywire.core.graph.base import BaseGraph

BGR = ChannelOrder.BGR


def _event_node() -> Any:
    from haybale_visiongraph.nodes.numpy_frame_event_node import NumpyFrameEventNode

    return _build(NumpyFrameEventNode)


def _capture(node: Any) -> dict[str, Any]:
    emitted: dict[str, Any] = {}
    node.out = lambda name, value: emitted.__setitem__(name, value)
    return emitted


def _bgr_image() -> ImageValue:
    return ImageValue.from_array(np.zeros((2, 4, 3), np.uint8), order=BGR)


def test_rgb_wraps_without_copying_and_is_bgr(library_system: Any) -> None:
    buf = np.zeros((2, 2, 3), np.uint8)
    buf[..., 0] = 200  # blue, in OpenCV's order
    out = _event_node().hb_wrap_streams({"rgb": buf, "timestamp": 1.5, "frame_number": 7})["rgb"]
    assert isinstance(out, ImageValue)
    assert np.shares_memory(out.array(np.uint8, BGR), buf)
    assert out.array(np.uint8, ChannelOrder.RGB)[0, 0, 2] == 200


def test_fields_are_stamped_on_every_stream(library_system: Any) -> None:
    payload = {
        "rgb": np.zeros((2, 2, 3), np.uint8),
        "depth": np.zeros((2, 2), np.uint16),
        "ir": np.zeros((2, 2), np.uint8),
        "timestamp": 1.5,
        "frame_number": 7,
    }
    values = _event_node().hb_wrap_streams(payload)
    assert isinstance(values["depth"], DepthValue)
    assert values["ir"].layout is Layout.GRAY
    for value in values.values():
        assert value.fields["camera_timestamp"].value == 1.5
        assert value.fields["camera_timestamp"].type_key == FLOAT.class_identity.registry_key
        assert value.fields["camera_frame_number"].value == 7
        assert value.fields["camera_frame_number"].type_key == INT.class_identity.registry_key


def test_a_missing_stream_is_left_out(library_system: Any) -> None:
    wrapped = _event_node().hb_wrap_streams({"rgb": np.zeros((2, 2, 3), np.uint8)})
    assert set(wrapped) == {"rgb"}


def _estimator() -> tuple[Any, MagicMock]:
    node = _build(_families()[0])
    estimator = MagicMock()
    estimator.process.return_value = []
    node.hb_ensure_estimator = lambda: estimator
    node.hb_current_spec = lambda: None
    return node, estimator


def test_estimator_gets_the_camera_buffer_as_bgr_uint8(library_system: Any) -> None:
    node, estimator = _estimator()
    buf = np.zeros((2, 2, 3), np.uint8)
    _capture(node)
    node.worker(SimpleNamespace(), frame=ImageValue.from_array(buf, order=BGR))
    seen = estimator.process.call_args.args[0]
    assert seen.dtype == np.uint8
    assert np.shares_memory(seen, buf)


def test_an_empty_image_is_refused(library_system: Any) -> None:
    node, estimator = _estimator()
    assert node.worker(SimpleNamespace(), frame=ImageValue.empty(Layout.RGB)) is None
    assert node.ports["status"].get_value() == "No valid frame"
    estimator.process.assert_not_called()


def test_an_estimator_writing_into_its_input_reports_and_does_not_corrupt(library_system: Any) -> None:
    node, estimator = _estimator()

    def scribble(image: np.ndarray) -> list:
        image[0, 0, 0] = 9
        return []

    estimator.process.side_effect = scribble
    buf = np.zeros((2, 2, 3), np.uint8)
    node.worker(SimpleNamespace(), frame=ImageValue.from_array(buf, order=BGR))
    assert "Inference error" in node.ports["status"].get_value()
    assert buf[0, 0, 0] == 0


def test_estimator_inlet_is_rgb(library_system: Any) -> None:
    node, _ = _estimator()
    assert node.ports["frame"].type_cls is IMAGE_RGB


def test_annotate_keeps_fields_and_metadata_and_leaves_the_input_alone(library_system: Any) -> None:
    from haybale_visiongraph.nodes.annotate_node import AnnotateNode

    node = _build(AnnotateNode)
    emitted = _capture(node)
    drawn = MagicMock()
    drawn.annotate.side_effect = lambda image, **_: image.__setitem__((0, 0, 0), 9)
    node.value = lambda name: {"a": SimpleNamespace(results=drawn, color="")}
    buf = np.zeros((2, 4, 3), np.uint8)
    frame = (
        ImageValue.from_array(buf, order=BGR)
        .with_metadata(ImageMetadata(icc=b"x"))
        .stamped("camera_timestamp", 1.5, FLOAT)
    )
    node.worker(SimpleNamespace(), frame=frame)
    out = emitted["annotated"]
    assert out.array(np.uint8, BGR)[0, 0, 0] == 9
    assert buf[0, 0, 0] == 0
    assert out.fields["camera_timestamp"].value == 1.5
    assert out.metadata.icc == b"x"


def _display() -> tuple[Any, dict[str, Any]]:
    from haybale_visiongraph.nodes.numpy_frame_display_node import FrameDisplayNode

    node = _build(FrameDisplayNode)
    return node, _capture(node)


def test_display_reads_stamped_facts(library_system: Any) -> None:
    node, emitted = _display()
    frame = _bgr_image().stamped("camera_frame_number", 7, INT).stamped("camera_timestamp", 1.5, FLOAT)
    node.worker(SimpleNamespace(), frame=frame)
    assert emitted["frame_number"] == 7
    assert emitted["timestamp"] == 1.5
    assert emitted["width"] == 4
    assert emitted["height"] == 2
    assert "#7" in emitted["info_display"]
    assert "4x2x3" in emitted["info_display"]


def test_display_without_fields_shows_zero_and_does_not_raise(library_system: Any) -> None:
    node, emitted = _display()
    node.worker(SimpleNamespace(), frame=_bgr_image())
    assert emitted["frame_number"] == 0
    assert emitted["timestamp"] == 0.0


def _viewer() -> Any:
    from haybale_visiongraph.widgets.numpy_viewer_widget import NumpyViewerWidget

    widget = NumpyViewerWidget.__new__(NumpyViewerWidget)
    widget._backend = MagicMock(_is_running=True)
    return widget


def test_viewer_streams_bgr_from_an_image_value() -> None:
    widget = _viewer()
    buf = np.zeros((2, 2, 3), np.uint8)
    widget.on_model_changed(ImageValue.from_array(buf, order=BGR))
    assert np.shares_memory(widget._backend.stream.call_args.args[0], buf)


@pytest.mark.parametrize("frame", [ImageValue.empty(Layout.RGB), None])
def test_viewer_ignores_a_frame_with_no_pixels(frame: Any) -> None:
    widget = _viewer()
    widget.on_model_changed(frame)
    widget._backend.stream.assert_not_called()


def test_the_frame_types_are_gone() -> None:
    with pytest.raises(ImportError):
        import haybale_visiongraph.types.frame_type  # noqa: F401


_REPO = Path(__file__).parent.parent
_MIGRATED = [
    _REPO / "graphs/webcam.haywire",
    _REPO.parent / "haywire-repo/graphs/webcam.haywire",
    _REPO.parent / "haywire-repo/graphs/oakNwebCam.haywire",
]
_OLD_KEY = "haybale-visiongraph:type:RGB_FRAME"


@pytest.mark.parametrize("path", _MIGRATED, ids=lambda p: f"{p.parent.parent.name}-{p.stem}")
def test_a_migrated_graph_loads_with_working_frame_edges(library_system: Any, path: Path) -> None:
    text = path.read_text()
    assert "_FRAME" not in text.replace("CALLBACK_MULTIFRAME", "")
    graph = BaseGraph(filestem="migrated")
    try:
        assert graph.load_from_dict(json.loads(text)) is True
        graph._validation.force_immediate_validation()
        assert not [w.node_id for w in graph.node_wrappers.values() if w.is_stand_in]
        for edge in graph.edge_wrappers.values():
            if isinstance(edge._outlet_port.type_cls, type) and issubclass(
                edge._outlet_port.type_cls, CARRIER
            ):
                assert edge.is_functional(), edge.edge_id
    finally:
        graph.cleanup()


def test_an_unmigrated_graph_opens_without_a_crash(library_system: Any) -> None:
    data = json.loads(
        (
            _REPO.parent / "haywire-repo/tests/core/test_graph/fixtures/prehydration/webcam.haywire"
        ).read_text()
    )
    assert _OLD_KEY in json.dumps(data)
    graph = BaseGraph(filestem="unmigrated")
    try:
        graph.load_from_dict(data)
        graph._validation.force_immediate_validation()
    finally:
        graph.cleanup()
