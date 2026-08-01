# Depth Frame

`visiongraph:type:DEPTH_FRAME` · kind: type

Single-channel uint16 metric depth buffer (millimetres)

## Details

- **flow_type**: `data`
- **default**: `{'data': None, 'timestamp': 0.0, 'frame_number': 0}`
- **color**: `#00838f`

## Notes

Single-channel uint16 metric depth buffer (H, W), each pixel = millimetres.

Its own datatype precisely so it cannot be silently wired into colour-image
nodes. Colourizing to a viewable image is an explicit node, never an adapter.
