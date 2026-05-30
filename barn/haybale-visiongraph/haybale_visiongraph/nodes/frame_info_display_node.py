"""
Webcam Frame Info Display Node - Displays frame information and preview
"""

from typing import Optional
import numpy as np

from haywire.core.execution.execution_context import ExecutionContext
from haywire.core.node import node, BaseNode, NodeType

from haybale_visiongraph.types.frame_type import FRAME


@node(
    label="Webcam Frame Info Display",
    description="Displays information about webcam frames with live preview",
    menu="vision/info",
    search_tags=["webcam", "frame", "camera", "display", "preview", "video"],
    node_type=NodeType.CONTROL,
)
class WebcamFrameInfoDisplayNode(BaseNode):
    """
    Displays webcam frame information and live preview.

    Shows frame metadata and streams the video to an embedded viewer.

    Inputs:
        execute: Control flow in
        frame: Frame to display (FRAME type)

    Outputs:
        frame_ready: Control flow out
        timestamp: Time since stream start
        frame_number: Sequential frame number
        width: Frame width
        height: Frame height
    """

    def init(self):
        from haybale_core.types import EXEC, STRING, INT, FLOAT
        from haybale_core.widgets.basic_widgets import SimpleLabelWidget
        from haybale_visiongraph.types.frame_type import FRAME
        from haybale_visiongraph.widgets.opencv_viewer_widget import OpencvViewerWidget

        # Control input
        self.add(EXEC.as_inlet("execute", label="Analyze Frame"))

        # Frame input with preview widget
        self.add(
            FRAME.as_inlet(
                "frame",
                label="Frame",
                widget=OpencvViewerWidget.config(
                    properties={
                        "quality": 85,
                        "width": "100%",
                        "height": "300px",
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
        self.add(FRAME.as_outlet("frame_pass", label="Frame Pass"))

        # Convenience data outputs
        self.add(FLOAT.as_outlet("timestamp", label="Timestamp (s)"))
        self.add(INT.as_outlet("frame_number", label="Frame Number"))
        self.add(INT.as_outlet("width", label="Width"))
        self.add(INT.as_outlet("height", label="Height"))

    def post_init(self):
        """Initialize state"""
        self.hb_last_frame_number = 0

    def worker(self, context: ExecutionContext, frame) -> Optional[str]:
        """Process and display frame information"""

        # Validate frame
        if frame is None:
            self.hb_update_display("No frame received")
            return None

        # Handle both FRAME objects and raw numpy arrays
        if isinstance(frame, FRAME):
            if not frame.is_valid():
                self.hb_update_display("Invalid frame")
                return None

            frame_number = frame.frame_number
            timestamp = frame.timestamp
            width = frame.width
            height = frame.height
            channels = frame.channels
        elif isinstance(frame, np.ndarray):
            # Raw numpy array - extract basic info
            frame_number = self.hb_last_frame_number + 1
            timestamp = 0.0
            height, width = frame.shape[:2]
            channels = frame.shape[2] if len(frame.shape) > 2 else 1
        else:
            self.hb_update_display("Unknown frame type")
            return None

        self.hb_last_frame_number = frame_number

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
