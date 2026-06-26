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

Frequently-reached knobs (``min_score``, ``show_info``) are config ports; the
styling long-tail lives in a ``NodeSettings`` inner class (notes.md Q14).
"""

from typing import Optional

from haywire.core.execution.execution_context import ExecutionContext
from haywire.core.node import node, BaseNode, NodeType
from haywire.core.settings import NodeSettings, setting


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
        min_score: Hide results / landmarks below this confidence.
        show_info: Draw labels / info text.

    Outputs:
        frame_ready: Control flow out.
        frame: The annotated frame (a copy; inputs are not mutated).
    """

    class style(NodeSettings):
        """Set-once styling knobs for the overlay (notes.md Q14)."""

        show_bounding_box = setting[bool](
            False,
            label="Show Bounding Box",
            description="Draw the bounding box for landmark/pose results",
        )
        marker_size = setting[int](
            3,
            min=1,
            max=20,
            label="Marker Size",
            description="Landmark marker radius in pixels",
        )
        stroke_width = setting[int](
            2,
            min=1,
            max=10,
            label="Stroke Width",
            description="Line width for boxes and skeleton connections",
        )

    def init(self):
        from haybale_core.types import EXEC, FLOAT, BOOL, PooledType
        from haybale_visiongraph.types.frame_type import RGB_FRAME
        from haybale_visiongraph.types.result_type import VISION_RESULT
        from haybale_core.widgets.basic_widgets import NumberWidget, SwitchWidget

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

        # Frequently-reached knobs → config ports (Q14).
        self.add(
            FLOAT.as_config(
                "min_score",
                default=0.0,
                label="Min Score",
                widget=NumberWidget.config(properties={"min": 0.0, "max": 1.0, "step": 0.05}),
            )
        )
        self.add(BOOL.as_config("show_info", default=True, label="Show Info", widget=SwitchWidget.config()))

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
            "min_score": self.value("min_score") or 0.0,
            "show_info": bool(self.value("show_info")),
            "show_bounding_box": bool(self.style.show_bounding_box),
            "marker_size": self.style.marker_size,
            "stroke_width": self.style.stroke_width,
        }

        # Pooled inlet yields {source_id: VISION_RESULT}; draw each result list.
        pooled = self.value("result") or {}
        for entry in pooled.values():
            result_list = getattr(entry, "results", None)
            if result_list is None:
                continue
            try:
                result_list.annotate(image, **kwargs)
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
