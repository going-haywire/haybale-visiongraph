"""
OpenCV Viewer Widget - Displays numpy arrays as streaming video in nodes
"""

from typing import Any, Optional, TYPE_CHECKING
from haybale_visiongraph.types.frame_type import FRAME
import numpy as np
from nicegui import ui

from haywire.ui.widget.interface import IWidget
from haywire.ui.widget.decorator import widget

from haybale_visiongraph.widgets.components.streaming_viewer import StreamingBackend, StreamingViewer

if TYPE_CHECKING:
    from haywire.core.types import DataPort


@widget(
    description="Streaming video viewer for numpy arrays using custom StreamingViewer",
    compatible_types=[FRAME],  # Will be FRAME type
)
class OpencvViewerWidget(IWidget):
    """
    Widget for displaying numpy arrays as streaming video.

    Uses a custom StreamingViewer component for efficient MJPEG streaming.
    Automatically streams frame updates when the port value changes.

    Config options (via ``OpencvViewerWidget.config(properties={...})``):

    - ``quality`` (int): JPEG compression quality (0–100, default: ``80``).
    - ``width`` (str): CSS width of the viewer (default: ``'100%'``).
    - ``height`` (str): CSS height of the viewer (default: ``'auto'``).
    - ``frame_queue_size`` (int): Internal frame buffer size (default: ``1``).
    - ``block_on_full`` (bool): Block the producer when the queue is full (default: ``False``).

    Usage:
        from haybale_visiongraph.widgets.opencv_viewer_widget import OpencvViewerWidget

        self.add(FRAME.as_inlet(
            'preview',
            label='Preview',
            widget=OpencvViewerWidget.config(properties={
                'quality': 80,
                'width': '100%',
                'height': '300px'
            })
        ))
    """

    def __init__(self, port: "DataPort"):
        self.port: "DataPort" = port
        self.port_id: str = port.id
        self._config: dict = (
            port.widget_config if hasattr(port, "widget_config") and port.widget_config else {}
        )
        self.ui_element: Optional[Any] = None
        self._backend: Optional[StreamingBackend] = None
        self._model_changed_callback: Optional[Any] = None

    def render(self) -> Any:
        props = self._config.get("properties", {})
        quality = props.get("quality", 80)
        width = props.get("width", "100%")
        height = props.get("height", "auto")
        frame_queue_size = props.get("frame_queue_size", 1)
        block_on_full = props.get("block_on_full", False)

        # Create the backend once — it owns the FastAPI route and async
        # queue reader.  Subsequent redraws reuse it so the browser's
        # MJPEG connection survives.
        if self._backend is None:
            self._backend = StreamingBackend(
                quality=quality, frame_queue_size=frame_queue_size, block_on_full=block_on_full
            )

        with ui.card().classes("w-full") as container:
            StreamingViewer(self._backend).style(f"width: {width}; height: {height};")

        self.ui_element = container

        self._setup_binding()
        self._sync_frame_to_viewer()

        return self.ui_element

    def _setup_binding(self) -> None:
        self._model_changed_callback = lambda _: self._sync_frame_to_viewer()
        self.port._data.on_changed += self._model_changed_callback

    def _sync_frame_to_viewer(self) -> None:
        if self._backend is None or not self._backend._is_running:
            return

        try:
            frame = self.port.get_value()
            if frame is None:
                return

            if hasattr(frame, "data"):
                frame_data = frame.data
            elif isinstance(frame, np.ndarray):
                frame_data = frame
            else:
                return

            if frame_data is None or not isinstance(frame_data, np.ndarray) or frame_data.size == 0:
                return

            self._backend.stream(frame_data)

        except Exception as e:
            if self._backend and self._backend._is_running:
                print(f"[OpencvViewerWidget] Error streaming frame: {e}")

    def cleanup(self) -> None:
        if self._model_changed_callback:
            try:
                self.port._data.on_changed -= self._model_changed_callback
            except Exception as e:
                print(f"[OpencvViewerWidget] Port cleanup warning: {e}")
        self._model_changed_callback = None
        self.ui_element = None

        if self._backend:
            try:
                self._backend.cleanup()
            except Exception as e:
                print(f"[OpencvViewerWidget] Viewer cleanup warning: {e}")
            self._backend = None
