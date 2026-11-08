# Visiongraph

<!-- marketstall:share-url:start -->
Always the latest (tracks the current branch):

```sh
https://github.com/going-haywire/haybale-visiongraph/blob/master/marketstall.toml
```

Frozen to this version:

```sh
https://github.com/going-haywire/haybale-visiongraph/blob/v0.0.42/marketstall.toml
```
<!-- marketstall:share-url:end -->

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
- **Detection Result** — Object detections: bounding box, class, score (and tracking id)
- **Landmark Result** — Landmark detections: a detection plus a set of landmark points
- **Callback Multiframe** — Subscription for multi-frame streams
- **Pose Result** — Human pose: landmarks with named joints and skeleton connections
- **Segmentation Result** — Instance segmentation: detection plus a per-instance mask
- **Vision Result** — A list of estimator results (base type for all result kinds)

## Widgets
- **NumpyViewerWidget** — Streaming video viewer for numpy arrays using custom StreamingViewer
