"""Enumerating attached webcams, per OS.

**OpenCV has no device enumeration API at all.** `cv2.videoio_registry` lists
*backends* (AVFOUNDATION, GSTREAMER, …), not devices; the only `*device*`
symbols in `cv2` are CUDA/OpenCL. visiongraph adds nothing either. So the index
passed to `cv2.VideoCapture` is the only OpenCV-native identifier, and it is
positional — unplug a camera and the indices shift.

Names can be had, but only per-OS and only outside OpenCV. This module supplies
them purely as **labels for an index**, which stays the stored value: the
name→index mapping is by position and is not contractual on any platform
(reliable on Linux, where `/dev/videoN` maps to index N; conventional but
unguaranteed on macOS and Windows). Storing the name instead would trade a
confusing label for a hard "cannot start", so we don't.

The listing is also backend-dependent — indices under AVFOUNDATION need not
match GSTREAMER — which none of these OS APIs can answer. The field description
carries that caveat rather than the code pretending otherwise.

Windows has no dependency-free path (`pygrabber`/DirectShow would be a new
Windows-only dependency), so it degrades to bare indices — exactly today's
behaviour. Adding it later means dropping in one function.
"""

import logging
import subprocess
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

MAX_PROBE_INDEX = 8
"""Upper bound for the synthetic index list used when names are unavailable."""


def _macos_camera_names() -> list[str]:
    """Camera names from `system_profiler` (~0.4s, no extra dependency)."""
    out = subprocess.run(
        ["system_profiler", "SPCameraDataType"],
        capture_output=True,
        text=True,
        timeout=10,
    ).stdout
    names: list[str] = []
    # Entries are indented "    Name:" lines under the "Camera:" heading;
    # their detail lines ("Model ID:", "Unique ID:") are indented further.
    for raw in out.splitlines():
        stripped = raw.strip()
        if not stripped.endswith(":") or stripped in ("Camera:",):
            continue
        indent = len(raw) - len(raw.lstrip())
        if indent == 4:
            names.append(stripped[:-1].strip())
    return names


def _linux_camera_names() -> list[str]:
    """Camera names from sysfs. Instant, no subprocess, and index-accurate:
    `/dev/videoN` is the index OpenCV uses."""
    names: list[str] = []
    base = Path("/sys/class/video4linux")
    if not base.is_dir():
        return names
    for node in sorted(base.glob("video*"), key=lambda p: int(p.name.removeprefix("video") or 0)):
        try:
            names.append((node / "name").read_text().strip())
        except OSError:
            names.append(node.name)
    return names


def list_camera_options() -> dict:
    """`{index: label}` for a SelectWidget, newest reading on every dropdown open.

    Always returns something usable: on any failure, or on a platform with no
    dependency-free enumeration, it falls back to bare indices.
    """
    names: list[str] = []
    try:
        if sys.platform == "darwin":
            names = _macos_camera_names()
        elif sys.platform.startswith("linux"):
            names = _linux_camera_names()
    except Exception:
        # A dropdown must never fail to open because enumeration misbehaved.
        logger.exception("Camera enumeration failed; falling back to bare indices")
        names = []

    if names:
        return {index: f"{index}: {name}" for index, name in enumerate(names)}
    return {index: f"Camera {index}" for index in range(MAX_PROBE_INDEX)}
