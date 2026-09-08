"""Per-backend settings bags shared by the estimator family nodes.

The ``model`` dropdown on one estimator node spans several visiongraph
backends whose tuning knobs are **disjoint**: NMS belongs to the Ultralytics
family and MoveNet, ``device`` to the OpenVINO ones, and MediaPipe has a set
all of its own. Rather than a flat union bag (where setting ``mask_threshold``
with MoveNet selected would silently do nothing), each backend gets its own
bag and the node hides the ones the current model doesn't use — the same
``set_ui_state_all`` mechanism ``OakDCameraNode`` uses for stream gating, but
driven by a condition local to the node.

Bags live here at module level rather than inline on a node so that several
family nodes can share one (``ObjectDetectorNode`` and ``SegmentationNode``
both offer Ultralytics models) and so each node can carry a ``TYPE_CHECKING``
annotation for them.

**Alias each bag under the same accessor name on every node.** The descriptors
below are shared objects and ``@node`` re-stamps ``_setting_key`` as
``f"{accessor}.{field}"`` for every node that declares the bag; re-stamping is
idempotent only while the accessor name is identical. Aliasing ``NmsSettings``
as ``nms`` on one node and something else on another would make the storage
key depend on decoration order — silently, for both nodes.

Liveness (which decides ``promotable=``) is a fact about where visiongraph
reads the attribute, verified against 1.2.0:

- read inside ``process()``  -> live, ``Promotable.ALL``
- read inside ``setup()``    -> rebuild-category, ``Promotable.CONFIG``, and
  the field name goes in the owning ``ModelSpec.rebuild_fields``
"""

from haywire.core.settings import NodeSettings, Promotable, setting
from haywire.barn.builtin.types import BOOL, CHOICES, COLOR, FLOAT, INT

# `eta` and `top_k` are Optional[...] in NMSOptions: "unset" is a distinct
# state from any number, and a settings field has no null. -1 is the sentinel.
# (is_locally_set() cannot serve here — a write equal to the default records
# no local override, so it cannot distinguish "untouched" from "set to the
# default value". See notes.md prerequisite 5.)
UNSET = -1

_NMS_BATCH_MODES = ["Auto", "Batched", "Sequential"]


class SelectionSettings(NodeSettings):
    """Which curated model this estimator runs.

    The options differ per family, so `BaseEstimatorNode` declares this empty
    base and each family node overrides it via `selection_bag(MODELS)` below.
    `@node` permits redeclaring an inherited bag **only** as a subclass of it,
    which is exactly what the factory returns.
    """

    model = setting[CHOICES](
        "",
        label="Model",
        category="Model",
        description="Which backend + weights to run. Changing this reloads the model.",
        widget_config={"options": []},
    )


def selection_bag(models: dict) -> type:
    """Build a family node's `selection` bag from its own MODELS map.

    A factory rather than a shared descriptor with a live callable: the options
    are a fixed property of the class, and a zero-arg `widget_config` callable
    could not see which node it was being rendered for anyway.
    """
    labels = list(models)

    class selection(SelectionSettings):
        model = setting[CHOICES](
            labels[0] if labels else "",
            label="Model",
            category="Model",
            description="Which backend + weights to run. Changing this reloads the model.",
            widget_config={"options": labels},
        )

    return selection


class OverlaySettings(NodeSettings):
    """How this estimator's results should be drawn downstream.

    Not a visiongraph concept: the value is stamped onto the emitted
    ``BaseVisionResult.color`` and read back by ``AnnotateNode``, so that a
    pooled overlay of several estimators can tell them apart. See
    ``BaseVisionResult`` for why it cannot live on the visiongraph result.
    """

    color = setting[COLOR](
        "",
        label="Overlay Colour",
        category="Overlay",
        description=(
            "Colour the Annotate node draws these results in. Empty keeps "
            "visiongraph's automatic per-tracking-id palette. Segmentation "
            "masks ignore this."
        ),
    )


class InferenceSettings(NodeSettings):
    """Knobs every backend understands (``ScoreThresholdEstimator.min_score``)."""

    min_score = setting[FLOAT](
        0.3,
        min=0.0,
        max=1.0,
        label="Min Score",
        category="Inference",
        description=(
            "Minimum confidence. Applied natively by the estimator, so it can "
            "go BELOW the backend's own default. MediaPipe consumes this when "
            "the model is built, so changing it there reloads the model."
        ),
    )


class NmsSettings(NodeSettings):
    """``NMSOptions`` — Ultralytics (YOLOv8 det/seg), DEIMv2, and MoveNet.

    Read inside ``process()`` via ``self.nms_options``, which is a mutable
    dataclass on the estimator — so all of these are live.
    """

    enabled = setting[BOOL](
        True,
        label="Apply NMS",
        category="NMS",
        description="Suppress overlapping detections.",
    )
    score_threshold = setting[FLOAT](
        0.3,
        min=0.0,
        max=1.0,
        label="NMS Score Threshold",
        category="NMS",
        description="Confidence floor used INSIDE non-maximum suppression. Distinct from Min Score.",
    )
    nms_threshold = setting[FLOAT](
        0.3,
        min=0.0,
        max=1.0,
        label="IoU Threshold",
        category="NMS",
        description="Overlap above which the lower-scoring box is dropped.",
    )
    eta = setting[FLOAT](
        UNSET,
        min=-1.0,
        max=1.0,
        label="Eta",
        category="NMS",
        description="Adaptive NMS threshold coefficient. -1 leaves it unset.",
    )
    top_k = setting[INT](
        UNSET,
        min=-1,
        max=1000,
        label="Top K",
        category="NMS",
        description="Keep at most this many detections. -1 leaves it unset.",
    )
    batch_mode = setting[CHOICES](
        "Auto",
        label="Batch Mode",
        category="NMS",
        description="How NMS is applied across classes.",
        widget_config={"options": _NMS_BATCH_MODES},
    )


class SegmentationSettings(NodeSettings):
    """YOLOv8-Seg only. Both read inside ``process()`` — live."""

    mask_threshold = setting[FLOAT](
        0.5,
        min=0.0,
        max=1.0,
        label="Mask Threshold",
        category="Segmentation",
        description="Probability above which a pixel is part of the mask.",
    )


class OpenVinoSettings(NodeSettings):
    """SSD / MaskRCNN / MoveNet. ``device`` is read when the model is built."""

    device = setting[CHOICES](
        "AUTO",
        label="Inference Device",
        category="Device",
        description="OpenVINO device. Applied when the model is built — changing it reloads.",
        widget_config={"options": ["AUTO", "CPU", "GPU", "NPU"]},
        promotable=Promotable.CONFIG,
    )


class MediaPipeSettings(NodeSettings):
    """MediaPipe Pose. Every field is consumed by ``setup()`` — rebuild-category."""

    max_num_poses = setting[INT](
        1,
        min=1,
        max=10,
        label="Max Poses",
        category="MediaPipe",
        description="How many people to track. Applied when the model is built.",
        promotable=Promotable.CONFIG,
    )
    min_pose_presence_confidence = setting[FLOAT](
        0.5,
        min=0.0,
        max=1.0,
        label="Min Presence Confidence",
        category="MediaPipe",
        description="Applied when the model is built.",
        promotable=Promotable.CONFIG,
    )
    min_tracking_confidence = setting[FLOAT](
        0.5,
        min=0.0,
        max=1.0,
        label="Min Tracking Confidence",
        category="MediaPipe",
        description="Applied when the model is built.",
        promotable=Promotable.CONFIG,
    )
    static_image_mode = setting[BOOL](
        False,
        label="Static Image Mode",
        category="MediaPipe",
        description=(
            "Treat every frame as unrelated (no temporal tracking). Applied when the model is built."
        ),
        promotable=Promotable.CONFIG,
    )
    output_segmentation_masks = setting[BOOL](
        True,
        label="Output Segmentation Masks",
        category="MediaPipe",
        description="Applied when the model is built.",
        promotable=Promotable.CONFIG,
    )


class MoveNetSettings(NodeSettings):
    """MoveNet's own knob. ``multi_pose`` is read inside ``process()`` — live."""

    multi_pose = setting[BOOL](
        False,
        label="Multi Pose",
        category="MoveNet",
        description="Detect several people rather than one.",
    )
