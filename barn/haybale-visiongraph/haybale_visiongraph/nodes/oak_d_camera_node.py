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
"""

import logging
import threading
import time
from typing import Optional

from haywire.core.execution.execution_context import ExecutionContext
from haywire.core.node import node, BaseNode, NodeType

logger = logging.getLogger(__name__)


@node(
    label="OAK-D Camera",
    description="Opens an OAK-D depth camera and emits colour/depth/infrared frame callbacks",
    menu="vision/input",
    search_tags=["oak", "oak-d", "depthai", "luxonis", "depth", "camera", "3d", "stream"],
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
    """

    def init(self):
        from haybale_core.types import EXEC, STRING
        from haybale_core.types import PooledType
        from haybale_core.widgets.basic_widgets import SimpleLabelWidget, TextWidget
        from ..types.multiframe_callback_type import MULTIFRAME_CALLBACK

        # Control inputs
        self.add(EXEC.as_inlet("start", label="Start"))
        self.add(EXEC.as_inlet("stop", label="Stop"))

        # Device selection (empty = first available device)
        self.add(
            STRING.as_config(
                "mxid", default="", label="Device MXID (empty=auto)", widget=TextWidget.config()
            )
        )

        # Pooled subscriptions: each connected event node contributes its
        # MULTIFRAME_CALLBACK (name + stream requirements).
        self.add(PooledType[MULTIFRAME_CALLBACK].as_inlet("callbacks", label="Subscribers", description="Connect to a Frame Event node"))

        # Status display
        self.add(
            STRING.as_config("status", default="Idle", label="Status", widget=SimpleLabelWidget.config())
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
            from visiongraph.input.OakDInput import OakDInput

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
            cam.setup()
            self.hb_input = cam

            self.hb_is_running = True
            self.hb_frame_count = 0
            self.hb_start_time = time.time()

            self.hb_thread = threading.Thread(target=self.hb_capture_loop, args=(context,), daemon=True)
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
                payload: dict = {"frame_number": self.hb_frame_count, "timestamp": timestamp}
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
