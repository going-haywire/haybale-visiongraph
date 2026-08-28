# Frame Event

`haybale-visiongraph:node:NumpyFrameEventNode` · kind: node

Triggered when a camera frame is ready; exposes colour/depth/infrared streams

## Ports

| id | direction | type | description |
|---|---|---|---|
| enable_rgb | config | haywire-core:type:BOOL | True or False |
| enable_depth | config | haywire-core:type:BOOL | True or False |
| enable_ir | config | haywire-core:type:BOOL | True or False |
| subscription | outlet | haybale-visiongraph:type:MULTIFRAME_CALLBACK | Subscribe for camera frames |
| frame_ready | outlet | haybale-core:type:EXEC | Signal for controlling execution flow between nodes |
| timestamp | outlet | haywire-core:type:FLOAT | Decimal numberer |
| frame_number | outlet | haywire-core:type:INT | Whole number |
| rgb | outlet | haybale-visiongraph:type:RGB_FRAME | 3-channel uint8 colour video frame |

## Notes

Event node that receives 3D-camera frame callbacks.

Config:
    rgb / depth / ir: Toggle which streams this node requests and exposes.

Outputs:
    subscription: MULTIFRAME_CALLBACK carrying the event name + requirements.
    frame_ready: Control flow when a frame arrives.
    rgb / depth / ir: The requested frame streams (dynamic outlets).
    frame_number / timestamp: Frame metadata.
