# NumpyViewerWidget

`haybale-visiongraph:widget:NumpyViewerWidget` · kind: widget

Streaming video viewer for numpy arrays using custom StreamingViewer

## Details

- **min_width**: `160`

## Notes

Widget for displaying numpy arrays as streaming video.

Uses a custom StreamingViewer component for efficient MJPEG streaming.
Automatically streams frame updates when the port value changes.

Config options (via ``NumpyViewerWidget.config(properties={...})``):

- ``quality`` (int): JPEG compression quality (0-100, default: ``80``).
- ``frame_queue_size`` (int): Internal frame buffer size (default: ``1``).
- ``block_on_full`` (bool): Block the producer when the queue is full (default: ``False``).
- ``frame_width`` (str): CSS border width around the viewer (default: ``'0'``, no frame).
- ``frame_color`` (str): CSS color of the frame border (default: ``'var(--hw-border)'``).

The viewer fills whatever space its host node gives it — it does not impose
its own width/height, so it cooperates with the node's own resize handling
(see ``UINode._apply_size``) instead of fighting it. The ``min_width``
declaration on the decorator is what lets the node shrink *below* the
streamed frame's natural size; without it the frame's pixel width becomes
the node's floor. Override it per call site with
``NumpyViewerWidget.config(min_width=320)`` — a top-level ``config()``
keyword, NOT one of the ``properties`` above.
