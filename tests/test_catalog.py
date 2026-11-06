"""The curated models as catalog entries: complete, pinned, and honest about their licences."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

import haybale_visiongraph

COMMIT = "0de7ab36c9cf7d0843a1a19fd8c83db34a19d8a3"
CATALOG = Path(haybale_visiongraph.__file__).parent / "catalog"


@pytest.fixture
def entries() -> list[Any]:
    from haywire.core.catalog import CatalogRegistry
    from haywire.core.library.identity import LibraryIdentity

    registry = CatalogRegistry()
    registry.add_folder(
        str(CATALOG),
        LibraryIdentity(
            label="Visiongraph",
            name="haybale-visiongraph",
            folder_path=str(CATALOG.parent),
            module_name="haybale_visiongraph",
        ),
    )
    return registry.entries()


def test_thirteen_entries_parse(entries: list[Any]) -> None:
    assert len(entries) == 13
    assert len(list(CATALOG.glob("*.json"))) == 13


def test_every_file_has_digest_size_and_pinned_address(entries: list[Any]) -> None:
    for entry in entries:
        for resource in entry.resources:
            for file in resource.files:
                sha = file.sha256 or resource.sha256
                size = file.size or resource.size
                urls = file.urls or resource.urls
                assert sha and len(sha) == 64, entry.name
                assert size, entry.name
                assert len(urls) == 1, entry.name
                assert urls[0].startswith("hf://cansik/visiongraph/"), urls[0]
                assert urls[0].endswith(f"@{COMMIT}"), urls[0]


def test_openvino_models_are_bundles_of_xml_and_bin(entries: list[Any]) -> None:
    bundles = [e for e in entries if e.resources[0].is_bundle]
    assert len(bundles) == 3
    for entry in bundles:
        suffixes = sorted(Path(f.path).suffix for f in entry.resources[0].files)
        assert suffixes == [".bin", ".xml"], entry.name


def test_commercial_follows_the_licence(entries: list[Any]) -> None:
    flags = {e.license: set() for e in entries}
    for entry in entries:
        flags[entry.license].add(entry.commercial)
    assert flags == {"Apache-2.0": {True}, "AGPL-3.0 or Ultralytics Enterprise": {False}}
    assert sum(e.commercial for e in entries) == 8


def test_every_entry_has_one_family(entries: list[Any]) -> None:
    families = {"object-detection": 6, "pose-estimation": 4, "segmentation": 3}
    counted = {family: 0 for family in families}
    for entry in entries:
        assert len(entry.purpose) == 1, entry.name
        counted[entry.purpose[0]] += 1
    assert counted == families


def test_nothing_is_recommended(entries: list[Any]) -> None:
    assert not any(e.recommended for e in entries)
