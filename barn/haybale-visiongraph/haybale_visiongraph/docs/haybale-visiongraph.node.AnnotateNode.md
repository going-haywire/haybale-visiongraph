# Annotate Results

`haybale-visiongraph:node:AnnotateNode` · kind: node

Draw estimator results (boxes / masks / poses) onto a frame

## Ports

| id | direction | type | description |
|---|---|---|---|
| execute | inlet | haybale-core:type:EXEC | Signal for controlling execution flow between nodes |
| result | inlet | haybale-core:type:PooledType | Connect one or more estimator result outlets |
| frame | inlet | haybale-visiongraph:type:RGB_FRAME | 3-channel uint8 colour video frame |
| min_score | config | haywire-core:type:FLOAT | Decimal numberer |
| show_info | config | haywire-core:type:BOOL | True or False |
| frame_ready | outlet | haybale-core:type:EXEC | Signal for controlling execution flow between nodes |
| annotated | outlet | haybale-visiongraph:type:RGB_FRAME | 3-channel uint8 colour video frame |

## Settings

| name | bag | default | description |
|---|---|---|---|
| show_bounding_box | style | False | Draw the bounding box for landmark/pose results |
| marker_size | style | 3 | Landmark marker radius in pixels |
| stroke_width | style | 2 | Line width for boxes and skeleton connections |

## Notes

Overlay pooled vision results onto a frame.

Inputs:
    execute: Control flow in.
    result: Pooled result lists (any mix of VISION_RESULT subtypes).
    frame: The image to draw on (RGB_FRAME).
    min_score: Hide results / landmarks below this confidence.
    show_info: Draw labels / info text.

Outputs:
    frame_ready: Control flow out.
    frame: The annotated frame (a copy; inputs are not mutated).
