# haybale-visiongraph v0.0.1
# Library ID: visiongraph
# Module: haybale_visiongraph
# Source: https://github.com/haywire/haywire-repo/libraries/haybale-visiongraph
# Dependencies: haywire-core>=0.1.0, haybale-core>=1.0.0, visiongraph[all]
# Description: Visiongraph library for Haywire node system demonstrating custom types, nodes, widgets, and renderers

## Nodes

### StartWebcamStreamNode
- registry_key: visiongraph:node:StartWebcamStreamNode
- module: haybale_visiongraph.nodes.start_web_cam_stream_node
- label: Start Webcam Stream
- menu: vision/input
- node_type: CONTROL
- description: Starts a webcam stream and emits frame callbacks
- ports:
  - inlet start: EXEC
  - inlet stop: EXEC
  - config camera_index: INT (default: 0) -- Camera index (0 = default camera)
  - config width: INT (default: 0) -- Desired frame width in pixels (0 = camera default)
  - config height: INT (default: 0) -- Desired frame height in pixels (0 = camera default)
  - config fps: INT (default: 0) -- Desired frames per second (0 = camera default)
  - config frame_skip: INT (default: 1) -- Emit callback every N frames
  - inlet callback_names: CALLBACK (pooled) -- Registered callback targets to invoke per frame
  - config status: STRING (default: Idle) -- Live status label (read-only)
  - outlet started: EXEC
  - outlet stopped: EXEC

### WebcamFrameEventNode
- registry_key: visiongraph:node:WebcamFrameEventNode
- module: haybale_visiongraph.nodes.webcam_frame_event_node
- label: Webcam Frame Event
- menu: event/vision
- node_type: EVENT
- description: Triggered when a webcam frame is ready
- ports:
  - outlet callback_name: CALLBACK -- Callback name this node listens on
  - outlet frame_ready: EXEC
  - outlet frame: FRAME
  - outlet timestamp: FLOAT
  - outlet frame_number: INT
  - outlet width: INT
  - outlet height: INT

### WebcamFrameInfoDisplayNode
- registry_key: visiongraph:node:WebcamFrameInfoDisplayNode
- module: haybale_visiongraph.nodes.frame_info_display_node
- label: Webcam Frame Info Display
- menu: vision/info
- node_type: CONTROL
- description: Displays information about webcam frames with live preview
- ports:
  - inlet execute: EXEC
  - inlet frame: FRAME
  - config info_display: STRING (default: No frame yet) -- Live frame metadata label (read-only)
  - outlet frame_ready: EXEC
  - outlet frame_pass: FRAME
  - outlet timestamp: FLOAT
  - outlet frame_number: INT
  - outlet width: INT
  - outlet height: INT

## Types

### FRAME
- registry_key: visiongraph:type:frame
- module: haybale_visiongraph.types.frame_type
- base: BaseType
- color: #9c27b0
- description: Video frame carrying a numpy array with timestamp and frame number metadata

## Widgets

### OpencvViewerWidget
- registry_key: visiongraph:widget:OpencvViewerWidget
- module: haybale_visiongraph.widgets.opencv_viewer_widget
- compatible_types: [visiongraph:type:frame]
- description: Streaming video viewer for numpy arrays using custom StreamingViewer
- config_options: quality: int, width: str, height: str, frame_queue_size: int, block_on_full: bool
