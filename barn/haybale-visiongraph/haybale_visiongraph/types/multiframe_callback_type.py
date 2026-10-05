"""
MULTIFRAME_CALLBACK — the subscription carrier between a 3D-camera emit node and
the shared ``NumpyFrameEventNode``.

A ``BaseType`` dataclass (NOT a subclass of core ``CALLBACK``) declared on
`CallbackWire`, so the framework recognises a callback edge by its wire type's
role. The event *name* is read off this value's ``name`` field by the node — not by
treating the whole value as a string. So a dataclass works cleanly (see notes.md Q14/Q15).

It serves two purposes on the single subscription edge:

1. Carries the event ``name`` (for callback dispatch routing) **and** the
   downstream node's per-stream requirements (``rgb`` / ``depth`` / ``ir``).
2. Type-gates the connection: only a camera emit node whose pooled inlet is
   ``PooledType[MULTIFRAME_CALLBACK]`` can be wired to a 3D event node — this is
   what binds the camera family (OAK-D emit, webcam emit, …) to the shared
   ``NumpyFrameEventNode``.

Note on the name: "multiframe" describes the type's *capability* (it can carry
up to several stream requirements), not a mandate that all be present. A
single-stream device legitimately uses it with one flag set — e.g. the webcam
emit node sets only ``rgb=True`` and ignores ``depth`` / ``ir``.

An absent value (``None``) means no subscription; the emitter's pool drops it.
"""

from dataclasses import dataclass

from haywire.core.types import type, BaseType
from haywire.barn.builtin.wires import CallbackWire


@type(
    label="Multiframe Callback",
    description="Subscription for multi-frame streams",
    wire_type=CallbackWire,
    default=None,
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
