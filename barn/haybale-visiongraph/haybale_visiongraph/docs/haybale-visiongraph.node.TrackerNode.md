# Tracker

`haybale-visiongraph:node:TrackerNode` · kind: node

Assign stable tracking ids to detections across frames

## Ports

| id | direction | type | description |
|---|---|---|---|
| execute | inlet | haybale-core:type:EXEC | Signal for controlling execution flow between nodes |
| result | inlet | haybale-visiongraph:type:DETECTION_RESULT | Object detections: bounding box, class, score (and tracking id) |
| status | config | haywire-core:type:STRING | Text data |
| choice.backend | config | haywire-core:type:CHOICES | Which tracker implementation to use. Changing this rebuilds the tracker. |
| choice.result_type | config | haywire-core:type:CHOICES | Which result subtype the inlet and outlet carry. Changing this retypes both ports. |
| tracked_ready | outlet | haybale-core:type:EXEC | Signal for controlling execution flow between nodes |
| tracked | outlet | haybale-visiongraph:type:DETECTION_RESULT | Object detections: bounding box, class, score (and tracking id) |

## Settings

| name | bag | default | description |
|---|---|---|---|
| backend | choice | 'Flate' | Which tracker implementation to use. Changing this rebuilds the tracker. |
| result_type | choice | 'Detection' | Which result subtype the inlet and outlet carry. Changing this retypes both ports. |
| max_cost | flate | 0.5 | Largest distance still accepted as a match. |
| min_alive | flate | 0 | Frames a track must survive before it is reported. |
| max_lost | flate | 5 | Frames a track may go unseen before it is dropped. |
| include_stale | flate | False | Also report tracks that were not matched this frame. |
| class_aware | flate | False | Only match detections of the same class. |
| delta_time | motpy | 0.1 | Kalman filter time step. Applied when the tracker is built. |
| min_iou | motpy | 0.1 | Smallest overlap accepted as a match. Applied when the tracker is built. |
| multi_match_min_iou | motpy | 1.0 | Above 1.0 disables multi-matching. Applied when the tracker is built. |
| min_steps_alive | motpy | -1 | Steps before a track is reported. None leaves it to motpy. |
| max_staleness_to_positive_ratio | motpy | 3.0 | Applied when the tracker is built. |
| max_staleness | motpy | 12.0 | Applied when the tracker is built. |
| use_predicted_bounding_box | motpy | False | Report the Kalman prediction rather than the detection. |
| enabled | centroid | True | When off, detections pass through untracked. |
| max_lost | centroid | 0 | Frames a track may go unseen. Applied when the tracker is built. |

## Notes

Frame-to-frame tracker.

Inputs:
    execute: Control flow in (pulse per frame).
    result: The result list to track (typed by ``result_type``).
    backend: Which tracker implementation to use.
    result_type: Which result subtype the inlet/outlet carry.

Outputs:
    tracked_ready: Control flow out.
    tracked: The same results, stamped with tracking ids (typed by ``result_type``).
