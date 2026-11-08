# Callback Multiframe

`haybale-visiongraph:type:CALLBACK_MULTIFRAME` · kind: type

Subscription for multi-frame streams

## Details

- **wire_type**: `haywire-core:wire:CallbackWire`
- **color**: `#ff3c00`

## Notes

Subscription value: callback name + which streams the subscriber requires.

Attributes:
    name: Callback event name used for dispatch routing.
    rgb: Subscriber wants the colour stream.
    depth: Subscriber wants the depth stream.
    ir: Subscriber wants the infrared stream.
