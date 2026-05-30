# OpenCV Viewer Widget - Usage Guide

## Overview

The `OpencvViewerWidget` provides efficient streaming video display for numpy arrays within Haywire nodes. It uses the duit library's `OpencvViewer` component for MJPEG streaming.

## Features

- **Efficient Streaming**: MJPEG encoding for low-latency video display
- **Automatic Updates**: Streams new frames automatically when port value changes
- **Configurable Quality**: Adjustable JPEG compression (0-100)
- **Flexible Sizing**: CSS-based width/height configuration
- **Low Overhead**: Minimal frame buffering (default: 1 frame)
- **Thread-Safe**: Handles async updates from capture threads

## Basic Usage

### In a Node Definition

```python
from haybale_visiongraph.types.frame_type import FRAME
from haybale_visiongraph.widgets.opencv_viewer_widget import OpencvViewerWidget

def init(self):
    # Add a FRAME inlet with the viewer widget
    self.add(FRAME.as_inlet(
        'frame',
        label='Video Preview',
        widget=OpencvViewerWidget.config(properties={
            'quality': 85,           # JPEG quality (0-100)
            'width': '100%',         # CSS width
            'height': '300px',       # CSS height
        })
    ))
```

### Configuration Options

| Property | Type | Default | Description |
|----------|------|---------|-------------|
| `quality` | int | 80 | JPEG compression quality (0-100, higher = better quality) |
| `width` | str | '100%' | CSS width (e.g., '100%', '640px', 'auto') |
| `height` | str | 'auto' | CSS height (e.g., '480px', 'auto', '50vh') |
| `frame_queue_size` | int | 1 | Number of frames to buffer |
| `block_on_full` | bool | False | Block when queue is full (True) or drop oldest frame (False) |

## Advanced Configuration

### High Quality Display

```python
self.add(FRAME.as_inlet(
    'preview',
    label='High Quality Preview',
    widget=OpencvViewerWidget.config(properties={
        'quality': 95,
        'width': '1280px',
        'height': '720px',
    })
))
```

### Low Latency Configuration

```python
self.add(FRAME.as_inlet(
    'preview',
    label='Low Latency Preview',
    widget=OpencvViewerWidget.config(properties={
        'quality': 70,
        'frame_queue_size': 1,
        'block_on_full': False,  # Drop frames to reduce latency
    })
))
```

### Responsive Sizing

```python
self.add(FRAME.as_inlet(
    'preview',
    label='Responsive Preview',
    widget=OpencvViewerWidget.config(properties={
        'quality': 80,
        'width': '100%',
        'height': '50vh',  # 50% of viewport height
    })
))
```

### Buffered Display

```python
self.add(FRAME.as_inlet(
    'preview',
    label='Buffered Preview',
    widget=OpencvViewerWidget.config(properties={
        'quality': 80,
        'frame_queue_size': 5,  # Buffer up to 5 frames
        'block_on_full': True,  # Wait if buffer is full
    })
))
```

## How It Works

### Data Flow

```
Node Worker
    ↓ (sets port value)
DataPort._data.on_changed
    ↓ (triggers callback)
OpencvViewerWidget._sync_frame_to_viewer()
    ↓ (extracts numpy array)
OpencvViewer.stream(frame)
    ↓ (encodes to JPEG)
MJPEG HTTP endpoint
    ↓ (streams to browser)
Browser displays video
```

### Frame Updates

1. **Worker sets value**: `self.out('frame', frame_obj)`
2. **Port triggers change**: DataPort fires `on_changed` event
3. **Widget receives callback**: `_sync_frame_to_viewer()` is called
4. **Extract array**: Gets `frame.data` from FRAME object
5. **Stream to viewer**: `opencv_viewer.stream(frame_data)`
6. **Encode & send**: JPEG encoding and HTTP streaming happen automatically

### Thread Safety

- The widget's callback runs in the main NiceGUI event loop
- The `OpencvViewer` component handles async streaming internally
- Frame updates are automatically queued and processed

## Example Node: Frame Display

```python
from haywire.core.node.decorator import node
from haywire.core.node.base import BaseNode
from haywire.core.execution.execution_context import ExecutionContext

@node(
    label='Frame Display',
    description='Displays video frames with metadata',
    menu='vision/display',
)
class FrameDisplayNode(BaseNode):
    
    def init(self):
        from haybale_core.types import EXEC
        from haybale_visiongraph.types.frame_type import FRAME
        from haybale_visiongraph.widgets.opencv_viewer_widget import OpencvViewerWidget
        
        # Control input
        self.add(EXEC.as_inlet('execute', label='Execute'))
        
        # Frame input with viewer
        self.add(FRAME.as_inlet(
            'frame',
            label='Video Stream',
            widget=OpencvViewerWidget.config(properties={
                'quality': 85,
                'width': '100%',
                'height': '400px'
            })
        ))
        
        # Control output
        self.add(EXEC.as_outlet('done', label='Done'))
    
    def worker(self, context: ExecutionContext, frame) -> str:
        # The frame is automatically displayed by the widget
        # Just pass through
        return 'done'
```

## Complete Flow Example

### Node Graph

```
[Begin Play] → [Start Webcam Stream]
                       ↓ (callbacks)
                [Webcam Frame Event] → [Frame Display Node]
                                             ↓ (with viewer)
                                       [Your Processing]
```

### Configuration

**Start Webcam Stream:**
- Camera Index: 0
- Resolution: 1280x720
- FPS: 30
- Callback Name: "webcam_frame"

**Webcam Frame Event:**
- Callback Name: "webcam_frame"

**Frame Display Node:**
- Frame inlet: Uses `OpencvViewerWidget` (quality: 85, 400px height)

## Performance Considerations

### Quality vs Performance

| Quality | Use Case | Frame Size (720p) | CPU Load |
|---------|----------|-------------------|----------|
| 60 | Low latency preview | ~20-30 KB | Low |
| 80 | **Balanced (recommended)** | ~50-70 KB | Medium |
| 95 | High quality display | ~150-200 KB | High |

### Frame Rate Impact

- **30 FPS stream**: ~2.1 MB/s @ quality 80
- **60 FPS stream**: ~4.2 MB/s @ quality 80
- Consider using frame skip in capture node for high FPS

### Buffering Strategy

**`frame_queue_size = 1` (default):**
- ✅ Lowest latency
- ✅ Minimal memory
- ⚠️ May drop frames under heavy load

**`frame_queue_size = 5`:**
- ✅ Smoother playback
- ✅ Handles temporary slowdowns
- ⚠️ Increased latency
- ⚠️ More memory usage

**`block_on_full = False` (default):**
- ✅ Never blocks the capture thread
- ⚠️ Drops oldest frame when full

**`block_on_full = True`:**
- ✅ Preserves all frames
- ⚠️ Can slow down capture thread

## Troubleshooting

### Issue: No video appears

**Check:**
- Is the frame data actually being set? Add debug print in worker
- Is the FRAME object valid? Check `frame.is_valid()`
- Is the numpy array empty? Check `frame.data.size > 0`

### Issue: Delayed/laggy video

**Solutions:**
- Lower quality setting (e.g., 70 instead of 85)
- Reduce frame rate in capture node
- Use `frame_queue_size = 1` with `block_on_full = False`
- Lower resolution in capture node

### Issue: High CPU usage

**Solutions:**
- Lower quality setting
- Increase frame skip in capture node
- Reduce resolution

### Issue: Widget not updating

**Check:**
- Is the port value being set correctly? `self.out('frame', frame_obj)`
- Is the widget properly configured in `init()`?
- Check console for errors

## Technical Details

### Widget Lifecycle

1. **Initialization**: `__init__(port)` - Store port reference
2. **Render**: `render()` - Create OpencvViewer, setup bindings
3. **Updates**: Port changes → `_sync_frame_to_viewer()` → stream frame
4. **Cleanup**: `cleanup()` - Unsubscribe from port events

### Data Types Supported

The widget handles both:
- **FRAME objects**: Extracts `frame.data` attribute
- **Raw numpy arrays**: Uses directly

This flexibility allows it to work with different data sources.

### MJPEG Endpoint

Each widget instance creates a unique HTTP endpoint:
- Format: `/stream/{random_id}`
- Protocol: `multipart/x-mixed-replace`
- Encoding: JPEG per frame
- Browser auto-connects and displays

## Integration with Other Libraries

### Compatible with OpenCV

```python
import cv2

# Apply OpenCV processing before display
gray = cv2.cvtColor(frame.data, cv2.COLOR_BGR2GRAY)
edges = cv2.Canny(gray, 100, 200)

# Convert back to 3-channel for display
edges_color = cv2.cvtColor(edges, cv2.COLOR_GRAY2BGR)

# Create new FRAME for display
display_frame = FRAME(data=edges_color, timestamp=frame.timestamp)
self.out('preview', display_frame)
```

### Multiple Viewers in One Node

```python
def init(self):
    # Original stream
    self.add(FRAME.as_inlet(
        'input',
        label='Input Stream',
        widget=OpencvViewerWidget.config(properties={'height': '300px'})
    ))
    
    # Processed output
    self.add(FRAME.as_outlet(
        'output',
        label='Processed Output',
        widget=OpencvViewerWidget.config(properties={'height': '300px'})
    ))
```

## Best Practices

1. **Use appropriate quality**: 80-85 for most cases
2. **Set explicit dimensions**: Prevents layout shifts
3. **Monitor performance**: Watch CPU/memory usage
4. **Handle errors gracefully**: Widget fails silently to avoid crashes
5. **Clean up resources**: Widget cleanup is automatic via port lifecycle
6. **Test with real streams**: Verify performance under load