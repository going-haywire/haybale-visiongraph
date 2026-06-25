"""
Start Webcam Stream Node - Initializes webcam capture and emits frame callbacks
"""

import time
import threading
from typing import Optional

import cv2

from haywire.core.execution.execution_context import ExecutionContext
from haywire.core.node import node, BaseNode, NodeType


@node(
    label="Start Webcam Stream",
    description="Starts a webcam stream and emits frame callbacks",
    menu="vision/input",
    search_tags=["webcam", "camera", "video", "capture", "stream"],
    node_type=NodeType.CONTROL,
)
class StartWebcamStreamNode(BaseNode):
    """
    Starts a webcam video stream that runs in a separate thread.
    Emits callbacks on each frame for downstream event nodes to process.

    Inputs:
        start: Begin capturing from webcam
        stop: Stop the capture stream
        camera_index: Which camera to use (0 = default)
        width: Desired frame width (0 = camera default)
        height: Desired frame height (0 = camera default)
        fps: Desired frames per second (0 = camera default)
        frame_skip: Emit callback every N frames (1 = every frame)
        callback_name: Name for the callback event

    Outputs:
        started: Triggered when stream starts successfully
        stopped: Triggered when stream stops
    """

    def init(self):
        from haybale_core.types import EXEC, STRING, INT
        from haybale_core.types import PooledType
        from haybale_core.widgets.basic_widgets import NumberWidget, SimpleLabelWidget
        from ..types.multiframe_callback_type import MULTIFRAME_CALLBACK

        # Control inputs
        self.add(EXEC.as_inlet("start", label="Start"))
        self.add(EXEC.as_inlet("stop", label="Stop"))

        # Camera configuration
        self.add(
            INT.as_config(
                "camera_index",
                default=0,
                label="Camera Index",
                widget=NumberWidget.config(properties={"min": 0, "max": 10, "step": 1}),
            )
        )

        self.add(
            INT.as_config(
                "width",
                default=0,
                label="Width (0=auto)",
                widget=NumberWidget.config(properties={"min": 0, "max": 3840, "step": 1}),
            )
        )

        self.add(
            INT.as_config(
                "height",
                default=0,
                label="Height (0=auto)",
                widget=NumberWidget.config(properties={"min": 0, "max": 2160, "step": 1}),
            )
        )

        self.add(
            INT.as_config(
                "fps",
                default=0,
                label="FPS (0=auto)",
                widget=NumberWidget.config(properties={"min": 0, "max": 120, "step": 1}),
            )
        )

        self.add(
            INT.as_config(
                "frame_skip",
                default=1,
                label="Frame Skip",
                widget=NumberWidget.config(properties={"min": 1, "max": 60, "step": 1}),
            )
        )

        # Subscriptions from 3D Frame Event nodes. The webcam is the RGB-only
        # member of the camera family: it honors only the `rgb` requirement and
        # ignores depth/ir (see notes.md "webcam joins the 3D-camera family").
        self.add(
            PooledType[MULTIFRAME_CALLBACK].as_inlet(
                "callbacks", 
                label="Subscribers",
                description="Connect to a Frame Event node. Beware: this camera type can only deliver rgb frames"
            )
        )

        # Status display
        self.add(
            STRING.as_config("status", default="Idle", label="Status", widget=SimpleLabelWidget.config())
        )

        # Control outputs
        self.add(EXEC.as_outlet("started", label="Started"))
        self.add(EXEC.as_outlet("stopped", label="Stopped"))

    def post_init(self):
        """Initialize node state"""
        self.hb_capture: Optional[cv2.VideoCapture] = None
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
        # Check which inlet triggered this execution
        if context.control_pin == "start":
            return self.hb_handle_start(context)
        elif context.control_pin == "stop":
            return self.hb_handle_stop()
        return None

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

        # Get configuration
        camera_index = self.value("camera_index")
        width = self.value("width")
        height = self.value("height")
        fps = self.value("fps")

        self.hb_update_status("Opening camera...")

        try:
            # Open camera
            self.hb_capture = cv2.VideoCapture(camera_index)

            if not self.hb_capture.isOpened():
                self.hb_update_status(f"Failed to open camera {camera_index}")
                return None

            # Configure camera
            if width > 0:
                self.hb_capture.set(cv2.CAP_PROP_FRAME_WIDTH, width)
            if height > 0:
                self.hb_capture.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
            if fps > 0:
                self.hb_capture.set(cv2.CAP_PROP_FPS, fps)

            # Get actual resolution
            actual_width = int(self.hb_capture.get(cv2.CAP_PROP_FRAME_WIDTH))
            actual_height = int(self.hb_capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
            actual_fps = int(self.hb_capture.get(cv2.CAP_PROP_FPS))

            # Start capture thread
            self.hb_is_running = True
            self.hb_frame_count = 0
            self.hb_start_time = time.time()

            self.hb_capture_thread = threading.Thread(
                target=self.hb_capture_loop, args=(context,), daemon=True
            )
            self.hb_capture_thread.start()

            self.hb_update_status(f"Running {actual_width}x{actual_height}@{actual_fps}fps")
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
        """True if any subscribed 3D Frame Event node requests the rgb stream."""
        subs: dict = self.value("callbacks") or {}
        return any(getattr(sub, "rgb", False) for sub in subs.values())

    def hb_capture_loop(self, context: ExecutionContext):
        """Main capture loop running in separate thread"""
        frame_skip = max(1, self.value("frame_skip"))

        while self.hb_is_running and self.hb_capture is not None:
            try:
                ret, frame = self.hb_capture.read()

                if not ret or frame is None:
                    self.hb_update_status("Failed to read frame")
                    break

                self.hb_frame_count += 1

                # Apply frame skip
                if (self.hb_frame_count - 1) % frame_skip != 0:
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
        with self.hb_lock:
            self.hb_is_running = False

        # Wait for thread to finish
        if self.hb_capture_thread is not None and self.hb_capture_thread.is_alive():
            self.hb_capture_thread.join(timeout=2.0)

        # Release camera
        if self.hb_capture is not None:
            self.hb_capture.release()
            self.hb_capture = None

    def hb_update_status(self, status: str):
        """Update the status label"""
        try:
            # Update the config value
            self.ports["status"].set_value(status)
        except Exception:
            # Silently fail if UI update fails
            pass
