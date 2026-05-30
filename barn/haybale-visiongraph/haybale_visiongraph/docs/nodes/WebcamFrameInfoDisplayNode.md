<!-- source: haybale_visiongraph/nodes/frame_info_display_node.py | sha256: 399c6177f003 -->

# Webcam Frame Info Display (`WebcamFrameInfoDisplayNode`)

Category: vision/info | Type: CONTROL | Library: visiongraph

Displays webcam frame information and live preview.

Shows frame metadata and streams the video to an embedded viewer.

## Ports

| Direction | Name | Type | Default | Description |
|-----------|------|------|---------|-------------|
| inlet | execute | EXEC | | Control flow in — triggers frame analysis |
| inlet | frame | FRAME | | Frame to display (shown in embedded video viewer) |
| config | info_display | STRING | No frame yet | Live label showing frame dimensions, timestamp, and FPS (read-only) |
| outlet | frame_ready | EXEC | | Control flow out after analysis completes |
| outlet | frame_pass | FRAME | | Frame passed through unchanged |
| outlet | timestamp | FLOAT | | Time in seconds since stream start |
| outlet | frame_number | INT | | Sequential frame counter |
| outlet | width | INT | | Frame width in pixels |
| outlet | height | INT | | Frame height in pixels |
