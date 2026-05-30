# Streaming Widget Architecture - Complete Explanation

## Overview

The streaming video widget uses a **producer-consumer pattern** with **MJPEG HTTP streaming** to display numpy arrays as live video in the browser.

## Component Hierarchy

```
OpencvViewerWidget (IWidget)
    ↓ creates
StreamingViewer (NiceGUI Element)
    ↓ renders to
opencv_viewer.js (Vue Component)
    ↓ displays
<img src="/stream/ENDPOINT_ID"> (Browser)
```

---

## Part 1: The StreamingViewer Component

### Initialization (`__init__`)

```python
def __init__(self, endpoint=None, quality=80, frame_queue_size=1, block_on_full=False):
```

**What happens:**

1. **Generate unique endpoint**:
   ```python
   endpoint_id = uuid.uuid4().hex[:8]  # e.g., "a3f7b2c4"
   endpoint = f"/stream/{endpoint_id}"  # e.g., "/stream/a3f7b2c4"
   ```
   Each widget instance gets its own HTTP endpoint for streaming.

2. **Create shared state for broadcasting**:
   ```python
   self.latest_frame: bytes = None      # Current JPEG frame
   self.frame_id: int = 0               # Counter for frame updates
   self.cond: asyncio.Condition = ...   # Async notification mechanism
   ```
   
   The `Condition` allows the queue reader to notify all connected browser clients when a new frame arrives.

3. **Create thread-safe queue**:
   ```python
   self._thread_queue: Queue[bytes] = Queue(maxsize=1)
   ```
   
   This bridges the gap between:
   - **Producer**: Node worker thread (calls `stream()`)
   - **Consumer**: Async background task (reads from queue)

4. **Register HTTP endpoint**:
   ```python
   self._register_endpoint()
   ```
   Creates a FastAPI route at `/stream/a3f7b2c4` that browsers can connect to.

5. **Start background task**:
   ```python
   self._start_queue_reader()
   ```
   Creates an async task that continuously pulls frames from the queue.

---

### The Queue Reader Background Task

```python
async def _queue_reader_loop(self):
    while self._is_running:
        # Get frame from thread-safe queue
        data = await asyncio.to_thread(self._thread_queue.get, timeout=0.1)
        
        if data:
            # Broadcast to all connected clients
            async with self.cond:
                self.latest_frame = data
                self.frame_id += 1
                self.cond.notify_all()  # Wake up all waiting clients
```

**What it does:**

1. **Pulls from queue**: Uses `asyncio.to_thread()` to run blocking `queue.get()` without blocking the event loop
2. **Updates shared state**: Stores the latest JPEG frame
3. **Increments counter**: `frame_id` acts as a version number
4. **Notifies clients**: `cond.notify_all()` wakes up all browser connections waiting for new frames

**Why a background task?**
- Decouples frame production (from node) from frame consumption (by browsers)
- Allows multiple browser clients to receive the same stream efficiently
- Keeps the async event loop responsive

---

### The Streaming Method (Producer Side)

```python
def stream(self, frame: np.ndarray):
    # Encode to JPEG
    success, buf = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, self.quality])
    data = buf.tobytes()
    
    # Add to queue
    self._thread_queue.put_nowait(data)  # Or drop oldest if full
```

**Data flow:**

```
Node Worker Thread
    ↓ calls
widget.stream(numpy_array)
    ↓ encodes
cv2.imencode() → JPEG bytes
    ↓ queues
thread_queue.put(jpeg_bytes)
    ↓ (crosses thread boundary)
_queue_reader_loop()
    ↓ reads
queue.get() → jpeg_bytes
    ↓ broadcasts
cond.notify_all()
    ↓ (notifies)
All connected browser clients
```

**Key design choices:**

1. **JPEG encoding happens synchronously** in the caller's thread:
   - Pro: Encoding doesn't block the event loop
   - Con: Caller waits for encoding (but it's fast, ~5ms)

2. **Queue size = 1** (default):
   - Pro: Minimal latency (no buffering)
   - Con: Drops frames if consumer is slow
   - Alternative: Larger queue for smoother playback but higher latency

3. **Drop oldest when full**:
   ```python
   try:
       self._thread_queue.put_nowait(data)
   except Full:
       _ = self._thread_queue.get_nowait()  # Drop oldest
       self._thread_queue.put_nowait(data)  # Add new
   ```
   Always shows the most recent frame, never blocks producer.

---

### The HTTP Endpoint (Consumer Side)

```python
@app.get(self.endpoint)
async def mjpeg_endpoint(request: Request):
    boundary = "--frame"
    
    async def generator():
        last_id = 0
        while True:
            # Wait for new frame
            async with self.cond:
                await self.cond.wait_for(lambda: self.frame_id > last_id)
                last_id = self.frame_id
                frame = self.latest_frame
            
            # Yield MJPEG frame
            yield (
                boundary.encode() + b"\r\n"
                b"Content-Type: image/jpeg\r\n"
                b"Content-Length: " + str(len(frame)).encode() + b"\r\n\r\n"
                + frame + b"\r\n"
            )
    
    return StreamingResponse(generator(), media_type="multipart/x-mixed-replace")
```

**How MJPEG streaming works:**

1. **Client connects**: Browser requests `GET /stream/a3f7b2c4`

2. **Server responds with headers**:
   ```
   HTTP/1.1 200 OK
   Content-Type: multipart/x-mixed-replace; boundary=frame
   ```
   
   This tells the browser: "I'm going to send you multiple parts, separated by `--frame`"

3. **Server sends frames continuously**:
   ```
   --frame
   Content-Type: image/jpeg
   Content-Length: 45678
   
   <JPEG binary data>
   
   --frame
   Content-Type: image/jpeg
   Content-Length: 46123
   
   <JPEG binary data>
   
   --frame
   ...
   ```

4. **Browser displays each frame**:
   The `<img>` tag automatically updates as new JPEG data arrives!

**Wait mechanism:**

```python
await self.cond.wait_for(lambda: self.frame_id > last_id)
```

This blocks until `frame_id` increases (meaning a new frame arrived), then immediately yields it. This is **event-driven** rather than polling - very efficient!

**Multiple clients:**

Each browser connection gets its own `generator()` instance, but they all share:
- `self.latest_frame` (the JPEG data)
- `self.cond` (the notification mechanism)

When a new frame arrives, `notify_all()` wakes up ALL waiting generators simultaneously!

---

## Part 2: The OpencvViewerWidget

### Initialization

```python
def __init__(self, port: DataPort):
    self.port = port
    self.streaming_viewer = None
    self._model_changed_callback = None
```

The widget just stores a reference to the port (inlet/outlet) that contains the FRAME data.

---

### Rendering

```python
def render(self):
    # Create container
    with ui.card() as container:
        self.streaming_viewer = StreamingViewer(
            quality=85,
            frame_queue_size=1,
            block_on_full=False
        )
    
    # Setup binding
    self._setup_binding()
    
    # Initial sync
    self._sync_frame_to_viewer()
    
    return container
```

**What happens:**

1. **Creates StreamingViewer**:
   - Generates endpoint `/stream/xyz`
   - Starts background task
   - Registers HTTP route

2. **Creates Vue component**:
   The `StreamingViewer` extends `Element` with `component='opencv_viewer.js'`, which causes NiceGUI to:
   - Load `opencv_viewer.js`
   - Create a Vue component instance
   - Pass `endpoint` prop to it

3. **Sets up data binding**:
   ```python
   self._model_changed_callback = lambda _: self._sync_frame_to_viewer()
   self.port._data.on_changed += self._model_changed_callback
   ```
   
   This subscribes to port changes. Whenever the node calls `self.out('frame', frame_obj)`, the port fires `on_changed`, which triggers `_sync_frame_to_viewer()`.

---

### Data Binding

```python
def _setup_binding(self):
    # Subscribe to port changes
    self._model_changed_callback = lambda _: self._sync_frame_to_viewer()
    self.port._data.on_changed += self._model_changed_callback
```

**Event flow:**

```
Node calls: self.out('frame', frame_obj)
    ↓
Port._data.set_value(frame_obj)
    ↓
Port._data.on_changed.fire()
    ↓
Widget._model_changed_callback()
    ↓
Widget._sync_frame_to_viewer()
```

---

### Frame Syncing

```python
def _sync_frame_to_viewer(self):
    # Get FRAME from port
    frame = self.port.get_value()
    
    # Extract numpy array
    if hasattr(frame, 'data'):
        frame_data = frame.data  # FRAME object
    elif isinstance(frame, np.ndarray):
        frame_data = frame       # Raw array
    
    # Stream to viewer
    self.streaming_viewer.stream(frame_data)
```

**Complete data flow:**

```
Node Worker Thread:
    self.out('frame', FRAME(data=np_array, ...))
        ↓ (thread-safe event)
Widget (Main UI Thread):
    _sync_frame_to_viewer()
        ↓
    streaming_viewer.stream(np_array)
        ↓
    cv2.imencode() → jpeg_bytes
        ↓
    thread_queue.put(jpeg_bytes)
        ↓ (crosses to async world)
Background Task (Event Loop):
    queue.get() → jpeg_bytes
        ↓
    self.latest_frame = jpeg_bytes
    cond.notify_all()
        ↓ (wakes up)
HTTP Generator (Event Loop):
    yield jpeg_bytes to browser
        ↓ (HTTP streaming)
Browser:
    <img> updates with new JPEG
```

---

## Part 3: The JavaScript Component

```javascript
// opencv_viewer.js
export default {
  template: `
    <div class="opencv-viewer-container">
      <img :src="endpoint" class="opencv-viewer-img" />
    </div>
  `,
  
  props: {
    endpoint: String  // e.g., "/stream/a3f7b2c4"
  }
}
```

**What the browser does:**

1. **Vue renders the template**:
   ```html
   <img src="/stream/a3f7b2c4">
   ```

2. **Browser makes HTTP request**:
   ```
   GET /stream/a3f7b2c4 HTTP/1.1
   ```

3. **Server responds with MJPEG stream**:
   ```
   HTTP/1.1 200 OK
   Content-Type: multipart/x-mixed-replace; boundary=frame
   
   --frame
   Content-Type: image/jpeg
   ...JPEG data...
   --frame
   Content-Type: image/jpeg
   ...JPEG data...
   ```

4. **Browser automatically updates `<img>`**:
   The browser's native handling of `multipart/x-mixed-replace` causes the image to update as new JPEG frames arrive!

No JavaScript event handlers needed - the browser does it all!

---

## Part 4: Hot Reload Problem

### Why Hot Reload Breaks

**During hot reload:**

```python
# 1. Hot reload detects file change
Library.reload_module('widgets.opencv_viewer_widget')

# 2. Python reimports the module
import haybale_visiongraph.widgets.opencv_viewer_widget

# 3. Widget class is re-registered
@widget(...)
class OpencvViewerWidget: ...

# 4. Existing widget instance is recreated
widget = OpencvViewerWidget(port)

# 5. Widget creates new StreamingViewer
self.streaming_viewer = StreamingViewer(...)

# 6. StreamingViewer.__init__ calls:
self._start_queue_reader()
    asyncio.create_task(...)  # ❌ No event loop!
```

**The problem:**

During module reload, Python is executing `__init__` **outside** the async event loop context. The NiceGUI event loop exists, but we're not *in* it.

**Current solution:**

```python
def _start_queue_reader(self):
    try:
        self._queue_reader_task = asyncio.create_task(...)
    except RuntimeError:
        # No event loop - skip for now
        pass
```

This prevents the error, but the task never starts! That's why you need to refresh.

---

## Part 5: Fixing Hot Reload Properly

The issue is that the task needs to be created **inside** the event loop. Let's defer task creation until we're sure we're in the right context:

### Option 1: Lazy Task Start (on first render)

Move task creation to `render()` in the widget, where we're guaranteed to be in NiceGUI's context:

```python
# StreamingViewer
def __init__(self, ...):
    # Don't start task here
    self._task_started = False

def ensure_task_started(self):
    """Call this from widget.render() when in proper context"""
    if not self._task_started:
        self._task_started = True
        self._is_running = True
        self._queue_reader_task = asyncio.create_task(self._queue_reader_loop())

# Widget
def render(self):
    self.streaming_viewer = StreamingViewer(...)
    self.streaming_viewer.ensure_task_started()  # Start task NOW
    ...
```

### Option 2: Use NiceGUI's timer

Schedule task creation to happen on next event loop tick:

```python
def _start_queue_reader(self):
    try:
        self._queue_reader_task = asyncio.create_task(...)
    except RuntimeError:
        # Schedule for next event loop tick
        from nicegui import ui
        ui.timer(0.001, self._start_queue_reader, once=True)
```

### Option 3: Create task when first frame arrives

Don't create task until `stream()` is actually called:

```python
def stream(self, frame):
    # Lazy task creation
    if not self._task_started:
        self._task_started = True
        self._is_running = True
        try:
            self._queue_reader_task = asyncio.create_task(self._queue_reader_loop())
        except RuntimeError:
            # Will retry on next frame
            self._task_started = False
            return
    
    # Continue with streaming...
```

---

## Summary

### The Complete Pipeline

```
┌─────────────────────────────────────────────────────────────┐
│ Node Worker Thread                                          │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ worker(context, frame: FRAME):                       │  │
│  │     self.out('frame', frame)                         │  │
│  └──────────────────────────────────────────────────────┘  │
└────────────────────┬────────────────────────────────────────┘
                     │ Port event: on_changed
                     ↓
┌─────────────────────────────────────────────────────────────┐
│ Widget (Main UI Thread)                                     │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ _sync_frame_to_viewer():                             │  │
│  │     frame = port.get_value()                         │  │
│  │     streaming_viewer.stream(frame.data)              │  │
│  └──────────────────────────────────────────────────────┘  │
└────────────────────┬────────────────────────────────────────┘
                     │ Synchronous call
                     ↓
┌─────────────────────────────────────────────────────────────┐
│ StreamingViewer Component                                   │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ stream(numpy_array):                                 │  │
│  │     jpeg = cv2.imencode(array)                       │  │
│  │     queue.put(jpeg)  ───────────┐                    │  │
│  └─────────────────────────────────│────────────────────┘  │
│                                     │ Thread-safe queue     │
│  ┌──────────────────────────────────│───────────────────┐  │
│  │ _queue_reader_loop():            │                   │  │
│  │     jpeg = queue.get() ←─────────┘                   │  │
│  │     latest_frame = jpeg                              │  │
│  │     frame_id += 1                                    │  │
│  │     cond.notify_all() ───────────┐                   │  │
│  └──────────────────────────────────│───────────────────┘  │
└────────────────────────────────────┬┘───────────────────────┘
                                     │ Async notification
                                     ↓
┌─────────────────────────────────────────────────────────────┐
│ HTTP Endpoint (FastAPI)                                     │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ async generator():                                   │  │
│  │     await cond.wait_for(new_frame)                   │  │
│  │     yield MJPEG_frame ────────────┐                  │  │
│  └──────────────────────────────────│───────────────────┘  │
└────────────────────────────────────┬┘───────────────────────┘
                                     │ HTTP streaming
                                     ↓
┌─────────────────────────────────────────────────────────────┐
│ Browser                                                      │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ <img src="/stream/xyz">                              │  │
│  │     [Displays JPEG frames automatically]             │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### Key Insights

1. **Thread boundaries**: Queue bridges worker thread → event loop
2. **Async boundaries**: Condition bridges event loop → HTTP responses
3. **Multiple consumers**: One producer, many browser clients
4. **Event-driven**: No polling, uses async notifications
5. **Low latency**: Queue size=1, drop-oldest strategy
6. **Hot reload issue**: Task creation needs event loop context
