# Tracker

`haybale-visiongraph:node:TrackerNode` · kind: node

Assign stable tracking ids to detections across frames

## Ports

| id | direction | type | description |
|---|---|---|---|
| execute | inlet | haybale-core:type:EXEC | Signal for controlling execution flow between nodes |
| result | inlet | haybale-visiongraph:type:DETECTION_RESULT | Object detections: bounding box, class, score (and tracking id) |
| backend | config | haywire-core:type:STRING | Text data |
| result_type | config | haywire-core:type:STRING | Text data |
| status | config | haywire-core:type:STRING | Text data |
| tracked_ready | outlet | haybale-core:type:EXEC | Signal for controlling execution flow between nodes |
| tracked | outlet | haybale-visiongraph:type:DETECTION_RESULT | Object detections: bounding box, class, score (and tracking id) |

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
