"""
OAK-D Emit Node - Opens a Luxonis OAK-D depth camera and emits multi-stream
frame callbacks (colour / depth / infrared) to subscribed NumpyFrameEventNodes.

Device-specific node (wraps visiongraph ``OakDInput``). The shared, camera-
agnostic subscriber is ``NumpyFrameEventNode``.

Lifecycle (see notes.md Q9-Q11):
- ``on_startup``  : read the *requirement union* from the pooled
  ``MULTIFRAME_CALLBACK`` inlet — which streams any subscriber wants. Config
  only; does NOT open the device.
- ``start`` pulse : open the OAK device + capture thread using that union.
- ``stop`` pulse  : close the device.
- ``on_shutdown`` : close the device as a fallback if ``stop`` was never pulsed.

Tuning surface (see notes.md "Depth-quality / IR / color live-control knobs"):
- ``depth`` (NodeSettings): pipeline-construction params, read once at
  ``pre_start_setup()``/``setup()``. Immutable while running — panel-only,
  never promotable to a port (promoting would imply live control that the
  hardware can't actually deliver without a device rebuild).
- ``ir`` / ``color`` (NodeSettings): live camera-control params. OakDInput's
  own setters guard on ``self.device is not None`` and push straight to the
  running device, so these ARE safe to promote to an inlet.
"""

import logging
import threading
import time
from typing import Optional

import depthai as dai

from haywire.core.execution.execution_context import ExecutionContext
from haywire.core.node import node, BaseNode, NodeType
from haywire.core.settings import NodeSettings, setting
from haywire.barn.builtin.types import BOOL, CHOICES, FLOAT, INT

logger = logging.getLogger(__name__)

# --- dai enum <-> CHOICES string lookup tables -----------------------------
# setting[CHOICES] stores plain strings; these map back to the dai.* (or
# visiongraph) enum members OakDInput's attributes actually expect. Keys must
# match the `widget_config={"options": [...]}` lists on the corresponding
# setting() fields below.

_DEPTH_PRESET_MODES = {
    "HIGH_DENSITY": dai.node.StereoDepth.PresetMode.HIGH_DENSITY,
    "HIGH_ACCURACY": dai.node.StereoDepth.PresetMode.HIGH_ACCURACY,
    "DEFAULT": dai.node.StereoDepth.PresetMode.DEFAULT,
    "FACE": dai.node.StereoDepth.PresetMode.FACE,
    "HIGH_DETAIL": dai.node.StereoDepth.PresetMode.HIGH_DETAIL,
    "ROBOTICS": dai.node.StereoDepth.PresetMode.ROBOTICS,
}

_DEPTH_MEDIAN_FILTERS = {
    "MEDIAN_OFF": dai.MedianFilter.MEDIAN_OFF,
    "KERNEL_3x3": dai.MedianFilter.KERNEL_3x3,
    "KERNEL_5x5": dai.MedianFilter.KERNEL_5x5,
    "KERNEL_7x7": dai.MedianFilter.KERNEL_7x7,
}

_AWB_MODES = {
    "AUTO": dai.CameraControl.AutoWhiteBalanceMode.AUTO,
    "OFF": dai.CameraControl.AutoWhiteBalanceMode.OFF,
    "INCANDESCENT": dai.CameraControl.AutoWhiteBalanceMode.INCANDESCENT,
    "FLUORESCENT": dai.CameraControl.AutoWhiteBalanceMode.FLUORESCENT,
    "WARM_FLUORESCENT": dai.CameraControl.AutoWhiteBalanceMode.WARM_FLUORESCENT,
    "DAYLIGHT": dai.CameraControl.AutoWhiteBalanceMode.DAYLIGHT,
    "CLOUDY_DAYLIGHT": dai.CameraControl.AutoWhiteBalanceMode.CLOUDY_DAYLIGHT,
    "TWILIGHT": dai.CameraControl.AutoWhiteBalanceMode.TWILIGHT,
    "SHADE": dai.CameraControl.AutoWhiteBalanceMode.SHADE,
}

_ANTI_BANDING_MODES = {
    "AUTO": dai.CameraControl.AntiBandingMode.AUTO,
    "OFF": dai.CameraControl.AntiBandingMode.OFF,
    "MAINS_50_HZ": dai.CameraControl.AntiBandingMode.MAINS_50_HZ,
    "MAINS_60_HZ": dai.CameraControl.AntiBandingMode.MAINS_60_HZ,
}

_EFFECT_MODES = {
    "OFF": dai.CameraControl.EffectMode.OFF,
    "MONO": dai.CameraControl.EffectMode.MONO,
    "NEGATIVE": dai.CameraControl.EffectMode.NEGATIVE,
    "SOLARIZE": dai.CameraControl.EffectMode.SOLARIZE,
    "SEPIA": dai.CameraControl.EffectMode.SEPIA,
    "POSTERIZE": dai.CameraControl.EffectMode.POSTERIZE,
    "WHITEBOARD": dai.CameraControl.EffectMode.WHITEBOARD,
    "BLACKBOARD": dai.CameraControl.EffectMode.BLACKBOARD,
    "AQUA": dai.CameraControl.EffectMode.AQUA,
}

# OakDFrameAlignment is a plain visiongraph Enum (light, no depthai import) —
# CHOICES stores the member's .name, resolved back via OakDFrameAlignment[name]
# lazily inside hb_handle_start (importing OakDInput at module top costs ~7s,
# see notes.md Q13 lazy-import discipline).
_FRAME_ALIGNMENT_OPTIONS = ["Disabled", "Color", "Infrared"]


@node(
    label="OAK-D Camera",
    description="Opens an OAK-D depth camera and emits colour/depth/infrared frame callbacks",
    menu="vision/input",
    search_tags=[
        "oak",
        "oak-d",
        "depthai",
        "luxonis",
        "depth",
        "camera",
        "3d",
        "stream",
    ],
    node_type=NodeType.CONTROL,
)
class OakDCameraNode(BaseNode):
    """
    Starts an OAK-D capture stream in a separate thread and emits one callback
    per frame carrying every active stream.

    Inputs:
        start: Open the device and begin capturing.
        stop: Stop capturing and close the device.
        mxid: Optional device MXID / name (empty = first available).
        callbacks: Pooled MULTIFRAME_CALLBACK subscriptions from event nodes.

    Outputs:
        started: Triggered when the device opens successfully.
        stopped: Triggered when capture stops.

    Settings:
        depth: Pipeline-construction params (read once at setup(), immutable
            while running). Panel-only — not promotable to a port.
        ir: Live IR laser/flood intensity. Promotable to an inlet — pushed
            straight to the running device.
        color: Live color-sensor controls (exposure/WB/focus/tuning).
            Promotable to an inlet. Inert while enable_color is False (no
            color control queue exists on the device in that case).
    """

    class depth(NodeSettings):
        preset_mode = setting[CHOICES](
            "HIGH_DENSITY",
            label="Preset Mode",
            category="Depth",
            description="Stereo depth quality/speed preset. Requires a device restart to apply.",
            widget_config={"options": list(_DEPTH_PRESET_MODES.keys())},
        )
        median_filter = setting[CHOICES](
            "KERNEL_7x7",
            label="Median Filter",
            category="Depth",
            description="Disparity smoothing kernel. Requires a device restart to apply.",
            widget_config={"options": list(_DEPTH_MEDIAN_FILTERS.keys())},
        )
        left_right_check = setting[BOOL](
            True,
            label="Left/Right Check",
            category="Depth",
            description="Better handling of occlusions. Requires a device restart to apply.",
        )
        subpixel = setting[BOOL](
            False,
            label="Subpixel",
            category="Depth",
            description="Fractional disparity for longer-range accuracy. Restart required.",
        )
        extended_disparity = setting[BOOL](
            False,
            label="Extended Disparity",
            category="Depth",
            description="Closer-in minimum depth, doubled disparity range. Restart required.",
        )
        frame_alignment = setting[CHOICES](
            "Color",
            label="Frame Alignment",
            category="Depth",
            description="Align the depth map to Color, Infrared, or leave Disabled. Restart required.",
            widget_config={"options": _FRAME_ALIGNMENT_OPTIONS},
        )

    class ir(NodeSettings):
        laser_intensity = setting[FLOAT](
            0.0,
            min=0.0,
            max=1.0,
            label="Projector Intensity",
            description="Sets intensity of laser dot projector",
            category="Infrared",
        )
        flood_intensity = setting[FLOAT](
            0.0,
            min=0.0,
            max=1.0,
            label="Flood Light Intensity",
            description="Sets intensity of the IR flood light",
            category="Infrared",
        )

    class color(NodeSettings):
        enable_auto_exposure = setting[BOOL](
            True,
            label="Auto Exposure",
            description="Enables or disables auto exposure. Inert if Color is off.",
            category="Exposure",
        )
        exposure = setting[INT](
            20000,
            min=1,
            max=33000,
            label="Exposure (µs)",
            description=(
                "Manual exposure time. Only applied while Auto Exposure is off. Inert if Color is off."
            ),
            category="Exposure",
        )
        iso = setting[INT](
            800,
            min=100,
            max=1600,
            label="ISO",
            description="Sensor ISO sensitivity. Inert if Color is off.",
            category="Exposure",
        )
        auto_exposure_compensation = setting[INT](
            0,
            min=-9,
            max=9,
            label="Auto Exposure Compensation",
            description="Bias applied to auto exposure, in the range [-9, 9]. Inert if Color is off.",
            category="Exposure",
        )
        enable_auto_white_balance = setting[BOOL](
            True,
            label="Auto White Balance",
            description="Enables or disables auto white balance. Inert if Color is off.",
            category="White Balance",
        )
        white_balance = setting[INT](
            4000,
            min=1000,
            max=12000,
            label="White Balance (K)",
            description=(
                "Manual white balance in Kelvin. Only applied while Auto White Balance is off. "
                "Inert if Color is off."
            ),
            category="White Balance",
        )
        auto_white_balance_mode = setting[CHOICES](
            "AUTO",
            label="Auto White Balance Mode",
            description=(
                "Auto white balance scene preset (e.g. Daylight, Fluorescent). Inert if Color is off."
            ),
            category="White Balance",
            widget_config={"options": list(_AWB_MODES.keys())},
        )
        auto_focus = setting[BOOL](
            True,
            label="Auto Focus",
            description="Enables or disables auto focus. Inert if Color is off.",
            category="Focus",
        )
        focus_distance = setting[INT](
            0,
            min=0,
            max=255,
            label="Focus Distance",
            description=(
                "Manual focus position. Only applied while Auto Focus is off. Inert if Color is off."
            ),
            category="Focus",
        )
        brightness = setting[INT](
            0,
            min=-10,
            max=10,
            label="Brightness",
            description="Image brightness, in the range [-10, 10]. Inert if Color is off.",
            category="Image Tuning",
        )
        contrast = setting[INT](
            0,
            min=-10,
            max=10,
            label="Contrast",
            description="Image contrast, in the range [-10, 10]. Inert if Color is off.",
            category="Image Tuning",
        )
        saturation = setting[INT](
            0,
            min=-10,
            max=10,
            label="Saturation",
            description="Image saturation, in the range [-10, 10]. Inert if Color is off.",
            category="Image Tuning",
        )
        sharpness = setting[INT](
            0,
            min=0,
            max=4,
            label="Sharpness",
            description="Image sharpness, in the range [0, 4]. Inert if Color is off.",
            category="Image Tuning",
        )
        luma_denoise = setting[INT](
            0,
            min=0,
            max=4,
            label="Luma Denoise",
            description="Luminance noise reduction, in the range [0, 4]. Inert if Color is off.",
            category="Image Tuning",
        )
        chroma_denoise = setting[INT](
            0,
            min=0,
            max=4,
            label="Chroma Denoise",
            description="Chrominance (color) noise reduction, in the range [0, 4]. Inert if Color is off.",
            category="Image Tuning",
        )
        anti_banding_mode = setting[CHOICES](
            "AUTO",
            label="Anti-Banding Mode",
            description="Reduces flicker banding from artificial lighting. Inert if Color is off.",
            category="Image Tuning",
            widget_config={"options": list(_ANTI_BANDING_MODES.keys())},
        )
        effect_mode = setting[CHOICES](
            "OFF",
            label="Effect Mode",
            description="Built-in color effect (e.g. Mono, Sepia, Negative). Inert if Color is off.",
            category="Image Tuning",
            widget_config={"options": list(_EFFECT_MODES.keys())},
        )

    def init(self):
        from haywire.barn.builtin.types import STRING
        from haybale_core.types import EXEC
        from haybale_core.types import PooledType
        from haywire.barn.builtin.widgets import SelectWidget, SimpleLabelWidget
        from ..types.multiframe_callback_type import MULTIFRAME_CALLBACK

        # Control inputs
        self.add(EXEC.as_inlet("start", label="Start"))
        self.add(EXEC.as_inlet("stop", label="Stop"))

        # Device selection (empty = first available device). Options are
        # resolved fresh on every dropdown open via dai.Device.getAllAvailableDevices()
        # (a static enumeration call — no device needs to be opened first).
        self.add(
            STRING.as_config(
                "mxid",
                default="",
                label="Device MXID",
                description="Leave empty to auto-select the first available OAK device.",
                widget=SelectWidget.config(
                    properties={"options": self.hb_list_available_mxids}
                ),
            )
        )

        # Pooled subscriptions: each connected event node contributes its
        # MULTIFRAME_CALLBACK (name + stream requirements).
        self.add(
            PooledType[MULTIFRAME_CALLBACK].as_inlet(
                "callbacks",
                label="Subscribers",
                description="Connect to a Frame Event node",
            )
        )

        # Status display
        self.add(
            STRING.as_config(
                "status",
                default="Idle",
                label="Status",
                widget=SimpleLabelWidget.config(),
            )
        )

        # Control outputs
        self.add(EXEC.as_outlet("started", label="Started"))
        self.add(EXEC.as_outlet("stopped", label="Stopped"))

    def post_init(self):
        """Initialize node state."""
        self.hb_input = None
        self.hb_thread: Optional[threading.Thread] = None
        self.hb_is_running = False
        self.hb_frame_count = 0
        self.hb_start_time = 0.0
        self.hb_lock = threading.Lock()
        # Requirement union, gathered in on_startup.
        self.hb_want_rgb = False
        self.hb_want_depth = False
        self.hb_want_ir = False

        # Live-control settings: one subscription per bag, dispatched by field
        # name to the running device. No-op (guarded) while hb_input is None.
        self.ir.subscribe(self.hb_on_ir_changed)
        self.color.subscribe(self.hb_on_color_changed)

    def hb_list_available_mxids(self) -> dict:
        """Enumerate connected OAK devices for the mxid dropdown (static query, no device opened)."""
        options = {"": "(auto — first available)"}
        try:
            for info in dai.Device.getAllAvailableDevices():
                options[info.mxid] = (
                    f"{info.mxid} ({info.name})" if info.name else info.mxid
                )
        except Exception:
            logger.exception("Failed to enumerate OAK-D devices")
        return options

    # ir setting field name -> OakDInput attribute name.
    _IR_ATTR_MAP = {
        "laser_intensity": "ir_laser_dot_projector_intensity",
        "flood_intensity": "ir_flood_light_intensity",
    }

    def hb_on_ir_changed(self, name: str, value, old):
        """Push an IR setting change straight to the running device."""
        if self.hb_input is None:
            return
        try:
            setattr(self.hb_input, self._IR_ATTR_MAP[name], value)
        except Exception as e:
            logger.exception("Failed to apply IR setting %r", name)
            self.hb_update_status(f"Setting error ({name}): {e}")

    def hb_on_color_changed(self, name: str, value, old):
        """Push a color setting change straight to the running device."""
        if self.hb_input is None:
            return
        try:
            resolved = self.hb_resolve_color_value(name, value)
            setattr(self.hb_input, name, resolved)
        except Exception as e:
            logger.exception("Failed to apply color setting %r", name)
            self.hb_update_status(f"Setting error ({name}): {e}")

    @staticmethod
    def hb_resolve_color_value(name: str, value):
        """Translate a CHOICES string back to its dai enum member, where applicable."""
        if name == "auto_white_balance_mode":
            return _AWB_MODES[value]
        if name == "anti_banding_mode":
            return _ANTI_BANDING_MODES[value]
        if name == "effect_mode":
            return _EFFECT_MODES[value]
        return value

    def hb_apply_live_settings(self):
        """Push current ir/color settings onto a freshly-opened device (apply-on-open)."""
        cam = self.hb_input
        if cam is None:
            return
        for ir_name, attr in self._IR_ATTR_MAP.items():
            setattr(cam, attr, getattr(self.ir, ir_name))
        for name in (
            "enable_auto_exposure",
            "exposure",
            "iso",
            "auto_exposure_compensation",
            "enable_auto_white_balance",
            "white_balance",
            "auto_white_balance_mode",
            "auto_focus",
            "focus_distance",
            "brightness",
            "contrast",
            "saturation",
            "sharpness",
            "luma_denoise",
            "chroma_denoise",
            "anti_banding_mode",
            "effect_mode",
        ):
            value = getattr(self.color, name)
            setattr(cam, name, self.hb_resolve_color_value(name, value))

    def on_startup(self, context: ExecutionContext):
        """Gather the stream requirement union from subscribers (config only)."""
        self.hb_gather_requirements()
        self.hb_update_status("Ready")

    def on_shutdown(self, context: ExecutionContext):
        """Fallback teardown if the user never pulsed stop."""
        self.hb_stop_capture()
        self.hb_update_status("Shutdown")

    def on_teardown(self):
        """Final cleanup when the node is destroyed."""
        self.hb_stop_capture()

    def hb_gather_requirements(self):
        """Union the per-stream requirements across all pooled subscribers."""
        subs = self.value("callbacks") or {}
        want_rgb = want_depth = want_ir = False
        for sub in subs.values():
            want_rgb = want_rgb or bool(getattr(sub, "rgb", False))
            want_depth = want_depth or bool(getattr(sub, "depth", False))
            want_ir = want_ir or bool(getattr(sub, "ir", False))
        self.hb_want_rgb = want_rgb
        self.hb_want_depth = want_depth
        self.hb_want_ir = want_ir
        self.hb_refresh_stream_status_indication()

    def hb_refresh_stream_status_indication(self):
        """Disable each stream's settings in the panel when nobody currently
        wants that stream (per the union gathered in hb_gather_requirements).

        Purely visual, and genuinely side-effect-free: the ui-disabled API
        rides the dedicated UI-state channel and never fires cell events, so
        the bag subscriptions that push live settings to the device
        (hb_on_ir_changed/hb_on_color_changed) never hear these calls, and
        transition-only firing makes steady-state re-gathers silent. The
        bulk form iterates each bag's own declared fields — no field-name
        list to maintain here. This is the cross-bag/external case
        set_ui_disabled exists for: the gating condition lives on THIS node
        (hb_want_rgb/depth/ir, derived from a different node's callback
        edge), not on a sibling setting within the same bag — so it cannot
        be expressed via the enabled_when metadata convention (same-bag
        only).
        """
        self.depth.set_ui_disabled_all(not self.hb_want_depth)
        self.ir.set_ui_disabled_all(not self.hb_want_ir)
        self.color.set_ui_disabled_all(not self.hb_want_rgb)

    def worker(self, context: ExecutionContext) -> Optional[str]:
        """Handle start/stop control signals."""
        if context.control_pin == "start":
            return self.hb_handle_start(context)
        elif context.control_pin == "stop":
            return self.hb_handle_stop()
        return None

    def hb_handle_start(self, context: ExecutionContext) -> Optional[str]:
        """Open the OAK device using the gathered requirement union."""
        if self.hb_is_running:
            self.hb_update_status("Already running")
            return "started"

        # Re-read the union in case it was not gathered (defensive).
        self.hb_gather_requirements()

        if not (self.hb_want_rgb or self.hb_want_depth or self.hb_want_ir):
            self.hb_update_status("No streams requested by subscribers")
            return None

        self.hb_update_status("Opening OAK-D...")
        try:
            from visiongraph.input.OakDInput import OakDInput, OakDFrameAlignment

            mxid = self.value("mxid") or None
            cam = OakDInput(mxid_or_name=mxid)
            cam.enable_color = self.hb_want_rgb
            cam.enable_depth = self.hb_want_depth
            cam.use_infrared = self.hb_want_ir
            # visiongraph's setup() unconditionally requests the 'rgb_still'
            # output queue when color is enabled, but only creates that output
            # node when enable_color_still is True. Enable it to keep setup
            # internally consistent (we never call capture_color_still()).
            if self.hb_want_rgb:
                cam.enable_color_still = True

            # Depth-quality settings: pipeline-construction params, must be
            # set before setup()/pre_start_setup() build the device pipeline.
            cam.depth_preset_mode = _DEPTH_PRESET_MODES[str(self.depth.preset_mode)]
            cam.depth_median_filter = _DEPTH_MEDIAN_FILTERS[
                str(self.depth.median_filter)
            ]
            cam.depth_left_right_check = self.depth.left_right_check
            cam.depth_subpixel = self.depth.subpixel
            cam.depth_extended_disparity = self.depth.extended_disparity
            cam.frame_alignment = OakDFrameAlignment[str(self.depth.frame_alignment)]

            cam.setup()
            self.hb_input = cam

            # Apply-on-open: push current ir/color live-control settings so
            # the device reflects the panel from the very first frame.
            self.hb_apply_live_settings()

            self.hb_is_running = True
            self.hb_frame_count = 0
            self.hb_start_time = time.time()

            self.hb_thread = threading.Thread(
                target=self.hb_capture_loop, args=(context,), daemon=True
            )
            self.hb_thread.start()

            streams = ", ".join(
                s
                for s, on in (
                    ("rgb", self.hb_want_rgb),
                    ("depth", self.hb_want_depth),
                    ("ir", self.hb_want_ir),
                )
                if on
            )
            self.hb_update_status(f"Running [{streams}]")
            return "started"
        except Exception as e:
            self.hb_update_status(f"Error: {e}")
            self.hb_stop_capture()
            return None

    def hb_handle_stop(self) -> Optional[str]:
        """Stop capturing and close the device."""
        if not self.hb_is_running:
            self.hb_update_status("Not running")
            return None
        self.hb_stop_capture()
        self.hb_update_status("Stopped")
        return "stopped"

    def hb_capture_loop(self, context: ExecutionContext):
        """Capture loop running in a separate thread."""
        from visiongraph.model.CameraStreamType import CameraStreamType

        cam = self.hb_input
        while self.hb_is_running and cam is not None:
            try:
                cam.read()
                self.hb_frame_count += 1
                timestamp = time.time() - self.hb_start_time

                # Open-keyed payload (notes.md Q20): only active streams present.
                payload: dict = {
                    "frame_number": self.hb_frame_count,
                    "timestamp": timestamp,
                }
                if self.hb_want_rgb:
                    payload["rgb"] = cam.get_raw_image(CameraStreamType.Color)
                if self.hb_want_depth:
                    payload["depth"] = cam.depth_buffer
                if self.hb_want_ir:
                    payload["ir"] = cam.get_raw_image(CameraStreamType.Infrared)

                subs = self.value("callbacks") or {}
                for sub in subs.values():
                    name = getattr(sub, "name", None)
                    if name:
                        context.emit_callback(event_name=name, payload=payload)
            except Exception as e:
                logger.exception("OakDEmit capture error")
                self.hb_update_status(f"Capture error: {e}")
                break

        with self.hb_lock:
            self.hb_is_running = False

    def hb_stop_capture(self):
        """Stop the thread and release the device."""
        # post_init() may never have run (e.g. init() failed during a reset/
        # reload), in which case none of the hb_* attributes exist yet —
        # nothing was ever opened, so there's nothing to stop.
        if not hasattr(self, "hb_lock"):
            return

        with self.hb_lock:
            self.hb_is_running = False

        if self.hb_thread is not None and self.hb_thread.is_alive():
            self.hb_thread.join(timeout=2.0)
            self.hb_thread = None

        if self.hb_input is not None:
            try:
                self.hb_input.release()
            except Exception:
                pass
            self.hb_input = None

    def hb_update_status(self, status: str):
        """Update the status label."""
        try:
            self.ports["status"].set_value(status)
        except Exception:
            pass
