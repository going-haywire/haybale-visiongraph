"""
Segmentation node — runs an instance-segmentation estimator on a frame and
outlets a list of ``SEGMENTATION_RESULT`` (a detection plus a per-instance mask).

Thin subclass of ``BaseEstimatorNode`` (see that module + notes.md Q6/Q13).
"""

from haywire.core.settings import bag
from haywire.core.node import node, NodeType

from .base_estimator_node import BaseEstimatorNode, ModelSpec
from .estimator_settings import (
    NmsSettings,
    OpenVinoSettings,
    SegmentationSettings,
)

# YOLOv8-Seg is Ultralytics-shaped (nms_options) and adds its own mask knob;
# MaskRCNN is OpenVINO-shaped (device, consumed when the model is built).
_YOLO_SEG = frozenset({"nms", "segmentation"})
_OPENVINO = frozenset({"openvino"})
_OPENVINO_REBUILD = frozenset({"device"})


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

    FAMILY = "segmentation"

    MODELS = {
        "haybale-visiongraph:catalog:yolov8n-seg": ModelSpec(
            "visiongraph.estimator.spatial.segmentation.YOLOv8SegmentationEstimator",
            "YOLOv8SegmentationEstimator",
            "YOLOv8SegmentationConfig",
            "YOLOv8_SEG_N",
            bags=_YOLO_SEG,
        ),
        "haybale-visiongraph:catalog:yolov8s-seg": ModelSpec(
            "visiongraph.estimator.spatial.segmentation.YOLOv8SegmentationEstimator",
            "YOLOv8SegmentationEstimator",
            "YOLOv8SegmentationConfig",
            "YOLOv8_SEG_S",
            bags=_YOLO_SEG,
        ),
        "haybale-visiongraph:catalog:instance-segmentation-security-0002-fp32": ModelSpec(
            "visiongraph.estimator.spatial.segmentation.MaskRCNNEstimator",
            "MaskRCNNEstimator",
            "MaskRCNNConfig",
            "ResNet50_1024x768_FP32",
            bags=_OPENVINO,
            rebuild_fields=_OPENVINO_REBUILD,
        ),
    }

    nms = bag(NmsSettings)
    segmentation = bag(SegmentationSettings)
    openvino = bag(OpenVinoSettings)
