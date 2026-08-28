# Object Detector

`haybale-visiongraph:node:ObjectDetectorNode` · kind: node

Detect objects in a frame (bounding box + class + score)

## Ports

| id | direction | type | description |
|---|---|---|---|
| execute | inlet | haybale-core:type:EXEC | Signal for controlling execution flow between nodes |
| frame | inlet | haybale-visiongraph:type:RGB_FRAME | 3-channel uint8 colour video frame |
| model | config | haywire-core:type:STRING | Text data |
| min_score | config | haywire-core:type:FLOAT | Decimal numberer |
| status | config | haywire-core:type:STRING | Text data |
| result_ready | outlet | haybale-core:type:EXEC | Signal for controlling execution flow between nodes |
| result | outlet | haybale-visiongraph:type:DETECTION_RESULT | Object detections: bounding box, class, score (and tracking id) |
| count | outlet | haywire-core:type:INT | Whole number |

## Notes

Object detection family node — outlets ``DETECTION_RESULT``.
