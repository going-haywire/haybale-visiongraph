"""
MULTIFRAME_CALLBACK — the subscription carrier between a 3D-camera emit node and
the shared ``ThreeDFrameEventNode``.

A ``BaseType`` dataclass (NOT a subclass of core ``CALLBACK``) declared with
``flow_type=FlowType.CALLBACK``. A callback edge is identified by the framework
purely via the edge's flow_type (set by ``@type``), and the event *name* is read
off this value's ``name`` field by the node — not by treating the whole value as
a string. So a dataclass works cleanly (see notes.md Q14/Q15).

It serves two purposes on the single subscription edge:

1. Carries the event ``name`` (for callback dispatch routing) **and** the
   downstream node's per-stream requirements (``rgb`` / ``depth`` / ``ir``).
2. Type-gates the connection: only a 3D-camera emit node (whose pooled inlet is
   ``PooledType[MULTIFRAME_CALLBACK]``) can be wired to a ``ThreeDFrameEventNode``
   — a plain webcam ``CALLBACK`` event node cannot connect.
"""

from dataclasses import dataclass

from haywire.core.types import type, FlowType, BaseType


@type(
    label="Multiframe Callback",
    description="Subscription signal carrying an event name plus per-stream requirements",
    flow_type=FlowType.CALLBACK,
    default={"name": "", "rgb": False, "depth": False, "ir": False},
    color="#ff3c00",
)
@dataclass
class MULTIFRAME_CALLBACK(BaseType):
    """
    Subscription value: callback name + which streams the subscriber requires.

    Attributes:
        name: Callback event name used for dispatch routing.
        rgb: Subscriber wants the colour stream.
        depth: Subscriber wants the depth stream.
        ir: Subscriber wants the infrared stream.
    """

    name: str = ""
    rgb: bool = False
    depth: bool = False
    ir: bool = False
