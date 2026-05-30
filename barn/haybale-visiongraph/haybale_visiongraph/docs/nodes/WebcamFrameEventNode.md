<!-- source: haybale_visiongraph/nodes/webcam_frame_event_node.py | sha256: 4fbd21d14bc8 -->

# Webcam Frame Event (`WebcamFrameEventNode`)

Category: event/vision | Type: EVENT | Library: visiongraph

Event node that receives webcam frame callbacks.
Provides the frame data and metadata for processing.

## Ports

| Direction | Name | Type | Default | Description |
|-----------|------|------|---------|-------------|
| outlet | callback_name | CALLBACK | {node_id} | Callback name this event node listens on |
| outlet | frame_ready | EXEC | | Triggered when a frame arrives |
| outlet | frame | FRAME | | Frame object with numpy data and metadata |
| outlet | timestamp | FLOAT | | Time in seconds since stream start |
| outlet | frame_number | INT | | Sequential frame counter |
| outlet | width | INT | | Frame width in pixels |
| outlet | height | INT | | Frame height in pixels |
