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

from typing import TYPE_CHECKING, Optional

from haywire.core.execution.event_source import CallbackEvent
from haywire.core.execution.execution_context import ExecutionContext
from haywire.core.execution.scheduler import QueueMode
from haywire.core.node import node, BaseNode, NodeType
from haywire.core.settings import NodeSettings, Promotable, setting
from haywire.core.types.enums import PortType
from haywire.barn.builtin.types import BOOL, CHOICES, INT

_QUEUE_MODES = {"Drop (realtime)": QueueMode.DROP, "Block (every frame)": QueueMode.BLOCK}


class StreamSettings(NodeSettings):
    """Which streams this node requests and exposes.

    All three are ``Promotable.CONFIG``: they drive ``rejig``, so an
    edge-driven inlet could destroy and rebuild the stream outlets mid-run —
    dropping the very edges downstream of them. A pinless face widget is fine.
    """

    enable_rgb = setting[BOOL](
        True,
        label="Color",
        category="Streams",
        description="Request and expose the colour stream.",
        promotable=Promotable.CONFIG,
    )
    enable_depth = setting[BOOL](
        False,
        label="Depth",
        category="Streams",
        description="Request and expose the depth stream.",
        promotable=Promotable.CONFIG,
    )
    enable_ir = setting[BOOL](
        False,
        label="Infrared",
        category="Streams",
        description="Request and expose the infrared stream.",
        promotable=Promotable.CONFIG,
    )


class DispatchSettings(NodeSettings):
    """How incoming frame callbacks are queued (ADR 0010).

    These were hardcoded to DROP/1. That is right for a live preview — a camera
    outrunning inference should skip stale frames rather than lag — and wrong
    for frame-accurate offline work, where every frame must be processed and
    the camera should be back-pressured instead. Nothing told the user which
    mode they were in, so the choice is theirs now.

    Rebuild-category: the ``CallbackEvent`` is constructed in ``post_init`` and
    registered with the VM at startup, so a change lands on the next start.
    """

    queue_mode = setting[CHOICES](
        "Drop (realtime)",
        label="Queue Mode",
        category="Dispatch",
        description=(
            "Drop keeps only the newest frame (live preview). Block queues every "
            "frame and back-pressures the camera (frame-accurate). Applies on next start."
        ),
        widget_config={"options": list(_QUEUE_MODES)},
        promotable=Promotable.CONFIG,
    )
    max_queue_size = setting[INT](
        1,
        min=1,
        max=256,
        label="Max Queue Size",
        category="Dispatch",
        description=(
            "How many pending frames to hold. Drop mode needs 1 to actually "
            "guarantee newest-wins. Applies on next start."
        ),
        promotable=Promotable.CONFIG,
    )


@node(
    label="Frame Event",
    description="Triggered when a camera frame is ready; exposes colour/depth/infrared streams",
    menu="vision/event",
    search_tags=[
        "3d",
        "depth",
        "camera",
        "oak",
        "kinect",
        "realsense",
        "frame",
        "event",
        "rgb",
        "ir",
        "image",
    ],
    node_type=NodeType.EVENT,
)
class NumpyFrameEventNode(BaseNode):
    """
    Event node that receives 3D-camera frame callbacks.

    Settings:
        streams: enable_rgb / enable_depth / enable_ir — which streams this node
            requests and exposes. Seeded to config ports: the node's face.
        dispatch: queue_mode / max_queue_size — how incoming callbacks queue
            (ADR 0010). Applies on next start.

    Outputs:
        subscription: MULTIFRAME_CALLBACK carrying the event name + requirements.
        frame_ready: Control flow when a frame arrives.
        rgb / depth / ir: The requested frame streams (dynamic outlets).
        frame_number / timestamp: Frame metadata.
    """

    if TYPE_CHECKING:
        streams: StreamSettings
        dispatch: DispatchSettings
    else:
        streams = StreamSettings
        dispatch = DispatchSettings

    def init(self):
        from haywire.barn.builtin.types import INT, FLOAT
        from haybale_core.types import EXEC
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

        # Control output
        self.add(EXEC.as_outlet("frame_ready", label="Frame Ready"))

        # Metadata outlets (always present)
        self.add(FLOAT.as_outlet("timestamp", label="Timestamp (s)"))
        self.add(INT.as_outlet("frame_number", label="Frame Number"))

        # Dynamic stream outlets built from the initial flags.
        self._build_stream_outlets()

        # Seeded promotions: the three stream toggles are this node's face.
        # In init(), NOT post_init — post_init also runs on graph load, after
        # promotions are restored, so promoting there would undo a demotion.
        self.streams.promote("enable_rgb", PortType.CONFIG)
        self.streams.promote("enable_depth", PortType.CONFIG)
        self.streams.promote("enable_ir", PortType.CONFIG)

    def _build_stream_outlets(self):
        """Add the frame outlets for whichever streams are currently enabled."""
        from ..types.frame_type import RGB_FRAME, DEPTH_FRAME, GRAY_FRAME

        if self.streams.enable_rgb:
            self.add(RGB_FRAME.as_outlet("rgb", label="Color"))
        if self.streams.enable_depth:
            self.add(DEPTH_FRAME.as_outlet("depth", label="Depth"))
        if self.streams.enable_ir:
            self.add(GRAY_FRAME.as_outlet("ir", label="Infrared"))

    def hb_reconfigure(self, value=None, old=None):
        """On a flag change: rebuild stream outlets and refresh the subscription.

        Driven from ``subscribe_field`` rather than a config port's
        ``on_change=`` (retired for settings, ADR 0013).
        """
        with self.rejig(include=r"^(rgb|depth|ir)$"):
            self._build_stream_outlets()
        self.hb_publish_subscription()

    def post_init(self):
        """Register the callback subscription and publish requirements."""
        # Queue behaviour is the user's choice now (see DispatchSettings); the
        # default is still realtime — drop stale frames and keep only the
        # newest, so a live camera outrunning inference never lags. DROP needs
        # a depth-1 queue to actually guarantee newest. See ADR 0010.
        self.event_subscription = CallbackEvent(
            event_name=self.node_id,
            queue_mode=_QUEUE_MODES.get(str(self.dispatch.queue_mode), QueueMode.DROP),
            max_queue_size=int(self.dispatch.max_queue_size),
        )
        for name in ("enable_rgb", "enable_depth", "enable_ir"):
            self.streams.subscribe_field(name, self.hb_reconfigure)
        self.hb_publish_subscription()

    def hb_publish_subscription(self):
        """Write the current name + requirements to the subscription outlet."""
        from ..types.multiframe_callback_type import MULTIFRAME_CALLBACK

        sub = MULTIFRAME_CALLBACK(
            name=self.node_id,
            rgb=bool(self.streams.enable_rgb),
            depth=bool(self.streams.enable_depth),
            ir=bool(self.streams.enable_ir),
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

        if self.streams.enable_rgb and payload.get("rgb") is not None:
            self.out("rgb", RGB_FRAME(data=payload["rgb"], timestamp=timestamp, frame_number=frame_number))
        if self.streams.enable_depth and payload.get("depth") is not None:
            self.out(
                "depth", DEPTH_FRAME(data=payload["depth"], timestamp=timestamp, frame_number=frame_number)
            )
        if self.streams.enable_ir and payload.get("ir") is not None:
            self.out("ir", GRAY_FRAME(data=payload["ir"], timestamp=timestamp, frame_number=frame_number))

        self.out("timestamp", timestamp)
        self.out("frame_number", frame_number)
        return "frame_ready"
