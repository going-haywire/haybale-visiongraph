# GrayToRgbAdapter

`visiongraph:adapter:GrayToRgbAdapter` · kind: adapter

Replicate a single-channel grey frame to a 3-channel colour frame

## Details

- **converts_from**: `visiongraph:type:GRAY_FRAME`
- **converts_to**: `visiongraph:type:RGB_FRAME`
- **priority**: `0`

## Notes

GRAY_FRAME -> RGB_FRAME by replicating the single channel across BGR.
