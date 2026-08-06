# visiongraph — component index (v0.0.23)

## node
- `visiongraph:node:AnnotateNode` — Annotate Results — Draw estimator results (boxes / masks / poses) onto a frame  _tags: annotate, draw, overlay, render, result, visualize_
- `visiongraph:node:FrameDisplayNode` — Frame Info Display — Displays information about frames with live preview  _tags: rgb, ir, frame, camera, display, preview, video, stream_
- `visiongraph:node:NumpyFrameEventNode` — Frame Event — Triggered when a camera frame is ready; exposes colour/depth/infrared streams  _tags: 3d, depth, camera, oak, kinect, realsense, frame, event, rgb, ir, image_
- `visiongraph:node:OakDCameraNode` — OAK-D Camera — Opens an OAK-D depth camera and emits colour/depth/infrared frame callbacks  _tags: oak, oak-d, depthai, luxonis, depth, camera, 3d, stream_
- `visiongraph:node:ObjectDetectorNode` — Object Detector — Detect objects in a frame (bounding box + class + score)  _tags: object, detection, detector, yolo, deim, ssd, bbox, coco_
- `visiongraph:node:PoseEstimatorNode` — Pose Estimator — Estimate human body pose (named joints + skeleton) per person  _tags: pose, human, body, skeleton, joints, landmark, mediapipe, movenet_
- `visiongraph:node:SegmentationNode` — Segmentation — Instance segmentation: detect objects and their pixel masks  _tags: segmentation, instance, mask, yolo, maskrcnn, yolact_
- `visiongraph:node:TrackerNode` — Tracker — Assign stable tracking ids to detections across frames  _tags: tracker, tracking, track, centroid, flate, motpy, id_
- `visiongraph:node:WebCameraNode` — Web Camera — Starts a webcam stream and emits frame callbacks  _tags: webcam, camera, video, capture, stream_

## type
- `visiongraph:type:DEPTH_FRAME` — Depth Frame — Single-channel uint16 metric depth buffer (millimetres)
- `visiongraph:type:DETECTION_RESULT` — Detection Result — Object detections: bounding box, class, score (and tracking id)
- `visiongraph:type:GRAY_FRAME` — Gray Frame — Single-channel uint8 luminance video frame (e.g. infrared)
- `visiongraph:type:LANDMARK_RESULT` — Landmark Result — Landmark detections: a detection plus a set of landmark points
- `visiongraph:type:MULTIFRAME_CALLBACK` — Multiframe Callback — Subscription for multi-frame streams
- `visiongraph:type:POSE_RESULT` — Pose Result — Human pose: landmarks with named joints and skeleton connections
- `visiongraph:type:RGB_FRAME` — RGB Frame — 3-channel uint8 colour video frame
- `visiongraph:type:SEGMENTATION_RESULT` — Segmentation Result — Instance segmentation: detection plus a per-instance mask
- `visiongraph:type:VISION_RESULT` — Vision Result — A list of estimator results (base type for all result kinds)

## adapter
- `visiongraph:adapter:GrayToRgbAdapter` — GrayToRgbAdapter — Replicate a single-channel grey frame to a 3-channel colour frame
- `visiongraph:adapter:RgbToGrayAdapter` — RgbToGrayAdapter — Convert a 3-channel colour frame to a single-channel grey frame (luminance)

## widget
- `visiongraph:widget:NumpyViewerWidget` — NumpyViewerWidget — Streaming video viewer for numpy arrays using custom StreamingViewer
