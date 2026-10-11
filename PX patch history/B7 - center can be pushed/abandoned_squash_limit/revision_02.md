# B7 endpoint stop before loop compression — design for review

Design only, 5 October 2026. No patch, build, package or version change. Master handover unchanged. Baseline is the owner hardware-tested B6 `PxUpdate_V2.2.2.0.9.bin`; older handovers’ “untested”/“B6 abandoned” statements are historical.

## Current investigation result

The latest feasibility pass, including the owner’s acceptance of approximate stopping, establishes a small **PIC-only normalized limit for Regular mode**. Sample length cancels from the ideal rule; fixed-table arithmetic can keep repeated inward edits from ratcheting the window smaller. Short/minimum-length loops can stop earlier than necessary. Pitched and Sync are not covered by that derivation; their behavior remains a review decision, not an adopted Regular-only release. See “Regular-mode normalized feasibility” below.

Earlier metadata findings remain valid. Their conclusion that complete exact all-mode playback geometry is unavailable on PIC does **not** prevent this approximate Regular calculation. The earlier exact-geometry/integration discussion is historical context, not the current recommendation to pursue frame-perfect arithmetic or communication. No protocol investigation, patch, build, package or version change is authorized. `2.2.2.1.0` remains reserved.

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
