"""
Object Detector node — runs a 2-D object detector on a frame and outlets a list
of ``DETECTION_RESULT`` (bounding box + class + score per object).

A thin subclass of ``BaseEstimatorNode``: it declares only the output type, the
curated model list, and the per-backend settings bags those models use. All
lifecycle (lazy load, synchronous inference, status, release) lives in the base.
Models are declared as lazily-resolved ``ModelSpec``s so no detector backend is
imported until the first frame flows (notes.md Q13).
"""

from haywire.core.settings import bag
from haywire.core.node import node, NodeType

from .base_estimator_node import BaseEstimatorNode, ModelSpec
from .estimator_settings import NmsSettings, OpenVinoSettings

# The Ultralytics-shaped backends (YOLOv8, DEIMv2) all take `nms_options`; the
# OpenVINO ones (SSD) take `device`. Everything here reads min_score inside
# process(), so none of them list it in rebuild_fields.
_ULTRALYTICS = frozenset({"nms"})
_OPENVINO = frozenset({"openvino"})
# `device` is consumed when the OpenVINO model is built, not per frame.
_OPENVINO_REBUILD = frozenset({"device"})


@node(
    label="Object Detector",
    description="Detect objects in a frame (bounding box + class + score)",
    menu="vision/estimate",
    search_tags=["object", "detection", "detector", "yolo", "deim", "ssd", "bbox", "coco"],
    node_type=NodeType.CONTROL,
)
class ObjectDetectorNode(BaseEstimatorNode):
    """Object detection family node — outlets ``DETECTION_RESULT``."""

    def hb_result_type(self):
        from haybale_visiongraph.types.result_type import DETECTION_RESULT

        return DETECTION_RESULT

    FAMILY = "object-detection"

    MODELS = {
        "haybale-visiongraph:catalog:yolov8n": ModelSpec(
            "visiongraph.estimator.spatial.YOLOv8Detector",
            "YOLOv8Detector",
            "YOLOv8Config",
            "YOLOv8_N",
            bags=_ULTRALYTICS,
        ),
        "haybale-visiongraph:catalog:yolov8s": ModelSpec(
            "visiongraph.estimator.spatial.YOLOv8Detector",
            "YOLOv8Detector",
            "YOLOv8Config",
            "YOLOv8_S",
            bags=_ULTRALYTICS,
        ),
        "haybale-visiongraph:catalog:yolov8m": ModelSpec(
            "visiongraph.estimator.spatial.YOLOv8Detector",
            "YOLOv8Detector",
            "YOLOv8Config",
            "YOLOv8_M",
            bags=_ULTRALYTICS,
        ),
        "haybale-visiongraph:catalog:deimv2_hgnetv2_pico_coco": ModelSpec(
            "visiongraph.estimator.spatial.DEIMv2Detector",
            "DEIMv2Detector",
            "DEIMv2Config",
            "DEIMv2_HgNetv2_Pico_COCO",
            bags=_ULTRALYTICS,
        ),
        "haybale-visiongraph:catalog:deimv2_hgnetv2_n_coco": ModelSpec(
            "visiongraph.estimator.spatial.DEIMv2Detector",
            "DEIMv2Detector",
            "DEIMv2Config",
            "DEIMv2_HgNetv2_N_COCO",
            bags=_ULTRALYTICS,
        ),
        "haybale-visiongraph:catalog:ssdlite_mobilenet_v2_fp32": ModelSpec(
            "visiongraph.estimator.spatial.SSDDetector",
            "SSDDetector",
            "SSDConfig",
            "SSDLiteMobileNetV2_FP32",
            bags=_OPENVINO,
            rebuild_fields=_OPENVINO_REBUILD,
        ),
    }

    nms = bag(NmsSettings)
    openvino = bag(OpenVinoSettings)
