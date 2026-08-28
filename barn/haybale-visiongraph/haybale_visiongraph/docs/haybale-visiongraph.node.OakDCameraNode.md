# OAK-D Camera

`haybale-visiongraph:node:OakDCameraNode` · kind: node

Opens an OAK-D depth camera and emits colour/depth/infrared frame callbacks

## Ports

| id | direction | type | description |
|---|---|---|---|
| start | inlet | haybale-core:type:EXEC | Signal for controlling execution flow between nodes |
| stop | inlet | haybale-core:type:EXEC | Signal for controlling execution flow between nodes |
| callbacks | inlet | haybale-core:type:PooledType | Connect to a Frame Event node |
| status | config | haywire-core:type:STRING | Text data |
| haybale-visiongraph.node.OakDCameraNode.device.mxid | config | haywire-core:type:STRING | Leave empty to auto-select the first available OAK device. |
| started | outlet | haybale-core:type:EXEC | Signal for controlling execution flow between nodes |
| stopped | outlet | haybale-core:type:EXEC | Signal for controlling execution flow between nodes |

## Settings

| name | bag | default | description |
|---|---|---|---|
| mxid | device | '' | Leave empty to auto-select the first available OAK device. |
| want_rgb | stream_flags | False | Set by connected subscribers. Not user-editable. |
| want_depth | stream_flags | False | Set by connected subscribers. Not user-editable. |
| want_ir | stream_flags | False | Set by connected subscribers. Not user-editable. |
| enable_auto_exposure | color | True | Enables or disables auto exposure. Inert if Color is off. |
| exposure | color | 20000 | Manual exposure time. Only applied while Auto Exposure is off. Inert if Color is off. |
| iso | color | 800 | Sensor ISO sensitivity. Inert if Color is off. |
| auto_exposure_compensation | color | 0 | Bias applied to auto exposure, in the range [-9, 9]. Inert if Color is off. |
| enable_auto_white_balance | color | True | Enables or disables auto white balance. Inert if Color is off. |
| white_balance | color | 4000 | Manual white balance in Kelvin. Only applied while Auto White Balance is off. Inert if Color is off. |
| auto_white_balance_mode | color | 'AUTO' | Auto white balance scene preset (e.g. Daylight, Fluorescent). Inert if Color is off. |
| auto_focus | color | True | Enables or disables auto focus. Inert if Color is off. |
| focus_distance | color | 0 | Manual focus position. Only applied while Auto Focus is off. Inert if Color is off. |
| brightness | color | 0 | Image brightness, in the range [-10, 10]. Inert if Color is off. |
| contrast | color | 0 | Image contrast, in the range [-10, 10]. Inert if Color is off. |
| saturation | color | 0 | Image saturation, in the range [-10, 10]. Inert if Color is off. |
| sharpness | color | 0 | Image sharpness, in the range [0, 4]. Inert if Color is off. |
| luma_denoise | color | 0 | Luminance noise reduction, in the range [0, 4]. Inert if Color is off. |
| chroma_denoise | color | 0 | Chrominance (color) noise reduction, in the range [0, 4]. Inert if Color is off. |
| anti_banding_mode | color | 'AUTO' | Reduces flicker banding from artificial lighting. Inert if Color is off. |
| effect_mode | color | 'OFF' | Built-in color effect (e.g. Mono, Sepia, Negative). Inert if Color is off. |
| laser_intensity | ir | 0.0 | Sets intensity of laser dot projector |
| flood_intensity | ir | 0.0 | Sets intensity of the IR flood light |
| preset_mode | depth | 'HIGH_DENSITY' | Stereo depth quality/speed preset. Requires a device restart to apply. |
| median_filter | depth | 'KERNEL_7x7' | Disparity smoothing kernel. Requires a device restart to apply. |
| left_right_check | depth | True | Better handling of occlusions. Requires a device restart to apply. |
| subpixel | depth | False | Fractional disparity for longer-range accuracy. Restart required. |
| extended_disparity | depth | False | Closer-in minimum depth, doubled disparity range. Restart required. |
| frame_alignment | depth | 'Color' | Align the depth map to Color, Infrared, or leave Disabled. Restart required. |

## Notes

Starts an OAK-D capture stream in a separate thread and emits one callback
per frame carrying every active stream.

Inputs:
    start: Open the device and begin capturing.
    stop: Stop capturing and close the device.
    callbacks: Pooled MULTIFRAME_CALLBACK subscriptions from event nodes.

Outputs:
    started: Triggered when the device opens successfully.
    stopped: Triggered when capture stops.

Settings:
    device: Device MXID / name (empty = first available). Panel-only —
        its dropdown resolves options via a live callable, which is only
        safe on a setting() field (see `device.mxid` for why).
    depth: Pipeline-construction params (read once at setup(), immutable
        while running). Panel-only — not promotable to a port.
    ir: Live IR laser/flood intensity. Promotable to an inlet — pushed
        straight to the running device.
    color: Live color-sensor controls (exposure/WB/focus/tuning).
        Promotable to an inlet. Inert while enable_color is False (no
        color control queue exists on the device in that case).
    stream_flags: Read-only display of the requirement union gathered
        from pooled subscribers (hb_gather_requirements). Not
        user-editable, never promotable — set only via the callback edge.
