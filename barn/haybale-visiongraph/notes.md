# haybale-visiongraph — design notes

Working notes for the OAK-D / depth-camera expansion. Design decisions resolved
in the inquisition interview; rationale kept here. Three terminology ambiguities
(frame/Frame, depth map/buffer, "multiframe") are flagged in
`docs/reference/glossary.md` ("Flagged ambiguities"); per-datatype defs deferred
to `datatype-canon.md` once the code exists.

## Webcam joins the 3D-camera family (second inquisition)

Goal: a webcam should be usable as the **RGB-only member** of the camera family,
feeding the *same* shared `ThreeDFrameEventNode`. One shared event node, per-device
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
  `deprecation_warning=` on `@node` (steers users to `ThreeDFrameEventNode`), but
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
- [ ] Rename `FRAME → RGB_FRAME` across the 3 existing nodes + `OpencvViewerWidget`
      `compatible_types` + `types/__init__.py` + docs; then `/check-rename`.
- [ ] `GRAY_FRAME ↔ RGB_FRAME` adapters. No `DEPTH_FRAME` adapter.
- [ ] `MULTIFRAME_CALLBACK` (`BaseType` dataclass, `flow_type=CALLBACK`,
      `name` + stream-requirement fields).
- [ ] `OakDEmitNode` (device-specific; wraps `OakDInput`; EXEC start/stop;
      `on_startup` reads union; capture thread; open-keyed payload).
- [ ] `ThreeDFrameEventNode` (shared/agnostic; 3 bool flags → `rejig` + requirement).
- [ ] `depthai` explicit in `pyproject.toml`; then `/haywire-dep-check`.
- [ ] `OpencvViewerWidget` → `compatible_types=[RGB_FRAME]`.

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
control flow, exactly like `StartWebcamStreamNode`. `OakDEmitNode` is
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
Update all call sites in lockstep: the 3 existing nodes, `OpencvViewerWidget`
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

- **`ThreeDFrameEventNode`** (shared, one class): subscribes via
  `MULTIFRAME_CALLBACK` to ANY 3D-camera emit node. Exposes `rgb`/`depth`/`ir`
  outlets. Reused across all current and future 3D cameras.
- **Per-device emit nodes**: `OakDEmitNode` now; `AzureKinectEmitNode`,
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
adding a key — WITHOUT changing `MULTIFRAME_CALLBACK` or `ThreeDFrameEventNode`.
The shared event node still only ever shows `rgb`/`depth`/`ir`.

**MULTIFRAME_CALLBACK meaning widens:** the type-gate is now "any 3D-camera emit
node ↔ the shared 3D event node" (not OAK-specific). The single type still
expresses it — all 3D emit nodes use it; the one event node consumes it.

### OpencvViewerWidget display path (Q17)

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
