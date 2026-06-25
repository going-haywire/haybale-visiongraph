"""
OpenCV Viewer Widget - Displays numpy arrays as streaming video in nodes
"""

from typing import Any
from haybale_visiongraph.types.frame_type import RGB_FRAME
import numpy as np
from nicegui import ui

from haywire.ui.widget.base import BaseWidget
from haywire.ui.widget.decorator import widget

from haybale_visiongraph.widgets.components.streaming_viewer import StreamingBackend, StreamingViewer


@widget(
    description="Streaming video viewer for numpy arrays using custom StreamingViewer",
    compatible_types=[RGB_FRAME],
)
class NumpyViewerWidget(BaseWidget):
    """
    Widget for displaying numpy arrays as streaming video.

    Uses a custom StreamingViewer component for efficient MJPEG streaming.
    Automatically streams frame updates when the port value changes.

    Config options (via ``NumpyViewerWidget.config(properties={...})``):

    - ``quality`` (int): JPEG compression quality (0-100, default: ``80``).
    - ``width`` (str): CSS width of the viewer (default: ``'100%'``).
    - ``height`` (str): CSS height of the viewer (default: ``'auto'``).
    - ``frame_queue_size`` (int): Internal frame buffer size (default: ``1``).
    - ``block_on_full`` (bool): Block the producer when the queue is full (default: ``False``).
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
        width = props.get("width", "100%")
        height = props.get("height", "auto")
        with ui.card().classes("w-full") as container:
            StreamingViewer(self._backend).style(f"width: {width}; height: {height};")
        return container

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
