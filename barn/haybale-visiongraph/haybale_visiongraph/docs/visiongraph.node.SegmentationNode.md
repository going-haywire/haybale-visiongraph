# Segmentation

`visiongraph:node:SegmentationNode` · kind: node

Instance segmentation: detect objects and their pixel masks

## Ports

| id | direction | type | description |
|---|---|---|---|
| execute | inlet | core:type:EXEC | Signal for controlling execution flow between nodes |
| frame | inlet | visiongraph:type:RGB_FRAME | 3-channel uint8 colour video frame |
| model | config | builtin:type:STRING | Text data |
| min_score | config | builtin:type:FLOAT | Decimal numberer |
| status | config | builtin:type:STRING | Text data |
| result_ready | outlet | core:type:EXEC | Signal for controlling execution flow between nodes |
| result | outlet | visiongraph:type:SEGMENTATION_RESULT | Instance segmentation: detection plus a per-instance mask |
| count | outlet | builtin:type:INT | Whole number |

## Notes

Instance-segmentation family node — outlets ``SEGMENTATION_RESULT``.
