# Web Camera

`visiongraph:node:WebCameraNode` · kind: node

Starts a webcam stream and emits frame callbacks

## Ports

| id | direction | type | description |
|---|---|---|---|
| start | inlet | core:type:EXEC | Signal for controlling execution flow between nodes |
| stop | inlet | core:type:EXEC | Signal for controlling execution flow between nodes |
| callbacks | inlet | core:type:PooledType | Connect to a Frame Event node. Beware: this camera type can only deliver rgb frames |
| camera_index | config | builtin:type:INT | Whole number |
| width | config | builtin:type:INT | Whole number |
| height | config | builtin:type:INT | Whole number |
| fps | config | builtin:type:INT | Whole number |
| frame_skip | config | builtin:type:INT | Whole number |
| status | config | builtin:type:STRING | Text data |
| started | outlet | core:type:EXEC | Signal for controlling execution flow between nodes |
| stopped | outlet | core:type:EXEC | Signal for controlling execution flow between nodes |

## Notes

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
