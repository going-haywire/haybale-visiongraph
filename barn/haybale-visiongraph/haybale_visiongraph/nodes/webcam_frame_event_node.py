"""
Webcam Frame Event Node - Receives frame callbacks and provides frame data.

DEPRECATED: the webcam is now a member of the 3D-camera family. Use the shared
``ThreeDFrameEventNode`` ("3D Frame Event") with only the Color stream enabled.
This node is kept functional (migrated to the ``MULTIFRAME_CALLBACK`` subscription
contract) so existing graphs keep working, but new graphs should use the shared
event node.
"""

from typing import Optional

from haywire.core.execution.event_source import CallbackEvent
from haywire.core.execution.execution_context import ExecutionContext
from haywire.core.node import node, BaseNode, NodeType


@node(
    label="Webcam Frame Event",
    description="Triggered when a webcam frame is ready",
    menu="vision/event",
    search_tags=["webcam", "frame", "camera", "event", "video"],
    node_type=NodeType.EVENT,
    deprecation_warning="Use '3D Frame Event' (with only Color enabled) instead.",
)
class WebcamFrameEventNode(BaseNode):
    """
    DEPRECATED — use ``ThreeDFrameEventNode`` instead.

    Event node that receives webcam frame callbacks. Migrated to the shared
    ``MULTIFRAME_CALLBACK`` contract (requests only the rgb stream, reads
    ``payload['rgb']``) so it still works against the current webcam emit node.

    Outputs:
        subscription: MULTIFRAME_CALLBACK carrying this node's name (rgb-only).
        frame_ready: Control flow when a frame arrives.
        frame: Frame data with metadata (RGB_FRAME type).
        frame_number: Sequential frame number.
        timestamp: Time since stream start.
        width: Frame width in pixels.
        height: Frame height in pixels.
    """

    def init(self):
        from haybale_core.types import EXEC, INT, FLOAT
        from ..types.frame_type import RGB_FRAME
        from ..types.multiframe_callback_type import MULTIFRAME_CALLBACK

        # Subscription outlet: rgb-only, same contract as ThreeDFrameEventNode.
        self.add(
            MULTIFRAME_CALLBACK.as_outlet(
                "subscription",
                label="Subscribe",
                default={"name": self.node_id, "rgb": True, "depth": False, "ir": False},
            )
        )

        # Control output
        self.add(EXEC.as_outlet("frame_ready", label="Frame Ready"))

        # Frame data output
        self.add(RGB_FRAME.as_outlet("frame", label="Frame"))

        # Convenience outputs for common data
        self.add(FLOAT.as_outlet("timestamp", label="Timestamp (s)"))
        self.add(INT.as_outlet("frame_number", label="Frame Number"))
        self.add(INT.as_outlet("width", label="Width"))
        self.add(INT.as_outlet("height", label="Height"))

    def post_init(self):
        """Initialize event subscription."""
        self.event_subscription = CallbackEvent(event_name=self.node_id)

    def worker(self, context: ExecutionContext) -> Optional[str]:
        """Process incoming frame callback."""
        from ..types.frame_type import RGB_FRAME

        payload = context.trigger.payload if context.trigger else None
        if not isinstance(payload, dict):
            return None

        # New contract: the webcam emit node sends the color stream under 'rgb'.
        frame_data = payload.get("rgb")
        frame_number = payload.get("frame_number", 0)
        timestamp = payload.get("timestamp", 0.0)

        if frame_data is None:
            return None

        frame_obj = RGB_FRAME(data=frame_data, timestamp=timestamp, frame_number=frame_number)

        # Output all data
        self.out("frame", frame_obj)
        self.out("timestamp", timestamp)
        self.out("frame_number", frame_number)
        self.out("width", frame_obj.width)
        self.out("height", frame_obj.height)

        return "frame_ready"
