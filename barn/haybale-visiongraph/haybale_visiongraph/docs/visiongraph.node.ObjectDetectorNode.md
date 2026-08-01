# Object Detector

`visiongraph:node:ObjectDetectorNode` · kind: node

Detect objects in a frame (bounding box + class + score)

## Ports

| id | direction | type | description |
|---|---|---|---|
| execute | inlet | core:type:EXEC | Signal for controlling execution flow between nodes |
| frame | inlet | visiongraph:type:RGB_FRAME | 3-channel uint8 colour video frame |
| model | config | builtin:type:STRING | Text data |
| min_score | config | builtin:type:FLOAT | Decimal numberer |
| status | config | builtin:type:STRING | Text data |
| result_ready | outlet | core:type:EXEC | Signal for controlling execution flow between nodes |
| result | outlet | visiongraph:type:DETECTION_RESULT | Object detections: bounding box, class, score (and tracking id) |
| count | outlet | builtin:type:INT | Whole number |

## Notes

Object detection family node — outlets ``DETECTION_RESULT``.
