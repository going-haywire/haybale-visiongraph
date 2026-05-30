<!-- source: haybale_visiongraph/nodes/start_web_cam_stream_node.py | sha256: a33ea5e09397 -->

# Start Webcam Stream (`StartWebcamStreamNode`)

Category: vision/input | Type: CONTROL | Library: visiongraph

Starts a webcam video stream that runs in a separate thread.
Emits callbacks on each frame for downstream event nodes to process.

## Ports

| Direction | Name | Type | Default | Description |
|-----------|------|------|---------|-------------|
| inlet | start | EXEC | | Begin capturing from webcam |
| inlet | stop | EXEC | | Stop the capture stream |
| config | camera_index | INT | 0 | Camera index (0 = default camera) |
| config | width | INT | 0 | Desired frame width in pixels (0 = camera default) |
| config | height | INT | 0 | Desired frame height in pixels (0 = camera default) |
| config | fps | INT | 0 | Desired frames per second (0 = camera default) |
| config | frame_skip | INT | 1 | Emit callback every N frames (1 = every frame) |
| inlet | callback_names | CALLBACK (pooled) | | Callback targets to invoke per captured frame |
| config | status | STRING | Idle | Live status display (read-only) |
| outlet | started | EXEC | | Triggered when the stream starts successfully |
| outlet | stopped | EXEC | | Triggered when the stream stops |
