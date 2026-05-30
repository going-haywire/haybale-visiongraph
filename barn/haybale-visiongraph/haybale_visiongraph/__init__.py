"""
Visiongraph Library for Haywire
"""

from importlib.metadata import version as _pkg_version
from pathlib import Path

from haywire.core.library.base import BaseLibrary
from haywire.core.library.decorator import library
from haywire.core.adapter.registry import AdapterRegistry
from haywire.core.node.registry import NodeRegistry
from haywire.core.types.registry import TypeRegistry

from haywire.ui.skin.registry import SkinRegistry
from haywire.ui.widget.registry import WidgetRegistry


@library(
    label="Visiongraph",
    id="visiongraph",
    version=_pkg_version("haybale-visiongraph"),
    description="Visiongraph library",
    url="https://github.com/haywire/haywire-repo/libraries/haybale-visiongraph",
    help_url="https://docs.github.io/haywire_library",
    author="Florian Briggisser, Martin Fröhlich",
    author_url="https://author_url",
    dependencies=["haybale_core"],
    tags=["vision", "camera", "video", "opencv"],
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


# Export for entry point discovery
__all__ = ["Library"]
