# B7 endpoint stop before loop compression — design for review

Design only, 5 October 2026. No patch, build, package or version change. Master handover unchanged. Baseline is the owner hardware-tested B6 `PxUpdate_V2.2.2.0.9.bin`; older handovers’ “untested”/“B6 abandoned” statements are historical.

## Current investigation result

The follow-up inspection found existing note-independent display/metadata paths, but **no path carrying effective loop length or the complete playback inputs needed for the endpoint stop**. The concrete findings and missing information are recorded in “PIC display and metadata follow-up” below. Stop for discussion; no protocol, replacement geometry or firmware work is proposed in this pass.

## Recommendation

Constrain each accepted inward Start/End edit **before its authoritative PIC store**, retaining the existing endpoint-driven push. Limit the endpoint to the last representable value whose remaining outer span can contain the pre-edit effective loop length. Leave the QNX length clamp as its existing safety calculation. Removing that clamp alone would permit out-of-window playback and would not stop the displayed/stored endpoint.

This is a small arithmetic/control change once the geometry inputs are available. **The existing traces do not establish a complete small PIC-only implementation:** PIC owns endpoint acceptance, while QNX owns sample-frame and loop-mode geometry. A full patch-size promise or an implementation-ready placement plan would be premature. Do not substitute a raw Size gap or silently restrict the behavior to ordinary loop mode.

## Verified baseline and compression site

Read-only length-based extraction of the supplied package:

- SHA-256 `438da40fee68dee6062f169e3ca9ed461bf31547f0c1f0a77279a3bc264e6e5d`, 3,151,848 bytes.
- Application 1,039,304 bytes; PIC 530,784 bytes; both record revisions 2.2.2.0.9. Extracted payloads exactly equal `b6_candidate_work/voice_2.2.2.0.9_qnx.elf` and `pic_2.2.2.0.9.bin`.
- QNX differs from the traced local .7 ELF only at version bytes `0x1F4E3` and `0x250EF`. Geometry `[0x3F91D,0x3FB18)`, UpdateLoc `[0x41870,0x424A2)`, exponential mapping `[0x18E60,0x18ED7)` and endpoint message store `[0x1FC73,0x1FCA6)` are byte-identical. No fresh decompilation is needed for these paths.

Existing evidence: `b7_audio_evidence.md`, “Units and effective loop geometry” in `handover_B7_center_push.md`, `b7_control_evidence.md`, `b7_combined_control_evidence.md`, and `b6_frame_duration_design/design_report.md`. The last report’s proposed frame-exact B6 translation is **not** part of this change; retain the implemented raw-coordinate B6 behavior.

For the existing reader calculation, A/B are effective outer endpoints, N is source frame count, R is mode-derived requested loop length, and C is effective Center:

```text
L = min(B-A, max(32, trunc(R)))
C = clamp(trunc(mapped_Center*(N-1)), A, B)
U = max(A, min(B-L, trunc(C-L/2)))
V = min(B, max(U+L, trunc(C+L/2)))
```

**Compression is the first line**, specifically `if (local_98 - local_84 <= iVar14) iVar14 = local_98 - local_84;` in the retained Read excerpt. Verified ELF Size-clamp range is `0x3FAA6–0x3FAB2`; duplicated UpdateLoc range is `0x41A3B–0x41A46`. Older Ghidra virtual addresses have an additional `0x100000`. The later edge confinement already moves a fixed-length loop within the outer span; reuse that calculation unchanged.

Outer endpoint conversion includes truncation, Start’s N−33 top rule, a nominal 32-frame minimum, and final N−1 clipping. Ordinary Size is mapped Size times N−1; quantized and BPM modes use additional reader quantities. Raw 0–999 coordinates use the exponential map, not linear frames. There is no loop-length input in the recovered PIC endpoint ordering branches or descriptor limiter `0x9D04D4FC`.

## Exact proposed acceptance rule

Evaluate the old and candidate geometry in the **same sample/mode context**, holding Size, opposite endpoint and non-edit inputs fixed. Protect the pre-edit L produced by the existing Size calculation, rather than the unclipped requested R. This distinction allows an already full-window or already Size-clipped loop to stop immediately instead of making an impossible demand for a larger span.

```text
old_A, old_B, L0 = existing_geometry(current accepted parameters)
q = existing per-layer ordering + descriptor-limited endpoint request
if loop is off, or q moves the endpoint outward:
    accept existing q
else:
    accept the furthest raw value toward q with candidate_B-candidate_A >= L0
```

Search only between the current endpoint and q. Start chooses the largest permitted raw value; End chooses the smallest. Use the actual mapped/clipped candidate A/B calculation for the predicate, not inverse-map nearest rounding. With monotone endpoint mapping, a bounded search over 0–999 needs at most ten predicate evaluations. At a raw-grid boundary choose the conservative value. Do not move the opposite endpoint, rewrite Size, force symmetry around Center, or introduce a retained “maximum ever” loop length.

For the illustrative linear example, L0=100 and End=500, so Start is capped at 400. Requests through 400 retain the existing loop push; requests above 400 cannot advance Start or pushed Center. The loop occupies 400–500. Symmetrically, with Start=200 and L0=100, inward End stops at 300. Repeated requests at the limit leave endpoint, Center and Size values unchanged. Preserve existing notification/custom-loop behavior; this design does not require suppressing a duplicate stock notification.

Outward endpoint edits and direct Size edits may change the span available to a subsequent inward edit. Recompute L0 on each endpoint edit from current state. Direct Center edits retain B6’s raw Start/End translation even if that changes mapped duration; this proposal does not add frame-exact B6 compensation. Loop-off endpoint equality/order behavior remains inherited.

L0 is the stock integer length used by the Size clamp. The existing float edge calculations can differ from that integer at very large positions, as the prior geometry model records. Do not fix that unrelated precision behavior here or claim an exact acoustic period invariant.

## Narrow control integration

Use the existing per-layer store paths. Current .9 bytes confirm:

| Site | Existing role | Proposed treatment |
|---|---|---|
| `9D04DE58` / `9D04DFA8` | A/B descriptor-limiter calls | Keep descriptor limiting and per-layer ordering |
| `9D04DE68` / `9D04DFBC` | J to existing A/B push adapters | Insert endpoint acceptance before the following SH |
| `9D04DE6C` / `9D04DFC0` | SH in the J delay slot | Store constrained value exactly once |
| `9D0012C0` / `9D0012F0` / `9D001320` | adapters and persistent Center push | Feed accepted endpoint into existing flow |
| `9D001220` / `9D001240` | original-request capture / B ordering | Preserve independent linked requests |
| `9D001224` → `9D000C00` | B6 direct Center helper | Preserve |

A hook after the existing SH is too late. A likely minimal gateway replaces each store-site J with a detour whose delay slot no longer stores; it filters endpoint IDs, computes acceptance, restores the original store pointer, then resumes the original adapter with the accepted SH as a delay slot. Unrelated parameters must retain their original value/store/path. Exact register allocation and displaced-instruction replay require instruction validation; no gateway has been assembled.

Keep the original captured absolute request at SP+0x10 intact. B must evaluate its own old window, loop flag and L0, independently of A’s constrained endpoint. A complete stop in A must still permit B’s legal movement. Do not redispatch linked setters or alter inherited custom-loop recursion. Center pushes must use the constrained value, never the rejected request.

## Necessary geometry ownership detail

The available PIC setter context supplies raw parameters and part/oscillator selection. It has no verified source N, quantization factor, BPM-derived rate, or selected reader’s mapped geometry. QNX has these inputs. Neither a synchronous geometry query/reply nor an authoritative PIC geometry cache is established by the existing traces. Ordinary parameter messages do not establish a pre-store acceptance transaction. A reader-only clamp cannot satisfy the persistent PIC endpoint stop.

**Preferred implementation shape:** reuse an existing control-side geometry/metadata path if it can supply this predicate at the PIC pre-store decision. If none exists, exact all-mode behavior needs a narrowly scoped QNX geometry query/response or equivalent authoritative acceptance path, with part/oscillator/context identity, and PIC committing only the accepted endpoint. That transport is necessary integration, not an already available capability. Its synchronization, silent/no-active-note operation, linked layers with different sample lengths, output-inhibited edits and UI/preset consistency must be resolved before a firmware patch. Do not infer acceptance from the latest active voice or untagged message timing.

The remaining investigation should be limited to whether that geometry information/return path already exists and which sample context defines the edit limit. Modulation must not turn this into a continuously enforced endpoint lock; enforce at endpoint acceptance only. Multiple samples/readers require an explicit reference-context rule if the existing control path does not already define one. These are unresolved implementation facts, not authorization to add a new mode or user setting.

## Estimated patch size

Planning estimates, not emitted sizes:

- If an existing geometry predicate is callable at acceptance: roughly **60–120 MIPS words / 240–480 bytes** for two gateways, endpoint/loop/direction filtering, bounded acceptance and ABI handling, plus roughly **4–8 changed site words / 16–32 bytes**. Predicate/map implementation and transport are excluded.
- If geometry must be duplicated or supplied across PIC/QNX, the total is larger and cannot be credibly bounded from these traces. Do not present the core estimate as the whole firmware patch. No new QNX playback hook is needed merely to locate/remove compression; the playback clamp remains.
- Existing PIC tail padding from `9D0013AC` to `9D001480` is only 212 bytes after B6’s version thunks; it cannot be assumed to fit the estimated core. No code cave, new state field or relocation is reserved by this design.

## Necessary validation before eventual release

1. Arithmetic oracle using existing map/geometry: linear 200/500/100 example and symmetric End case; actual nonlinear raw grid, one-step/exact/overshoot/repeated edits, outward retreat, full-window Size, already clipped Size, 32-frame and short-file rules; ordinary/quantized/BPM modes in the chosen authoritative context. Assert candidate span never falls below pre-edit L0 on an inward edit and chosen raw value is maximal legal progress.
2. Extend the existing B7 decoded-instruction harness against .9 for both oscillators, A/B/linked, unequal windows and independent loop flags. Verify actual accepted values, original request retention for B, Center persistence on retreat, stopped-request behavior, custom-loop side effects, output gates, MIDI paths, SH-once semantics, registers/stack/RA and delay slots. Existing external-call summaries will need the geometry acceptance contract explicitly modeled.
3. Differential checks for loop-off, direct Center/B6 translation and direct Size edits. QNX playback bytes and inherited B1/B3/B5/B8 logic remain unchanged unless the necessary geometry service specifically requires a separate control-path change; account for every byte.
4. Hardware: repeat the worked movement and reversal on both oscillators and unequal linked layers, with held/new notes; at saturation verify endpoint/display/Center stop and no further loop compression. Exercise supported Size modes, save/reload/power cycle, normal MIDI and inhibited-output conditions. Re-run the existing B6 and inherited regression sequence.
5. Only after design review and implementation authorization, produce `PxUpdate_V2.2.2.1.0.bin`. Update applicable application/PIC headers, QNX report/updater constants, PIC reports/thunks and display formatter consistently for **2.2.2.1.0**; check the fourth-field transition and fifth-field reset rather than blindly changing 9→0. Preserve FPGA revision/payload and established packaging/checksum contracts. Re-extract and independently verify the final package and actual updater gates.

Review outcome sought: accept this endpoint-acceptance rule and the pre-store integration point. A small complete patch is not yet established until the necessary geometry ownership path is verified. Baseline .9, master handover, all firmware and version fields remain unchanged.


## PIC display and metadata follow-up — existing paths only

Follow-up scope: inspect availability, provenance and operation without held notes. No new protocol, playback-geometry implementation, patch, binary, version change, Ghidra modification or additional artifact. This section updates the uncertainty in the earlier ownership discussion; its conditional integration suggestions remain unimplemented and were not developed in this pass.

### Evidence provenance

Reuse the verified .9 package/payloads and existing geometry traces. The connected Ghidra session exposes the established PIC program at `9D000000–9D08195F`; it does not expose a whole-program hash. Read-only decompilation/xrefs therefore served as navigation, with actual .9 bytes inspected locally. The loop graphic is not defined as a complete function in that session, so its arithmetic was decoded directly from .9 words; no new function definition was created.

Local byte comparisons confirm the following entire ranges are identical between traced .7 and .9 PIC: `[3AD9C,3B5D4)` display handler; `[5F7F4,60C18)` formatting; `[41048,41DB0)` selected-instrument metadata refresh; `[41E8C,420CC)` cached record read; `[42B80,42E28)` cache builder; `[79220,79B00)` metadata getters/requests; `[51300,51BB0)` relevant reply dispatch. Offsets are from PIC base `9D000000`. QNX metadata ranges `[1E8F8,1E951)`, `[20077,200EA)`, `[22DAE,22E17)`, `[22E73,230C6)` and parser `[34360,34B70)` likewise equal .7. The .9 package SHA-256 remains the baseline hash above.

### What PIC already has

| Available information | Concrete source / consumer | Available without held notes? | Sufficient for exact stop? |
|---|---|---|---|
| Raw Start, End, Center, Size, Loop, Custom and Loop Mode for each layer/oscillator | Existing array `8000046C`; getter `9D04D300`; Size IDs `0B/4C` and additional Size IDs `0D/4E`; mode `06/47` | Yes, stored preset/control state | Necessary raw inputs, but not mapped frame geometry |
| Loop graphic and numerical labels | Display handler `9D03AD9C–3B5D0`, raw reads and descriptor maxima; formatter `9D05F7F4` | Yes, redraw from stored state; no reader/note query in geometry path | No: display pixels/raw values |
| Two instrument names, loop-present flag, velocity-selection limit | Cached 64-byte record, `9D041048`, getters `9D079264/9280/92A0/92C0` | Yes, serial-flash metadata selected by group/category/instrument | No sample frame count, loop endpoints or loop length |
| Instrument identity, 16 bytes | `9D079534`, existing `4021` + `4039` requests, replies `6080–608F` | Request is indexed by instrument, not active voice | No: identity bytes, not geometry |
| Instrument count in a folder | `9D079978`, message `4012`; QNX `22C6A` calls `GetNumInstrumentsInFolder` | Yes, folder lookup | No |
| Group/folder storage usage | `9D079744`, request `4037`, replies `4037/4038`; QNX `22DAE` | Yes, filesystem lookup | No: storage usage, not source frames/duration |

“Without held notes” here is established by control/data flow, not a fresh hardware test. Cached paths perform local reads. Request paths use dictionary/cache/filesystem services and have no active-reader or note-on precondition in the inspected branch. They still require valid cached content or a responding QNX system; this is not evidence that a query is safe to invoke synchronously inside the endpoint setter.

### Loop display: a raw-coordinate drawing, not a playback measurement

At `9D03B024–3B06C`, the handler gets the selected part via `9D031B70`, reads the parameter selected by UI-object `+B6` via `9D04D300`, reads its descriptor maximum from `9D047498`, and computes `floor(246*raw/max)`. The instructions use shifts/subtractions for 123*raw, then shift once and `divu`. The display adds a five-pixel offset. Parallel paths at `3B120–3B170` and `3B16C–3B1BC` scale the `+B2/+B8` parameter IDs the same way.

The Size path at `3B0AC–3B100` derives a half-width in pixels using `(raw+1)` and `(descriptor_max+1)`, followed by pixel-boundary adjustment at `3B104–3B21C`; a special Size branch exists at `3B55C–3B5AC`. These calculations use raw controls, descriptor limits and screen bounds. They do not read source N, exponential-map values, a QNX reader, mode-derived requested frames or returned loop edges. The drawing calls at `3B200`, `3B218` and `3B230` consume those local pixel coordinates; no authoritative parameter store is introduced by the drawing arithmetic.

Numerical Size formatting is equally concrete: `9D05F7F4` cases `0B/0D/4C/4E` format `raw+1`; Loop Mode cases `06/47` select the existing Regular/Pitched/Sync labels from `9D0615C0`. The label “Loop Size” is not a returned duration. The loop-present getter call at `3B004` decides whether a native loop exists when Custom is off; it supplies a flag, not native loop bounds.

### Metadata: exact record fields and their origin

`9D079340` selects group/category with `4021` and requests an instrument with `4020`. QNX dispatcher `1E916/1E928` routes these: `4021` stores group/category at message-loop `+3754/+3758`; `4020` enters `22E73`, resolves `CSampleGroups::GetSampleGroupFolder` (`33C10`) and parses the instrument path into name character replies `6030…` / `6044…`.

For the two scalar fields, QNX `23050–2307C` calls `CGroupFileInfoCache::GetGroupFileInfoCache` / `GetGroupFileInfo`, obtaining a `CWavHandler*`. At `23093–230BC` it sends:

```text
4032 payload = handler->u32_at_21C
4033 payload = (handler->field_at_210 != -1)
```

PIC `9D0519E4–51A00` stores `4032` into record byte `+2D`; `9D051860–518E8` stores `4033` into `+2C` and completes the name/metadata response. The latter is used as the native-loop-present flag. The former is a velocity-selection limit: `9D041374` reads it through `9D0792C0` and caps IDs `13/1C` (descriptors “Stretch Vel”/“Sample Vel”; oscillator 2 adds `41`). In the group parser, `345B0/345E8` populate handler `+21C` while walking the WAV-handler list. It is not sample length in frames.

Cache builder `9D042B80` writes the two 22-byte name regions and bytes `+2C/+2D` into each 64-byte serial-flash record beginning at `C00000`, then explicitly zeroes `+2E…+3F`. The cached-record reader `9D041E8C` and selected-instrument loader `9D041048` copy those fields. The latter loads the per-part/oscillator record at `80037D3C + (part*2+osc)*40h`. Getters `9D079264/9280` return names; `92A0/92C0` read bytes `+2C/+2D`. Thus the 18 trailing bytes copied by these loaders are not evidence of hidden frame metadata: the existing builder writes zeros there.

The 16-byte `4039` result is separately stored at `80037E7C`; reply IDs `6080–608F` are copied byte by byte at `9D051A88–51AC4`. Its consumer `9D0419BC` compares/copies it against the instrument identity parameters (16 slots beginning at `25`, oscillator 2 at `66`) and may resolve a moved instrument. QNX `20077–200E5` obtains the bytes through the instrument dictionary virtual method at vtable `+30` and sends exactly 16 bytes. No loop arithmetic uses this buffer.

Finally, the tempting “size” query is disproved by its source: QNX `22DCA` calls `GetFolderContentsSize` (`15320`), rounds byte usage into decimal-million units and sends the low/high halves with `4037/4038`. PIC assembles them in GP−`7B9C`; `9D079A08` caches them per group. This cannot supply N for the selected sample.

### Information still missing and why it matters

No existing path was found in these display/metadata consumers and their corresponding request/reply branches for either **effective loop length L0** or a complete set of inputs from which the PIC currently derives it.

The missing information is:

- **Source frame count N for the relevant WAV/sample context.** Existing metadata identifies an instrument/folder, not the concrete reader selected by note/velocity/sample choice. N determines mapped frame rounding, the nominal 32-frame minimum and short-file/file-end rules. Folder usage, velocity count and loop-present flag cannot substitute for N.
- **Mapped playback positions and mode-derived requested loop frames.** PIC has the raw controls and mode selector, but the inspected display has no playback exponential map or callable frame-geometry result. Pitched/quantized mode requires the reader’s quantization factor; Sync/BPM mode requires its effective rate/BPM-derived length context. Musical control settings alone do not establish these source-frame quantities.
- **Native loop bounds when the current loop uses sample metadata rather than Custom geometry.** PIC receives only “loop exists”; neither handler `+210/+214` loop coordinates nor a computed native loop span is returned by the inspected metadata response.
- **An authoritative sample association for those quantities without active notes.** The found responses are instrument-level and not a per-layer/per-reader current geometry snapshot. A held voice’s length, even if obtained elsewhere, would not establish the edit limit for a silent instrument or all of its note/velocity-selected samples.

For ordinary large-sample, unmodulated geometry, normalized fractions may cancel N approximately. That does not establish an existing PIC calculator and does not reproduce integer rounding, minimum/short-file rules or other Size modes. No such approximation or duplicated geometry was designed in this pass.

**Conclusion:** PIC has enough note-independent data to draw the existing loop controls and identify whether an instrument has a loop, but the inspected paths do not supply the exact geometry needed to stop endpoint acceptance before compression. This is a bounded negative finding about the inspected paths, not a proof that every firmware subsystem has been exhaustively searched. The missing data above remains unresolved. Stop for discussion; retain the endpoint-stop requirement, hardware-tested B6, linked ordering, persistent B7 Center push and all other inherited behavior unchanged.
