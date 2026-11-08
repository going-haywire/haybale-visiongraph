# haybale-visiongraph — component index (v0.0.42)

## node
- `haybale-visiongraph:node:AnnotateNode` — Annotate Results — Draw estimator results (boxes / masks / poses) onto a frame  _tags: annotate, draw, overlay, render, result, visualize_
- `haybale-visiongraph:node:FrameDisplayNode` — Frame Info Display — Displays information about frames with live preview  _tags: rgb, ir, frame, camera, display, preview, video, stream_
- `haybale-visiongraph:node:NumpyFrameEventNode` — Frame Event — Triggered when a camera frame is ready; exposes colour/depth/infrared streams  _tags: 3d, depth, camera, oak, kinect, realsense, frame, event, rgb, ir, image_
- `haybale-visiongraph:node:OakDCameraNode` — OAK-D Camera — Opens an OAK-D depth camera and emits colour/depth/infrared frame callbacks  _tags: oak, oak-d, depthai, luxonis, depth, camera, 3d, stream_
- `haybale-visiongraph:node:ObjectDetectorNode` — Object Detector — Detect objects in a frame (bounding box + class + score)  _tags: object, detection, detector, yolo, deim, ssd, bbox, coco_
- `haybale-visiongraph:node:PoseEstimatorNode` — Pose Estimator — Estimate human body pose (named joints + skeleton) per person  _tags: pose, human, body, skeleton, joints, landmark, mediapipe, movenet_
- `haybale-visiongraph:node:SegmentationNode` — Segmentation — Instance segmentation: detect objects and their pixel masks  _tags: segmentation, instance, mask, yolo, maskrcnn, yolact_
- `haybale-visiongraph:node:TrackerNode` — Tracker — Assign stable tracking ids to detections across frames  _tags: tracker, tracking, track, centroid, flate, motpy, id_
- `haybale-visiongraph:node:WebCameraNode` — Web Camera — Starts a webcam stream and emits frame callbacks  _tags: webcam, camera, video, capture, stream_

## type
- `haybale-visiongraph:type:DETECTION_RESULT` — Detection Result — Object detections: bounding box, class, score (and tracking id)
- `haybale-visiongraph:type:LANDMARK_RESULT` — Landmark Result — Landmark detections: a detection plus a set of landmark points
- `haybale-visiongraph:type:CALLBACK_MULTIFRAME` — Callback Multiframe — Subscription for multi-frame streams
- `haybale-visiongraph:type:POSE_RESULT` — Pose Result — Human pose: landmarks with named joints and skeleton connections
- `haybale-visiongraph:type:SEGMENTATION_RESULT` — Segmentation Result — Instance segmentation: detection plus a per-instance mask
- `haybale-visiongraph:type:VISION_RESULT` — Vision Result — A list of estimator results (base type for all result kinds)

## widget
- `haybale-visiongraph:widget:NumpyViewerWidget` — NumpyViewerWidget — Streaming video viewer for numpy arrays using custom StreamingViewer
