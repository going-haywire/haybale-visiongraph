# Segmentation

`haybale-visiongraph:node:SegmentationNode` · kind: node

Instance segmentation: detect objects and their pixel masks

## Ports

| id | direction | type | description |
|---|---|---|---|
| execute | inlet | haybale-core:type:EXEC | Signal for controlling execution flow between nodes |
| frame | inlet | haybale-visiongraph:type:RGB_FRAME | 3-channel uint8 colour video frame |
| model | config | haywire-core:type:STRING | Text data |
| min_score | config | haywire-core:type:FLOAT | Decimal numberer |
| status | config | haywire-core:type:STRING | Text data |
| result_ready | outlet | haybale-core:type:EXEC | Signal for controlling execution flow between nodes |
| result | outlet | haybale-visiongraph:type:SEGMENTATION_RESULT | Instance segmentation: detection plus a per-instance mask |
| count | outlet | haywire-core:type:INT | Whole number |

## Notes

Instance-segmentation family node — outlets ``SEGMENTATION_RESULT``.
