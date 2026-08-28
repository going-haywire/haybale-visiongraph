# Detection Result

`haybale-visiongraph:type:DETECTION_RESULT` · kind: type

Object detections: bounding box, class, score (and tracking id)

## Details

- **flow_type**: `data`
- **default**: `{'results': []}`
- **color**: `#f57c00`

## Notes

``ResultList[ObjectDetectionResult]`` — each result carries a bounding box,
class id/name, confidence score, and a (post-tracking) tracking id.
