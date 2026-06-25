"""
3D Frame Event Node - Receives multi-stream frame callbacks from any 3D-camera
emit node (OAK-D now; Azure Kinect / RealSense later) and exposes the requested
streams as typed frame outlets.

Camera-AGNOSTIC and shared across all 3D cameras (see notes.md Q19-Q20). Only the
emit node is device-specific. Three bool flags (rgb / depth / ir) drive BOTH:

1. Which outlets exist (dynamic ports via ``rejig``), and
2. The per-stream requirements published on the ``MULTIFRAME_CALLBACK``
   subscription outlet, which the emit node unions to decide which device
   streams to open.

The contract is fixed at ``rgb`` / ``depth`` / ``ir``; the runtime payload is
open-keyed so future device-specific nodes can carry extra streams without
changing this node or the callback type.
"""

from typing import Optional

from haywire.core.execution.event_source import CallbackEvent
from haywire.core.execution.execution_context import ExecutionContext
from haywire.core.node import node, BaseNode, NodeType


@node(
    label="Frame Event",
    description="Triggered when a camera frame is ready; exposes colour/depth/infrared streams",
    menu="vision/event",
    search_tags=["3d", "depth", "camera", "oak", "kinect", "realsense", "frame", "event", "rgb", "ir"],
    node_type=NodeType.EVENT,
)
class ThreeDFrameEventNode(BaseNode):
    """
    Event node that receives 3D-camera frame callbacks.

    Config:
        rgb / depth / ir: Toggle which streams this node requests and exposes.

    Outputs:
        subscription: MULTIFRAME_CALLBACK carrying the event name + requirements.
        frame_ready: Control flow when a frame arrives.
        rgb / depth / ir: The requested frame streams (dynamic outlets).
        frame_number / timestamp: Frame metadata.
    """

    def init(self):
        from haybale_core.types import EXEC, INT, FLOAT, BOOL
        from haybale_core.widgets.basic_widgets import SwitchWidget
        from ..types.multiframe_callback_type import MULTIFRAME_CALLBACK

        # Subscription outlet: carries this node's name + stream requirements.
        self.add(
            MULTIFRAME_CALLBACK.as_outlet(
                "subscription",
                label="Subscribe",
                description="Subscribe for camera frames",
                default={"name": self.node_id, "rgb": True, "depth": False, "ir": False},
            )
        )

        # Stream selection flags (user is the source of truth). Named distinctly
        # from the stream outlets (rgb/depth/ir) — port ids are unique per node.
        self.add(
            BOOL.as_config(
                "enable_rgb",
                default=True,
                label="Color",
                widget=SwitchWidget.config(),
                on_change="hb_reconfigure",
            )
        )
        self.add(
            BOOL.as_config(
                "enable_depth",
                default=False,
                label="Depth",
                widget=SwitchWidget.config(),
                on_change="hb_reconfigure",
            )
        )
        self.add(
            BOOL.as_config(
                "enable_ir",
                default=False,
                label="Infrared",
                widget=SwitchWidget.config(),
                on_change="hb_reconfigure",
            )
        )

        # Control output
        self.add(EXEC.as_outlet("frame_ready", label="Frame Ready"))

        # Metadata outlets (always present)
        self.add(FLOAT.as_outlet("timestamp", label="Timestamp (s)"))
        self.add(INT.as_outlet("frame_number", label="Frame Number"))

        # Dynamic stream outlets built from the initial flags.
        self._build_stream_outlets()

    def _build_stream_outlets(self):
        """Add the frame outlets for whichever streams are currently enabled."""
        from ..types.frame_type import RGB_FRAME, DEPTH_FRAME, GRAY_FRAME

        if self.value("enable_rgb"):
            self.add(RGB_FRAME.as_outlet("rgb", label="Color"))
        if self.value("enable_depth"):
            self.add(DEPTH_FRAME.as_outlet("depth", label="Depth"))
        if self.value("enable_ir"):
            self.add(GRAY_FRAME.as_outlet("ir", label="Infrared"))

    def hb_reconfigure(self, port=None, *args):
        """On a flag change: rebuild stream outlets and refresh the subscription."""
        with self.rejig(include=r"^(rgb|depth|ir)$"):
            self._build_stream_outlets()
        self.hb_publish_subscription()

    def post_init(self):
        """Register the callback subscription and publish requirements."""
        self.event_subscription = CallbackEvent(event_name=self.node_id)
        self.hb_publish_subscription()

    def hb_publish_subscription(self):
        """Write the current name + requirements to the subscription outlet."""
        from ..types.multiframe_callback_type import MULTIFRAME_CALLBACK

        sub = MULTIFRAME_CALLBACK(
            name=self.node_id,
            rgb=bool(self.value("enable_rgb")),
            depth=bool(self.value("enable_depth")),
            ir=bool(self.value("enable_ir")),
        )
        try:
            self.out("subscription", sub)
        except Exception:
            pass

    def worker(self, context: ExecutionContext) -> Optional[str]:
        """Unpack an incoming multi-stream payload into the enabled outlets."""
        from ..types.frame_type import RGB_FRAME, DEPTH_FRAME, GRAY_FRAME

        payload = context.trigger.payload if context.trigger else None
        if not isinstance(payload, dict):
            return None

        frame_number = payload.get("frame_number", 0)
        timestamp = payload.get("timestamp", 0.0)

        if self.value("enable_rgb") and payload.get("rgb") is not None:
            self.out("rgb", RGB_FRAME(data=payload["rgb"], timestamp=timestamp, frame_number=frame_number))
        if self.value("enable_depth") and payload.get("depth") is not None:
            self.out(
                "depth", DEPTH_FRAME(data=payload["depth"], timestamp=timestamp, frame_number=frame_number)
            )
        if self.value("enable_ir") and payload.get("ir") is not None:
            self.out("ir", GRAY_FRAME(data=payload["ir"], timestamp=timestamp, frame_number=frame_number))

        self.out("timestamp", timestamp)
        self.out("frame_number", frame_number)
        return "frame_ready"
