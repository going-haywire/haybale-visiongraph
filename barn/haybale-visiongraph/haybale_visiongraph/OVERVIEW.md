# Visiongraph

Visiongraph is a computer-vision pipeline library designed to simplify the prototyping of image-based algorithms

## Nodes
### Vision
- **Annotate Results** — Draw estimator results (boxes / masks / poses) onto a frame
- **Frame Event** — Triggered when a camera frame is ready; exposes colour/depth/infrared streams
- **Frame Info Display** — Displays information about frames with live preview
- **OAK-D Camera** — Opens an OAK-D depth camera and emits colour/depth/infrared frame callbacks
- **Object Detector** — Detect objects in a frame (bounding box + class + score)
- **Pose Estimator** — Estimate human body pose (named joints + skeleton) per person
- **Segmentation** — Instance segmentation: detect objects and their pixel masks
- **Tracker** — Assign stable tracking ids to detections across frames
- **Web Camera** — Starts a webcam stream and emits frame callbacks

## Types
- **Depth Frame** — Single-channel uint16 metric depth buffer (millimetres)
- **Detection Result** — Object detections: bounding box, class, score (and tracking id)
- **Gray Frame** — Single-channel uint8 luminance video frame (e.g. infrared)
- **Landmark Result** — Landmark detections: a detection plus a set of landmark points
- **Multiframe Callback** — Subscription for multi-frame streams
- **Pose Result** — Human pose: landmarks with named joints and skeleton connections
- **RGB Frame** — 3-channel uint8 colour video frame
- **Segmentation Result** — Instance segmentation: detection plus a per-instance mask
- **Vision Result** — A list of estimator results (base type for all result kinds)

## Widgets
- **NumpyViewerWidget** — Streaming video viewer for numpy arrays using custom StreamingViewer

## Adapters
- **GrayToRgbAdapter** — Replicate a single-channel grey frame to a 3-channel colour frame
- **RgbToGrayAdapter** — Convert a 3-channel colour frame to a single-channel grey frame (luminance)
