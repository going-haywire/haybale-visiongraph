# Frame Info Display

`haybale-visiongraph:node:FrameDisplayNode` · kind: node

Displays information about frames with live preview

## Ports

| id | direction | type | description |
|---|---|---|---|
| execute | inlet | haybale-core:type:EXEC | Signal for controlling execution flow between nodes |
| frame | inlet | haybale-visiongraph:type:RGB_FRAME | 3-channel uint8 colour video frame |
| info_display | config | haywire-core:type:STRING | Text data |
| frame_ready | outlet | haybale-core:type:EXEC | Signal for controlling execution flow between nodes |
| frame_pass | outlet | haybale-visiongraph:type:RGB_FRAME | 3-channel uint8 colour video frame |
| timestamp | outlet | haywire-core:type:FLOAT | Decimal numberer |
| frame_number | outlet | haywire-core:type:INT | Whole number |
| width | outlet | haywire-core:type:INT | Whole number |
| height | outlet | haywire-core:type:INT | Whole number |

## Notes

Displays frame information and live preview.

Shows frame metadata and streams the video to an embedded viewer.

Inputs:
    execute: Control flow in
    frame: Frame to display (RGB_FRAME type)

Outputs:
    frame_ready: Control flow out
    timestamp: Time since stream start
    frame_number: Sequential frame number
    width: Frame width
    height: Frame height
