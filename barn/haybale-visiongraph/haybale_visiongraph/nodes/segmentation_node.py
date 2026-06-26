"""
Segmentation node — runs an instance-segmentation estimator on a frame and
outlets a list of ``SEGMENTATION_RESULT`` (a detection plus a per-instance mask).

Thin subclass of ``BaseEstimatorNode`` (see that module + notes.md Q6/Q13).
"""

from haywire.core.node import node, NodeType

from .base_estimator_node import BaseEstimatorNode, ModelSpec


@node(
    label="Segmentation",
    description="Instance segmentation: detect objects and their pixel masks",
    menu="vision/estimate",
    search_tags=["segmentation", "instance", "mask", "yolo", "maskrcnn", "yolact"],
    node_type=NodeType.CONTROL,
)
class SegmentationNode(BaseEstimatorNode):
    """Instance-segmentation family node — outlets ``SEGMENTATION_RESULT``."""

    def hb_result_type(self):
        from haybale_visiongraph.types.result_type import SEGMENTATION_RESULT

        return SEGMENTATION_RESULT

    MODELS = {
        "YOLOv8-Seg-N (COCO)": ModelSpec(
            "visiongraph.estimator.spatial.segmentation.YOLOv8SegmentationEstimator",
            "YOLOv8SegmentationEstimator",
            "YOLOv8SegmentationConfig",
            "YOLOv8_SEG_N",
        ),
        "YOLOv8-Seg-S (COCO)": ModelSpec(
            "visiongraph.estimator.spatial.segmentation.YOLOv8SegmentationEstimator",
            "YOLOv8SegmentationEstimator",
            "YOLOv8SegmentationConfig",
            "YOLOv8_SEG_S",
        ),
        "Mask R-CNN ResNet50 (FP32)": ModelSpec(
            "visiongraph.estimator.spatial.segmentation.MaskRCNNEstimator",
            "MaskRCNNEstimator",
            "MaskRCNNConfig",
            "ResNet50_1024x768_FP32",
        ),
    }
