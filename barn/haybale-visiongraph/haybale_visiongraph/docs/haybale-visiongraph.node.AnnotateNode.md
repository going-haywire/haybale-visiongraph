# Annotate Results

`haybale-visiongraph:node:AnnotateNode` · kind: node

Draw estimator results (boxes / masks / poses) onto a frame

## Ports

| id | direction | type | description |
|---|---|---|---|
| execute | inlet | haybale-core:type:EXEC | Signal for controlling execution flow between nodes |
| result | inlet | haybale-core:type:PooledType | Connect one or more estimator result outlets |
| frame | inlet | haybale-visiongraph:type:RGB_FRAME | 3-channel uint8 colour video frame |
| style.min_score | config | haywire-core:type:FLOAT | Hide results and landmarks below this confidence. |
| style.show_info | config | haywire-core:type:BOOL | Draw the label / info text next to each result. |
| frame_ready | outlet | haybale-core:type:EXEC | Signal for controlling execution flow between nodes |
| annotated | outlet | haybale-visiongraph:type:RGB_FRAME | 3-channel uint8 colour video frame |

## Settings

| name | bag | default | description |
|---|---|---|---|
| min_score | style | 0.0 | Hide results and landmarks below this confidence. |
| show_info | style | True | Draw the label / info text next to each result. |
| show_bounding_box | style | None | Draw bounding boxes. None keeps each result type's own default (off for landmark/pose, on for segmentation). |
| marker_size | style | 3 | Landmark marker radius in pixels |
| stroke_width | style | 2 | Line width for boxes and skeleton connections |
| use_class_color | style | True | Segmentation only: colour each mask by its class instead of by tracking id. Ignored by every other result type. |

## Notes

Overlay pooled vision results onto a frame.

Inputs:
    execute: Control flow in.
    result: Pooled result lists (any mix of VISION_RESULT subtypes).
    frame: The image to draw on (RGB_FRAME).

Settings (``style``):
    min_score / show_info: seeded to config ports — the node's default face.
    show_bounding_box / marker_size / stroke_width / use_class_color:
        panel-only; promote from the Setting-row menu if you reach for one.

Outputs:
    frame_ready: Control flow out.
    frame: The annotated frame (a copy; inputs are not mutated).
