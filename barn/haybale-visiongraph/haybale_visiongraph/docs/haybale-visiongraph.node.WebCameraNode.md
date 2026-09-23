# Web Camera

`haybale-visiongraph:node:WebCameraNode` · kind: node

Starts a webcam stream and emits frame callbacks

## Ports

| id | direction | type | description |
|---|---|---|---|
| start | inlet | haybale-core:type:EXEC | Signal for controlling execution flow between nodes |
| stop | inlet | haybale-core:type:EXEC | Signal for controlling execution flow between nodes |
| callbacks | inlet | haybale-core:type:PooledType | Connect to a Frame Event node. Beware: this camera type can only deliver rgb frames |
| status | config | haywire-core:type:STRING | Text data |
| capture.camera_index | config | haywire-core:type:INT | Which camera to open. The stored value is the positional index OpenCV uses — names are labels only, and may not match under a different capture backend. |
| capture.frame_skip | config | haywire-core:type:INT | Emit a callback every Nth frame. 1 emits every frame. |
| started | outlet | haybale-core:type:EXEC | Signal for controlling execution flow between nodes |
| stopped | outlet | haybale-core:type:EXEC | Signal for controlling execution flow between nodes |

## Settings

| name | bag | default | description |
|---|---|---|---|
| camera_index | capture | 0 | Which camera to open. The stored value is the positional index OpenCV uses — names are labels only, and may not match under a different capture backend. |
| width | capture | 0 | Requested frame width. 0 keeps the camera's own default. |
| height | capture | 0 | Requested frame height. 0 keeps the camera's own default. |
| fps | capture | 0.0 | Requested frame rate. 0 keeps the camera's own default. |
| capture_backend | capture | 'Any' | Which OpenCV capture API to use. Any lets OpenCV choose. |
| frame_skip | capture | 1 | Emit a callback every Nth frame. 1 emits every frame. |
| rotate | image | 'None' | Rotate each frame. Useful for a camera mounted sideways. |
| flip | image | 'None' | Mirror each frame horizontally or vertically. |
| crop_x | image | 0.0 | Normalized left edge. |
| crop_y | image | 0.0 | Normalized top edge. |
| crop_width | image | 1.0 | Normalized width. |
| crop_height | image | 1.0 | Normalized height. |
| raw_input | image | False | Skip the automatic grayscale-to-3-channel conversion. |

## Notes

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
