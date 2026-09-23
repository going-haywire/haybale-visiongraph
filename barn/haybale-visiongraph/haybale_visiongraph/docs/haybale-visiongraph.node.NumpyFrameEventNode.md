# Frame Event

`haybale-visiongraph:node:NumpyFrameEventNode` · kind: node

Triggered when a camera frame is ready; exposes colour/depth/infrared streams

## Ports

| id | direction | type | description |
|---|---|---|---|
| streams.enable_rgb | config | haywire-core:type:BOOL | Request and expose the colour stream. |
| streams.enable_depth | config | haywire-core:type:BOOL | Request and expose the depth stream. |
| streams.enable_ir | config | haywire-core:type:BOOL | Request and expose the infrared stream. |
| subscription | outlet | haybale-visiongraph:type:MULTIFRAME_CALLBACK | Subscribe for camera frames |
| frame_ready | outlet | haybale-core:type:EXEC | Signal for controlling execution flow between nodes |
| timestamp | outlet | haywire-core:type:FLOAT | Decimal numberer |
| frame_number | outlet | haywire-core:type:INT | Whole number |
| rgb | outlet | haybale-visiongraph:type:RGB_FRAME | 3-channel uint8 colour video frame |

## Settings

| name | bag | default | description |
|---|---|---|---|
| enable_rgb | streams | True | Request and expose the colour stream. |
| enable_depth | streams | False | Request and expose the depth stream. |
| enable_ir | streams | False | Request and expose the infrared stream. |
| queue_mode | dispatch | 'Drop (realtime)' | Drop keeps only the newest frame (live preview). Block queues every frame and back-pressures the camera (frame-accurate). Applies on next start. |
| max_queue_size | dispatch | 1 | How many pending frames to hold. Drop mode needs 1 to actually guarantee newest-wins. Applies on next start. |

## Notes

Event node that receives 3D-camera frame callbacks.

Settings:
    streams: enable_rgb / enable_depth / enable_ir — which streams this node
        requests and exposes. Seeded to config ports: the node's face.
    dispatch: queue_mode / max_queue_size — how incoming callbacks queue
        (ADR 0010). Applies on next start.

Outputs:
    subscription: MULTIFRAME_CALLBACK carrying the event name + requirements.
    frame_ready: Control flow when a frame arrives.
    rgb / depth / ir: The requested frame streams (dynamic outlets).
    frame_number / timestamp: Frame metadata.
