"""
Webcam Frame Info Display Node - Displays frame information and preview
"""

from typing import Optional

from haywire.core.execution.execution_context import ExecutionContext
from haywire.core.node import node, BaseNode, NodeType
from haywire.core.types.enums import ShowWidgetStrategy

from haybale_image.types.image import IMAGE_RGB
from haybale_image.value import ImageValue


@node(
    label="Frame Info Display",
    description="Displays information about frames with live preview",
    menu="vision/info",
    search_tags=["rgb", "ir", "frame", "camera", "display", "preview", "video", "stream"],
    node_type=NodeType.CONTROL,
)
class FrameDisplayNode(BaseNode):
    """
    Displays frame information and live preview.

    Shows frame metadata and streams the video to an embedded viewer.

    Inputs:
        execute: Control flow in
        frame: Frame to display

    Outputs:
        frame_ready: Control flow out
        timestamp: Time since stream start
        frame_number: Sequential frame number
        width: Frame width
        height: Frame height
    """

    def init(self):
        from haywire.barn.builtin.types import STRING, INT, FLOAT
        from haywire.barn.builtin.types import EXEC
        from haywire.barn.builtin.widgets import SimpleLabelWidget
        from haybale_visiongraph.widgets.numpy_viewer_widget import NumpyViewerWidget

        # Control input
        self.add(EXEC.as_inlet("execute", label="Analyze Frame"))

        # Frame input with preview widget
        self.add(
            IMAGE_RGB.as_inlet(
                "frame",
                label="Frame",
                show_widget=ShowWidgetStrategy.WHEN_LINKED,
                widget=NumpyViewerWidget.config(
                    properties={
                        "quality": 85,
                        "frame_queue_size": 1,
                        "block_on_full": False,
                    }
                ),
            )
        )

        # Status displays
        self.add(
            STRING.as_config(
                "info_display", default="No frame yet", label="Frame Info", widget=SimpleLabelWidget.config()
            )
        )

        # Control output
        self.add(EXEC.as_outlet("frame_ready", label="Frame Ready"))

        # Convenience data outputs
        self.add(IMAGE_RGB.as_outlet("frame_pass", label="Frame Pass"))

        # Convenience data outputs
        self.add(FLOAT.as_outlet("timestamp", label="Timestamp (s)"))
        self.add(INT.as_outlet("frame_number", label="Frame Number"))
        self.add(INT.as_outlet("width", label="Width"))
        self.add(INT.as_outlet("height", label="Height"))

    def worker(self, context: ExecutionContext, frame) -> Optional[str]:
        """Process and display frame information"""

        # Validate frame
        if frame is None:
            self.hb_update_display("No frame received")
            return None

        if not isinstance(frame, ImageValue) or frame.is_empty:
            self.hb_update_display("Invalid frame")
            return None

        fields = frame.fields
        frame_number = fields["camera_frame_number"].value if "camera_frame_number" in fields else 0
        timestamp = fields["camera_timestamp"].value if "camera_timestamp" in fields else 0.0
        width = frame.width
        height = frame.height
        channels = frame.channels

        # Calculate FPS
        fps = frame_number / timestamp if timestamp > 0 else 0

        # Format info display
        info = f"Frame #{frame_number} | {width}x{height}x{channels} | {timestamp:.2f}s | {fps:.1f} FPS"

        self.hb_update_display(info)

        # Output metadata
        self.out("frame_pass", frame)
        self.out("timestamp", timestamp)
        self.out("frame_number", frame_number)
        self.out("width", width)
        self.out("height", height)

        # Trigger downstream
        return "frame_ready"

    def hb_update_display(self, info: str):
        """Update the info display label"""
        try:
            self.out("info_display", info)
        except Exception:
            # Silently fail if UI update fails
            pass
