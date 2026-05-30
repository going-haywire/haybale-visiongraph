<!-- source: haybale_visiongraph/widgets/opencv_viewer_widget.py | sha256: f0d85f18f39b -->

# OpencvViewerWidget (`OpencvViewerWidget`)

Library: visiongraph | Compatible types: visiongraph:type:frame

Widget for displaying numpy arrays as streaming video.

Uses a custom StreamingViewer component for efficient MJPEG streaming.
Automatically streams frame updates when the port value changes.

Config options:

| Property | Type | Default | Description |
|----------|------|---------|-------------|
| quality | int | 80 | JPEG compression quality (0–100) |
| width | str | '100%' | CSS width of the viewer |
| height | str | 'auto' | CSS height of the viewer |
| frame_queue_size | int | 1 | Internal frame buffer size |
| block_on_full | bool | False | Block the producer when the queue is full |

```python
OpencvViewerWidget.config(properties={
    'quality': 80,
    'width': '100%',
    'height': '300px'
})
```
