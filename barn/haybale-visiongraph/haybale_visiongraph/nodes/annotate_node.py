"""
Annotate node — draws one or more result lists onto a frame.

The result inlet is a ``PooledType[VISION_RESULT]`` (notes.md Q10): it accepts a
*mix* of detection / segmentation / landmark / pose result outlets at once (each is
a subtype of ``VISION_RESULT``, and a pooled inlet checks compatibility against its
element type). So a single Annotate node can overlay detections + pose + masks from
several estimators onto one frame.

Every visiongraph ``ResultList`` knows how to ``annotate(image, **kwargs)`` itself
(mutating the image in place, using normalized coordinates). The worker **copies**
the frame first — annotating in place would corrupt the shared ``RGB_FRAME`` value
flowing to other consumers — then draws every pooled result onto the copy.

Every knob is a ``setting()`` in ``AnnotateStyle``; ``min_score`` and
``show_info`` are *seeded* to config ports in ``init()`` so the node arrives
with its familiar face, and the user may demote them. See "Settings-first
configuration" in notes.md (which supersedes Q14's config-port/settings split).
"""

from typing import TYPE_CHECKING, Optional

from haywire.core.execution.execution_context import ExecutionContext
from haywire.core.node import node, BaseNode, NodeType
from haywire.core.settings import NodeSettings, setting
from haywire.core.types.enums import PortType
from haywire.barn.builtin.types import BOOL, CHOICES, FLOAT, INT

# `show_bounding_box` is a TRI-state, not a bool, because the visiongraph
# subtypes disagree on its default: LandmarkDetectionResult and
# PoseLandmarkResult default it to False, InstanceSegmentationResult to True.
# AUTO means "don't pass the kwarg at all", so each subtype keeps its own
# default; the other two force it for every connected result list.
#
# A plain BOOL cannot express this. `is_locally_set()` looked like it could —
# untouched ⇒ omit — but a write equal to the default records no local
# override (cell writes are transition-only), so a user explicitly choosing
# False is indistinguishable from one who never touched the field, and
# segmentation would keep drawing boxes against an explicit instruction.
BBOX_AUTO = "Auto (per result type)"
BBOX_ALWAYS = "Always"
BBOX_NEVER = "Never"
_BBOX_OPTIONS = [BBOX_AUTO, BBOX_ALWAYS, BBOX_NEVER]


def hex_to_bgr(value: str) -> Optional[tuple]:
    """``"#rrggbb"`` → an OpenCV ``(B, G, R)`` tuple. ``None`` for empty/invalid.

    **BGR, not RGB.** Frames here are OpenCV-native: a webcam's `cv2.VideoCapture`
    and OAK's `get_raw_image` both yield BGR, and the viewer re-encodes with
    `cv2.imencode(".jpg", frame)`, which reads BGR. `RGB_FRAME` is a misnomer
    the drawing code must not believe. Every visiongraph annotate() forwards
    its `color` straight to a cv2 draw call, so the tuple's first element lands
    in channel 0 — blue. Emitting RGB here would render a user's red as blue.

    (visiongraph's own `COLOR_SEQUENCE` looks like RGB triples — `(230, 25, 75)`
    for "red" — so its built-in palette *is* channel-swapped on these frames.
    We match the user's intent rather than that inconsistency: a picked #ff0000
    draws red. A colour set here will therefore not match the same hue in the
    automatic tracking-id palette.)

    Tolerant by construction: this runs per frame in the draw loop, and a
    half-typed value from a colour picker must never break the overlay.
    """
    text = (value or "").strip().lstrip("#")
    if len(text) == 8:  # #rrggbbaa — alpha is meaningless to cv2, drop it
        text = text[:6]
    if len(text) != 6:
        return None
    try:
        r, g, b = (int(text[i : i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        return None
    return (b, g, r)


class AnnotateStyle(NodeSettings):
    """Set-once styling knobs for the overlay.

    Declared at module level rather than inline so the node can carry a
    `TYPE_CHECKING` annotation for it (see `AnnotateNode.style`) — a bag
    touched from an *annotated* method needs one, or mypy sees the class
    rather than the bound instance. `@node` collects it exactly the same way.
    """

    min_score = setting[FLOAT](
        0.0,
        min=0.0,
        max=1.0,
        label="Min Score",
        category="Filter",
        description="Hide results and landmarks below this confidence.",
    )
    show_info = setting[BOOL](
        True,
        label="Show Info",
        category="Filter",
        description="Draw the label / info text next to each result.",
    )
    show_bounding_box = setting[CHOICES](
        BBOX_AUTO,
        label="Show Bounding Box",
        category="Style",
        description=(
            "Draw bounding boxes. Auto keeps each result type's own default "
            "(off for landmark/pose, on for segmentation)."
        ),
        widget_config={"options": _BBOX_OPTIONS},
    )
    marker_size = setting[INT](
        3,
        min=1,
        max=20,
        label="Marker Size",
        category="Style",
        description="Landmark marker radius in pixels",
    )
    stroke_width = setting[INT](
        2,
        min=1,
        max=10,
        label="Stroke Width",
        category="Style",
        description="Line width for boxes and skeleton connections",
    )
    use_class_color = setting[BOOL](
        True,
        label="Colour Masks by Class",
        category="Style",
        description=(
            "Segmentation only: colour each mask by its class instead of by "
            "tracking id. Ignored by every other result type."
        ),
    )


@node(
    label="Annotate Results",
    description="Draw estimator results (boxes / masks / poses) onto a frame",
    menu="vision/draw",
    search_tags=["annotate", "draw", "overlay", "render", "result", "visualize"],
    node_type=NodeType.CONTROL,
)
class AnnotateNode(BaseNode):
    """
    Overlay pooled vision results onto a frame.

    Inputs:
        execute: Control flow in.
        result: Pooled result lists (any mix of VISION_RESULT subtypes).
        frame: The image to draw on (RGB_FRAME).

    Settings (``style``):
        min_score / show_info: seeded to config ports — the node's default face.
        show_bounding_box / marker_size / stroke_width / use_class_color:
            panel-only; promote from the Setting-row menu if you reach for one.

    Outputs:
        frame_ready: Control flow out.
        frame: The annotated frame (a copy; inputs are not mutated).
    """

    if TYPE_CHECKING:
        # mypy view: instances expose `style` as a bound AnnotateStyle. Without
        # this the class-body alias below is all mypy sees, and every field read
        # types as the `setting[T]` descriptor instead of T.
        style: AnnotateStyle
    else:
        style = AnnotateStyle

    def init(self):
        from haybale_core.types import EXEC, PooledType
        from haybale_visiongraph.types.frame_type import RGB_FRAME
        from haybale_visiongraph.types.result_type import VISION_RESULT

        # Control in.
        self.add(EXEC.as_inlet("execute", label="Run"))

        # Pooled result inlet — accepts any mix of VISION_RESULT subtypes (Q10).
        self.add(
            PooledType[VISION_RESULT].as_inlet(
                "result",
                label="Results",
                description="Connect one or more estimator result outlets",
            )
        )

        # Frame to draw on.
        self.add(RGB_FRAME.as_inlet("frame", label="Frame"))

        # Seeded promotions: this node's default face. Seeded in init() (NOT
        # post_init) so a user who demotes one keeps that choice across a
        # save/load — init() runs only on a fresh drop.
        self.style.promote("min_score", PortType.CONFIG)
        self.style.promote("show_info", PortType.CONFIG)

        # Control out.
        self.add(EXEC.as_outlet("frame_ready", label="Frame Ready"))

        # Annotated frame out. (Distinct id from the "frame" inlet — port ids are
        # unique per node; cf. FrameDisplayNode's "frame_pass".)
        self.add(RGB_FRAME.as_outlet("annotated", label="Annotated"))

    def worker(self, context: ExecutionContext, result=None, frame=None) -> Optional[str]:
        """Copy the frame, draw every pooled result onto it, output the copy."""
        from haybale_visiongraph.types.frame_type import BaseFrame, RGB_FRAME

        if frame is None or not isinstance(frame, BaseFrame) or not frame.is_valid():
            return None

        data = frame.data
        if data is None:
            return None

        # Copy so in-place annotate() does not corrupt the shared frame (Q10).
        image = data.copy()

        # NodeSettings fields resolve to their unwrapped values on read.
        kwargs = {
            "min_score": self.style.min_score,
            "show_info": bool(self.style.show_info),
            "marker_size": self.style.marker_size,
            "stroke_width": self.style.stroke_width,
            "use_class_color": bool(self.style.use_class_color),
        }

        # AUTO omits the kwarg entirely so each subtype keeps its own default;
        # the two explicit choices force it. See the _BBOX_OPTIONS comment.
        bbox = str(self.style.show_bounding_box)
        if bbox != BBOX_AUTO:
            kwargs["show_bounding_box"] = bbox == BBOX_ALWAYS

        # Pooled inlet yields {source_id: VISION_RESULT}; draw each result list.
        pooled = self.value("result") or {}
        for entry in pooled.values():
            result_list = getattr(entry, "results", None)
            if result_list is None:
                continue
            # Per-estimator overlay colour, set upstream on the result wrapper
            # (see BaseVisionResult.color). Empty = no opinion, so visiongraph
            # falls back to its own tracking-id palette.
            per_entry = dict(kwargs)
            bgr = hex_to_bgr(getattr(entry, "color", ""))
            if bgr is not None:
                per_entry["color"] = bgr
            try:
                result_list.annotate(image, **per_entry)
            except Exception:
                # A subtype that rejects a kwarg shouldn't kill the whole overlay;
                # fall back to a bare annotate for that list.
                try:
                    result_list.annotate(image)
                except Exception:
                    pass

        self.out(
            "annotated", RGB_FRAME(data=image, timestamp=frame.timestamp, frame_number=frame.frame_number)
        )
        return "frame_ready"
