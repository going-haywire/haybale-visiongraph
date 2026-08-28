# Pose Estimator

`haybale-visiongraph:node:PoseEstimatorNode` · kind: node

Estimate human body pose (named joints + skeleton) per person

## Ports

| id | direction | type | description |
|---|---|---|---|
| execute | inlet | haybale-core:type:EXEC | Signal for controlling execution flow between nodes |
| frame | inlet | haybale-visiongraph:type:RGB_FRAME | 3-channel uint8 colour video frame |
| model | config | haywire-core:type:STRING | Text data |
| min_score | config | haywire-core:type:FLOAT | Decimal numberer |
| status | config | haywire-core:type:STRING | Text data |
| result_ready | outlet | haybale-core:type:EXEC | Signal for controlling execution flow between nodes |
| result | outlet | haybale-visiongraph:type:POSE_RESULT | Human pose: landmarks with named joints and skeleton connections |
| count | outlet | haywire-core:type:INT | Whole number |

## Notes

Human-pose family node — outlets ``POSE_RESULT``.
