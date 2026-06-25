"""
Frame adapters — conversions among the *image* frame types only.

`GRAY_FRAME <-> RGB_FRAME` are registered because they are always safe to apply
invisibly (channel replicate / luminance). **No adapter touches `DEPTH_FRAME`**:
depth colourization is lossy, parameterized, and display-only, so it must be a
deliberate node, never an auto edge-time coercion (see notes.md Q5).

Adapters operate on **unwrapped values** — here, ``BaseFrame`` instances.
"""

import numpy as np
from typing_extensions import override

from haywire.core.adapter.base import BaseAdapter, adapter

from ..types.frame_type import GRAY_FRAME, RGB_FRAME


@adapter(
    description="Replicate a single-channel grey frame to a 3-channel colour frame",
    converts_from=GRAY_FRAME,
    converts_to=RGB_FRAME,
)
class GrayToRgbAdapter(BaseAdapter):
    """GRAY_FRAME -> RGB_FRAME by replicating the single channel across BGR."""

    @override
    def convert(self, value: GRAY_FRAME) -> RGB_FRAME:
        rgb = value.data
        if rgb is not None and rgb.ndim == 2:
            rgb = np.stack([rgb, rgb, rgb], axis=-1)
        return RGB_FRAME(data=rgb, timestamp=value.timestamp, frame_number=value.frame_number)

    def get_test_value(self) -> GRAY_FRAME:
        return GRAY_FRAME(data=np.zeros((4, 4), dtype=np.uint8))


@adapter(
    description="Convert a 3-channel colour frame to a single-channel grey frame (luminance)",
    converts_from=RGB_FRAME,
    converts_to=GRAY_FRAME,
)
class RgbToGrayAdapter(BaseAdapter):
    """RGB_FRAME -> GRAY_FRAME via luminance."""

    @override
    def convert(self, value: RGB_FRAME) -> GRAY_FRAME:
        gray = value.data
        if gray is not None and gray.ndim == 3:
            # Rec. 601 luma weights over BGR (OpenCV channel order).
            gray = (gray[..., 0] * 0.114 + gray[..., 1] * 0.587 + gray[..., 2] * 0.299).astype(np.uint8)
        return GRAY_FRAME(data=gray, timestamp=value.timestamp, frame_number=value.frame_number)

    def get_test_value(self) -> RGB_FRAME:
        return RGB_FRAME(data=np.zeros((4, 4, 3), dtype=np.uint8))
