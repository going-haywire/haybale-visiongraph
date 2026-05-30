"""
Webcam Frame Event Node - Receives frame callbacks and provides frame data
"""

from typing import Optional

from haywire.core.execution.event_source import CallbackEvent
from haywire.core.execution.execution_context import ExecutionContext
from haywire.core.node import node, BaseNode, NodeType


@node(
    label="Webcam Frame Event",
    description="Triggered when a webcam frame is ready",
    menu="event/vision",
    search_tags=["webcam", "frame", "camera", "event", "video"],
    node_type=NodeType.EVENT,
)
class WebcamFrameEventNode(BaseNode):
    """
    Event node that receives webcam frame callbacks.
    Provides the frame data and metadata for processing.

    Config:
        callback_name: Name of the callback to listen for

    Outputs:
        frame_ready: Control flow when frame arrives
        frame: Frame data with metadata (FRAME type)
        raw_data: Raw numpy array (for convenience)
        frame_number: Sequential frame number
        timestamp: Time since stream start
        width: Frame width in pixels
        height: Frame height in pixels
    """

    def init(self):
        from haybale_core.types import EXEC, INT, FLOAT, CALLBACK
        from ..types.frame_type import FRAME

        # Declare callback interest
        self.add(CALLBACK.as_outlet("callback_name", label="Listen", default=self.node_id))

        # Control output
        self.add(EXEC.as_outlet("frame_ready", label="Frame Ready"))

        # Frame data output
        self.add(FRAME.as_outlet("frame", label="Frame"))

        # Convenience outputs for common data
        # Note: For raw_data, we'll use a generic outlet since we don't have
        # a specific numpy array type defined yet
        self.add(FLOAT.as_outlet("timestamp", label="Timestamp (s)"))
        self.add(INT.as_outlet("frame_number", label="Frame Number"))
        self.add(INT.as_outlet("width", label="Width"))
        self.add(INT.as_outlet("height", label="Height"))

    def post_init(self):
        """Initialize event subscription"""
        callback_name = self.value("callback_name")
        self.event_subscription = CallbackEvent(event_name=callback_name)

    def worker(self, context: ExecutionContext) -> Optional[str]:
        """Process incoming frame callback"""
        # Extract payload from trigger
        payload = context.trigger.payload if context.trigger else None

        if not isinstance(payload, dict):
            return None

        # Extract frame data from payload
        frame_data = payload.get("frame")
        frame_number = payload.get("frame_number", 0)
        timestamp = payload.get("timestamp", 0.0)

        if frame_data is None:
            return None

        # Create FRAME object with metadata
        from ..types.frame_type import FRAME

        frame_obj = FRAME(data=frame_data, timestamp=timestamp, frame_number=frame_number)

        # Output all data
        self.out("frame", frame_obj)
        self.out("timestamp", timestamp)
        self.out("frame_number", frame_number)
        self.out("width", frame_obj.width)
        self.out("height", frame_obj.height)

        # Trigger downstream execution
        return "frame_ready"
