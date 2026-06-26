"""
Vision estimator result datatypes.

Estimators (object detection, segmentation, pose) take an image and return a
visiongraph ``ResultList`` — a list of ``BaseResult`` objects that know how to
``annotate(image)`` themselves. These datatypes wrap that ``ResultList`` and form
a **subtype hierarchy mirroring visiongraph's own** (see notes.md Q2):

    VISION_RESULT          (base; any ResultList[BaseResult])
    └── DETECTION_RESULT    (ResultList[ObjectDetectionResult]; bbox, score, class)
        ├── SEGMENTATION_RESULT  (+ per-instance mask)
        └── LANDMARK_RESULT      (+ landmarks)
            └── POSE_RESULT          (+ named joints, connections)

The hierarchy is *wired*: a derived ``@type`` is auto-compatible with any
registered ancestor type via the framework's ``issubclass`` passthrough (no
adapter needed). So a ``POSE_RESULT`` outlet connects straight into a base
``VISION_RESULT`` inlet (e.g. the Annotate node's pooled inlet), while a
detection-specific consumer accepts only ``DETECTION_RESULT`` and up.

The wrapped value is the **visiongraph ``ResultList`` itself** (notes.md Q3) — we
reuse its ``.annotate()`` / tracker / ``.map_coordinates()`` rather than
re-extracting fields. All declare ``store_strategy=NEVER`` — results never
serialize (exactly like frames), so there is no save/load round-trip to support.

``visiongraph.result`` imports are light (~0.45s) and are needed here as field
types, so they live at module top — unlike the heavy estimator *backends*, which
node modules lazy-import inside ``setup()`` (notes.md Q13).
"""

from dataclasses import dataclass, field

from visiongraph.result.ResultList import ResultList

from haywire.core.types import type, FlowType, BaseType
from haywire.core.types.enums import StoreStrategy


@dataclass
class BaseVisionResult(BaseType):
    """
    Shared base for all estimator-result datatypes.

    Attributes:
        results: The visiongraph ``ResultList`` returned by an estimator's
            ``process()``. Each element is a ``BaseResult`` that can
            ``annotate(image)`` itself; the ``ResultList`` annotates the batch.
    """

    results: ResultList = field(default_factory=ResultList)

    def count(self) -> int:
        """Number of results in the list (0 if empty/None)."""
        return len(self.results) if self.results is not None else 0


@type(
    label="Vision Result",
    description="A list of estimator results (base type for all result kinds)",
    flow_type=FlowType.DATA,
    default={"results": []},
    color="#455a64",
    store_strategy=StoreStrategy.NEVER,
)
@dataclass
class VISION_RESULT(BaseVisionResult):
    """Base result type: any ``ResultList[BaseResult]``. Annotatable; the common
    denominator every estimator outlet is assignable to."""


@type(
    label="Detection Result",
    description="Object detections: bounding box, class, score (and tracking id)",
    flow_type=FlowType.DATA,
    default={"results": []},
    color="#f57c00",
    store_strategy=StoreStrategy.NEVER,
)
@dataclass
class DETECTION_RESULT(VISION_RESULT):
    """``ResultList[ObjectDetectionResult]`` — each result carries a bounding box,
    class id/name, confidence score, and a (post-tracking) tracking id."""


@type(
    label="Segmentation Result",
    description="Instance segmentation: detection plus a per-instance mask",
    flow_type=FlowType.DATA,
    default={"results": []},
    color="#7b1fa2",
    store_strategy=StoreStrategy.NEVER,
)
@dataclass
class SEGMENTATION_RESULT(DETECTION_RESULT):
    """``ResultList[InstanceSegmentationResult]`` — a detection plus a binary mask
    for the segmented region."""


@type(
    label="Landmark Result",
    description="Landmark detections: a detection plus a set of landmark points",
    flow_type=FlowType.DATA,
    default={"results": []},
    color="#00897b",
    store_strategy=StoreStrategy.NEVER,
)
@dataclass
class LANDMARK_RESULT(DETECTION_RESULT):
    """``ResultList[LandmarkDetectionResult]`` — a detection plus a vector of
    landmark points. Parent of the more specific pose result."""


@type(
    label="Pose Result",
    description="Human pose: landmarks with named joints and skeleton connections",
    flow_type=FlowType.DATA,
    default={"results": []},
    color="#0288d1",
    store_strategy=StoreStrategy.NEVER,
)
@dataclass
class POSE_RESULT(LANDMARK_RESULT):
    """``ResultList[PoseLandmarkResult]`` — landmarks with named joints (nose,
    shoulders, …) and the skeleton connections used to draw the pose."""
