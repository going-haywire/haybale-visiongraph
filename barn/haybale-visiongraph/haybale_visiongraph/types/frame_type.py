"""
Frame data types for video / depth-camera streams.

Three concrete datatypes share a common base (`BaseFrame`):

- ``RGB_FRAME``   — 3-channel uint8 colour image.
- ``DEPTH_FRAME`` — single-channel uint16 metric depth buffer (millimetres).
- ``GRAY_FRAME``  — single-channel uint8 luminance image (e.g. infrared).

Dimensions (``width`` / ``height`` / ``channels``) are **read-only properties
derived from ``data.shape``** — not stored fields. All three declare
``store_strategy=NEVER``, so frame values never persist; there is no save/load
round-trip for cached metadata to survive, which is why deriving is correct
(see notes.md, Q7).

Depth is carried as the **raw uint16 buffer** (the measurement); colourizing it
for display is an explicit downstream node, never an adapter (notes.md Q3/Q5).
"""

from dataclasses import dataclass
from typing import Optional

import numpy as np

from haywire.core.types import type, FlowType, BaseType
from haywire.core.types.enums import StoreStrategy


@dataclass
class BaseFrame(BaseType):
    """
    Shared base for all video / depth frame datatypes.

    Attributes:
        data: Numpy array containing the frame data (H, W) or (H, W, C).
        timestamp: Time when the frame was captured (seconds).
        frame_number: Sequential frame number since stream start.

    ``width`` / ``height`` / ``channels`` are derived read-only properties off
    ``data.shape`` — they are never stored, so they can never go stale.
    """

    data: Optional[np.ndarray] = None
    timestamp: float = 0.0
    frame_number: int = 0

    @property
    def width(self) -> int:
        """Frame width in pixels (0 if no data)."""
        if self.data is not None and self.data.ndim >= 2:
            return int(self.data.shape[1])
        return 0

    @property
    def height(self) -> int:
        """Frame height in pixels (0 if no data)."""
        if self.data is not None and self.data.ndim >= 2:
            return int(self.data.shape[0])
        return 0

    @property
    def channels(self) -> int:
        """Number of channels (1 for 2-D arrays, else the last axis; 0 if no data)."""
        if self.data is None or self.data.ndim < 2:
            return 0
        return int(self.data.shape[2]) if self.data.ndim > 2 else 1

    def is_valid(self) -> bool:
        """Check if the frame contains a non-empty numpy array."""
        return self.data is not None and isinstance(self.data, np.ndarray) and self.data.size > 0


@type(
    label="RGB Frame",
    description="3-channel uint8 colour video frame",
    flow_type=FlowType.DATA,
    default={"data": None, "timestamp": 0.0, "frame_number": 0},
    color="#9c27b0",
    store_strategy=StoreStrategy.NEVER,
)
@dataclass
class RGB_FRAME(BaseFrame):
    """3-channel uint8 colour image (H, W, 3)."""


@type(
    label="Depth Frame",
    description="Single-channel uint16 metric depth buffer (millimetres)",
    flow_type=FlowType.DATA,
    default={"data": None, "timestamp": 0.0, "frame_number": 0},
    color="#00838f",
    store_strategy=StoreStrategy.NEVER,
)
@dataclass
class DEPTH_FRAME(BaseFrame):
    """
    Single-channel uint16 metric depth buffer (H, W), each pixel = millimetres.

    Its own datatype precisely so it cannot be silently wired into colour-image
    nodes. Colourizing to a viewable image is an explicit node, never an adapter.
    """


@type(
    label="Gray Frame",
    description="Single-channel uint8 luminance video frame (e.g. infrared)",
    flow_type=FlowType.DATA,
    default={"data": None, "timestamp": 0.0, "frame_number": 0},
    color="#607d8b",
    store_strategy=StoreStrategy.NEVER,
)
@dataclass
class GRAY_FRAME(BaseFrame):
    """Single-channel uint8 luminance image (H, W)."""
