# haybale-visiongraph — design notes

Working notes for the OAK-D / depth-camera expansion. Design decisions resolved
in the inquisition interview; rationale kept here. Three terminology ambiguities
(frame/Frame, depth map/buffer, "multiframe") are flagged in
`docs/reference/glossary.md` ("Flagged ambiguities"); per-datatype defs deferred
to `datatype-canon.md` once the code exists.

# Estimator expansion (third inquisition — IN PROGRESS)

Adding vision **estimators** to the library: nodes that take an image and return
a list of results (object detection, instance segmentation, human pose). Wraps
visiongraph's `estimator.spatial.*` classes. Source ref:
`/Volumes/Ddrive/03_personal/visiongraph/visiongraph/estimator/spatial/`.

## Vocabulary (this expansion)

- **Estimator** — a visiongraph object that does `create(Config.VARIANT)` →
  `setup()` → `process(frame: np.ndarray) -> ResultList[...]` → `release()`.
  Image in, result-list out. (Distinct from a haywire *node* — one family node
  fronts many estimators.)
- **Result** — a `visiongraph.result.BaseResult`; carries `.annotate(image)` and
  (for spatial results) `.map_coordinates(...)`. `ResultList` is itself a
  `BaseResult` (a `list` subclass), so it annotates the whole batch.
- **Estimator family node** — one haywire node per result-subtype family
  (Object Detector / Segmentation / Pose), fronting every curated backend in
  that family via a model dropdown. NOT one node per concrete estimator.

## Resolved decisions

### Q1 — node granularity: one node per estimator *family* (not per class)

A `model` enum config picks the concrete backend; the node maps the choice to a
`(EstimatorClass, ConfigVariant)` internally. Mirrors visiongraph's own examples
(swap one `.create()` line). ~3 nodes for v1, not ~40.

### Q2 — result datatypes: a WIRED SUBTYPE HIERARCHY (not siblings, not one flat)

Investigated the visiongraph result tree — it is **linear**, not parallel:
`ClassificationResult → ObjectDetectionResult → LandmarkDetectionResult →
PoseLandmarkResult` (and `InstanceSegmentationResult ⊂ ObjectDetectionResult`).
So the haywire types mirror that lineage:

```
VISION_RESULT          (base; wraps ResultList[BaseResult]; carries .annotate)
└── DETECTION_RESULT    (ResultList[ObjectDetectionResult]; bbox, score, class, tracking)
    ├── SEGMENTATION_RESULT  (ResultList[InstanceSegmentationResult]; + mask)
    └── LANDMARK_RESULT      (ResultList[LandmarkDetectionResult]; + landmarks)
        └── POSE_RESULT          (ResultList[PoseLandmarkResult]; + named joints, connections)
```

**Why a wired hierarchy works (verified against the framework):** a derived
`@type` is auto-compatible with any registered ancestor type via an
`issubclass()` passthrough — NO adapter needed. Confirmed at
`packages/haywire-core/src/haywire/core/adapter/factory.py:223`
(`if issubclass(source_type, sink_type): return (ReturnAdapter(), None)`) and the
`@type` decorator's parent-identity tracking at
`packages/haywire-core/src/haywire/core/types/decorator.py:108-117`. The
`issubclass` check is on the IType classes, so it works for `BaseType`
dataclasses, not just primitives. Reverse (ancestor→descendant) is correctly
rejected unless an explicit adapter is written.

Payoff: ONE generic Annotate node and ONE Tracker node declare the base
`VISION_RESULT` inlet and accept all three families for free (subtype→ancestor
passthrough); a pose-specific consumer (e.g. "Get Joint by Name") declares
`POSE_RESULT` and only pose lists can wire in. Gets B's universal connectivity
AND A's type-gating, via the inheritance chain — mirroring visiongraph 1:1.

### Q3 — result wrapper internals: store the visiongraph `ResultList` DIRECTLY

The `@type` dataclass holds the visiongraph `ResultList` as its single field
(e.g. `results: ResultList = field(default_factory=ResultList)`). The whole point
of wrapping visiongraph is reusing `.annotate()`, the tracker, and
`.map_coordinates()` — re-extracting fields into neutral Python throws that away.
`store_strategy=NEVER` (these never serialize, exactly like frames), so there's
no serialization coupling. Importing `ResultList`/`BaseResult` in the type module
is free (library already depends on `visiongraph[all]`, like `frame_type.py`
imports numpy).

### Q4 — image inlet type: `RGB_FRAME`

`process(np.ndarray)` wants a colour array. Inlet typed `RGB_FRAME`: the natural
producer output, gets `GRAY_FRAME` for free via the existing
`GRAY_FRAME→RGB_FRAME` adapter, and correctly refuses `DEPTH_FRAME` (depth is not
a detection input). Node does `frame.data → process()`.

### Q5 — model selection: one curated FLAT enum per family node

`model` dropdown lists curated variants across backends in the family; an
internal `{label: (EstimatorClass, ConfigVariant)}` dict maps the choice to a
`.create(...)` call. Curation is a feature — only expose variants that work with
plain `.create(config)` and no exotic constructor args. (Rejected a cascading
backend→variant pair as needless friction for a once-made choice.)

### Q6 — the three v1 families over ONE shared `BaseEstimatorNode`

Inventory finding: across detection, segmentation, AND pose, every curated
estimator shares the identical `create(Config) → setup() → process(frame) →
ResultList → release()` lifecycle. Only two things differ per node: the dispatch
map and the output `@type`. So the architecture is **one shared base node class**
with thin subclasses:

```
BaseEstimatorNode(BaseNode)        # all lifecycle in ONE place
  ├─ ObjectDetectorNode  → DETECTION_RESULT     (YOLOv5/8/8-OBB, DEIMv2, SSD, DETR, CenterNet, CrowdHuman)
  ├─ SegmentationNode    → SEGMENTATION_RESULT  (MaskRCNN, MODNet, Yolact, YOLOv8-Seg)
  └─ PoseEstimatorNode   → POSE_RESULT          (MediaPipe, MoveNet, LitePose, EfficientPose, Ultralytics, LiteHRNet, OpenPose, AE, KAPAO, MobileNetV2)
```

Base owns (once): `RGB_FRAME` inlet, `model` enum config + rejig, lazy `setup()`,
`process(frame.data)`, wrapping the `ResultList` into the subclass `@type`,
score-threshold config, `release()` on teardown/reload. Each subclass declares
only `RESULT_TYPE` + `MODELS` dict.

**Deferred to fast-follow** (bespoke `__init__`, distinct outputs — do NOT force
into v1):
- Hand / Face-mesh landmark nodes (bespoke construction; carry handedness / mesh)
  → their own subtypes when built.
- Emotion / HeadPose — these are `RoiEstimator`s: they take a *detection result +
  frame*, not just a frame. Different inlet contract entirely.

### Q7 — estimator lifecycle: LAZY `setup()` on first frame (not control inlets)

An estimator is a *transform*, not a *device* — it has no resource to hold open
between frames except the loaded weights, which a cache holds. So: `setup()`
(model load/download — slow, network+disk) runs lazily on the **first**
`worker()` call, result cached; changing the `model` config releases the old
estimator and clears the cache so the next frame reloads. `release()` fires on
`on_shutdown` / `on_teardown` / model-change for clean GPU/file handles. NO
explicit load/unload EXEC inlets (that's device-idiom cargo-culted onto a
transform) and NOT `on_startup` (would couple model choice to Flow restart). Graph
stays minimal: just wire frame → estimator → consumer.

### Q8 — threading: SYNCHRONOUS inference in `worker()` (not off-thread)

The node is a per-frame CONTROL transform (`execute` EXEC inlet pulsed by upstream
`frame_ready`, a `frame` data inlet) — same shape as `FrameDisplayNode`. `process()`
(50–500ms) runs **synchronously** in `worker()`; returns `result_ready`. The
camera's capture thread is what blocks, so the pipeline self-throttles to
inference speed for free, and frame→result ordering is trivially correct. The
viewer queue already provides backpressure (`frame_queue_size=1,
block_on_full=False` → newest-frame-wins, drops under load). Off-threading
(latest-frame queue + async result emission) re-implements the camera's threading
inside a transform and injects async emission into control flow — deliberate
fast-follow only if a specific slow model demands it, NOT v1.

### Q9 — busy feedback: STATUS LABEL (node-busy highlight is a FRAMEWORK concern)

Constraint: there is no built-in node "busy" spinner wired to the skin, and a
synchronous `worker()` (Q8) has **no yield point** — you cannot animate a progress
bar *during* `process()`. You *can* push a status value before/after via
`port.set_value()` (re-renders the bound widget live — verified at
`packages/haywire-core/src/haywire/core/types/port.py:272`; this is how the camera
status label updates from its thread). So:

- `SimpleLabelWidget` status, same idiom as the camera nodes.
- `"Loading model…"` before first-frame `setup()` (the slow, separable step).
- Rolling `"N results · Xms"` after each inference (last-frame timing). No
  per-frame "Inferring…" mid-call — the synchronous design can't deliver it.

A real "this node is executing" visual belongs in the **framework**, driven from
the existing-but-unsurfaced `is_executing` flag
(`packages/haywire-core/src/haywire/core/node/node_wrapper.py:46`), surfaced in the
skin. **FOLLOW-UP (framework, possible ADR — cross-cutting UI capability, not a
visiongraph concern):** wire a node-busy highlight from `is_executing`. Out of
scope for these nodes. (Rejected: a display-only off-thread spinner toggling a
flag around an already-blocking call — spends a thread to fake motion, and the
toggle's render may stall because the main thread is busy.)

### Q10 — Annotate node: `PooledType[VISION_RESULT]` result inlet + `RGB_FRAME` frame inlet

Contract found: visiongraph results carry **normalized** coords (annotate does
`x * w`), and `.annotate(image)` **mutates the image in place** (returns None).
Canonical pipeline annotates onto the same frame fed to `process()`.

The generic Annotate node (the `VISION_RESULT` consumer) takes:
- **`result`: `PooledType[VISION_RESULT]`** — inlet-only, multi-connection.
  Accepts any MIX of `DETECTION_RESULT` / `SEGMENTATION_RESULT` /
  `LANDMARK_RESULT` / `POSE_RESULT` outlets *simultaneously*: each is a subtype of
  `VISION_RESULT`, and a pooled inlet checks compatibility against its ELEMENT
  type (verified: `PooledField.get_stored_type()` returns `element_type_cls`, and
  the live `PooledType[MULTIFRAME_CALLBACK]` ← scalar callback outlets proves
  scalar-source→pooled-sink works via the Q2 `issubclass` passthrough). So one
  Annotate node overlays detections + pose + masks from several estimators onto
  one frame — the user's key insight.
- **`frame`: `RGB_FRAME`** — single inlet, the target image.

Worker: **COPY** the frame first (in-place `.annotate()` would corrupt the shared
`RGB_FRAME` value flowing to other consumers), iterate the pooled dict
`{source_id: ResultList}`, call `result_list.annotate(frame_copy, **opts)` for
each, outlet the composited `RGB_FRAME`.

Rejected: (B) estimator forwards the frame alongside the result — bloats every
estimator outlet for a feature only the annotate path uses; (C) result type
carries its source frame — fuses pixels into the coordinate abstraction, drags a
frame through count/get-joint consumers that only want coords.

NOTE this also means: the `result` inlet being pooled is the general shape — even
single-result annotate just has one pooled entry. No separate single-inlet
variant needed.

### Q11 — `min_score` is an estimator config; Tracker is its OWN node

Source separation: `min_score` is a per-estimator attribute
(`ScoreThresholdEstimator.min_score`, set on the object) — intrinsic to the
estimator, so it's a config on the estimator node. **Tracking** is a wholly
separate stateful object (`BaseObjectDetectionTracker.process(ResultList) ->
ResultList`, assigns `tracking_id` across frames) → its own node, backend via the
same curated-enum pattern (Centroid / Flate / Motpy). Mirrors visiongraph's
pipeline staging: `network.process()` → `tracker.process()` → annotate.
Composes: detector → tracker → (pooled) annotate.

### Q12 — Tracker node: `result_type` config retypes inlet+outlet (chosen: B)

The tracker preserves runtime subtype — it stores/returns `t.reference`, the
ORIGINAL result object (verified `FlateTracker.process`), so a pose passed in
comes back as the same pose object with joints intact, even though visiongraph
types the return `ResultList[ObjectDetectionResult]`. But haywire ports are
statically typed, so the node needs a declared type per port.

Decision: a **`result_type` enum config** (default `DETECTION_RESULT`; also
`POSE_RESULT`, `SEGMENTATION_RESULT`) drives a `rejig` that retypes BOTH the
inlet and the outlet to the chosen subtype. One tracker node serves all families.

Why this is elegant, not convoluted (verified against the framework):
- `rejig` retype = re-add same port id with a different type; edges on a refreshed
  port are preserved IFF still compatible, else detached
  (`data.py:_pop` lines 387-398; `rejig` lines 408-452).
- On switch `DETECTION_RESULT → POSE_RESULT`: the narrower inlet can no longer be
  fed by a plain detector outlet (ancestor→descendant rejected) → that edge breaks
  CORRECTLY; the outlet wired to a pooled `VISION_RESULT` annotate inlet survives
  (pose ⊂ vision); a `DETECTION_RESULT`-specific downstream breaks CORRECTLY. Edges
  break exactly when the subtype relationship genuinely fails — the config cannot
  produce an inconsistent graph. That's the signature of an elegant feature.
- The one dependency — visiongraph preserving subtype at runtime — is a VERIFIED
  contract (returns the original object), not a hope.

Default stays `DETECTION_RESULT` (the common case, type-safe); the enum widens it
deliberately. (Rejected A: single fixed `DETECTION_RESULT` — loses pose-after-
tracking for no real saving now that rejig-retype is shown safe.)

### Q13 — import discipline: light result imports top-level, heavy backends lazy

Measured (real imports):
- `visiongraph.result.{ResultList,BaseResult}` → **0.45s**. Light, and needed as
  dataclass field types → import at the type module's TOP. No lazy gymnastics for
  a sub-second cost.
- `visiongraph.estimator.spatial.YOLOv8Detector` → **2.6s** (pulls the ML stack).
  Heavy → **lazy-import inside the `setup()` path** (the worker's first-frame
  load), exactly the OAK node precedent (`oak_d_camera_node.py` imports
  `OakDInput` inside `hb_handle_start`, not at module top). Top-level backend
  imports would add ~2.6s × N backends to every library load AND hot-reload cycle.

No pyproject change: `visiongraph[all]` already ships `estimator.spatial.*`;
`depthai~=2.30` stays for the camera side. `@library(dependencies=["haybale_core"])`
unchanged — visiongraph is not a haywire library. Run `/haywire-dep-check` after
implementing per CLAUDE.md.

### Q14 — config vs. NodeSettings split: by FREQUENCY OF USE (governing principle)

The axis is NOT "operational vs. styling" — it's **how often a user reaches for
it**. Frequently-touched knobs → first-class **config ports** (visible on the node
face, immediately reachable, AND optionally wire-able from an upstream value).
Set-once long-tail → **NodeSettings** inner class (panel-rendered, stored only when
overridden, no port clutter). This matches the existing nodes (camera puts
`camera_index`/`width`/`fps` as config; viewer tuning lives in the widget).

Annotate node, applying the test:
- **config ports:** `min_score` (FLOAT, default 0 — reached for constantly to hide
  low-confidence overlays; bonus: wire-able from a slider) + `show_info` (BOOL,
  default True — label decluttering, toggled often).
- **`NodeSettings` (`class style(NodeSettings)`):** `show_bounding_box`,
  `marker_size`, `stroke_width`, colors, connection toggles — set once to taste.

Worker merges config + settings into the `**kwargs` dict passed to every pooled
`ResultList.annotate(frame_copy, **kwargs)`. Safe because every visiongraph
annotate signature ends in `**kwargs` — a subtype that ignores a knob absorbs it
harmlessly. Subtype-specific knobs not surfaced keep visiongraph defaults.

This frequency principle is the RULE for all nodes in this expansion (estimator
`model`/`min_score` are config; deep tuning would be settings).

### Registration — folder-drop only, NO `__init__.py` changes (confirmed by inspection)

The Library already scans `types/`, `adapters/`, `nodes/` (+ widgets/skins) via
`add_folder_to_registry` (`haybale_visiongraph/__init__.py:43-55`). New result
types → `types/`; estimator/tracker/annotate nodes → `nodes/`; any new adapters →
`adapters/`. `@library(dependencies=["haybale_core"])` unchanged. Nothing to wire
in registration. (NodeSettings need no registration — scanned off the `@node`
class.)

### Q15 — names / labels / menus / colors (pinned for a clean first build)

Result types (`registry_id` = class name = persisted key; `_RESULT` suffix mirrors
the `_FRAME` convention):

| Class (registry_id)   | label                 | color     |
|-----------------------|-----------------------|-----------|
| `VISION_RESULT`       | "Vision Result"       | `#455a64` |
| `DETECTION_RESULT`    | "Detection Result"    | `#f57c00` |
| `SEGMENTATION_RESULT` | "Segmentation Result" | `#7b1fa2` |
| `LANDMARK_RESULT`     | "Landmark Result"     | `#00897b` |
| `POSE_RESULT`         | "Pose Result"         | `#0288d1` |

Nodes (`menu="vision/<area>"`, extending existing `input`/`event`/`info`):

| Class                | label              | menu              |
|----------------------|--------------------|-------------------|
| `ObjectDetectorNode` | "Object Detector"  | `vision/estimate` |
| `SegmentationNode`   | "Segmentation"     | `vision/estimate` |
| `PoseEstimatorNode`  | "Pose Estimator"   | `vision/estimate` |
| `TrackerNode`        | "Tracker"          | `vision/process`  |
| `AnnotateNode`       | "Annotate Results" | `vision/draw`     |

Three small menu groups read as a left-to-right pipeline: estimate → process → draw.

---

## BUILD CHECKLIST (all design decisions resolved — ready to implement)

- [ ] `types/result_type.py`: `VISION_RESULT` base + `DETECTION_RESULT` →
      `{SEGMENTATION_RESULT, LANDMARK_RESULT → POSE_RESULT}` wired subtype chain;
      each `@type(store_strategy=NEVER, flow_type=DATA)`, single field holding the
      visiongraph `ResultList` (import `ResultList`/`BaseResult` at module top —
      0.45s, Q13). Mirror `BaseFrame` style.
- [ ] `nodes/base_estimator_node.py`: shared `BaseEstimatorNode` — `RGB_FRAME`
      inlet, `model` enum config (+ rejig/cache-invalidate on change), `min_score`
      config, lazy `setup()` on first frame (Q7), synchronous `process()` (Q8),
      wrap `ResultList` into subclass `RESULT_TYPE`, status label (Q9),
      `release()` on shutdown/teardown/model-change. Subclasses declare only
      `RESULT_TYPE` + `MODELS` dict. Lazy-import backends inside setup (Q13).
- [ ] `nodes/object_detector_node.py`, `segmentation_node.py`,
      `pose_estimator_node.py` — thin subclasses (Q6 model lists).
- [ ] `nodes/tracker_node.py`: `result_type` enum config rejigs inlet+outlet
      (Q12); curated backend enum (Centroid/Flate/Motpy); `DETECTION_RESULT`
      default.
- [ ] `nodes/annotate_node.py`: `PooledType[VISION_RESULT]` result inlet +
      `RGB_FRAME` frame inlet; COPY frame, iterate pooled dict, `.annotate(**kwargs)`
      each, outlet `RGB_FRAME` (Q10). `min_score`+`show_info` config; `class
      style(NodeSettings)` for the styling long-tail (Q14).
- [ ] No `pyproject.toml` / `__init__.py` changes (Q13 + registration finding).
- [ ] After build: `/haywire-dep-check`, then `uv run pytest` +
      ruff/mypy baseline per CLAUDE.md.

## OPEN QUESTIONS — none (design complete)

- FOLLOW-UP (framework, separate from this work): node-busy highlight from
  `is_executing` (see Q9) — possible ADR, cross-cutting UI capability.

---

## Webcam joins the 3D-camera family (second inquisition)

Goal: a webcam should be usable as the **RGB-only member** of the camera family,
feeding the *same* shared `NumpyFrameEventNode`. One shared event node, per-device
emit nodes (OAK-D, webcam, later Azure/RealSense).

- **Reuse `MULTIFRAME_CALLBACK`** (not a new `RGBFRAME_CALLBACK`): goal requires
  one subscription type flowing out of the single shared event node, so a second
  callback type would split it. The webcam emit node's pooled inlet is
  `PooledType[MULTIFRAME_CALLBACK]`, same as OAK.
- **Webcam honours only `rgb`**, silently ignores depth/ir requirements (mirrors
  an OAK with a stream off → unfired outlet). Reads the requirement union; if no
  subscriber wants rgb, it does not capture (`hb_any_rgb_requested` guard).
- **Payload key changed** `"frame"` → `"rgb"` to match the OAK open-keyed payload.
- **`WebcamFrameEventNode`: deprecated, not deleted.** Marked with
  `deprecation_warning=` on `@node` (steers users to `NumpyFrameEventNode`), but
  **migrated to the new contract** — subscribes via `MULTIFRAME_CALLBACK`
  (`rgb=True`) and reads `payload["rgb"]` — so it stays *functional* against the
  updated webcam emit node, not just a dead badge.
- **"multiframe" = capability, not mandate** — documented on the type docstring +
  glossary; a single-stream webcam using one flag is a valid degenerate case.
- **Future:** when camera #3 lands, extract a shared emit-node base class
  (union/dispatch/thread lifecycle once; per-device `_open`/`_read` overrides).

## v1 build checklist

- [ ] Shared base frame type; `RGB_FRAME` / `DEPTH_FRAME` / `GRAY_FRAME` derive
      dims as properties (no cached fields, no `to_dict`/`from_dict`).
- [ ] Rename `FRAME → RGB_FRAME` across the 3 existing nodes + `NumpyViewerWidget`
      `compatible_types` + `types/__init__.py` + docs; then `/check-rename`.
- [ ] `GRAY_FRAME ↔ RGB_FRAME` adapters. No `DEPTH_FRAME` adapter.
- [ ] `MULTIFRAME_CALLBACK` (`BaseType` dataclass, `flow_type=CALLBACK`,
      `name` + stream-requirement fields).
- [ ] `OakDCameraNode` (device-specific; wraps `OakDInput`; EXEC start/stop;
      `on_startup` reads union; capture thread; open-keyed payload).
- [ ] `NumpyFrameEventNode` (shared/agnostic; 3 bool flags → `rejig` + requirement).
- [ ] `depthai` explicit in `pyproject.toml`; then `/haywire-dep-check`.
- [ ] `NumpyViewerWidget` → `compatible_types=[RGB_FRAME]`.

## OAK-D camera support — resolved decisions

### Integration boundary (Q1)
Wrap visiongraph's `OakDInput` (not raw `depthai`, not a reimplementation).
Haywire has no argparse `Namespace`, so configure the device by setting its
**public attributes** directly before `setup()` — bypass `configure(args)`.
Source ref: `/Volumes/Ddrive/03_personal/visiongraph/visiongraph/input/OakDInput.py`.

### Node shape (Q2, emit/event split)
Follow the existing webcam emit/event pattern:
- **Emit node** wraps `OakDInput`, runs its own capture thread, emits **one**
  `emit_callback` per frame carrying all active streams.
- **Event node** subscribes via CALLBACK; per-stream flags toggle which outlets
  appear (dynamic ports via `rejig`).

### Stream typing (Q4) — three distinct datatypes
Rename `FRAME` → **`RGB_FRAME`**; add **`DEPTH_FRAME`** and **`GRAY_FRAME`**.
- `RGB_FRAME`: 3-ch uint8 colour.
- `DEPTH_FRAME`: 1-ch **uint16 metric millimetres** (raw buffer, the measurement).
- `GRAY_FRAME`: 1-ch uint8 luminance (e.g. IR).
Distinct types so depth can't be silently wired into colour-expecting nodes.
Extract shared dataclass into a base frame type (one definition of
`data/timestamp/frame_number` + derived dims).

### width/height/channels (Q7) — derive, don't cache
`store_strategy=NEVER` means frames never serialize, so there is **no**
save/load round-trip for cached metadata to survive. Therefore width/height/
channels are **read-only @properties** derived from `data.shape`, not stored
fields. Drop the vestigial `to_dict`/`from_dict`. `RGB_FRAME` adopts this too on
rename. `DEPTH_FRAME` (2-D) reports `channels == 1`; null frames report 0.

### Adapters (Q5) — image types only
Register `GRAY_FRAME ↔ RGB_FRAME` only (channel replicate / luminance — always
safe to apply invisibly). **No adapter touches `DEPTH_FRAME`**: colourization is
lossy, parameterized (colormap/clip range), and display-only, so it must be a
**deliberate "Colorize Depth" node**, never an auto edge-time coercion. This is
what keeps the `DEPTH_FRAME` type split meaningful.

### Depth encoding (Q3) — carry raw, colourize downstream
Payload carries the **raw uint16 depth buffer** (`OakDInput.depth_buffer`), not
a colourized map. `depth_map` (JET/HSV) is a *display* artifact; colourizing in
the emit payload would permanently destroy the metric depth that is the whole
reason to use an OAK over a webcam.

### Payload format (Q6) — raw arrays, event node wraps
`emit_callback` payload dict:
`{"rgb": ndarray|None, "depth": ndarray_uint16|None, "ir": ndarray|None,
  "frame_number": int, "timestamp": float}`.
Raw numpy arrays + scalars only — keeps the capture thread free of type-system
imports. The **event node** constructs `RGB_FRAME`/`DEPTH_FRAME`/`GRAY_FRAME` in
its worker (where those types are imported anyway). Absent stream = `None`.

### Device lifecycle (Q9–Q11) — the key decision
Driven by demand, but **user controls activation**:
- **`on_startup`**: read the **requirement union** (which streams are demanded)
  from the Pooled CALLBACK inlet. Config-gathering only — does NOT open device.
- **`start` pulse**: open the device using the union gathered in `on_startup`.
- **`stop` pulse**: close the device.
- **`on_shutdown`**: close the device as a **fallback** if the user forgot to
  pulse `stop` before the flow tore down (the interpreter's producer-thread
  backstop).

**Requirement union** = union of streams demanded across all subscribed event
nodes, carried on the CALLBACK value, aggregated by the emit node's Pooled inlet.

**Trigger source (Q-final):** `start`/`stop` are EXEC inlets pulsed by upstream
control flow, exactly like `WebCameraNode`. `OakDCameraNode` is
`NodeType.CONTROL`, driven by a Start/Stop control chain — no auto-start, no
button widget.

**Why this is self-correcting:** changing an event node's stream flags is a
footprint change → marks the Flow dirty → framework stop→recompile→restart →
`on_shutdown` kills the old device → `on_startup` re-reads the union. The device
lands **stopped, awaiting a fresh `start`**. No surprise camera activation, no
manual "Stop/Start to apply" dance. And any new stream that's actually *used*
must be wired downstream — itself a graph edit that dirties the Flow — so the
restart is unavoidable anyway; the device-drops-to-stopped behaviour is free.

Do NOT copy the webcam node's habit of binding capture *only* to start/stop
inlets while ignoring the union — that's the precedent that would miss
requirement changes.

### CALLBACK-carries-requirements (user's key insight)
The emit node's Pooled CALLBACK inlet already gives it a live dict of every
subscribed event node. Extend the CALLBACK value to carry each event node's
stream requirements, so the emit node configures the device from demand rather
than from its own redundant config. (New CALLBACK-payload shape — TBD in build.)

### Rename FRAME → RGB_FRAME (Q13) — hard rename, no backward compat
Update all call sites in lockstep: the 3 existing nodes, `NumpyViewerWidget`
`compatible_types`, `types/__init__.py`, and docs. Run `/check-rename` for
string refs the IDE misses (docstrings, QUICKREF.md, OVERVIEW.md).

`registry_id` defaults to the class name (`decorator.py` `setdefault`), so the
rename changes the persisted key `visiongraph:FRAME` → `visiongraph:RGB_FRAME`.
**Safe to ignore**: grep found zero saved graphs referencing a `frame` port type
(repo + `~/.haywire/`), and no backward compat is wanted. Escape hatch if ever
needed: `@type(registry_id="...")` pins the key independent of class name — we
deliberately do NOT use it.

### MULTIFRAME_CALLBACK type (Q14–Q15) — the subscription carrier

A **visiongraph-local `BaseType` dataclass** (NOT a subclass of core `CALLBACK`),
declared with `flow_type=FlowType.CALLBACK`. Fields: `name: str` +
stream-requirement fields (e.g. `rgb: bool, depth: bool, ir: bool`, or a
`streams: set[str]`).

Why a dataclass works (verified against the framework):
- A callback edge is identified by `edge._edge_type == FlowType.CALLBACK`
  (`flow_assembly_manager.py:254`) — set by the `@type` decorator, NOT by
  subclassing `STRING`. So a `BaseType` with `flow_type=CALLBACK` IS a callback edge.
- The event name is read by the **node**, not the edge value: the event node
  does `CallbackEvent(event_name=self.value("...").name)` in `post_init`
  (cf. `webcam_frame_event_node.py:60`). A dataclass with a `name` field
  satisfies dispatch registration cleanly — no fighting STRING's
  "value-is-the-name" assumption.

Two payoffs over a bare CALLBACK + sidecar:
1. **Requirements ride the one subscription edge** (event outlet → emit's
   `PooledType[MULTIFRAME_CALLBACK]` inlet). No second parallel edge.
2. **Type-gating**: only OAK-compatible event nodes can wire into the OAK emit
   node — a plain webcam `CALLBACK` event node can't connect.

Two channels, opposite directions (do not conflate):
- **Subscription edge** (event → emit): carries `MULTIFRAME_CALLBACK`
  (name + requirements). The emit node unions `.streams` across the pooled
  entries in `on_startup`.
- **Runtime dispatch** (emit → event): `context.emit_callback(name, payload)` —
  the per-frame raw-array payload from Q6. NOT an edge; keyed by `name`. Unchanged.

### Node taxonomy — shared event node, per-device emit nodes (Q19–Q20)

**The event node is camera-AGNOSTIC; only emit nodes are device-specific.**
More 3D cameras are coming (Azure Kinect, RealSense, ZED) — they all extend
visiongraph's `BaseDepthCamera` with the same `CameraStreamType.{Color,Depth,
Infrared}` model, so the *streams* are a shared abstraction and only the *device
setup* differs.

- **`NumpyFrameEventNode`** (shared, one class): subscribes via
  `MULTIFRAME_CALLBACK` to ANY 3D-camera emit node. Exposes `rgb`/`depth`/`ir`
  outlets. Reused across all current and future 3D cameras.
- **Per-device emit nodes**: `OakDCameraNode` now; `AzureKinectEmitNode`,
  `RealSenseEmitNode`, … later. Each wraps its own visiongraph input class.

**Stream flags (Q19) — explicit config, user is source of truth.** Three bool
config flags (`rgb`/`depth`/`ir`) on the event node. Each `on_change` → `rejig`
that BOTH builds/removes the outlet AND sets the matching field in the
`MULTIFRAME_CALLBACK` requirement sent upstream. NOT derived from downstream
wiring (chicken-and-egg: can't wire to an outlet that doesn't exist yet).

**Shared contract (Q20) — fixed three, open-keyed payload.** The shared node's
contract is exactly `rgb`/`depth`/`ir` (the `BaseDepthCamera` common
denominator). If a device lacks a stream, its payload slot is `None`. The
runtime payload dict (Q6) is **open-keyed by stream name**, so a future
device-specific node can carry extra streams (e.g. RealSense second IR) by
adding a key — WITHOUT changing `MULTIFRAME_CALLBACK` or `NumpyFrameEventNode`.
The shared event node still only ever shows `rgb`/`depth`/`ir`.

**MULTIFRAME_CALLBACK meaning widens:** the type-gate is now "any 3D-camera emit
node ↔ the shared 3D event node" (not OAK-specific). The single type still
expresses it — all 3D emit nodes use it; the one event node consumes it.

### NumpyViewerWidget display path (Q17)

`compatible_types=[RGB_FRAME]` only — NOT all three.

- `GRAY_FRAME` displays via the `GRAY_FRAME → RGB_FRAME` adapter (Q5): wiring a
  gray outlet to the RGB-only viewer inlet auto-adapts at edge-build (channel
  replicate). The widget does NOT list `GRAY_FRAME` — the adapter is the
  sanctioned path; the widget must not duplicate that knowledge.
- `DEPTH_FRAME` cannot be wired to the viewer (no adapter, by design). Viewing
  depth requires the explicit Colorize-Depth node (emits `RGB_FRAME`), deferred
  to fast-follow. The absence of a depth view in v1 is intended discipline, not
  a gap — keeps colorization off the edge and out of the widget.

### Dependencies (Q18)

Add `depthai` **explicitly** to `pyproject.toml` `dependencies` (alongside the
existing `visiongraph[all]`). `OakDInput` is wrapped by this library's own code,
so `depthai` is now a *direct* import → must be a direct, explicit, pinnable
dependency, not relied upon transitively via visiongraph's `[all]` extra.
After adding, run `/haywire-dep-check` to verify the `@library(dependencies=[...])`
declaration (uses *package* names) matches actual imports.

Deferred: an optional `[oak]` extra to spare non-OAK users the heavy native
wheel — not worth it now because `visiongraph[all]` already drags `depthai` in
regardless; would require slimming visiongraph's extras too + import-guards.

**TRAP — must set `enable_color_still=True` when color is enabled.**
visiongraph's `DepthAIBaseInput.setup()` unconditionally requests the
`rgb_still` output queue inside its `if self.enable_color:` block, but only
*creates* the still output node when `enable_color_still` is True. With color on
and still off (the natural default), this throws at runtime:
`Queue for stream name 'rgb_still' doesn't exist`. The OAK emit node sets
`cam.enable_color_still = True` whenever RGB is requested. We never call
`capture_color_still()`, so the only cost is the extra still node at setup; the
per-frame `read()` path is unaffected. Verified working on real OAK-D hardware
(OV9782 sensor) — RGB + IR streams flow and the GRAY→RGB adapter renders IR.

**TRAP — depthai must be v2, pinned `~=2.30`.** visiongraph's DepthAI input
stack (`DepthAIBaseInput`, `OakDInput`) is written against the depthai **v2**
API: `dai.RawCameraControl` (referenced in `DepthAIBaseInput.__init__`, so it
throws at *construction*), `XLinkOut`, `getOutputQueue`, the `pipeline.create` +
queue model. depthai **v3** is an incompatible API rewrite that removed these;
an unpinned `depthai` resolves to v3 and fails with
`module 'depthai' has no attribute 'RawCameraControl'`. visiongraph itself pins
`depthai~=2.30` (gated to non-Darwin OR arm64 — note: no v2 wheel on Intel
macOS). Our pyproject pins `depthai~=2.30` to match.

## Scope (Q16)

### v1 — in scope

- Emit node config: device selection (mxid/name), the three stream enables
  (driven by the requirement union, not standalone toggles), color resolution.
- Depth uses `OakDInput`'s defaults: HIGH_DENSITY preset, 7x7 median filter,
  left-right-check on. Produces working depth out of the box, no tuning ports.
- The three frame datatypes + GRAY↔RGB adapters + MULTIFRAME_CALLBACK + the
  emit/event pair with the full lifecycle.

### v1 — explicit non-goals (fast-follow or later)

- **Depth-quality knobs** (depth preset mode, subpixel, extended disparity, IR
  laser/flood intensity) — clean fast-follow; independent additions, change no
  settled architecture.
- **`distance(x, y)` query node** — deferred.
- **Frame-alignment control** (Color/IR/Disabled) — deferred; use default.
- **Sensor-resolution micromanagement** beyond color resolution — deferred.
- **"Colorize Depth" node** — needed to make `DEPTH_FRAME` viewable and to anchor
  any future depth→image conversion. NOT an adapter. Deferred.
- **Migrating existing `FRAME` semantics** (the "properties + serialized
  fallback" model) — out of scope; we just rename + derive.
