"""
Pose Estimator node — runs a human-pose estimator on a frame and outlets a list
of ``POSE_RESULT`` (per person: landmarks with named joints + skeleton connections).

Thin subclass of ``BaseEstimatorNode`` (see that module + notes.md Q6/Q13).
"""

from typing import TYPE_CHECKING

from haywire.core.node import node, NodeType

from .base_estimator_node import BaseEstimatorNode, ModelSpec
from .estimator_settings import (
    MediaPipeSettings,
    MoveNetSettings,
    NmsSettings,
    OpenVinoSettings,
    selection_bag,
)

# MediaPipe builds its PoseLandmarker in setup(), so EVERY one of its knobs is
# rebuild-category — including min_score, which it consumes as
# `min_pose_detection_confidence`. That is the whole reason rebuild_fields is
# per-spec rather than a single node-level list: on MoveNet the same
# `min_score` is read inside process() and must stay live.
_MEDIAPIPE = frozenset({"mediapipe"})
_MEDIAPIPE_REBUILD = frozenset(
    {
        "min_score",
        "max_num_poses",
        "min_pose_presence_confidence",
        "min_tracking_confidence",
        "static_image_mode",
        "output_segmentation_masks",
    }
)

# MoveNet takes nms_options (live) and multi_pose (live); device is OpenVINO's
# and is consumed when the model is built.
_MOVENET = frozenset({"nms", "movenet", "openvino"})
_MOVENET_REBUILD = frozenset({"device"})


@node(
    label="Pose Estimator",
    description="Estimate human body pose (named joints + skeleton) per person",
    menu="vision/estimate",
    search_tags=["pose", "human", "body", "skeleton", "joints", "landmark", "mediapipe", "movenet"],
    node_type=NodeType.CONTROL,
)
class PoseEstimatorNode(BaseEstimatorNode):
    """Human-pose family node — outlets ``POSE_RESULT``."""

    def hb_result_type(self):
        from haybale_visiongraph.types.result_type import POSE_RESULT

        return POSE_RESULT

    MODELS = {
        "MediaPipe Pose (Full)": ModelSpec(
            "visiongraph.estimator.spatial.pose.MediaPipePoseEstimator",
            "MediaPipePoseEstimator",
            "MediaPipePoseConfig",
            "Full",
            bags=_MEDIAPIPE,
            rebuild_fields=_MEDIAPIPE_REBUILD,
        ),
        "MediaPipe Pose (Lite)": ModelSpec(
            "visiongraph.estimator.spatial.pose.MediaPipePoseEstimator",
            "MediaPipePoseEstimator",
            "MediaPipePoseConfig",
            "Light",
            bags=_MEDIAPIPE,
            rebuild_fields=_MEDIAPIPE_REBUILD,
        ),
        "MediaPipe Pose (Heavy)": ModelSpec(
            "visiongraph.estimator.spatial.pose.MediaPipePoseEstimator",
            "MediaPipePoseEstimator",
            "MediaPipePoseConfig",
            "Heavy",
            bags=_MEDIAPIPE,
            rebuild_fields=_MEDIAPIPE_REBUILD,
        ),
        "MoveNet MultiPose": ModelSpec(
            "visiongraph.estimator.spatial.pose.MoveNetPoseEstimator",
            "MoveNetPoseEstimator",
            "MoveNetConfig",
            "MoveNet_MultiPose_256x320_FP32",
            bags=_MOVENET,
            rebuild_fields=_MOVENET_REBUILD,
        ),
    }

    if TYPE_CHECKING:
        mediapipe: MediaPipeSettings
        movenet: MoveNetSettings
        nms: NmsSettings
        openvino: OpenVinoSettings
    else:
        selection = selection_bag(MODELS)
        mediapipe = MediaPipeSettings
        movenet = MoveNetSettings
        nms = NmsSettings
        openvino = OpenVinoSettings
