"""
Pose Estimator node — runs a human-pose estimator on a frame and outlets a list
of ``POSE_RESULT`` (per person: landmarks with named joints + skeleton connections).

Thin subclass of ``BaseEstimatorNode`` (see that module + notes.md Q6/Q13).
"""

from haywire.core.node import node, NodeType

from .base_estimator_node import BaseEstimatorNode, ModelSpec


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
        ),
        "MediaPipe Pose (Lite)": ModelSpec(
            "visiongraph.estimator.spatial.pose.MediaPipePoseEstimator",
            "MediaPipePoseEstimator",
            "MediaPipePoseConfig",
            "Light",
        ),
        "MediaPipe Pose (Heavy)": ModelSpec(
            "visiongraph.estimator.spatial.pose.MediaPipePoseEstimator",
            "MediaPipePoseEstimator",
            "MediaPipePoseConfig",
            "Heavy",
        ),
        "MoveNet MultiPose": ModelSpec(
            "visiongraph.estimator.spatial.pose.MoveNetPoseEstimator",
            "MoveNetPoseEstimator",
            "MoveNetConfig",
            "MoveNet_MultiPose_256x320_FP32",
        ),
    }
