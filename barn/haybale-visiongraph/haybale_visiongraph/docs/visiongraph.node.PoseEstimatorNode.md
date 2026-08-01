# Pose Estimator

`visiongraph:node:PoseEstimatorNode` · kind: node

Estimate human body pose (named joints + skeleton) per person

## Ports

| id | direction | type | description |
|---|---|---|---|
| execute | inlet | core:type:EXEC | Signal for controlling execution flow between nodes |
| frame | inlet | visiongraph:type:RGB_FRAME | 3-channel uint8 colour video frame |
| model | config | builtin:type:STRING | Text data |
| min_score | config | builtin:type:FLOAT | Decimal numberer |
| status | config | builtin:type:STRING | Text data |
| result_ready | outlet | core:type:EXEC | Signal for controlling execution flow between nodes |
| result | outlet | visiongraph:type:POSE_RESULT | Human pose: landmarks with named joints and skeleton connections |
| count | outlet | builtin:type:INT | Whole number |

## Notes

Human-pose family node — outlets ``POSE_RESULT``.
