"""
Visiongraph Library for Haywire
"""

from pathlib import Path

from haywire.core.library.base import BaseLibrary
from haywire.core.library.compatibility import CompatibilityWarning
from haywire.core.library.decorator import library
from haywire.core.adapter.registry import AdapterRegistry
from haywire.core.node.registry import NodeRegistry
from haywire.core.types.registry import TypeRegistry

from haywire.ui.skin.registry import SkinRegistry
from haywire.ui.widget.registry import WidgetRegistry


@library(
    file_watcher=False,
)
class Library(BaseLibrary):
    """Example library implementation"""

    def register_components(self):
        """Register all test components with the global registries"""

        """Register nodes and types"""
        base_path = Path(__file__).parent

        # Register types (both variants and custom types)
        self.add_folder_to_registry(folder_path=str(base_path / "types"), registry_cls=TypeRegistry)

        # Register adapters
        self.add_folder_to_registry(folder_path=str(base_path / "adapters"), registry_cls=AdapterRegistry)

        # Register widgets
        self.add_folder_to_registry(folder_path=str(base_path / "widgets"), registry_cls=WidgetRegistry)

        # Register skins (node skins)
        self.add_folder_to_registry(folder_path=str(base_path / "skins"), registry_cls=SkinRegistry)

        # Register nodes
        self.add_folder_to_registry(folder_path=str(base_path / "nodes"), registry_cls=NodeRegistry)

    def validate(self) -> bool:
        """Validate that the test library is properly structured"""
        return True

    def compatibility_warnings(self) -> list[CompatibilityWarning]:
        """Append-only history of compatibility notices. See ADR 0005."""
        from .nodes import (
            AnnotateNode,
            FrameDisplayNode,
            NumpyFrameEventNode,
            ObjectDetectorNode,
            PoseEstimatorNode,
            SegmentationNode,
            TrackerNode,
            WebCameraNode,
        )

        # 0.0.39 converted every user-facing config PORT into a settings field
        # (see notes.md "Settings-first configuration"). That is not a
        # transparent change for a saved graph: _deserialize_ports rebuilds
        # ports verbatim from the saved spec and init() does not run on load,
        # so an old graph keeps its stale config port — showing the value the
        # user set — while the worker now reads a settings field sitting at its
        # default. The two do not even collide, because a promoted port's id is
        # the setting's storage_key ("style.min_score", not "min_score"), so
        # both appear side by side. Reset re-derives the node from current code
        # and clears this warning; it also returns the node to defaults.
        _SETTINGS_FIRST = "0.0.39"

        def _converted(component, knobs: str) -> CompatibilityWarning:
            return CompatibilityWarning(
                version=_SETTINGS_FIRST,
                component=component,
                message=(
                    f"{knobs} moved from config ports to settings in 0.0.39. A graph "
                    "saved before then keeps the old ports with their saved values, but "
                    "the node now reads the settings — which are at their defaults. "
                    "Reset the node to re-derive it from current code, then re-enter "
                    "these values in the properties panel."
                ),
            )

        return [
            CompatibilityWarning(
                version="0.0.13",
                component=FrameDisplayNode,
                message=(
                    "The 'frame' inlet's widget visibility (show_widget) is now "
                    "author-declared (WHEN_LINKED). Graphs saved before 0.0.13 may "
                    "not show the live preview widget even when the inlet is linked. "
                    "Reset the node to re-derive it from current code."
                ),
            ),
            _converted(AnnotateNode, "'min_score' and 'show_info'"),
            _converted(ObjectDetectorNode, "'model' and 'min_score'"),
            _converted(SegmentationNode, "'model' and 'min_score'"),
            _converted(PoseEstimatorNode, "'model' and 'min_score'"),
            _converted(TrackerNode, "'backend' and 'result_type'"),
            _converted(NumpyFrameEventNode, "'enable_rgb', 'enable_depth' and 'enable_ir'"),
            _converted(
                WebCameraNode,
                "'camera_index', 'width', 'height', 'fps' and 'frame_skip'",
            ),
            CompatibilityWarning(
                version=_SETTINGS_FIRST,
                component=WebCameraNode,
                message=(
                    "This node now captures through visiongraph's VideoCaptureInput "
                    "instead of cv2 directly, which adds rotate/flip/crop and capture "
                    "backend selection. Requires visiongraph >= 1.2.0."
                ),
            ),
        ]


# Export for entry point discovery
__all__ = ["Library"]
