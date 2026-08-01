# Frame Info Display

`visiongraph:node:FrameDisplayNode` · kind: node

Displays information about frames with live preview

## Ports

| id | direction | type | description |
|---|---|---|---|
| execute | inlet | core:type:EXEC | Signal for controlling execution flow between nodes |
| frame | inlet | visiongraph:type:RGB_FRAME | 3-channel uint8 colour video frame |
| info_display | config | builtin:type:STRING | Text data |
| frame_ready | outlet | core:type:EXEC | Signal for controlling execution flow between nodes |
| frame_pass | outlet | visiongraph:type:RGB_FRAME | 3-channel uint8 colour video frame |
| timestamp | outlet | builtin:type:FLOAT | Decimal numberer |
| frame_number | outlet | builtin:type:INT | Whole number |
| width | outlet | builtin:type:INT | Whole number |
| height | outlet | builtin:type:INT | Whole number |

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
