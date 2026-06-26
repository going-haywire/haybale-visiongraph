"""
Object Detector node — runs a 2-D object detector on a frame and outlets a list
of ``DETECTION_RESULT`` (bounding box + class + score per object).

A thin subclass of ``BaseEstimatorNode``: it declares only the output type and the
curated model list; all lifecycle (lazy load, synchronous inference, status,
release) lives in the base. Models are declared as lazily-resolved ``ModelSpec``s
so no detector backend is imported until the first frame flows (notes.md Q13).
"""

from haywire.core.node import node, NodeType

from .base_estimator_node import BaseEstimatorNode, ModelSpec


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

    MODELS = {
        "YOLOv8-N (COCO)": ModelSpec(
            "visiongraph.estimator.spatial.YOLOv8Detector", "YOLOv8Detector", "YOLOv8Config", "YOLOv8_N"
        ),
        "YOLOv8-S (COCO)": ModelSpec(
            "visiongraph.estimator.spatial.YOLOv8Detector", "YOLOv8Detector", "YOLOv8Config", "YOLOv8_S"
        ),
        "YOLOv8-M (COCO)": ModelSpec(
            "visiongraph.estimator.spatial.YOLOv8Detector", "YOLOv8Detector", "YOLOv8Config", "YOLOv8_M"
        ),
        "DEIMv2-Pico (COCO)": ModelSpec(
            "visiongraph.estimator.spatial.DEIMv2Detector",
            "DEIMv2Detector",
            "DEIMv2Config",
            "DEIMv2_HgNetv2_Pico_COCO",
        ),
        "DEIMv2-N (COCO)": ModelSpec(
            "visiongraph.estimator.spatial.DEIMv2Detector",
            "DEIMv2Detector",
            "DEIMv2Config",
            "DEIMv2_HgNetv2_N_COCO",
        ),
        "SSDLite MobileNetV2": ModelSpec(
            "visiongraph.estimator.spatial.SSDDetector",
            "SSDDetector",
            "SSDConfig",
            "SSDLiteMobileNetV2_FP32",
        ),
    }
