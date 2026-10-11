# B7 endpoint stop before loop compression — design for review

Design only, 5 October 2026. No patch, build, package or version change. Master handover unchanged. Baseline is the owner hardware-tested B6 `PxUpdate_V2.2.2.0.9.bin`; older handovers’ “untested”/“B6 abandoned” statements are historical.

## Current investigation result

The current recommendation is **asynchronous QNX calculation with a tagged PIC cache of one required normalized width per layer/oscillator**, carried by the existing 32-bit transport. PIC retains immediate local endpoint acceptance and Center push when the cache is valid. Do not query synchronously for each knob tick or cache independent Start/End caps. The Pitched/Sync permanent inward-stop fallback remains rejected.

This is a conditional feasibility design, not implementation-ready firmware: silent multi-sample header coverage, a useful Sync rate envelope, transport retry/tag lifetime and the behavior during invalid-cache intervals remain explicit blockers/choices. The latest section identifies observed hook points, proposed message encoding, state, response implications and footprint. Endpoint compression remains a preexisting factory behavior, not a B6/B7 regression.

Automatic Custom activation is acceptance-gated per layer so a rejected edit does not switch the native loop. Only this focused handover is updated. No patch, build, package or version change; `PxUpdate_V2.2.2.1.0.bin` remains reserved and the master handover remains unchanged. Older dispositions are historical where superseded.

## Earlier exact-geometry proposal — retained for context

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


## Regular-mode normalized feasibility — approximate PIC-only candidate

Design only. This pass uses the owner’s clarification that small rounding differences are acceptable, while noticeable squeeze or progressive shrink is not. It does not pursue frame-perfect geometry, new communication or further metadata searches. Only this handover is updated.

### Sample length cancellation

Let F(r) be the existing normalized exponential map, x=F(Start), y=F(End), z=F(Size), and P=N−1. For Regular custom-loop geometry, before integer/minimum/file rules:

```text
outer span = (y-x)*P
requested loop length = z*P
no compression requires y-x >= z
Start limit: F(Start) <= y-z
End limit:   F(End)   >= x+z
```

P cancels for P>0. The map is the existing 1000-entry table, built using the saved .9 float constants: base approximately 1.005, scale approximately 0.00690389844, F(0)=0, F(999)=1. Use mapped values, not `End-Start >= raw_Size`. The linear 200/500/100 example gives Start=400; actual raw coordinates need the nonlinear mapping and do not give that raw-number result.

Protect an already Size-clipped window by **freezing further inward movement** when its current normalized span is smaller than the Size requirement. Otherwise stop at the fixed Size boundary. No retained loop-length state, sample metadata or inverse-map rounding is needed. Outward edits and direct Size/Center edits remain inherited and may establish a different subsequent limit.

### Smallest practical fixed-table candidate

Use a read-only, strictly increasing 1000-entry `uint16` table:

```text
K = 65535
T[r] = floor(K * F(r))
H = T[Size] + 3                 // compute in 32 bits; never wrap uint16
D = T[End] - T[Start]

loop off or outward request: accept inherited ordered/limited request
Regular inward request:
    if D < H: keep current endpoint
    else choose furthest raw endpoint toward request with
         T[candidate_End] - T[candidate_Start] >= H
```

The three table units are a small **fixed conservative allowance**, not a frame minimum. Two cover the table’s endpoint/Size quantization; the remaining margin also comfortably exceeds ordinary float-product errors. `3/K` is about 0.0000458 of full sample range. The residual normalized margin at a guarded boundary is between roughly one and four table units before the raw endpoint grid is considered. Do not scale 32 frames into a guessed raw gap.

Implement acceptance by a binary search restricted to `[current endpoint, ordered request]`, at most ten comparisons, using the same table for the old and candidate states. This avoids per-edit powers/logs, floating subtraction and inverse rounding. A threshold lookup plus a global search is also possible, but must never return behind the current endpoint on an inward request. The restricted search makes this automatic. Requests above descriptor bounds still use inherited descriptor limiting.

This 16-bit table is a practical small choice: the modeled map’s minimum adjacent table increment is **2**, so every raw inward step strictly reduces D. An 8-bit table would flatten many nearby raw values and substantially coarsen stopping; it is not proposed. A 4000-byte 32-bit table could reduce approximation, but is unnecessary for the accepted tolerance and was not selected.

### Why repeated edits cannot squeeze gradually

H depends on the unchanged Size setting, not the previous rounded accepted endpoint. If the old width is below H, every inward request returns the existing endpoint. If it is above H, all accepted inward edits keep D≥H. Once the next raw step fails that comparison, the same request fails again. Both endpoint directions share the same width invariant; alternately advancing Start and retreating End cannot walk below H.

Do not calculate a new smaller target from the last rounded loop width, round an inverse-map result to nearest, or subtract a fresh encoder delta from the remaining span. Those would permit drift. The proposed integer comparison has no such feedback. Existing B6 direct Center translation can change the mapped span; that is intentionally preserved, and a later inward endpoint edit simply uses the new current raw values. Direct Size changes intentionally change H. These are separate edits, not rounding squeeze.

### Comparison with existing QNX geometry

For exact real multiplication and normal outer bounds, floor rounding alone does not break the rule:

```text
if (y-x)*P >= z*P,
then floor(y*P) - floor(x*P) >= floor(z*P).
```

QNX also ensures an outer span of at least 32 frames for N≥33, including its Start top clamp and End extension. Therefore a Regular Size request below 32 does not progressively squeeze below 32 when raw endpoints move: QNX’s outer span and loop length are both raised to that minimum. For N≤32, the traced outer rules give A=0, B=N−1 and L=N−1 for valid positive N, independently of the endpoint coordinates. N=1 gives zero span. The PIC normalized limiter is conservative in these regions because it cannot know that extra inward raw movement would remain harmless.

Separate QNX float32 products can invalidate an unguarded real-number boundary at large frame counts. The small fixed table allowance addresses this without computing frame-perfect geometry. Example from the host comparison: N=1,887,552,812, old Start=0, End=831, Size=188; the unguarded normalized boundary permits Start=826 and QNX L changes **20,250,780→20,250,752** (28 frames, approximately 0.00014%). These unusually long test inputs demonstrate the rounding distinction; they are not evidence of such an installed sample. The guarded table rejects that boundary.

All model arithmetic reused the .9 constants and the existing QNX window/Size formulas; no firmware or executable helper was generated. Concrete checks run in memory:

- Unguarded Start-boundary sweep: **6,993,000 cases**, 499,500 End/Size combinations at each of 14 N values from 1 through 33,554,433; no L loss in that sweep. Symmetric End sweep: **4,495,500 cases**, nine N values; no L loss. These are boundary sweeps, not all presets/sample lengths.
- Near-boundary float checks: **1,128,000** randomized N≤16,777,217 cases; no L loss. Separate large-N targeting found **10** pairs with a loss among **186,343** checks (the search stopped at the first loss for each pair), establishing that unguarded equality is not an all-N theorem for float32 products.
- Guarded 16-bit candidate: **225,000** mixed Start/End/Size/direction cases over 15 N values including 1, 17, 32, 33, 4096, 48000, 1,000,000 and 2,147,483,647; **zero L loss**. **900,000** duplicate saturation checks returned the same endpoint. These are host arithmetic checks, not decoded candidate or hardware checks.
- Against the unguarded normalized Start boundary over **499,500** combinations, the allowance changed **54,791** stops and moved them back by at most **two raw steps**. That bound is for this table/matrix, not the difference from an exact sample-aware stop. QNX’s 32-frame rule can cause a much larger difference from the latter.

Representative comparisons; all start at raw Start=200, End=500:

| N | raw Size | QNX L before edit | PIC Start stop / sample-aware stop | PIC End stop / sample-aware stop | QNX L at PIC stop |
|---|---:|---:|---|---|---:|
| 4096 | 200 | 48 | 469 / 470 | 299 / 297 | 48 |
| 48000 | 200 | 567 | 469 / 469 | 299 / 299 | 567 |
| 4096 | 100 | 32 | 488 / 500 | 244 / 200 | 32 |
| 4096 | 500 | 266 | 200 / 201 | 500 / 500 | 266 |
| 64 | 100 | 32 | 488 / 500 | 244 / 200 | 32 |
| 32 | 100 | 31 | 488 / 500 | 244 / 200 | 31 |

“Sample-aware stop” is the furthest ordered raw value retaining pre-edit L under the existing geometry, used only as a comparison oracle. No such PIC implementation is proposed. When loop length is already clipped by Size/window settings, the normalized rule may stop immediately while a few raw positions share the same rounded frame boundary. For very short samples it may stop even though **all** ordered endpoint positions produce the same loop. This is early stopping, not squeeze, and is the main sample-length-free limitation.

Model map generation uses host `powf` and saved target constants. Before implementation, table generation must be checked against the existing QNX constructor’s rounding/end-entry rules; no new runtime mapping semantics are intended. Integer L comparisons do not prove audible period invariance under modulation, slewing or the inherited large-coordinate float edge arithmetic. The latter can produce V−U different from L above float integer precision; this pass does not fix it.

### Integration and size estimate

Retain the previously identified pre-store A/B endpoint sites `9D04DE68/DE6C` and `9D04DFBC/DFC0`. Read the current endpoint before SH, constrain only the accepted value, then store it once and enter the existing B7 push adapter/helper. Center must be pushed from that constrained endpoint. No QNX hook or payload behavior change is part of this candidate.

Each linked layer uses its own endpoints, Size, Loop and Mode with the original captured absolute request. Preserve the B ordering shim and SP+10 capture. Do not clamp A’s request and reuse it for B. Preserve stock notification gates, custom-loop activation and MIDI flow; a blocked edit may still produce an inherited duplicate notification. Loop-off endpoints bypass the new Size test. Direct Center/B6 helper and direct Size paths bypass it. At saturation, recursive Center push sees no new crossing; it must not use the rejected endpoint request.

Estimated added footprint: **2000 table bytes plus roughly 80–140 MIPS words / 320–560 code bytes**, including filtering, two gateways, per-layer loads, restricted search and delay slots. Roughly **four replaced site words / 16 bytes** for the two pre-store J/delay pairs. No persistent new state or additional protocol bytes. Total added code/table is about **2.3–2.6 KB**, excluding later mandatory version metadata. This is a planning estimate, not assembled size or verified placement. The known 212-byte PIC tail gap cannot fit it; no new cave or relocation has been selected. A local temporary/ABI frame may be needed, but no extra recursive setter activation is proposed.

The calculation applies to the raw custom window that endpoint editing uses. Stock endpoint editing activates Custom before the endpoint store; preserve that behavior. The first edit of a native, non-Custom loop can therefore inherit the existing transition to raw custom geometry. The PIC has no native loop-span measurement, so this candidate does **not** promise to preserve the old native loop duration across that transition.

### Explicit Pitched / Sync outcome — review required

Regular corresponds to `mode % 3 == 0` in the existing QNX geometry, including applicable directional variants. Pitched is `%3 == 1`; Sync is `%3 == 2`. Preserve these inherited mode meanings.

**A mode-gated candidate would apply the new limit only to Regular. Pitched and Sync would retain .9 endpoint acceptance, persistent Center push and existing QNX compression.** That is an explicit limitation and mode policy for review; a Regular-only release is not adopted or authorized by this report.

Applying the same mapped-Size limit to Pitched/Sync would not solve their compression reliably:

- Pitched rounds requested frames to a quantization factor with a minimum of one factor. The needed normalized width depends on that factor divided by P, which does not cancel. Illustratively, a Regular request of 100 frames can quantize to 128 with a 64-frame factor. Stopping at a 100-frame outer span would still compress 128→100, about **22%**. It could also stop too early when quantization rounds down. These are arithmetic illustrations, not observed hardware settings.
- Sync multiplies mapped Size by its rate/BPM-derived context rather than P. The normalized length requires that context divided by P. Illustratively, if it produces 400 frames where the Regular formula gives 100, the shared Regular limit allows **75%** compression before stopping. Other contexts reverse the error and cause premature stops.

Raw controls and the mapping alone cannot bound these discrepancies to “small rounding.” No new communication, mode-specific playback duplication or investigation to eliminate these limitations is undertaken. The owner’s tolerance for approximate stopping supports the Regular candidate; it does not silently establish acceptance of substantial Pitched/Sync squeeze. Review must resolve that mode limitation before implementation.

### Validation and review boundary

If the approximate candidate and mode policy are accepted later, extend the existing .9 decoded-instruction B7 harness for inward sequences and alternating endpoints, saturation/duplicates, outward retreat, unequal linked layers/loop modes, output gates and Center persistence; compare loop-off and direct Center/Size with unchanged .9. Validate table monotonicity, search bounds, SH-once flow and ABI. Hardware should cover normal/very small Size, short samples, initially native loops and save/reload, with explicit Regular/Pitched/Sync results. Do not start these firmware implementation checks in this design pass.

**Current recommendation for review:** the fixed-table normalized clamp is a feasible, small, non-ratcheting approximate solution for Regular custom-loop endpoint edits. It has conservative early stops for minimum/short-sample cases and does not establish the requested stop in Pitched/Sync. No firmware scope decision, binary or version update has been made; retain baseline .9 and all inherited fixes. Stop for review.


## Conservative all-mode revision — current proposal for review

The priority is to prevent endpoint-induced loop compression, accepting early stops. Retain the normalized Regular candidate above; replace the former suggestion to leave Pitched/Sync acceptance unchanged with the following **explicit immediate-stop fallbacks**. These fallbacks sacrifice inward pushing in those modes. They are proposed for owner review, not silently adopted as a firmware policy.

| Loop state / mode | Proposed accepted endpoint | Useful inward push / restriction |
|---|---|---|
| Loop off, any mode | Inherited ordered and descriptor-limited request | Entire inherited behavior |
| Loop on, outward or equal request, any mode | Inherited request | Outward travel preserved |
| Loop on, Regular (`mode % 3 == 0`) | If current `D < H`, current endpoint; otherwise furthest ordered request satisfying `D >= H`, with `D=T[End]-T[Start]`, `H=T[RegularSize]+3` | Push retained until the guarded mapped Size boundary; already clipped loops stop immediately |
| Loop on, Pitched (`mode % 3 == 1`) | Current endpoint for every inward request | Immediate stop; no inward push can be certified from the available settings |
| Loop on, Sync (`mode % 3 == 2`) | Current endpoint for every inward request | Immediate stop; no inward push can be certified from the available settings |

“Inward” is determined against the **current endpoint of that layer after inherited ordering/limiting of the request**, not encoder direction or another linked layer's accepted request. The Regular Size lanes are `0B/4C`; Pitched uses `0D/4E`; Sync uses division `1D/5E` plus its existing tempo processing. Do not use Regular Size as a proxy for the other modes. Preserve directional variants through the established modulo-three mode selection.

### Bounds and why stronger limits are unavailable

**Regular:** `R=zP`, where `P=N-1`, `z=F(RegularSize)`. Thus `(F(End)-F(Start)) >= z` eliminates P. Use the same strictly increasing 2000-byte table and fixed three-unit arithmetic allowance already assessed above. That allowance follows table/float rounding, not a guessed mode multiplier. QNX's 32-frame minimum and short-sample outer bounds make this limit early rather than permitting progressive compression. Keep the existing `L=min(B-A,max(32,trunc(R)))` and window-edge push calculations unchanged. The preceding model comparisons quantify frame rounding and early stops.

**Pitched:** the existing Read calculation uses

```text
R = max(Q, trunc(zP/Q + 0.5) * Q)
```

Here `z=F(PitchedSize)` and Q is the selected reader's quantization interval. For positive Q, nearest-interval rounding gives `R <= max(Q, zP+Q/2)`. A useful normalized sufficient bound would therefore require an established upper bound on `Q/P`, giving `max(Q/P, z+Q/(2P))`, in addition to the inherited frame minimum. The related UpdateLoc calculation truncates the mapped frame request before quantizing; preserve that existing distinction. Neither variant removes the need for Q/P.

Concrete provenance from the .9 ELF, reusing the traced playback path: `HandleMessage` at `23ADF–23B02` loads the float constant **48000** from ELF `5EDE0`, divides by selected handler field `+228`, and stores the result at stack `-768`, the quantization member of the playback parameters passed to `CSampleOsc::NoteOn` at `23B2D`. `GroupFileParse` at `348D0–348E0` obtains handler `+228` through `atof` and float conversion. `CWavReader::Open` copies the supplied quantization field into its pending state, subsequently used at reader `+6C`; its positivity handling does not establish an upper bound relative to N. The existing setter can also supply a quantization value. Consequently the relevant bound depends on selected sample data, not just the PIC's mapped controls. This narrow provenance check is not a new metadata search.

The reused evidence establishes neither a positive lower bound on that handler field times P nor a global upper bound on Q/P. A reader's default quantum cannot be used as a universal value. Even assuming `Q <= P` would only yield a worst-case requirement of a full sample span (or greater under that loose bound), so it would not certify useful inward travel. For an admissible context with `Q >= B-A`, the current loop already fills its outer span; any inward edit that reduces that frame span shortens it. The same PIC endpoints/Size can represent another context with a much smaller quantum and ample travel. PIC cannot distinguish these contexts. Zero inward travel is therefore the conservative fallback; any positive normalized allowance needs an additional proved sample-dependent bound. No arbitrary multiplier is proposed.

**Sync:** existing preprocessing in `b5_endpoint_ghidra_evidence.md` around lines 3150–3180 interpolates `gpBPMToSampleSizeMul`/Diffs from the division setting and Size modulation, then divides by actual global tempo parameter `182`. Denote that resulting duration lane by tau. Read uses effective reader rate when positive, otherwise its existing fallback of 1, to form `R=rate*tau`. Thus the necessary normalized width is `rate*tau/P`, not `F(RegularSize)` or `F(PitchedSize)`. Tempo/division knowledge alone cannot eliminate effective source-frame rate and P; silent note/velocity-selected samples need not share either ratio. The available evidence supplies no useful upper bound on `rate/P`, even without modulation. QNX's fallback rate of 1 is not an upper bound on positive rates.

If `rate*tau >= B-A`, Sync already fills its outer span. An inward edit that reduces that span compresses it. This context cannot be excluded from PIC settings alone; small and large requested spans can have identical PIC endpoints/division/tempo. The safest fallback is immediate inward stop. Tempo, division, pitch and direct Size/Center behavior remain inherited; changing them may establish a different loop, but this proposal does not infer a safe travel allowance from them.

These arguments do not assert that every shipped sample has a problematic quantum/rate. They establish that the available inputs and verified formulas cannot certify a nonzero useful allowance across the selectable sample contexts. Frame-rounding tolerance does not cover these potentially whole-window differences. A frame-identical raw step may be harmless, but identifying such steps requires the unavailable sample context; do not exploit a guessed rounding plateau.

### Repeated, alternating and inherited behavior

For fixed Regular Size, every accepted inward edit either leaves the endpoint identical (old width below H) or preserves the same absolute invariant `D >= H`. Alternating Start/End edits use that same D and H. Never regenerate H from the last rounded loop width. For Pitched/Sync each inward edit is endpoint-identical, so alternating or repeated requests cannot accumulate a span reduction. After outward movement Regular recomputes from current endpoints and fixed Size; the other modes continue to stop inward immediately. No remembered maximum width or history latch is required.

Additional arithmetic check executed in memory in this pass: **300,000 alternating Start/End requests**, 1000 sequences of 100 requests per mode, including outward retreats and saturation. Regular compared the existing QNX L formula at N values from 1 through 2,147,483,647 and observed no inward L decrease. Pitched/Sync verified endpoint identity on every inward request; this is independent of their quantum/rate. This supplements the earlier guarded-boundary and duplicate tests; it is not firmware execution or a hardware validation.

Use the previously identified A/B pre-store acceptance sites. Feed only the accepted endpoint into the existing persistent Center push. An inward fallback must not push Center from the rejected request. Keep independent linked-layer ordering, the original absolute request capture, B6's direct Center translation, direct Size paths, save/reload state, stock notifications and output gates. Different linked layers may stop differently according to their own Loop/Mode/Size. Do not turn off looping or change Mode to implement the fallback.

Two practical limits must remain explicit:

- Stock endpoint editing activates Custom **before** the proposed pre-store acceptance. A blocked endpoint request can therefore still cause the inherited native-to-custom transition. Without native loop bounds this design cannot promise preservation of the old native loop's duration on that first transition. Moving or suppressing activation would change inherited behavior and is not proposed. If preservation across that transition is mandatory, the current constraints do not establish a complete solution; this is a review issue, not permission to add metadata or a protocol.
- The Regular rule protects the static raw-control geometry considered here. Active endpoint/Size modulation, slew and other inherited geometry changes are not bounded by this static test; independent changes to them or direct Center/Size, tempo or mode can change duration. Pitched/Sync fallback introduces no inward endpoint change even in those contexts, but cannot prevent independently changing geometry. Existing very-large-coordinate float edge differences are retained. Do not describe the proposal as an all-context acoustic-period lock.

### Smallest integration footprint and validation

The all-mode revision needs the same **2000-byte table**, no Pitched/Sync table and no new persistent state or communication. Add an early mode branch returning the old endpoint for looping Pitched/Sync inward requests. Estimated total remains about **90–150 MIPS words (360–600 bytes)** plus the table, roughly **2.4–2.6 KB** added; the mode policy costs approximately 5–10 words over the Regular candidate. The two pre-store jump/delay pairs still account for roughly 16 replaced bytes. These are design estimates, not assembled placement; the known 212-byte tail space is insufficient, and no cave has been selected. No QNX patch is required.

Before an authorized implementation, validate table construction against the target mapping and review the immediate-stop restrictions and native-transition limitation. Then extend the existing .9 instruction harness to verify per-layer acceptance before the single store, accepted-value Center push, ABI/delay slots and original request capture. Cover all mode variants, repeated/alternating inward requests, outward retreats, unequal linked layers, Loop off and direct Center/Size. Hardware must confirm Regular pushes then stops, Pitched/Sync inward controls stop immediately while outward controls work, persistent Center/save-reload and all inherited B6 fixes remain. Include first native-to-custom edits explicitly; do not conceal that limitation behind a passing custom-loop test.

**Review disposition:** useful approximate Regular travel is feasible. Pitched/Sync compression prevention from these PIC inputs requires the stated immediate-stop fallback; useful inward travel there is not established. No implementation, build, binary, version update or master-handover edit was made. Stop for review.


## Practical all-mode assessment and acceptance-gated Custom — latest disposition

### Scope and evidence quality

The owner confirms factory firmware compresses the loop in all modes. The proposed correction must retain useful endpoint-driven pushing in Regular, Pitched and Sync; the prior every-inward-edit Pitched/Sync stop is rejected. Early stopping and modest approximation are acceptable, but no arbitrary safety factor is accepted. The shared QNX span clamp identified above explains the preexisting behavior; nothing in this report attributes it to B6/B7.

A narrow inventory of existing sample-related files and the established handovers found **no local WAV/AIFF/GRP sample files, sample-metadata export, or documented sample-length/quantization range**. Existing parser and NoteOn traces recover fields/formulas, not concrete selected-sample values. The PIC's previously established loop-present and velocity-count fields supply no numeric length or quantum. No broad metadata investigation or communication design was undertaken.

Evidence must not be conflated:

| Available evidence | What it establishes | What it does not establish |
|---|---|---|
| .9 map constants and playback/control instruction traces | Mapping and geometry formulas; `Q=48000/handler[228]` in the traced NoteOn construction | Actual selected samples' handler values, frame counts or distributions |
| Earlier Regular host-model matrices, including N=4096/48000 and larger | Arithmetic behavior at deliberately chosen model inputs | Measured factory/user sample lengths or representative sample coverage |
| Existing B5 duration handover, recovered reader-rate cap 32 | A documented recovered playback-rate ceiling in that investigation | A minimum N; typical Sync rate; measured sample durations; blanket applicability to every alternate Sync path without its existing rate-clamp context |
| Existing B5 host benchmarks at rates .01–32 | Predictor host timing for selected synthetic rates | Sample metadata or practical Sync loop lengths |
| Group parser `atof` at `348D0–348E0` and NoteOn `23ADF–23B2D` | Quantum provenance from sample handler data | Positive minimum handler value or a bound on its product with N−1 |

There are therefore **zero measured sample contexts available for an honest numeric sample-grounded error table**. The earlier illustrative examples and large-N probes must not be used as evidence that a practical Pitched/Sync multiplier is adequate. Nor does lack of metadata prove useful PIC-only limits are impossible: practical bounded sample domains could permit them. It means their viability and approximation error are currently unestablished.

### Candidate bounds and quantifiable error once sample evidence is supplied

**Regular: unchanged.** Keep `T[r]=floor(65535*F(r))`, `H=T[RegularSize]+3`, the current-span freeze when D<H, and the restricted monotone endpoint search maintaining D>=H. No new Regular table or geometry is needed. The fixed allowance is about 0.0000458 normalized range; earlier host checks bound its extra retreat against the ideal normalized boundary to at most two raw steps in the tested full raw-grid matrix. The 32-frame/short-file cases remain conservatively early. This is an assessed Regular proposal, not a measured all-mode acoustic guarantee.

**Pitched: conditional useful extension, not a chosen constant.** Let `q=Q/P` with P=N−1 and `z=F(PitchedSize)`. Established quantization gives

```text
R/P = max(q, trunc(z/q + 0.5)*q)
R/P <= max(q, z+q/2).
```

For a grounded upper bound `q_bar` across all relevant selected samples, a fixed safe normalized threshold is `h=max(q_bar, z+q_bar/2)`, plus the existing table/rounding allowance. It uses the Pitched Size lane, the same map table and endpoint search. If current span is smaller than h, stop there; otherwise useful inward travel exists down to h. A supplied q_bar must cover the actual reader quantum and alternate quantization setters, not just a nominal note frequency. No q_bar is selected in this pass.

This gives explicit approximation error without arbitrary examples. Ignoring the existing integer-frame correction, when `z>=q_bar`, quantization can differ from z by at most q_bar/2. The conservative threshold can exceed a particular actual requested normalized length by at most q_bar. Relative to z, its added allowance is at most `q_bar/(2*z)`; relative to the smallest rounded request in this regime, worst early-stop overhead is at most `q_bar/(z-q_bar/2)`. For `z<q_bar`, the one-quantum minimum matters and there is no corresponding small relative-error claim across samples without their q distribution. These formulas distinguish modest error at many periods per sample from potentially severe early stopping at tiny Size; actual metadata is needed to quantify how often each regime occurs.

The relevant missing statistic can be supplied compactly as **the maximum Q/(N−1)**, with measured distribution/representative cases and the sample selection coverage. For the traced construction it is `48000/(handler[228]*(N−1))`. A minimum positive handler value and minimum N could provide a looser documented bound; paired values are preferable because independently combining minima can unnecessarily eliminate useful travel. N=1 and other short samples require the established outer-bound handling rather than division by zero. No note-frequency range alone proves this ratio, and no sample-length range alone proves it either.

**Sync: conditional useful extension, not a Regular multiplier.** Let `tau=division_multiplier/BPM` from the existing table preprocessing and let `b=effective_source_frame_rate/P`. Then `R/P=b*tau`. A grounded upper bound b_bar gives a normalized stop threshold `h=b_bar*tau`, plus table/rounding allowance, using the same search. Static tempo/division values are known controls; their known values do not supply b. Existing modulation remains a separate limitation and must not be silently included in a static-control guarantee.

Granting the recovered rate ceiling 32 for the relevant path, even the strong global bound would be `b_bar=32/P_min`, hence `h=32*tau/P_min`. The missing **positive lower bound on relevant sample frame length** is still essential. No P_min is available in the evidence. More useful bounds can use paired effective rate and length across the covered note/velocity/stretch/pitch contexts rather than assuming every sample can reach the maximum rate. For a concrete context b, excess normalized early-stop margin is `(b_bar-b)*tau`; for an unclipped request its relative overhead is `b_bar/b-1`. Thus even a valid rate cap can be much too conservative unless the sample-duration and rate ranges are documented. If h is at least the current span, the conditional rule stops immediately; useful pushing requires h below it. No claim that this condition is common or rare is grounded yet.

A practical extension would retain the same fixed-threshold invariant as Regular: neither h nor its rounding allowance may be regenerated from the last accepted loop width. Repeated/alternating edits then cannot ratchet below the threshold while its non-edit inputs stay fixed. Changing Size, tempo, pitch, division, Center or selection changes the underlying loop context; their existing direct behavior must remain intact. Any proposed context-dependent bound needs coverage of those available control ranges and silent note/velocity selection, not a measurement from one held note.

**Disposition:** useful Pitched/Sync limits are mathematically conditional on q_bar and b_bar, but their numerical values, practical usefulness and errors cannot be established from the available sample evidence. Do not implement the conditional formulas with guessed constants, leave the old compression silently accepted, or reinstate the rejected immediate-stop fallback. The all-mode design remains incomplete pending the information below.

### Smallest handling of rejected edits and Custom activation

Current automatic activation precedes endpoint acceptance: oscillator 1 converges at `9D04DCE0–DD08` (`Custom=11`); oscillator 2 at `9D04DC18–DC40` (`Custom=52`). These paths load Custom, then recursively call setter `9D04DACC` with a3=1 before reaching the endpoint store. Linked-layer branches use the corresponding B Custom loads (`E440/E47C`) and may activate both layers through the linked selector. A guard only at `DE68/DFBC` is too late to prevent that side effect.

**Proposed minimal semantic change:** defer only the automatic Custom activation initiated by endpoint edits until acceptance has been calculated for the particular layer. Bypass that early recursive activation on these endpoint paths; at each existing per-layer pre-store adapter:

1. Apply inherited ordering and descriptor limiting, then the applicable endpoint-stop calculation against the old state. Preserve the original captured absolute request for B.
2. If a looping request is constrained to the existing endpoint (including an equal/no-progress request), skip automatic Custom activation for that layer. Keep its endpoint and Center unchanged. Do not abort linked-layer processing: another layer may have an accepted change.
3. For an accepted endpoint change, activate Custom if needed using the existing Custom setter/initialization, with the **exact layer selector** rather than linked selection; then store the accepted endpoint once and run the existing persistent Center push with that value. Preserve existing activation on loop-off endpoint paths, which bypass the new stopping behavior.

Use the existing setter so Custom initialization and notifications remain stock; do not write its bit directly, roll back an already-sent activation, or send Custom=0 afterward. Explicit Custom edits remain untouched. No endpoint setter redispatch is needed. A local saved candidate/address and normal register preservation around the Custom call are sufficient in principle. Verify that deferred initialization does not invalidate the candidate or mutate endpoints before its final store; the existing trace establishes the early call ordering, not a completed instruction-level proof of this rearrangement.

This handling changes precisely the unwanted rejected-edit side effect. If Custom was already active, no additional activation is required. If inactive, a rejected edit leaves the native loop selected. For accepted edits, the inherited native-to-custom transition still occurs. **Avoiding rejection side effects does not establish duration preservation across an accepted transition:** native bounds `handler+210/+214` are still absent from PIC. Assessing that first accepted edit needs native normalized loop span/current endpoints as well as the mode's requested geometry. A candidate safe for stored raw custom parameters can still replace a longer native loop with a shorter custom loop. Do not call that transition protected without those data. This is a second missing-information issue, distinct from the activation-gating fix.

Preserve B6's direct Center route and inherited translations; this gate applies to automatic activation from endpoint edits, not direct Center/Size/Custom operations. Keep per-layer ordering, original request capture, notifications/output gates, outward and loop-off behavior. No independently rejected A edit may suppress an accepted B edit or activate A merely because B changed.

### Footprint, validation and exact missing information

Regular arithmetic remains approximately **2000 table bytes + 320–560 code bytes**. Deferring and gating per-layer activation is estimated to add **40–80 MIPS words / 160–320 bytes**, plus approximately **16–32 bytes of additional replaced hook words**, depending on convergence/branch placement. Combined known Regular-plus-activation logic is roughly **2.5–2.9 KB added**, no new persistent state or protocol. This is a planning range, not assembled code. Pitched/Sync constants/calculation cannot yet receive an implementation-ready footprint: a global bounded extension could reuse the table/search, but per-instrument data or effective-rate derivation would materially change storage/code requirements. No such table, runtime path or cave is selected.

Necessary later validation includes acceptance before activation/store; rejected native edits preserving Custom, endpoint and Center; accepted native transitions compared against recorded native bounds; A-rejected/B-accepted and reverse linked cases; loop-off/outward behavior; direct Center/Size and B6 preservation. Use .9 decoded-instruction checks for setter recursion/ABI/delay slots and hardware audio/save-reload checks for the selected sample contexts. Quantify mode errors from real paired metadata first; prior synthetic tests cannot substitute for that assessment.

To complete the requested practical assessment, the missing information is:

- **Pitched:** paired N and actual Q (or handler+228 plus verified quantum construction) for relevant factory/user samples, with note/velocity/sample-selection coverage; a documented or measured maximum Q/(N−1) and representative distribution. This determines quantization overhead and whether the fixed conservative limit permits useful travel.
- **Sync:** paired N and effective source-frame rate/range across relevant pitch/stretch/note controls, or a documented lower sample-length bound plus a verified applicable rate ceiling. Together with existing division/tempo processing these determine b_bar and quantify early-stop error. Tempo/division alone cannot do so.
- **Accepted native-to-custom transition:** native loop bounds (handler+210/+214), source length and the raw custom geometry that replaces them. These determine whether the first accepted edit itself shortens the old loop. Rejected-edit activation can be fixed without this information, as above.

No measured metadata is substituted with assumptions in this pass. The accepted constraints therefore require stopping for discussion of these missing data, rather than recommending an ungrounded multiplier or an unwanted freeze policy. No firmware, build, package, internal version or master-handover change; the eventual `.1.0` binary remains reserved.


## QNX-supplied cached width — transport and feasibility revision

### Recommended shape and comparison

Recommend a **background refresh request after relevant context changes, one atomic tagged width reply, and PIC-local endpoint limiting**. The existing transport is reusable; existing metadata reply meanings and synchronous wait helpers are not. No geometry payload exists in .9 today.

| Approach | Endpoint response | Code/state implications | Safety requirements |
|---|---|---|---|
| Asynchronously request/cache QNX width after dependencies change | Immediate table search at each edit once valid; no per-tick round trip | Four small cache records, invalidation, tagged reply handler; QNX geometry/header work reused between edits | Exact association with the current context, complete sample coverage, no use of a stale reply |
| Query QNX at every endpoint edit before committing | At least transport scheduling plus QNX computation and reply for every tick; cold headers add loading delay | Outstanding edit/linked-layer transaction, request coalescing, cancel/retry, eventual PIC commit and Center push | PIC must defer storage, display, Custom and playback notification until acceptance; concurrent context changes invalidate the answer |
| Accept locally, then QNX corrects the endpoint | Apparently immediate but may briefly compress and show rejected values | Rollback and cross-processor authority changes | Fails the requested pre-acceptance behavior; not recommended |

The second approach can reuse the same packet transport, but not an existing acceptance transaction. PIC `9D079340` (names) and `9D079978` (count) send through `9D075C1C`, then spin/retry until flags change. They are blocking and not a safe endpoint-setter template. Their timer values are not measured milliseconds. Moving a query into every edit would also make linked acceptance depend on two replies. Cached width gives the least endpoint-path work and avoids a request on alternating/repeated edits. The recommendation does **not** promise instant response during a cold or invalid-cache interval.

### Verified wire mechanism, handlers and candidate IDs

All addresses here are baseline .9 ELF addresses or PIC absolute addresses. Narrow byte comparison confirms PIC `[514B8,51BA0)`, sender/receiver `[75B18,75D80)` and name-request prefix `[79340,793F0)` match the previously traced .7. Differences in the larger PIC reply-region comparison are only the .9 version-report words at `51BC4/51BC8`; no version changes were made.

- QNX `CMessageAudioLoop::SendMessageToPIC` at **`1D7F0`** packs `word=(id<<16)|(value & 0xFFFF)` at `1D815–1D820`, then invokes the existing message interface. There is one 16-bit payload per 16-bit ID, not an arbitrary blob.
- QNX `get_messages` at **`1D668–1D67E`** extracts payload with `movzwl dx`, shifts the ID down 16, and calls `HandleMessage`. It processes received messages serially in that thread. The special `4024` case must remain untouched.
- PIC `9D075C1C` is the interrupt-protected existing send wrapper; `9D075B18` writes the supplied 32-bit word to `BF860430` and configures four-byte transfer. `9D075D10` reads four FIFO bytes from `BF860420`, assembles shifts 0/8/16/24, and returns `FFFFFFFF` on its empty indication. The proposed IDs have neither the empty-word nor the special top-byte `F1` MIDI format.
- Existing reply consumers at **`9D051628`** distinguish name ranges, and **`9D051A88–51ACC`** accept only identity IDs `6080–608F`. IDs outside that identity range take the default path to `9D05153C`. Hook a narrow new range **before** the stock identity-range test; do not write new results into its identity buffer or reuse its completion flag.
- QNX dispatcher routes values above `403C` through **`1EB43 -> 1F3E8`**. Values at/below `6000` go to **`206A6`**, which accepts only `403D` there. Thus proposed requests **`4040–4043`** currently reach the no-op/default exit `1E453`. They do not invoke an existing geometry handler.
- Proposed replies **`6098–609B`** are outside stock names `6030–6057` and identity `6080–608F`; stock PIC ignores them through the verified default range. The scoped QNX dispatcher/sender inspection found no producer for `6098–609B`. `6090` itself appears as the identity-loop end constant, so it is deliberately not selected.

These are **candidate unclaimed IDs in the inspected .9 transport dispatch paths**, not a claim of a vendor-wide reserved allocation. Before implementation, confirm no inherited side channel/source module owns them. No stock ID is repurposed, no existing reply's payload meaning is changed, and no existing shared name/count/search flag becomes the cache-valid flag.

Smallest proposed atomic encoding:

```text
slot = 2*layer + oscillator               // 0..3, A/B independently
request ID 4040+slot, payload token       // token 0..63; other bits zero
reply   ID 6098+slot,
        payload (token<<10) | width_code

width_code 0..999: mapped minimum-width coordinate
width_code 1000: native-to-custom inward transition cannot preserve duration
width_code 1001: geometry/header coverage not ready or unavailable
width_code 1002..1023: reserved; reject, never interpret as a width
```

The width coordinate uses the **existing exponential Size map**, not an endpoint raw gap and not a new unit. QNX chooses the least c with `F(c) >= required_normalized_width`; PIC uses `H=T[c]+3` in the already assessed table/search. It never stores c as a user Size value. A full-range requirement maps to c=999 and naturally leaves no inward headroom under the guarded rule. This represents a genuinely full-window context, not a blanket mode freeze.

One reply is atomic at the transport word level, so there is no partial low/high result or commit assembly. The extra upward rounding is at most one map-grid interval. Using the saved .9 constants, the largest adjacent F interval is **0.00500947237 of the full sample range**; actual early-stop error at a given c is its preceding interval, plus the existing three table units. This may be material for very small requested loops; do not call it a universal 0.5% relative loop error. A 16-bit width plus a separate tagged commit would be finer but needs a verified multiword association/assembly rule and more state; it is not the smallest candidate.

In-memory encoding-only check covered all **262,144** slot/token/code combinations and recovered each field exactly. This is not a transport delivery, geometry, firmware or hardware test.

The six-bit token is feasible **only under the outstanding-request/lifetime contract below**. If that contract cannot be established, the encoding needs a wider tagged transaction, and its footprint estimate must increase. Do not assume a six-bit token alone prevents staleness.

### QNX calculation without held notes and with multiple samples

Cache one **required width**, not separate raw `Start_max` and `End_min` from an old endpoint snapshot. Separate caps can each consume the same headroom; alternating edits can then compress the loop. A fixed width is tested against both current endpoints and needs no refresh just because a custom-loop endpoint moved inward/outward.

For every sample context covered by the selected layer/oscillator, obtain its actual N, quantum Q, native coordinates when relevant, and Sync effective-rate bound from that instrument/control context. Reuse the existing map, mode Size calculation and frame/outer-bound rules. Define the uncompressed requested integer length

```text
Regular: req = max(32, trunc(F(RegularSize)*(N-1)))
Pitched: req = max(32, trunc(max(Q, trunc(F(PitchedSize)*(N-1)/Q+.5)*Q)))
Sync:    req = max(32, trunc(effective_rate * division_multiplier / BPM))
```

Preserve the recorded Read/UpdateLoc quantization differences by taking a sufficient requirement for both, not by changing either playback calculation. Sync's existing positive-rate/fallback behavior and actual units must be retained. For samples whose outer span can be reduced by endpoints, use `min(req,N-1)/(N-1)` as the normalized requirement, plus the guard applied on PIC. Combine by **maximum across the covered samples/rate contexts**. The actual short-sample outer calculation can identify cases with an endpoint-independent span; those need no inward-width constraint. This avoids treating tiny samples' nominal 32-frame minimum as an arbitrary normalized gap. Check the large-coordinate float allowance against this generalized requirement before implementation.

PIC freezes an inward request if the current mapped span is already below H; otherwise it searches toward the requested value for `D>=H`. It retains useful pushing whenever current span has headroom above the calculated threshold. The requirement is stable for fixed sample/Size/mode/tempo/rate context, so repeated and alternating inward edits cannot lower it. No learned “last loop length” or maximum-ever state is used. A file/context whose loop already fills the window can correctly stop immediately; that is distinct from refusing every inward edit in a whole mode.

**Observed silent-data entry points:**

- `CSampleGroup::SwitchSampleGroup` **`35860`**, specifically the cache call at **`358C6`**, installs the handler head into group `+680`. `GetWavHandlers` **`35C10`** returns that head without a voice requirement. Handlers link through **`+240`**. Note/velocity ranges `+200/+204`, `+208/+20C`, sample/velocity selection fields and alternate availability flags are used by the already traced `FindHandler` **`35940`**. This supports an instrument-wide calculation independently of held notes.
- `CWavHandler` constructor **`3C5E0`** initializes native loop bounds `+210/+214` and quantum-source `+228` (default 440, not a measured sample value). `GroupFileParse` overrides those fields; Q at the traced NoteOn construction is `48000/handler[228]`. Enumerate relevant alternatives rather than taking the first handler or last played reader.
- **N is not established in that group handler metadata.** `CWavReader::Open` **`42660`** obtains a loaded RAM file through `RAMFile_GetFile` **`3EDF0`**, parses RIFF/fmt/data with `LocalRead`, and at **`42B07–42B2A`** derives frame count from data bytes, sample byte width and channels, storing reader `+A0`. `GetTotalSamples` **`42DB0`** exposes that reader quantity. `RAMFile_GetFile` only searches loaded lists; it does not open every missing sample.
- The existing background `RAMFile_ReadThread` **`3DA40`** calls `GetNextFileLoadWavHandler` at **`3E2F0`**, then opens/reads files (`3E5CD`, `3E679`) and publishes loaded state through its locked path around **`3E6D6–3E73D`**. This is a candidate place to populate a small **new geometry-only header cache** after data/header readiness. It does not prove all future selectable samples are simultaneously loaded or that all headers have already been inspected while silent.

The minimal calculation must therefore add header-derived N coverage on the **instrument/background loading path**, reusing the existing RIFF parsing semantics, and keep the result associated with the handler/file lifetime. Do not instantiate a temporary playback reader in the knob path: Open mutates reader state/allocates playback resources and is not a metadata query. Do not use file byte size as frames. A header-only parser/factored reader header routine can reuse the existing parsing calculation, but is **new code**, not a discovered callable metadata getter.

Silent support requires completion for **all contexts included in the bound**, even alternatives not loaded for current notes. Missing headers keep the result not ready. Existing loading can be reused when it provides complete coverage; otherwise header-only background access to those specific instrument files is necessary. The exact safe completion/ownership hook for that additional coverage is an unresolved integration point; no broad filesystem or global bound is proposed.

**Essential behavior choice — coverage:** recommend the bound cover all samples selectable for that instrument/layer/oscillator under the current selection controls, and all permitted note/velocity/alternate choices, so it remains usable while silent and after a new note. Using only held voices is insufficient. This can stop earlier than a limit for one voice. The existing `FindHandler` selection logic should define the set, not a guessed “representative” sample. Taking all handlers is a conservative simplification, but may include presently unreachable variants and unnecessarily remove travel; its practical usefulness must be checked on actual instruments.

For Sync, notes affect effective source-frame rate. QNX must derive a **sample-specific envelope over the covered note/pitch/stretch context using the established rate calculation**, including ongoing held voices if their prior sample remains playable. The voice-preparation path **`18EE0–193F0`** reads actual/float controls and modulation and performs rate arithmetic; it is not a pure preview function safe to call on invented voices. Factoring its rate arithmetic for the covered context, or proving the envelope from those inputs, remains required. No global 32-rate/minimum-sample-length approximation or new arbitrary multiplier is recommended. A useful all-note envelope is not proved by the current traces; this remains the principal Sync calculation blocker.

### Refresh, freshness and transport lifetime

PIC owns cache validity. Before a relevant stored state changes, mark the affected slot(s) invalid and increment a local **context revision**. Request a refresh after the normal corresponding QNX parameter notifications have been sent, preserving their FIFO order. Each request records its slot, token and full local context revision. QNX snapshots the matching parameter/group state after those notifications and emits the result for that token. PIC installs it only if the slot has an outstanding request with that token **and** its recorded context revision still equals the current revision. Otherwise discard it and request the latest state. A token match without the local-revision check is insufficient.

Refresh dependencies:

- Instrument/group/category selection and preset/part reconfiguration; group/header replacement or load/reload completion. Keep old held samples in the coverage if inherited playback can outlive a selection change.
- Size lane relevant to the mode; Loop Mode/directional variant and Custom changes; Loop enable before the first guarded inward edit. Regular can retain its local Size rule for an established custom window, but must still guard rejected native activation.
- Sync division, actual tempo (including external-clock changes), and every pitch/stretch/tuning/selection input used by the computed effective-rate envelope. Pitched quantum-affecting input changes require a new result. Modulation coverage cannot silently be assumed.
- If Custom is off, old Start/End contribute to native fallback coordinates; invalidate on their changes and on B6 Center translation of them. For an established custom loop, accepted endpoint/Center push does not invalidate a width independent of endpoints. Direct Center/Size still follow inherited routes; only validity is affected where they change inputs to the bound.

Coalesce refresh requests while one is outstanding **per slot**; four slots permit independent linked contexts. Do not issue a refresh on every endpoint tick in an established custom context. If the response is for an old local revision, retire that transaction and request the current revision. All cache records start invalid at boot/disconnect/preset reconstruction; none is preset-persistent.

The six-bit token can cycle after 64 transactions only if no response from the previous use can still arrive. Proposed small contract: one response per request, one outstanding request per slot, no automatic duplicate resend of that token, and serialized completion before its reuse. A matching single-word completion retires it; a changed local revision does not make an unanswered request disappear. **After timeout/drop/disconnect, do not reuse its token without a proven transport/session drain or retirement rule.** Existing name/count retries do not supply this guarantee. If bounded retirement cannot be proved, use a larger tagged response scheme rather than assert safety from wrap arithmetic.

`CPCIeMessages::PushMessage` **`44F10`** has a finite 4096-entry ring and returns an error when full (`44F3F -> 44F65`). `SendMessageToPIC` does not propagate/check that result. Successful code execution therefore does not prove delivery. Cached publication needs a checked enqueue/retry on the same outstanding transaction or a reviewed not-ready recovery; reply drop must never revive an old cache. `WriteOutMessageStream` **`45030`** drains at most 128 words per stream invocation. No word/knob latency bound follows from this alone.

**Essential behavior choice — invalid cache:** stale limits cannot be used even temporarily. Recommend leaving an inward edit uncommitted while refreshing; outward movement, Loop off and direct edits retain their inherited paths. This is a temporary data-readiness condition, not the rejected permanent Pitched/Sync mode fallback. Whether knob intent is discarded, accumulated or replayed after readiness is an owner choice; replay/accumulation needs extra pending-edit state and input integration and is **not silently included** in this minimum design. Without such a policy decision, cold/miss behavior is not complete. Never activate Custom for the uncommitted request.

If PIC output gates suppress the normal parameter notifications, QNX's snapshot may not match PIC storage. Mark the result unavailable until the existing full parameter synchronization completes; do not force-send user parameters through those gates. Output-inhibited limiting needs a coherent explicit snapshot if it must operate during that interval; that would add request fields/code and remains a blocker for claiming complete coverage of every setter context.

Changes initiated solely on QNX (for example tempo/loading/geometry replacement not preceded by PIC invalidation) need an ordering rule that prevents PIC using the old limit before notification arrives. An unacknowledged asynchronous invalidation alone cannot guarantee this. Prefer the existing PIC-owned parameter-change boundary where applicable; for autonomous changes either the bound must already cover them or QNX/PIC need a reviewed invalidation/acknowledgement boundary. This is unresolved, particularly for Sync/external clock and modulation; do not claim static caching protects arbitrary evolving playback geometry.

### Acceptance, native transition and consistency

PIC remains authoritative for stored/displayed endpoints. Keep per-layer ordering and descriptor limiting, clamp the candidate at **`9D04DE68/DE6C` (A)** and **`9D04DFBC/DFC0` (B)** before the single SH, then run the existing **`9D0012C0/12F0/1320`** persistent Center push using the accepted endpoint. Preserve SP+10 original request capture and B's ordering shim. Linked layers use their own slot and validity; A's accepted value never replaces B's original request. Stock parameter messages convey only the accepted endpoint and accepted Center changes to QNX. QNX's existing endpoint store **`1FC73–1FCA6`** and playback clamp remain unchanged; no later correction or second endpoint authority is added.

Keep the established local Regular rule. The same PIC table/search accepts QNX-derived width codes for Pitched/Sync. The resulting interval pushes the existing QNX window until the fixed-width bound is reached; no playback geometry is duplicated on PIC. Outward moves and Loop-off operations bypass the new inward-width check. Direct Center/Size remain inherited, including B6 translation; they are not rewritten to enforce a historical duration.

Defer only automatic Custom activation from the existing endpoint paths **`9D04DCE0–DD08` / `9D04DC18–DC40`** until that exact layer has a nonzero accepted endpoint change. A rejected/equal/no-cache looping request must leave Custom, endpoint and pushed Center unchanged. An accepted linked B edit must not activate rejected A: invoke the existing Custom initialization with an exact layer selector, not a linked recursive selector. Do not change explicit Custom or B6/direct edit handling. Verify deferred initialization preserves the candidate/address and original B request before the store.

For a first **inward** native-to-custom edit, QNX can additionally evaluate the existing native loop endpoints (handler `+210/+214`, with stock raw outer fallbacks when absent). Let L_native be their current effective span. A custom requested length smaller than L_native cannot be made safe just by stopping the endpoint sooner: Custom activation would shorten the loop even with unchanged endpoints. Return code **1000** for such a covered context, rather than inventing a larger Size. If every context's uncompressed custom request can preserve its native span, the required-width reply and candidate-span test provide a conservative acceptance boundary. Native-read fallback inputs must be part of the requested context revision. This may legitimately reject that first inward transition until direct Size/Custom editing changes the context; it is a geometry condition, not a mode exclusion. Outward accepted edits retain stock activation behavior as required.

### Concrete integration points and estimated resources

| Component | Candidate hook / reuse | New work |
|---|---|---|
| PIC endpoint acceptance | `DE68/DFBC`, existing adapters/helpers | Cache-valid/mode dispatch; clamp before SH; accepted-value push |
| PIC automatic Custom | `DCE0–DD08`, `DC18–DC40` | Defer and activate only accepted exact layer |
| PIC refresh triggers | Setter `DACC` per-layer storage; selection refresh `41048`; preset/sync completion | Invalidate before dependency mutations, coalesce request after normal notification |
| PIC transport | Send `75C1C`; reply range check before `51A88` | Four-slot reply/token validator and no stock-buffer writes |
| QNX request | `HandleMessage 1E050`, narrow default path for `4040–4043` before `206A6` return | Snapshot correct layer/oscillator, schedule/return cached geometry result |
| QNX group/header data | `358C6` handler-list installation; RAM loading `3E2F0/3E6D6–3E73D`; Read/Open formulas | Header coverage/lifetime, pure geometry/rate calculation and per-slot result |
| QNX reply | `1D7F0` encoding / `44F10` queue | Checked tagged atomic publication/recovery |

The addresses establish candidate instruction boundaries/owners, **not approved relocation sites**. No code cave, RAM hole, expanded object layout or safe header-cache owner has been selected.

Planning estimate, unassembled:

- PIC: retain the **2000-byte map table**; endpoint/Custom logic roughly **0.5–0.9 KB**; invalidation/request/reply/coalescing roughly **0.7–1.4 KB**. Total about **3.2–4.3 KB** code/table plus approximately **32–64 bytes replaced hook words**, subject to actual setter/preset hooks. Roughly **16 bytes per slot / 64 bytes RAM** for cached H, token, flags, context revision, outstanding revision and refresh state; timeout/session handling may add state. No pending knob replay is included.
- QNX: approximately **2–4 KB code** for header/geometry aggregation, request scheduling and checked reply, excluding placement/CFI/unwind bookkeeping and any newly factored Sync envelope complexity. Roughly **32–48 bytes per slot / 128–192 bytes RAM**, plus **24–32 bytes per covered sample** if a new header-geometry record stores association, N and validity/derived data. Existing handler Q/native fields can be referenced under verified lifetime, not duplicated unnecessarily. Sample count/coverage is not measured, so total per-sample RAM is not asserted.
- Normal refresh: **one 4-byte request and one 4-byte reply per affected slot**, no message per guarded endpoint tick. Cold/not-ready responses or recovery add traffic. Regular keeps its existing practical local limit; shared infrastructure mainly supplies missing all-mode context and native-transition protection.

Warm response is a local at-most-ten-comparison table search plus existing push. Cold instrument selection needs header readiness and rate-envelope work; Size/mode/tempo refresh can reuse headers but still requires a transport turn. No measured PIC clock/bus refresh latency or QNX cold-header timing is available; do not promise sub-millisecond response. Do geometry/header I/O outside the audio process and avoid a wait inside the PIC setter. Moving long header scans into QNX's serialized message thread would delay ordinary parameter/notes and must be avoided or bounded.

### Review blockers and required validation

This is the recommended direction because it preserves immediate **warm** knob handling and shares one monotone width invariant across modes. The inspected transport supports it, with candidate unclaimed IDs. It is not yet a complete safe patch design. Resolve:

1. Complete silent header coverage and ownership for the actual selectable instrument samples, including unloading/replacement and held old samples. No current pure metadata getter supplies N for every handler.
2. A useful sample-specific Sync rate envelope from the existing playback formulas and chosen note/stretch/modulation coverage. Active voices alone do not solve silent/future-note behavior; a globally guessed envelope is excluded.
3. Context invalidation for all relevant PIC paths and autonomous QNX tempo/geometry changes, plus output-inhibited/preset synchronization. A token cannot repair an unobserved state change.
4. Temporary invalid-cache knob behavior; whether all selectable note contexts are the desired acceptance domain; the six-bit token lifetime/drop recovery contract. These are explicit choices, not adopted new features.
5. Exact ID ownership outside the inspected dispatch paths, queue/delivery behavior, target table rounding and protected code/RAM placement.

Later validation should compare QNX aggregated requirements against each covered sample's existing Read/UpdateLoc geometry in all modes; test silent instruments, alternative/velocity samples and first native transitions; show useful Pitched/Sync travel on real instruments rather than only a bound. Exercise repeated/alternating endpoints, saturation, outward movement, linked A/B with one stale/rejected slot, Custom remaining unchanged on rejection, delayed/dropped/old/wrapped replies, rapid Size/mode/tempo/selection changes, disconnect/preset load and output gates. Verify PIC display/storage equals the accepted values sent to QNX, persistent Center/save-reload behavior and every inherited B6 fix. Transport tests must execute decoded .9 receive/store flows, followed by hardware response/audio checks; arithmetic encoding checks alone are insufficient.

**Stop for review.** Only this focused handover changed. No firmware patch, build, package, internal version or master-handover update; `PxUpdate_V2.2.2.1.0.bin` remains reserved.


## Calculation-only follow-up — useful conservative QNX span

Design only. The requested `handover_B7_endpoint_loop_stop_design(6).md` is not present in this workspace; the available focused handover above supplies the established findings used here. This appendix makes no transport changes and implements no cache. It supersedes the earlier statement that a safe first Sync envelope necessarily requires a full pitch/note preview: verified branch-specific playback-rate caps provide a cheaper conservative starting point, subject to inherited retained-rate transitions below.

**Recommendation:** the cached QNX-to-PIC calculation is practical in principle. With complete per-sample frame counts, its normal refresh can be a single pass over the covered sample records. Regular is already feasible; Pitched is straightforward; Sync has a cheap safe cap-based candidate, but its practical travel on real instruments remains unmeasured. Do not approve an all-mode implementation until header coverage, retained contexts and tempo lifetime are resolved.

### Required sample domain and metadata

For each layer/oscillator cover every sample that can be selected by its instrument: note zones, velocity/sample-selection alternatives and round-robin/random variants, including files not playing or presently loaded. `FindHandler` (`35940`, existing B5 trace) can choose the closest zone outside a declared note interval; simply testing each handler only inside `+200/+204` is insufficient. Initially taking the instrument's whole linked handler list is a cheap conservative superset. Narrowing that set requires evidence of permanent exclusion under the actual selection controls, not current availability flags.

Also cover still-playing/pending readers from an old selection where inherited playback has not finished. Their file lengths/quantum/rates must not be silently replaced by those of the newly selected instrument. Keep A/B and oscillators independent. No held note is needed for the future-sample domain: `SwitchSampleGroup` installs the handler list at group `+680`, `GetWavHandlers` (`35C10`) returns it, and handlers link at `+240`.

Existing handler metadata supplies quantum-source `+228`, native bounds `+210/+214` and selection fields. The constructor's default 440 and NoteOn's `Q=48000/handler[228]` are **code evidence**, not measured factory sample metadata. Apply the actual reader's existing quantum coercion/default rules; do not divide blindly for malformed/nonpositive handler data or introduce unrelated sanitization.

**The missing arithmetic input is N for every covered file**, not an instrument-wide average duration. Existing `CWavReader::Open` (`42660`; frame conversion `42B07–42B2A`) derives it from WAV data bytes divided by sample byte width and channels. Group metadata does not supply it. Smallest additional work: reuse/factor those header parsing semantics once per covered file, on the existing instrument/background-loading path, and retain a valid file/handler association and N. No PCM scan, sample-body playback, synthetic note or global sample-length approximation is needed. A loaded reader's `GetTotalSamples` is sufficient only for that file; unloaded future alternatives still require header coverage. Whether existing loading has made every such header accessible without held notes remains unverified.

Native coordinates are needed only for first native-to-custom assessment; the prior acceptance-gated Custom proposal remains unchanged. A rejected edit must not activate Custom. A first accepted inward transition requires the custom requested duration to be at least the old native duration for each covered context; a span limit cannot repair a shorter intrinsic custom request.

### Minimal arithmetic and useful refinements

For each covered sample i let `P_i=N_i-1`. Reuse the existing Read and UpdateLoc Size calculations, preserving their different truncation ordering, to obtain a sufficient **unclipped requested integer length** `req_i`. For Pitched/Sync take the larger requirement from those two paths. Do not derive it from the endpoint-clipped current L.

```text
Regular: R_i = F(RegularSize) * P_i
Pitched Read: R_i = max(Q_i, trunc(F(PitchedSize)*P_i/Q_i + .5)*Q_i)
Sync Read: R_i = r_i * (M(division)/BPM)
req_i = max(32, trunc(R_i))         // also cover UpdateLoc ordering

Pitched/Sync per-sample normalized requirement:
    if N_i <= 33 or req_i <= 32: h_i = 0
    else: h_i = min(1, req_i/P_i)
h = max_i(h_i)
```

For valid short files N≤33 the inherited outer span is endpoint-independent. For longer files, outer span is always at least 32; when both requests are ≤32 the minimum alone protects length. Those cases need no `32/P` gap. This refinement avoids unnecessarily freezing a whole instrument because a tiny file has the nominal 32-frame minimum. The existing conservative map/table allowance remains; zero requirement may still stop a final extremely small raw gap early. Keep the existing Regular rule `H=T[RegularSize]+3` unchanged, rather than replacing it with this sample-aware refinement.

When a requested length equals/exceeds a sample's full range, h=1 appropriately leaves no inward headroom. No endpoint movement can create the missing duration, and the design must not enlarge Size or repair an already compressed loop automatically. PIC tests the same absolute required span against both current endpoints; when current span is below it, inward movement stops at the current value. Repeated/alternating edits cannot ratchet the requirement down. Outward movement and direct Center/Size edits retain their inherited behavior.

Pitched can either evaluate the existing quantization once per sample or use `R_i <= max(Q_i, F(Size)*P_i+Q_i/2)` and round upward. Exact evaluation of the two existing expressions is inexpensive and avoids an unnecessary half-quantum allowance. Q is independent of played note in the traced construction; tempo does not enter this mode's requested geometry. Size/quantum/sample changes need a new calculation. The raw mapped Size plus a guessed multiplier is still unsuitable.

### Sync: verified units and branch-specific rate bounds

The .9 initializer `7BF0–7D23` constructs `gpBPMToSampleSizeMul` from **60 × 48000 × 4**, then division factors. For example, index 0 is **720000**, index 3 **2880000**, index 7 **11520000**. These are verified table-construction constants. `PreLPFProcessLoop` (`1AE7F–1AED8`) interpolates M and multiplies by `1/BPM`. Thus `M/BPM` is already a **frame quantity at unit traversal rate**, not seconds. Do not multiply by 48000 again. Read uses the positive effective rate, otherwise fallback 1; UpdateLoc first truncates the duration lane. Reuse those exact orders.

The reused `CSampleOsc::PlayNote` trace and narrow .9 constant/branch check establish:

| Playback branch | Sufficient ceiling for newly requested source-frame rate |
|---|---:|
| Stretch off (`sample oscillator +6C == 0`) | 4 |
| Stretch on, AB-mode actual parameter `198 <= 1` | 32 |
| Stretch on, AB-mode `198 > 1` | 8 |

The loading/guard branch can reduce a high stretched rate to 4; using 8/32 without exploiting that temporary condition is conservative. `SetIsStretchMode` (`367C0`, store `367D6`) and SetParams establish the +6C meaning. At `372AD` the incoming note frequency is divided by handler `+228`; `372BB–372D1`, `374C0–374F0` and `37738–37740` apply constants at `566F0=4`, `5EC58=8`, `5EC5C=32`. These caps are playback-branch bounds, **not Regular/Pitched/Sync mode identities**. A Sync loop can use any of these branches.

Consequently a safe starting Sync envelope for future samples is their applicable **4/8/32 cap**, requiring no full note-frequency/modulation preview and protecting ordinary rate increases within that unchanged branch. It is not an arbitrary safety multiplier. Sample-specific tighter envelopes could improve travel later, but are unnecessary to establish this first candidate's arithmetic safety.

**Inherited transition qualification:** .9 contains rate-holding adapters (the existing B5/B8 evidence). In particular `b8_adapters.c` uses retained `effective.rate_bits`; the .9 thunk at `F8742–F8749` restores the rate-call setup. `ClientProcessStream` passes its float rate onward to Read; its `>32` branch limits read-block allocation, not the rate itself. Therefore a freshly selected cap of 4 must not silently exclude a retained rate of 8/32 from a still-live context. Add the actual retained/pending rate requirement for that reader, or retain the old branch envelope until it is quiescent. The smallest unresolved inspection is the existing rate-hold lifetime and which live/pending records must be included when a cap decreases; no new audio behavior is proposed.

Tempo and division remain explicit inputs. Slowing BPM increases the required width; doubling r doubles it. A result for current BPM is safe only while that BPM/division context remains valid. To cover an interval of future tempos cheaply, use its established **positive minimum BPM**, and the maximum interpolated M in its established division/Size-modulation domain. No such interval is adopted here. The front-panel minimum of 30 does not by itself prove every external-clock path obeys 30, and using the whole tempo/division range may make travel unusable. Resolve actual tempo-change ordering and numeric range in the known tempo writer before claiming safety across asynchronous changes. This is a calculation/lifetime dependency, not further messaging design.

Rate caps can cover pitch-induced rate changes but cannot protect arbitrary independent endpoint or Size modulation. The required Size/M envelope must cover whatever modulation context the feature promises to protect. Using instantaneous active-voice Size fails the silent/future-note case; using the entire modulation range may force full-window requirements. No silent modulation-policy choice is made here.

### Focused host examples — assumptions are explicit

All sample lengths and sample-frequency assignments below are **synthetic model inputs**, not measured factory/user sample metadata. N=48001/192001/480001 means P=48000/192000/480000; “one/four/ten seconds” is shorthand under the explicit 48 kHz assumption. Values 220/440 are assumed handler frequencies; 440 also occurs as the constructor default. Sync M values and branch caps are verified code constants. The host uses the saved .9 float32 map/constants and the existing outer/Size formulas, without executing target firmware.

| Context, Size=500 for Regular/Pitched | Requested frames | Required normalized span before map guard |
|---|---:|---:|
| Regular, N=48001 | 3680 | Existing Regular mapped Size rule retained |
| Regular, N=192001 | 14722 | Same mapped Size rule despite different N |
| Pitched, N=48001, assumed handler=440 | 3709 | 0.077270833; width code 502 |
| Pitched, N=192001, assumed handler=220 | 14618 | 0.076135417; width code 499 |
| Both Pitched samples selectable | 3709 / 14618 | Maximum 0.077270833; first sample governs both |

The quantized difference here is modest: +29 frames over the one-second Regular request, −104 frames on the four-second request. This is a useful arithmetic example, not evidence that all instruments have similarly small quantization error. With the existing width-code ceiling and guard, the combined h becomes about **0.077561608**, permitting Start to advance from 0 to raw **982** with End=999. A small Size near/below one quantum can stop proportionally much earlier; actual Q/P values decide that frequency.

Sync examples use normal-branch cap **4**, no retained higher rate, no Size modulation, and all samples selectable. `r=1` is a comparison assumption, not the protected envelope:

| P | M | BPM | Requested frames at r=1 / cap 4 | Required h at cap 4 |
|---:|---:|---:|---:|---:|
| 48000 | 720000 | 120 | 6000 / 24000 | 0.5 |
| 192000 | 720000 | 120 | 6000 / 24000 | 0.125 |
| 480000 | 720000 | 120 | 6000 / 24000 | 0.05 |
| 48000 | 2880000 | 120 | 24000 / 96000 | 1, no inward headroom |
| 192000 | 2880000 | 120 | 24000 / 96000 | 0.5 |
| 480000 | 2880000 | 120 | 24000 / 96000 | 0.2 |
| 192000 | 2880000 | 60 | 48000 / 192000 | 1, no inward headroom |

For M=720000/BPM120, combining the one- and four-second samples yields h=0.5: the shorter sample dominates even while silent. Guarded width becomes about **0.501579309**, giving raw Start stop **860** with End=999. On a ten-second-only sample the analogous width is about **0.050064851**, allowing raw Start **988**. The normal cap costs up to a factor of four versus a constant r=1 context; 8/32 branches can be much more restrictive. Some ordinary short-sample/long-division contexts therefore have no safe headroom under this all-note bound. This is an explicit practical restriction; it is not evidence of how routinely real instruments encounter it.

**Already compressed:** raw Start=200, End=500, N=48001, M=720000/BPM120, cap 4 produces requested length **24000**, while the existing QNX outer span is only **3113** (normalized raw span about 0.064864188). The fixed requirement 0.5 exceeds that span. Both further inward directions retain their old raw endpoint and L=3113; the design does not gradually accept smaller targets from this clipped L or pretend to restore 24000. Outward expansion or a direct Size/context edit remains available.

Additional in-memory check: **48,000 alternating inward requests** across 1200 three-sample scenarios, with different N in `{17,33,34,64,4096,48001,192001,480001}`, assumed handler frequencies `{220,440,880}`, applicable modeled caps `{4,8,32}`, tempos `{30,60,120,240}` and verified M values `{720000,2880000}`. It compared **288,000** per-sample Read/UpdateLoc length values before/after acceptance, with zero decreases. The check used fixed context/Size, the short/minimum refinements and the existing guarded width-code search. The numerical tempo set is test input, not a proved external-clock range. Many deliberately tight/full-window scenarios stop immediately, so these counts measure invariant checks, not practical usability. No script/output artifact, firmware code, cache or binary was generated. These checks do **not** establish hardware responsiveness or full floating-point/transition/modulation coverage.

### Remaining smallest investigations and disposition

The warm arithmetic is O(number of covered samples), with one Pitched quantization evaluation per path/sample or one Sync multiplication/division plus a maximum. Precomputing file-derived reciprocal P and Q is optional, not necessary to prove the rule. Header access and transition ownership, rather than the basic formulas, are the potentially costly work. No target execution timing or new footprint measurement is claimed.

The next smallest necessary investigations are:

1. Inspect one real selected instrument's full handler list and corresponding WAV headers while silent; obtain paired N/Q/native data for every alternative, verify unloaded alternatives and keep a small representative set of short/long and stretched instruments. Compute the bound distribution and resulting raw travel. No such measured sample set is currently present locally, so whether the bound would **routinely** stop too early remains unknown.
2. Follow only the known .9 retained-rate records and their release/change points to establish inclusion of old/pending contexts after selection/stretch/AB changes. A cap-based reliable bound must cover those records; current controls alone do not prove they are gone.
3. Follow the existing tempo `182`/external-clock update path to establish the lowest tempo within a limit's valid lifetime; establish the intended Size/division/endpoint modulation domain. No protocol expansion or general audio investigation is needed for this numeric/lifetime audit.

**For review:** proceed with the cached-width approach as a feasible direction, using existing Regular behavior, per-sample Pitched geometry and verified branch-cap Sync bounds. The earlier full note-preview blocker can be reduced to a usefulness refinement rather than a prerequisite for the first safe bound. All-mode readiness remains blocked by complete sample-header coverage, retained-context accounting, tempo/modulation scope and measured usability. Keep the previously documented cache/Custom integration blockers; do not implement anything in this pass. All inherited fixes and B6 remain unchanged; master handover untouched and `PxUpdate_V2.2.2.1.0.bin` reserved.
