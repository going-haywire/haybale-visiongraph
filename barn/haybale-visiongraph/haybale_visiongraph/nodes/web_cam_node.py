"""
Web Camera node — opens a camera and emits frame callbacks.

Wraps visiongraph's ``VideoCaptureInput`` rather than driving ``cv2`` directly.
It was the only node in this library still bypassing the library it exists to
wrap, and the hand-rolled capture code duplicated ``_setup_cap``'s size
read-back. Going through visiongraph also brings the ``BaseInput`` post-processing
chain — ``rotate`` / ``flip`` / ``crop`` / ``raw_input``, applied per frame —
and backend selection, none of which were reachable before.

The webcam is the RGB-only member of the camera family: it honours only the
``rgb`` requirement from its pooled subscribers and ignores depth/ir (see
notes.md "webcam joins the 3D-camera family").

Not in scope here: ``VideoCaptureInput.channel`` also accepts a *path*, which
with ``loop`` / ``fps_lock`` / ``input_skip`` would make this a video-file
player. That is a different node's identity (label, menu, and the type of a
saved config value) and belongs in its own ``VideoFileNode``.
"""

import time
import threading
from typing import TYPE_CHECKING, Optional

from haywire.core.execution.execution_context import ExecutionContext
from haywire.core.node import node, BaseNode, NodeType
from haywire.core.settings import NodeSettings, Promotable, setting
from haywire.core.types.enums import PortType
from haywire.barn.builtin.types import BOOL, CHOICES, FLOAT, INT
from haywire.barn.builtin.widgets import SelectWidget

from .webcam_devices import list_camera_options

# visiongraph ships the string -> cv2 constant tables for these, so no
# hand-written lookup like OakDCameraNode's dai enum maps is needed.
ROTATE_NONE = "None"
FLIP_NONE = "None"

_CAPTURE_BACKENDS = ["Any", "AVFoundation", "V4L2", "GStreamer", "FFmpeg", "MSMF", "DirectShow"]


class CaptureSettings(NodeSettings):
    """Everything consumed when the capture device is OPENED.

    All rebuild-category (``Promotable.CONFIG``): ``_setup_cap`` reads them
    while building the ``cv2.VideoCapture``, so an edge could not drive them
    mid-capture — but a face widget is harmless.

    ``frame_skip`` is the exception and is deliberately live: it is node-local
    (emit every Nth callback), not a visiongraph concept, and it is the one
    knob here you tune while watching output. Note visiongraph's own
    ``input_skip`` is an unrelated millisecond seek into a *file*.
    """

    camera_index = setting[INT](
        0,
        min=0,
        max=64,
        label="Camera",
        category="Capture",
        description=(
            "Which camera to open. The stored value is the positional index "
            "OpenCV uses — names are labels only, and may not match under a "
            "different capture backend."
        ),
        # A live callable is safe on a setting() field (and on the port it is
        # promoted to): neither serializes widget_config, so the callable never
        # has to survive a save/load. It re-runs on every dropdown open.
        widget=SelectWidget.config(properties={"options": list_camera_options}),
        promotable=Promotable.CONFIG,
    )
    width = setting[INT](
        0,
        min=0,
        max=7680,
        label="Width (0=auto)",
        category="Capture",
        description="Requested frame width. 0 keeps the camera's own default.",
        promotable=Promotable.CONFIG,
    )
    height = setting[INT](
        0,
        min=0,
        max=4320,
        label="Height (0=auto)",
        category="Capture",
        description="Requested frame height. 0 keeps the camera's own default.",
        promotable=Promotable.CONFIG,
    )
    fps = setting[FLOAT](
        0.0,
        min=0.0,
        max=240.0,
        label="FPS (0=auto)",
        category="Capture",
        description="Requested frame rate. 0 keeps the camera's own default.",
        promotable=Promotable.CONFIG,
    )
    capture_backend = setting[CHOICES](
        "Any",
        label="Capture Backend",
        category="Capture",
        description="Which OpenCV capture API to use. Any lets OpenCV choose.",
        widget_config={"options": _CAPTURE_BACKENDS},
        promotable=Promotable.CONFIG,
    )
    frame_skip = setting[INT](
        1,
        min=1,
        max=60,
        label="Frame Skip",
        category="Capture",
        description="Emit a callback every Nth frame. 1 emits every frame.",
    )


class ImageSettings(NodeSettings):
    """``BaseInput`` post-processing, applied per frame — all live.

    ``mask`` is deliberately absent: it is image-valued, so it has no widget
    and would want to be an inlet, which is a separate design.
    """

    rotate = setting[CHOICES](
        ROTATE_NONE,
        label="Rotate",
        category="Image",
        description="Rotate each frame. Useful for a camera mounted sideways.",
        widget_config={"options": [ROTATE_NONE, "90", "-90", "180"]},
    )
    flip = setting[CHOICES](
        FLIP_NONE,
        label="Flip",
        category="Image",
        description="Mirror each frame horizontally or vertically.",
        widget_config={"options": [FLIP_NONE, "h", "v"]},
    )
    crop_x = setting[FLOAT](
        0.0, min=0.0, max=1.0, label="Crop X", category="Crop", description="Normalized left edge."
    )
    crop_y = setting[FLOAT](
        0.0, min=0.0, max=1.0, label="Crop Y", category="Crop", description="Normalized top edge."
    )
    crop_width = setting[FLOAT](
        1.0, min=0.0, max=1.0, label="Crop Width", category="Crop", description="Normalized width."
    )
    crop_height = setting[FLOAT](
        1.0, min=0.0, max=1.0, label="Crop Height", category="Crop", description="Normalized height."
    )
    raw_input = setting[BOOL](
        False,
        label="Raw Input",
        category="Image",
        description="Skip the automatic grayscale-to-3-channel conversion.",
    )


@node(
    label="Web Camera",
    description="Starts a webcam stream and emits frame callbacks",
    menu="vision/input",
    search_tags=["webcam", "camera", "video", "capture", "stream"],
    node_type=NodeType.CONTROL,
)
class WebCameraNode(BaseNode):
    """
    Starts a webcam video stream that runs in a separate thread.
    Emits callbacks on each frame for downstream event nodes to process.

    Inputs:
        start: Begin capturing from webcam
        stop: Stop the capture stream
        callbacks: Pooled MULTIFRAME_CALLBACK subscriptions from event nodes

    Settings:
        capture: camera_index / width / height / fps / capture_backend /
            frame_skip. ``camera_index`` and ``frame_skip`` are seeded to
            config ports — the node's default face.
        image: rotate / flip / crop / raw_input, applied per frame.

    Outputs:
        started: Triggered when stream starts successfully
        stopped: Triggered when stream stops
    """

    if TYPE_CHECKING:
        capture: CaptureSettings
        image: ImageSettings
    else:
        capture = CaptureSettings
        image = ImageSettings

    def init(self):
        from haywire.barn.builtin.types import STRING
        from haybale_core.types import EXEC
        from haybale_core.types import PooledType
        from haywire.barn.builtin.widgets import SimpleLabelWidget
        from ..types.multiframe_callback_type import MULTIFRAME_CALLBACK

        # Control inputs
        self.add(EXEC.as_inlet("start", label="Start"))
        self.add(EXEC.as_inlet("stop", label="Stop"))

        # Subscriptions from Frame Event nodes.
        self.add(
            PooledType[MULTIFRAME_CALLBACK].as_inlet(
                "callbacks",
                label="Subscribers",
                description=(
                    "Connect to a Frame Event node. Beware: this camera type can only deliver rgb frames"
                ),
            )
        )

        # Status display — a read-only label, never a setting.
        self.add(
            STRING.as_config("status", default="Idle", label="Status", widget=SimpleLabelWidget.config())
        )

        # Control outputs
        self.add(EXEC.as_outlet("started", label="Started"))
        self.add(EXEC.as_outlet("stopped", label="Stopped"))

        # Seeded promotions: this node's default face. The open-time knobs
        # (width/height/fps/backend) stay panel-only — they are set once when
        # the camera is first wired, and would otherwise crowd the card.
        # In init(), NOT post_init: post_init also runs on graph load, after
        # promotions are restored, so promoting there would undo a demotion.
        self.capture.promote("camera_index", PortType.CONFIG)
        self.capture.promote("frame_skip", PortType.CONFIG)

    def post_init(self):
        """Initialize node state"""
        self.hb_input = None
        self.hb_capture_thread: Optional[threading.Thread] = None
        self.hb_is_running = False
        self.hb_frame_count = 0
        self.hb_start_time = 0.0
        self.hb_lock = threading.Lock()

    def on_startup(self, context: ExecutionContext):
        """Called when node starts in VM"""
        self.hb_update_status("Ready")

    def on_shutdown(self, context: ExecutionContext):
        """Called when node shuts down - clean up resources"""
        self.hb_stop_capture()
        self.hb_update_status("Shutdown")

    def on_teardown(self):
        """Final cleanup when node is destroyed"""
        self.hb_stop_capture()

    def worker(self, context: ExecutionContext) -> Optional[str]:
        """Handle start/stop control signals"""
        if context.control_pin == "start":
            return self.hb_handle_start(context)
        elif context.control_pin == "stop":
            return self.hb_handle_stop()
        return None

    def hb_build_input(self):
        """Construct + configure a ``VideoCaptureInput`` for the current settings.

        Everything here happens BEFORE ``setup()``, which is the window in which
        ``VideoCaptureInput`` reads its open-time attributes.
        """
        import cv2
        from visiongraph.input.VideoCaptureInput import VideoCaptureInput

        cam = VideoCaptureInput(channel=int(self.capture.camera_index))

        backend = str(self.capture.capture_backend)
        backends = {
            "Any": cv2.CAP_ANY,
            "AVFoundation": cv2.CAP_AVFOUNDATION,
            "V4L2": cv2.CAP_V4L2,
            "GStreamer": cv2.CAP_GSTREAMER,
            "FFmpeg": cv2.CAP_FFMPEG,
            "MSMF": cv2.CAP_MSMF,
            "DirectShow": cv2.CAP_DSHOW,
        }
        cam.capture_backend = backends.get(backend, cv2.CAP_ANY)

        # 0 means "keep the camera's default". BaseInput seeds width/height to
        # 640x480, so assigning a 0 through would request a 0x0 frame — the
        # one place the old node's "0 = auto" convention has to be preserved
        # by hand against visiongraph's own defaults.
        if self.capture.width > 0:
            cam.width = int(self.capture.width)
        if self.capture.height > 0:
            cam.height = int(self.capture.height)
        if self.capture.fps > 0:
            cam.fps = float(self.capture.fps)

        self.hb_apply_image_settings(cam)
        return cam

    def hb_apply_image_settings(self, cam):
        """Push the per-frame post-processing settings onto the input.

        Live: ``BaseInput._post_process`` reads all of these every frame, so
        they can be re-applied on a running capture.
        """
        from visiongraph.model.geometry.BoundingBox2D import BoundingBox2D
        from visiongraph.model.parameter.NamedParameter import FlipParameter, RotationParameter

        cam.rotate = RotationParameter.get(str(self.image.rotate))
        cam.flip = FlipParameter.get(str(self.image.flip))
        cam.raw_input = bool(self.image.raw_input)

        # A full-frame crop is no crop: leaving it None skips the ROI step.
        x, y = float(self.image.crop_x), float(self.image.crop_y)
        w, h = float(self.image.crop_width), float(self.image.crop_height)
        cam.crop = None if (x, y, w, h) == (0.0, 0.0, 1.0, 1.0) else BoundingBox2D(x, y, w, h)

    def hb_handle_start(self, context: ExecutionContext) -> Optional[str]:
        """Start the webcam capture"""
        if self.hb_is_running:
            self.hb_update_status("Already running")
            return "started"

        # Requirement union: the webcam only provides rgb, so it captures only
        # if some subscriber wants it. depth/ir requirements are silently ignored.
        if not self.hb_any_rgb_requested():
            self.hb_update_status("No RGB subscriber")
            return None

        self.hb_update_status("Opening camera...")

        try:
            cam = self.hb_build_input()
            cam.setup()
            self.hb_input = cam

            # visiongraph reads back what the camera actually granted when it
            # refuses a requested size, so these are the real values.
            self.hb_is_running = True
            self.hb_frame_count = 0
            self.hb_start_time = time.time()

            self.hb_capture_thread = threading.Thread(
                target=self.hb_capture_loop, args=(context,), daemon=True
            )
            self.hb_capture_thread.start()

            self.hb_update_status(f"Running {int(cam.width)}x{int(cam.height)}@{cam.fps:.0f}fps")
            return "started"

        except Exception as e:
            self.hb_update_status(f"Error: {str(e)}")
            self.hb_stop_capture()
            return None

    def hb_handle_stop(self) -> Optional[str]:
        """Stop the webcam capture"""
        if not self.hb_is_running:
            self.hb_update_status("Not running")
            return None

        self.hb_stop_capture()
        self.hb_update_status("Stopped")
        return "stopped"

    def hb_any_rgb_requested(self) -> bool:
        """True if any subscribed Frame Event node requests the rgb stream."""
        subs: dict = self.value("callbacks") or {}
        return any(getattr(sub, "rgb", False) for sub in subs.values())

    def hb_capture_loop(self, context: ExecutionContext):
        """Main capture loop running in separate thread"""
        while self.hb_is_running and self.hb_input is not None:
            try:
                # Live image settings, re-applied per frame so a panel change
                # takes effect without a restart.
                self.hb_apply_image_settings(self.hb_input)

                _ts, frame = self.hb_input.read()

                if frame is None:
                    self.hb_update_status("Failed to read frame")
                    break

                self.hb_frame_count += 1

                # Apply frame skip
                if (self.hb_frame_count - 1) % max(1, int(self.capture.frame_skip)) != 0:
                    continue

                # Open-keyed payload, same shape as the OAK emit node: the webcam
                # provides only `rgb`. Subscribers' depth/ir requirements yield no
                # payload key, so those event-node outlets stay unfired.
                timestamp = time.time() - self.hb_start_time
                payload = {
                    "rgb": frame,
                    "frame_number": self.hb_frame_count,
                    "timestamp": timestamp,
                }

                # Dispatch to every subscriber that wants rgb, keyed by its name.
                subs: dict = self.value("callbacks") or {}
                for sub in subs.values():
                    name = getattr(sub, "name", None)
                    if name and getattr(sub, "rgb", False):
                        context.emit_callback(event_name=name, payload=payload)

            except Exception as e:
                self.hb_update_status(f"Capture error: {str(e)}")
                break

        # Clean exit
        with self.hb_lock:
            self.hb_is_running = False

    def hb_stop_capture(self):
        """Stop capture and clean up resources"""
        # post_init() may never have run (e.g. init() failed during a reset or
        # reload), in which case none of the hb_* attributes exist yet.
        if not hasattr(self, "hb_lock"):
            return

        with self.hb_lock:
            self.hb_is_running = False

        if self.hb_capture_thread is not None and self.hb_capture_thread.is_alive():
            self.hb_capture_thread.join(timeout=2.0)
            self.hb_capture_thread = None

        if self.hb_input is not None:
            try:
                self.hb_input.release()
            except Exception:
                pass
            self.hb_input = None

    def hb_update_status(self, status: str):
        """Update the status label"""
        try:
            self.ports["status"].set_value(status)
        except Exception:
            # Silently fail if UI update fails
            pass
