# Segmentation

`haybale-visiongraph:node:SegmentationNode` · kind: node

Instance segmentation: detect objects and their pixel masks

## Ports

| id | direction | type | description |
|---|---|---|---|
| `execute` | inlet | `haywire-core:type:EXEC` | Signal for controlling execution flow between nodes |
| `frame` | inlet | `haybale-image:type:IMAGE_RGB` | A three-channel picture. |
| `model` | inlet | `haybale-models:type:MODEL_REF` | Which backend + weights to run. Changing this reloads the model. |
| `status` | config | `haywire-core:type:STRING` | Text data |
| `inference.min_score` | config | `haywire-core:type:FLOAT` | Minimum confidence. Applied natively by the estimator, so it can go BELOW the backend's own default. MediaPipe consumes this when the model is built, so changing it there reloads the model. |
| `result_ready` | outlet | `haywire-core:type:EXEC` | Signal for controlling execution flow between nodes |
| `result` | outlet | `haybale-visiongraph:type:SEGMENTATION_RESULT` | Instance segmentation: detection plus a per-instance mask |
| `count` | outlet | `haywire-core:type:INT` | Whole number |

## Settings

| name | bag | default | description |
|---|---|---|---|
| `min_score` | inference | `0.3` | Minimum confidence. Applied natively by the estimator, so it can go BELOW the backend's own default. MediaPipe consumes this when the model is built, so changing it there reloads the model. |
| `color` | overlay | `''` | Colour the Annotate node draws these results in. Empty keeps visiongraph's automatic per-tracking-id palette. Segmentation masks ignore this. |
| `enabled` | nms | `True` | Suppress overlapping detections. |
| `score_threshold` | nms | `0.3` | Confidence floor used INSIDE non-maximum suppression. Distinct from Min Score. |
| `nms_threshold` | nms | `0.3` | Overlap above which the lower-scoring box is dropped. |
| `eta` | nms | `None` | Adaptive NMS threshold coefficient. None disables it. |
| `top_k` | nms | `None` | Keep at most this many detections. None disables it. |
| `batch_mode` | nms | `'Auto'` | How NMS is applied across classes. |
| `mask_threshold` | segmentation | `0.5` | Probability above which a pixel is part of the mask. |
| `device` | openvino | `'AUTO'` | OpenVINO device. Applied when the model is built — changing it reloads. |

## Notes

Instance-segmentation family node — outlets ``SEGMENTATION_RESULT``.
