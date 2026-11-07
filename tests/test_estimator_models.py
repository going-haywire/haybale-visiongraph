"""Estimator nodes take their model from a MODEL_REF port and never download by themselves."""

from __future__ import annotations

import inspect
import json
import os
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

import numpy as np
import pytest

import haybale_visiongraph
from haybale_image.value import ImageValue
from haybale_models.resolver import ModelMissing
from haybale_models.value.model_ref import ModelRef
from haybale_visiongraph.nodes import base_estimator_node as base

CATALOG = Path(haybale_visiongraph.__file__).parent / "catalog"
PREFIX = "haybale-visiongraph:catalog:"


class _Wrapper:
    node: Any = None
    graph = None
    state = None
    is_cleaned_up = False

    def __init__(self) -> None:
        self.warnings: dict[str, list[Any]] = {}

    def mark_as_structuraly_dirty(self) -> None:
        pass

    def redraw(self) -> None:
        pass

    def replace_warnings(self, kind: str, warnings: list[Any]) -> None:
        self.warnings[kind] = warnings


def _families() -> list[type]:
    from haybale_visiongraph.nodes.object_detector_node import ObjectDetectorNode
    from haybale_visiongraph.nodes.pose_estimator_node import PoseEstimatorNode
    from haybale_visiongraph.nodes.segmentation_node import SegmentationNode

    return [ObjectDetectorNode, SegmentationNode, PoseEstimatorNode]


def _all_specs() -> list[tuple[str, Any]]:
    return [(key, spec) for cls in _families() for key, spec in cls.MODELS.items()]


def _build(cls: type) -> Any:
    wrapper = _Wrapper()
    node = cls(node_id="test-node", wrapper=wrapper)
    wrapper.node = node
    node.init()
    node._regenerate_promoted_ports()
    node.post_init()
    return node


def _choose(node: Any, key: str) -> None:
    node.ports["model"].set_value(ModelRef(catalog=key))


def _entry_files(key: str) -> dict[str, Path]:
    document = json.loads((CATALOG / f"{key.removeprefix(PREFIX)}.json").read_text())
    resource = document["resources"][0]
    if "files" in resource:
        return {f["path"]: Path("/models") / f["path"] for f in resource["files"]}
    name = resource["urls"][0].rsplit("/", 1)[1].split("@")[0]
    return {"": Path("/models") / name}


class _Estimator:
    def __init__(self) -> None:
        self.released = 0
        self.setups = 0

    def setup(self) -> None:
        self.setups += 1

    def release(self) -> None:
        self.released += 1


def _resolved(key: str = "k1", files: dict[str, Path] | None = None) -> Any:
    return SimpleNamespace(files=files or {"": Path("/models/m")}, key=key)


def test_every_entry_has_a_spec_and_every_spec_an_entry(library_system: Any) -> None:
    stems = {p.stem for p in CATALOG.glob("*.json")}
    assert {key.removeprefix(PREFIX) for key, _spec in _all_specs()} == stems


@pytest.mark.parametrize("cls", _families(), ids=lambda c: c.__name__)
def test_each_family_lists_only_its_own_entries(library_system: Any, cls: type) -> None:
    for key in cls.MODELS:
        document = json.loads((CATALOG / f"{key.removeprefix(PREFIX)}.json").read_text())
        assert document["purpose"] == [cls.FAMILY]


@pytest.mark.parametrize("cls", _families(), ids=lambda c: c.__name__)
def test_the_port_is_catalog_only_and_filters_on_the_family(library_system: Any, cls: type) -> None:
    node = _build(cls)
    properties = node.ports["model"].widget_config["properties"]
    assert properties["catalog_only"] is True
    assert properties["filter"] == {"purpose": [cls.FAMILY]}
    assert "selection.model" not in node.ports


@pytest.mark.parametrize(("key", "spec"), _all_specs(), ids=lambda v: v if isinstance(v, str) else "")
def test_build_passes_local_assets_as_create_would(library_system: Any, key: str, spec: Any) -> None:
    from visiongraph.data.Asset import Asset
    from visiongraph.data.LocalAsset import LocalAsset

    module = __import__(spec.module, fromlist=[spec.cls_name])
    estimator_cls = getattr(module, spec.cls_name)
    calls: list[tuple[tuple, dict]] = []

    def record(self: Any, *args: Any, **kwargs: Any) -> None:
        calls.append((args, kwargs))

    config = getattr(getattr(module, spec.config_cls_name), spec.variant)
    with patch.object(estimator_cls, "__init__", record):
        estimator_cls.create(config)
        spec.build(_entry_files(key))
    (create_args, create_kwargs), (args, kwargs) = calls

    def same(theirs: Any, ours: Any) -> None:
        if isinstance(theirs, Asset):
            assert isinstance(ours, LocalAsset)
            assert Path(ours.path).name == theirs.name
        else:
            assert ours == theirs

    assert len(args) == len(create_args)
    assert set(kwargs) == set(create_kwargs)
    for theirs, ours in zip(create_args, args):
        same(theirs, ours)
    for name in create_kwargs:
        same(create_kwargs[name], kwargs[name])


def test_build_never_touches_repository_assets(library_system: Any) -> None:
    from visiongraph.data.RepositoryAsset import RepositoryAsset

    with patch.object(RepositoryAsset, "prepare", side_effect=AssertionError("would download")):
        for key, spec in _all_specs():
            module = __import__(spec.module, fromlist=[spec.cls_name])
            with patch.object(getattr(module, spec.cls_name), "__init__", lambda self, *a, **k: None):
                spec.build(_entry_files(key))


def test_a_new_node_starts_empty_and_asks(library_system: Any) -> None:
    node = _build(_families()[0])
    assert node.ports["model"].get_value() == ModelRef()
    with patch.object(base, "resolve_port", side_effect=ModelMissing(ModelRef(), [])):
        assert node.hb_ensure_estimator() is None
    assert node.ports["status"].get_value() == "Choose a model"


def test_a_missing_file_runs_nothing_and_says_so(library_system: Any) -> None:
    cls = _families()[0]
    node = _build(cls)
    key, spec = next(iter(cls.MODELS.items()))
    _choose(node, key)
    with (
        patch.object(base, "resolve_port", side_effect=ModelMissing(ModelRef(), [])),
        patch.object(base.ModelSpec, "build", side_effect=AssertionError("must not build")),
    ):
        assert node.hb_ensure_estimator() is None
    assert node.ports["status"].get_value() == "Model not downloaded"


def test_no_model_empties_the_outputs_and_does_not_continue(library_system: Any) -> None:
    node = _build(_families()[0])
    emitted: dict[str, Any] = {}
    node.out = lambda name, value: emitted.__setitem__(name, value)
    frame = ImageValue.from_array(np.zeros((2, 2, 3), np.uint8))
    with patch.object(base, "resolve_port", side_effect=ModelMissing(ModelRef(), [])):
        assert node.worker(SimpleNamespace(), frame=frame) is None
    assert emitted["count"] == 0
    assert list(emitted["result"].results) == []


def test_choosing_builds_once_and_changing_releases(library_system: Any) -> None:
    cls = _families()[0]
    node = _build(cls)
    keys = list(cls.MODELS)
    first, second = _Estimator(), _Estimator()
    with (
        patch.object(base, "resolve_port", return_value=_resolved()),
        patch.object(base.ModelSpec, "build", side_effect=[first, second]) as build,
    ):
        _choose(node, keys[0])
        assert node.hb_ensure_estimator() is first
        assert node.hb_ensure_estimator() is first
        assert build.call_count == 1
        _choose(node, keys[1])
        assert first.released == 1
        assert node.hb_ensure_estimator() is second
    assert second.setups == 1


def test_the_resolved_files_reach_the_build(library_system: Any) -> None:
    cls = _families()[0]
    node = _build(cls)
    key = next(iter(cls.MODELS))
    files = {"": Path("/models/x.onnx")}
    with (
        patch.object(base, "resolve_port", return_value=_resolved(files=files)),
        patch.object(base.ModelSpec, "build", return_value=_Estimator()) as build,
    ):
        _choose(node, key)
        node.hb_ensure_estimator()
    assert build.call_args.args[0] == files


def test_a_foreign_entry_warns_and_runs_nothing(library_system: Any) -> None:
    detector, _segmentation, pose = _families()
    node = _build(detector)
    _choose(node, next(iter(pose.MODELS)))
    with (
        patch.object(base, "resolve_port", return_value=_resolved()),
        patch.object(base.ModelSpec, "build", side_effect=AssertionError("must not build")),
    ):
        assert node.hb_ensure_estimator() is None
    assert node.ports["status"].get_value() == "This node cannot run this model"
    assert node.wrapper.warnings["model"]


def test_a_load_error_is_reported_and_not_retried_each_frame(library_system: Any) -> None:
    cls = _families()[0]
    node = _build(cls)
    keys = list(cls.MODELS)
    with (
        patch.object(base, "resolve_port", return_value=_resolved()),
        patch.object(base.ModelSpec, "build", side_effect=OSError("corrupt")) as build,
    ):
        _choose(node, keys[0])
        assert node.hb_ensure_estimator() is None
        assert node.hb_ensure_estimator() is None
        assert build.call_count == 1
        assert "corrupt" in node.ports["status"].get_value()
        _choose(node, keys[1])
        node.hb_ensure_estimator()
        assert build.call_count == 2


def test_a_replaced_file_is_tried_again_after_a_load_error(library_system: Any) -> None:
    cls = _families()[0]
    node = _build(cls)
    with (
        patch.object(base, "resolve_port", side_effect=[_resolved("k1"), _resolved("k2")]),
        patch.object(base.ModelSpec, "build", side_effect=[OSError("corrupt"), _Estimator()]) as build,
    ):
        _choose(node, next(iter(cls.MODELS)))
        assert node.hb_ensure_estimator() is None
        assert node.hb_ensure_estimator() is not None
        assert build.call_count == 2


def test_an_old_saved_model_setting_is_ignored(library_system: Any) -> None:
    """A saved label belongs to a setting that no longer exists: the node asks for a model."""
    cls = _families()[0]
    node = _build(cls)
    assert not hasattr(node, "selection")
    assert node.hb_current_spec() is None


def test_nothing_in_the_node_module_calls_create() -> None:
    assert ".create(" not in inspect.getsource(base)


@pytest.fixture
def real_state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, library_system: Any) -> Any:
    """A real catalog, index and model sources over temp volumes."""
    from haybale_models import consumer
    from haybale_models.keys import HF_VOLUME, MODELS_VOLUME
    from haybale_models.sources import builtin_sources
    from haybale_models.store.index import ModelIndex
    from haywire.core.catalog import CatalogRegistry
    from haywire.core.library.identity import LibraryIdentity
    from haywire.core.volumes import VolumeStore, get_volume_store, set_volume_store

    previous = get_volume_store()
    store = VolumeStore(tmp_path / "volumes.toml")
    set_volume_store(store)
    (tmp_path / "models").mkdir()
    (tmp_path / "hf").mkdir()
    store.ensure(MODELS_VOLUME, label="Models", description="", location=tmp_path / "models")
    store.ensure(HF_VOLUME, label="HF", description="", location=tmp_path / "hf")
    catalog = CatalogRegistry()
    catalog.add_folder(
        str(CATALOG),
        LibraryIdentity(
            label="Visiongraph",
            name="haybale-visiongraph",
            folder_path=str(CATALOG.parent),
            module_name="haybale_visiongraph",
        ),
    )
    index = ModelIndex()
    state = SimpleNamespace(
        index=index,
        catalog=catalog,
        hf_cache=tmp_path / "hf",
        sources=builtin_sources(index, hf_cache=lambda: tmp_path / "hf"),
    )
    monkeypatch.setattr(consumer, "models_state", lambda: state)
    yield state, tmp_path / "models"
    set_volume_store(previous)


def _place(state: Any, root: Path, file: dict[str, Any]) -> Path:
    """Put a sparse file of the right size in the models volume, recorded under its digest."""
    path = root / file["path"]
    path.touch()
    os.truncate(path, file["size"])
    state.index.add(path, file["sha256"], None)
    return path


def test_a_bundle_with_a_missing_part_runs_nothing(real_state: Any) -> None:
    state, root = real_state
    detector = _families()[0]
    key = PREFIX + "ssdlite_mobilenet_v2_fp32"
    files = json.loads((CATALOG / "ssdlite_mobilenet_v2_fp32.json").read_text())["resources"][0]["files"]
    xml = next(f for f in files if f["path"].endswith(".xml"))
    _place(state, root, xml)
    node = _build(detector)
    _choose(node, key)
    with patch.object(base.ModelSpec, "build", side_effect=AssertionError("must not build")):
        assert node.hb_ensure_estimator() is None
    assert node.ports["status"].get_value() == "Model not downloaded"


def test_a_complete_bundle_reaches_the_build_by_file_name(real_state: Any) -> None:
    state, root = real_state
    detector = _families()[0]
    key = PREFIX + "ssdlite_mobilenet_v2_fp32"
    files = json.loads((CATALOG / "ssdlite_mobilenet_v2_fp32.json").read_text())["resources"][0]["files"]
    paths = {f["path"]: _place(state, root, f) for f in files}
    node = _build(detector)
    _choose(node, key)
    with patch.object(base.ModelSpec, "build", return_value=_Estimator()) as build:
        assert node.hb_ensure_estimator() is not None
    assert build.call_args.args[0] == paths


OLD_MODEL_PORT = {
    "kwargs": {
        "registry_id": "STRING",
        "registry_key": "haywire-core:type:STRING",
        "label": "Model",
        "default": {"value": "YOLOv8-N (COCO)"},
        "widget_key": "haywire-core:widget:SelectWidget",
        "widget_config": {"properties": {"options": ["YOLOv8-N (COCO)", "YOLOv8-S (COCO)"]}},
        "id": "model",
        "port_type": "config",
        "order": 2,
        "on_change": "hb_on_model_change",
        "show_widget": "always",
    },
    "recipe": {"registry_key": "haywire-core:type:STRING"},
    "field_data": {"value": "YOLOv8-N (COCO)"},
}


def _saved_graph() -> tuple[Any, str]:
    """A graph holding a real detector node, and its saved form."""
    from haywire.core.graph.base import BaseGraph
    from haywire.core.graph.scheduler import SyncScheduler

    graph = BaseGraph(filestem="old", validation_scheduler=SyncScheduler())
    wrapper = graph.create_node_wrapper(_families()[0].class_identity.registry_key, position=(0, 0))
    assert wrapper is not None
    return graph, wrapper.node_id


def _reload(data: dict[str, Any]) -> Any:
    from haywire.core.graph.base import BaseGraph
    from haywire.core.graph.scheduler import SyncScheduler

    graph = BaseGraph(filestem="old", validation_scheduler=SyncScheduler())
    assert graph.load_from_dict(data)
    return graph


@pytest.mark.parametrize("old_id", ["model", "selection.model"])
def test_an_old_graph_opens_with_the_new_empty_port(library_system: Any, old_id: str) -> None:
    from haybale_models.types.model_ref import MODEL_REF

    graph, node_id = _saved_graph()
    data = graph.to_dict()
    ports = data["nodes"][node_id]["node_data"]["ports"]
    ports.pop("model")
    old = json.loads(json.dumps(OLD_MODEL_PORT))
    old["kwargs"]["id"] = old_id
    ports[old_id] = old

    node = _reload(data).get_node_wrapper(node_id).node

    assert node.ports["model"].type_cls is MODEL_REF
    assert node.ports["model"].get_value() == ModelRef()
    assert node.ports["model"].widget_config["properties"]["catalog_only"] is True
    assert "selection.model" not in node.ports
    with patch.object(base, "resolve_port", side_effect=ModelMissing(ModelRef(), [])):
        assert node.hb_ensure_estimator() is None
    assert node.ports["status"].get_value() == "Choose a model"


def test_a_chosen_model_survives_save_and_load(library_system: Any) -> None:
    graph, node_id = _saved_graph()
    cls = _families()[0]
    key = next(iter(cls.MODELS))
    graph.get_node_wrapper(node_id).node.ports["model"].set_value(ModelRef(catalog=key))

    node = _reload(graph.to_dict()).get_node_wrapper(node_id).node

    assert node.ports["model"].get_value() == ModelRef(catalog=key)
    assert node.hb_current_spec() is cls.MODELS[key]


def test_a_stray_value_on_the_port_reads_as_no_model(library_system: Any) -> None:
    node = _build(_families()[0])
    with patch.object(node.ports["model"], "get_value", return_value="YOLOv8-N (COCO)"):
        assert node.hb_current_ref() == ModelRef()


MEDIAPIPE = PREFIX + "pose_landmarker_full"


def _failing_pose_node() -> tuple[Any, Any]:
    """A pose node on a model that has just failed to load, and its patch of the build."""
    node = _build(_families()[2])
    _choose(node, MEDIAPIPE)
    return node, patch.object(base.ModelSpec, "build", side_effect=[OSError("bad"), _Estimator()])


def test_fixing_a_build_setting_retries_after_a_load_error(library_system: Any) -> None:
    node, build = _failing_pose_node()
    with patch.object(base, "resolve_port", return_value=_resolved()), build as called:
        assert node.hb_ensure_estimator() is None
        node.inference.min_score = 0.77  # read at build time by this backend
        assert node.hb_ensure_estimator() is not None
    assert called.call_count == 2


def test_stopping_and_starting_retries_after_a_load_error(library_system: Any) -> None:
    node, build = _failing_pose_node()
    with patch.object(base, "resolve_port", return_value=_resolved()), build as called:
        assert node.hb_ensure_estimator() is None
        node.on_shutdown(SimpleNamespace())
        assert node.hb_ensure_estimator() is not None
    assert called.call_count == 2


def test_removing_and_fetching_again_retries_after_a_load_error(library_system: Any) -> None:
    """A pinned entry keeps its key when its corrupt file is replaced by a good one."""
    node, build = _failing_pose_node()
    outcomes = [_resolved(), ModelMissing(ModelRef(), []), _resolved()]
    with patch.object(base, "resolve_port", side_effect=outcomes), build as called:
        assert node.hb_ensure_estimator() is None
        assert node.hb_ensure_estimator() is None
        assert node.ports["status"].get_value() == "Model not downloaded"
        assert node.hb_ensure_estimator() is not None
    assert called.call_count == 2


def test_the_load_error_stays_readable_on_later_frames(library_system: Any) -> None:
    node, build = _failing_pose_node()
    with patch.object(base, "resolve_port", return_value=_resolved()), build:
        node.hb_ensure_estimator()
        node.hb_update_status("No valid frame")
        assert node.hb_ensure_estimator() is None
    assert "bad" in node.ports["status"].get_value()


def test_the_library_subscribes_to_haybale_models() -> None:
    import tomllib

    document = tomllib.loads((CATALOG.parent / "haybale.toml").read_text())
    assert "haybale_models" in str(document)
    linked = next(
        value["linked_libraries"]
        for value in [document, *[v for v in document.values() if isinstance(v, dict)]]
        if "linked_libraries" in value
    )
    assert "haybale_models" in linked
