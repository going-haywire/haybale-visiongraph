# Multiframe Callback

`haybale-visiongraph:type:MULTIFRAME_CALLBACK` · kind: type

Subscription for multi-frame streams

## Details

- **flow_type**: `callback`
- **default**: `{'name': '', 'rgb': False, 'depth': False, 'ir': False}`
- **color**: `#ff3c00`

## Notes

Subscription value: callback name + which streams the subscriber requires.

Attributes:
    name: Callback event name used for dispatch routing.
    rgb: Subscriber wants the colour stream.
    depth: Subscriber wants the depth stream.
    ir: Subscriber wants the infrared stream.
