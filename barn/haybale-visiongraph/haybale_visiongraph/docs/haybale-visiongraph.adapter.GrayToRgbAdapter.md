# GrayToRgbAdapter

`haybale-visiongraph:adapter:GrayToRgbAdapter` · kind: adapter

Replicate a single-channel grey frame to a 3-channel colour frame

## Details

- **converts_from**: `haybale-visiongraph:type:GRAY_FRAME`
- **converts_to**: `haybale-visiongraph:type:RGB_FRAME`
- **priority**: `0`

## Notes

GRAY_FRAME -> RGB_FRAME by replicating the single channel across BGR.
