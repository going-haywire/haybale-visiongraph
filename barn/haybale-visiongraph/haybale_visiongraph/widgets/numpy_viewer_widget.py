"""
OpenCV Viewer Widget - Displays numpy arrays as streaming video in nodes
"""

from typing import Any
from haybale_visiongraph.types.frame_type import RGB_FRAME
import numpy as np

from haywire.ui.widget.base import BaseWidget
from haywire.ui.widget.decorator import widget

from haybale_visiongraph.widgets.components.streaming_viewer import StreamingBackend, StreamingViewer


@widget(
    description="Streaming video viewer for numpy arrays using custom StreamingViewer",
    # Declared inline-axis size: the frame's natural pixel size (1280px for a
    # 720p stream) no longer votes on the host node's size floor, so the resize
    # gadget can shrink the node below the image instead of being stuck at it.
    # Width only, deliberately — the block axis stays content-driven, so the
    # image's aspect ratio keeps the viewer growing proportionally as the node
    # widens. See haywire.ui.widget.sizing.
    min_width=160,
)
class NumpyViewerWidget(BaseWidget):
    """
    Widget for displaying numpy arrays as streaming video.

    Uses a custom StreamingViewer component for efficient MJPEG streaming.
    Automatically streams frame updates when the port value changes.

    Config options (via ``NumpyViewerWidget.config(properties={...})``):

    - ``quality`` (int): JPEG compression quality (0-100, default: ``80``).
    - ``frame_queue_size`` (int): Internal frame buffer size (default: ``1``).
    - ``block_on_full`` (bool): Block the producer when the queue is full (default: ``False``).
    - ``frame_width`` (str): CSS border width around the viewer (default: ``'0'``, no frame).
    - ``frame_color`` (str): CSS color of the frame border (default: ``'var(--hw-border)'``).

    The viewer fills whatever space its host node gives it — it does not impose
    its own width/height, so it cooperates with the node's own resize handling
    (see ``UINode._apply_size``) instead of fighting it. The ``min_width``
    declaration on the decorator is what lets the node shrink *below* the
    streamed frame's natural size; without it the frame's pixel width becomes
    the node's floor. Override it per call site with
    ``NumpyViewerWidget.config(min_width=320)`` — a top-level ``config()``
    keyword, NOT one of the ``properties`` above.
    """

    def __init__(self, port: Any) -> None:
        super().__init__(port)
        self._backend: StreamingBackend | None = None

    def build(self) -> Any:
        props = self._config.get("properties", {})
        if self._backend is None:
            self._backend = StreamingBackend(
                quality=props.get("quality", 80),
                frame_queue_size=props.get("frame_queue_size", 1),
                block_on_full=props.get("block_on_full", False),
            )
        frame_width = props.get("frame_width", "0")
        frame_color = props.get("frame_color", "var(--hw-border)")
        # flex: 1 lets the viewer grow into whatever the host node's own sizing
        # (UINode._apply_size) gives it, rather than imposing a size that fights
        # the node's ResizeObserver loop; min-height: 0 lets it shrink again when
        # the column squeezes. The node's size FLOOR is NOT handled here — an
        # inline min-width can't lower it, because percentages and mins don't
        # affect intrinsic sizing. That's what @widget(min_width=) above does.
        viewer = StreamingViewer(self._backend).style(
            f"width: 100%; flex: 1; min-width: 0; min-height: 0; border: {frame_width} solid {frame_color};"
        )
        return viewer

    def on_model_changed(self, frame: Any) -> None:
        # Floor-only widget: owns sync entirely, does not call super().
        if self._backend is None or not self._backend._is_running:
            return
        frame_data = frame.data if hasattr(frame, "data") else frame
        if isinstance(frame_data, np.ndarray) and frame_data.size:
            try:
                self._backend.stream(frame_data)
            except Exception as e:
                if self._backend and self._backend._is_running:
                    print(f"[NumpyViewerWidget] Error streaming frame: {e}")

    def _on_cleanup(self) -> None:
        if self._backend:
            try:
                self._backend.cleanup()
            except Exception as e:
                print(f"[NumpyViewerWidget] Viewer cleanup warning: {e}")
            self._backend = None
