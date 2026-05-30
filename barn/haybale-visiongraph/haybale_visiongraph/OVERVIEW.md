# Visiongraph (haybale-visiongraph)

v0.0.1 | By Florian Briggisser, Martin Fröhlich
Visiongraph library for Haywire node system demonstrating custom types, nodes, widgets, and renderers

**Source:** https://github.com/haywire/haywire-repo/libraries/haybale-visiongraph
**Dependencies:** haywire-core>=0.1.0, haybale-core>=1.0.0, visiongraph[all]
**Tags:** vision, camera, video, opencv

---

## Nodes

### Events

- **Webcam Frame Event** (`WebcamFrameEventNode`) — event node triggered by webcam frame callbacks, providing frame data and metadata for downstream processing

### Vision

- **Start Webcam Stream** (`StartWebcamStreamNode`) — starts a webcam video stream in a background thread and emits frame callbacks for connected event nodes
- **Webcam Frame Info Display** (`WebcamFrameInfoDisplayNode`) — displays webcam frame metadata and streams a live preview using an embedded video viewer

---

## Types

- **FRAME** (`frame`) — video frame carrying a numpy array with timestamp and frame number metadata

---

## Widgets

- **OpencvViewerWidget** (`OpencvViewerWidget`) — streaming MJPEG video viewer for numpy arrays. Compatible: frame
