# B14 - Encoder acceleration and responsive sample display

Technical handover for the retained B14 encoder and display changes. The implementation is hardware-confirmed, including the final sample-encoder acceleration refinement. These identify B14 milestones, not the latest combined project firmware.

**Firmware:** `2.2.2.1.10` (sample-encoder refinement), inheriting the accepted `.1.7` stable-display implementation through `.1.9`.

**Hardware: PASS:** The .1.7 display behavior was accepted and .1.10 sample-encoder refinement reported working. Some residual rapid-browsing lag remains in the type/instrument encoders, but this has been deemed acceptable.

## Accepted behavior

B14 removes speed-dependent acceleration from general/menu encoders and preserves accumulated canonical movement through individual signed-unit events. The dedicated sample Size, Center, Start and End encoders regain factory acceleration in 2.2.2.1.10. Type and Instrument browsing remain unaccelerated. Mod-matrix Amount acceleration was discussed but was not implemented in the available evidence.

The .1.10 sample-acceleration refinement was implemented and reported working on hardware. These reports supersede the original handovers' build-time hardware-not-verified statements; they do not imply exhaustive hardware coverage.

## Investigation and original implementation

**Patch location:** PIC controller (MIPS) for decoding, dispatch, metadata reads and display; QNX edits are revision metadata only.

**Patch size:** Stage-specific write spans: .1.4 decoder/service 160 bytes (146 actual changed values); .1.6 metadata reads 84 bytes (73 changed); .1.7 display 240 bytes (229 changed), including 192 helper bytes. Final .1.10 refinement: 416 functional span bytes + eight revision-span bytes, with 328 actual changed PIC bytes and 333 package bytes versus .1.9. These are successive baseline comparisons, not a cumulative byte total. No payload growth.

Acceleration originated in the PIC encoder decoder at 9d07a298, rather than QNX. The fast path adds weighted magnitudes and accepts extra noncanonical transitions. Movement is also legitimately accumulated in signed encoder record offset +8. Some UI consumers use the entire delta; others consume only its sign. Removing source acceleration alone would leave sign-only consumers collapsing several genuine counts into one step.

The initial global candidate used the B9 .1.2 PIC baseline:

- Baseline: b9_250_candidate_work/pic_2.2.2.1.2.bin
- Baseline SHA-256: 8f3fcbccd5763324e5f0b7d9cc5941df806a9ecb46affa5c18f5f4d1b082a16c
- Candidate: b14_candidate_work/pic_B14_global_no_acceleration_unpackaged.bin
- Candidate SHA-256: c8bead4c8d7cee282af0d2bd7269a6816910d0fe4029473ab57afcbbcdd516e5
- Candidate size: 530784 bytes, unchanged from baseline.

Two branch instructions at 9d07a34c and 9d07a3c8 became NOPs, forcing canonical slow decoding. Service entry 9d07a208 was redirected to a 144-byte helper in [9d07a468,9d07a4f8), reusing now-dead acceleration code. The helper atomically snapshots and clears movement with interrupts briefly disabled, restores the original CP0 Status before dispatch, and emits one ±1 event for each snapshot count through 9d07db44. New ISR movement remains pending for the next pass. No post-dispatch clear occurs.

The original implementation replaced 40 words /160 write-span bytes, with146 byte values changed. No payload growth or persistent RAM was added. Its32-byte frame was8 bytes deeper than the original24-byte service frame. The later .1.10 statement of no added stack describes that refinement, not a retroactive zero-stack claim for initial B14.

Existing quadrature rejection/history and downstream handlers, buttons, INC/DEC, B9 and inherited patches were preserved. Signed-net acquisition can cancel opposite-direction movements before service; it is not a per-detent FIFO. Full synchronous replay can delay other main-loop work under large backlogs.

Initial reported host validation:65,536 decoder cases,42 quadrature sweeps,462 service/ABI cases,39 instruction-boundary ISR injections and2 during-dispatch injections, with placement and independent disassembly checks. These are reported results from the original handover, not rerun results from this documentation session.

## Accepted releases and responsiveness improvements

| Revision | Change and outcome |
|---|---|
| .1.4 | Packaged global canonical decoding and atomic unit replay; owner reported almost perfect behavior with residual very-fast Type/Instrument catchup. |
| .1.6 | Built from .1.4. Reads valid64-byte sample metadata in one SPI transaction rather than64 separate transactions. Owner still reported lag. |
| .1.7 | Stable primary display frames: render all dirty sample fields only when both transfers are idle; preserve primary buffer while transfer runs; retain new dirty flags for the next frame. Owner reported improvement and accepted good-enough behavior. |
| .1.10 | Built on .1.9, preserving B15 and inherited behavior; restores acceleration for four dedicated sample encoders. Owner confirmed working on hardware. |

The accepted `.1.7` solution retains complete snapshot replay and protects display-buffer ownership during transfer.

The .1.6 metadata change uses the existing destination and formatting, retains dependent attribute semantics and bounded polling, and adds no RAM/helper cave. Its valid-record change is73 differing byte values /84 write-span bytes. Enabled Instrument can still refresh metadata twice; reducing transactions is not proof of measured latency.

The .1.7 renderer guard and page/blank/resume/general-clear wrappers occupy192 bytes in [9d0013ac,9d00146c). The raw change is229 differing byte values /240 write-span bytes. No new RAM, queue, IRQ masking or stack depth. Page/blanking boundaries cancel obsolete primary transfers before buffer changes. This is not a claim of atomically displayed physical page transitions. Ownership auditing retained36 unresolved indirect sites.

Reported .1.7 validation includes8256 active-primary guard cases,774 active-secondary cases,64 render masks, cancellation/prologue equivalence, sustained input, page transitions and secondary fairness; packaging includes22 updater-gate cases and130 transport blocks /260 valid-corrupt comparisons. Drawing/OLED bodies were modeled summaries, not physical I/O emulation.

## Sample encoder acceleration refinement (.1.10)

| Control | Physical encoder ID |
|---|---|
| Size |4|
| Center |5|
| Start |18|
| End |19|

These IDs accelerate in every assignment mode using original timing, warm-up and gain rules. Their full atomic snapshots dispatch once; other IDs retain unit replay. Size alternate assignments retain descriptor maxima. No additional RAM, stack usage or PIC payload growth was reported for this refinement. QNX changes are version metadata only; FPGA unchanged.

Reported host checks:80,640 decoder cases,1,323 service cases,180 numeric routes, patch/ABI and package/checksum/modeled updater checks. Exact replacement ranges and bytes are now supplied in `b14_sample_acceleration_work/build.py` and `patch_manifest.json`, summarized below.

## Package identities (reference only; binaries not included)

| Package | SHA-256 |
|---|---|
| PxUpdate_V2.2.2.1.4.bin |eadf12ea51991ad749155c89136fa01176578b8e936df6851c6987b728af94f4|
| PxUpdate_V2.2.2.1.7.bin |91ec37c306731743c62f10b915450f8e64bccec3260e84a9ca8938d146df7f82|
| PxUpdate_V2.2.2.1.10_B14_sample_acceleration_candidate.bin |6ab00ccd1f9461ffcf5927b54b317d7644c85a3a129dff6115f8cd0cd6a6a6e3|

.1.7 package size:3151848 bytes. .1.10 package size:3187784 bytes. .1.10 is based on .1.9, so that package-size difference cannot be attributed to B14 alone. The `.1.10` package inherits the older B5 endpoint-click-under-pitch-modulation bug. B5 `.1.11` supersedes that B5 behavior while preserving B14; see the [B5 handover](../B5%20-%20sample%20end%20fade/README.md). B14 hardware acceptance does not turn `.1.10` into the final integrated firmware.

## Exact .1.10 implementation map

All addresses are PIC virtual addresses; ranges end exclusively. The `.1.10` builder starts from the exact `.1.9` PIC and accounts for every changed byte:

| Location | Write span | Purpose |
|---|---:|---|
| `0x9D07A298–0x9D07A400` | 360 bytes | Decoder with original acceleration policy for physical IDs 4, 5, 18 and 19; canonical unaccelerated policy for other IDs |
| `0x9D07A440–0x9D07A468` | 40 bytes | Snapshot classifier selecting full dispatch versus unit replay |
| `0x9D07A244–0x9D07A24C` | 8 bytes | Full-snapshot continuation |
| `0x9D07A4B8–0x9D07A4C0` | 8 bytes | Unit-replay sign hook |
| `0x9D001394`, `0x9D0013A0` | 4 bytes each | Revision component 9 → 10 |

The six write spans contain 328 differing PIC byte values including revision metadata. Candidate PIC SHA-256 is `6622acc21ba805bd6049ba639b60399dde77e299048cabf2865d56892dc8c145`. All B15 helper pieces are compared against their baseline bytes using `absolute_pic_integration.json`. Additional RAM, stack depth and payload growth for this refinement are zero; the reported remaining code margin is 28 bytes.

The `.1.10` package changes two QNX revision bytes (`0x1F4E3`, `0x250EF`), with no QNX behavior change. Overall package differences total 333 byte values. Full exact before/after spans are in the patch manifest; saved package results record component identities and checksum checks.

## Hardware result and regression scope

**Hardware PASS:**  `.1.7` and  `.1.10` have been successfully tested on hardware. Saved tests are separate from these qualitative device reports; no latency or CPU headroom measurements are recorded.

Regression scenarios cover slow/fast turns, reversal, bounds, Size/Center/Start/End, both instruments and A/B/Both layers, Size modes and alternate assignments. Type/Instrument and mod-matrix Amount retain unaccelerated behavior. Check menu movement, stable display updates and inherited B15 functionality. Mod-matrix Amount acceleration was discussed but was not implemented.

## Recovered build and packaging path

The original source, manifests, test runners and saved reports are under `implementation/`. Their sibling directory paths are preserved for imports. All working paths below are relative to that directory. Python 3 is required; MIPS assembly is emitted by the supplied encoders rather than an external compiler. The core `.1.10` sequence, from `implementation/` in a private working copy, is:

```sh
cd implementation
python3 b14_sample_acceleration_work/build.py
python3 b14_sample_acceleration_work/validate.py
python3 b14_sample_acceleration_work/package.py
```

Supply these exact private inputs:

| Private input | SHA-256 |
|---|---|
| `b15_candidate_work/PxUpdate_V2.2.2.1.9_B15_LFO_fade_candidate.bin` | `fe1858e1da01aeae69e41799dfbdfb1471f90b0c19d34687663533438f52a2da` |
| `b15_candidate_work/pic_2.2.2.1.9_B15_LFO_fade_candidate.bin` | `bc4b1109ccf3f45988cac165b5e8e7b41381c4f6e7cbdfb4f3d619351a7ba82f` |

The builder emits `b14_sample_acceleration_work/pic_2.2.2.1.10_B14_sample_acceleration_candidate.bin`. The validator executes decoder/service bytes with modeled external operations. The packager imports established container helpers, reuses bounded updater/version/checksum tests, sets application/PIC headers and revision replies to `.1.10`, recalculates the application checksum and preserves the complete FPGA record and inherited PIC trailer `30 30`. It writes the updater-facing package inside `b14_sample_acceleration_work/` and verifies parse/serialize/re-extraction identities. Some original scripts write named checkpoint files; use a fresh private copy and keep generated firmware outside the public repository.

Earlier retained stages are `.1.4` global canonical decoder/unit replay (`b14_candidate_work/`, `b14_packaging_work/`), `.1.6` bulk metadata read (`b14_metadata_candidate_work/`, `b14_metadata_packaging_work/`), and `.1.7` stable display (`b14_stable_frame_candidate_work/`, `b14_stable_frame_packaging_work/`). Their original scripts require exact preceding packages and extracted components. The [direct firmware patcher](../../firmware_builder/patch_prophet_x.py) builds the final combined update directly from the exact factory input using authored generators and pinned redacted objects. See the [direct builder implementation](../../firmware_builder/direct/IMPLEMENTATION.md). The separate [compiler audit path](../../firmware_builder/source_rebuild/README.md) retains incremental source rebuilding and its original validation scope.

`b14_ui_candidate_work/build_display.py` is retained solely because the accepted stable-frame builder imports its `enc` function. Its experimental scheduler entry point is not part of the accepted build. `b15_candidate_work/build_candidate_1_8.py`, `build_candidate_1_9.py` and `validate_pic_emission.py` provide container/checksum/decoder utilities; their standalone B15 entry points are not B14 build steps.

The source pipeline now supplies SHA-256 guards to the metadata builder (`b14_investigation/ui_exact_1_4.json`). Historical listing-based audits used private exported firmware listings/logs (`b14_investigation/ui_exact_1_4.txt`, metadata `ghidra_disassembly.txt`/`ghidra.log`). Those proprietary exports are excluded. Their saved PASS reports are included, but those historical evidence checks are not a self-contained public rerun. The optional stable-frame Ghidra evidence checker and an unused service-layout sketch are archived privately; neither is needed by the retained build path. The retained `.1.10` build/validation/package path does not require Ghidra or those exports.

## Complete supporting-file inventory

The root contains this handover, [SHA256SUMS](SHA256SUMS), and `implementation/`. Every supporting file is linked below, grouped by its role. Earlier accepted stages explain behavior inherited by `.1.10`; they are not all needed to build that refinement. Firmware packages, extracted payloads, objects and proprietary disassembly exports remain excluded.

### Retained .1.10 implementation and tests

| File | Purpose |
|---|---|
| [b14_sample_acceleration_investigation/check_layout.py](implementation/b14_sample_acceleration_investigation/check_layout.py) | Independent reference decoder behavior used by .1.10 tests. |
| [b14_sample_acceleration_investigation/decoder_layout.txt](implementation/b14_sample_acceleration_investigation/decoder_layout.txt) | Source decoder layout consumed by .1.10 builder and reference checks. |
| [b14_sample_acceleration_investigation/layout_results.json](implementation/b14_sample_acceleration_investigation/layout_results.json) | Saved assembly/patch, validation, diff or owner hardware evidence. |
| [b14_sample_acceleration_work/build.py](implementation/b14_sample_acceleration_work/build.py) | Implementation builder for this accepted stage. |
| [b14_sample_acceleration_work/package.py](implementation/b14_sample_acceleration_work/package.py) | Incremental packager and independent extraction/checksum checks. |
| [b14_sample_acceleration_work/package_results.json](implementation/b14_sample_acceleration_work/package_results.json) | Saved assembly/patch, validation, diff or owner hardware evidence. |
| [b14_sample_acceleration_work/patch_manifest.json](implementation/b14_sample_acceleration_work/patch_manifest.json) | Saved assembly/patch, validation, diff or owner hardware evidence. |
| [b14_sample_acceleration_work/validate.py](implementation/b14_sample_acceleration_work/validate.py) | Emitted instruction or placement validation. |
| [b14_sample_acceleration_work/validation_results.json](implementation/b14_sample_acceleration_work/validation_results.json) | Saved assembly/patch, validation, diff or owner hardware evidence. |

### Accepted global decoding and unit replay — .1.4

| File | Purpose |
|---|---|
| [b14_candidate_work/assembly_input.json](implementation/b14_candidate_work/assembly_input.json) | Saved assembly/patch, validation, diff or owner hardware evidence. |
| [b14_candidate_work/build_b14.py](implementation/b14_candidate_work/build_b14.py) | Implementation builder for this accepted stage. |
| [b14_candidate_work/patch_manifest.json](implementation/b14_candidate_work/patch_manifest.json) | Saved assembly/patch, validation, diff or owner hardware evidence. |
| [b14_candidate_work/placement_results.json](implementation/b14_candidate_work/placement_results.json) | Saved assembly/patch, validation, diff or owner hardware evidence. |
| [b14_candidate_work/validate_b14.py](implementation/b14_candidate_work/validate_b14.py) | Emitted instruction or placement validation. |
| [b14_candidate_work/validation_results.json](implementation/b14_candidate_work/validation_results.json) | Saved assembly/patch, validation, diff or owner hardware evidence. |
| [b14_candidate_work/verify_placement.py](implementation/b14_candidate_work/verify_placement.py) | Emitted instruction or placement validation. |
| [b14_packaging_work/binary_diff.json](implementation/b14_packaging_work/binary_diff.json) | Saved assembly/patch, validation, diff or owner hardware evidence. |
| [b14_packaging_work/package_b14.py](implementation/b14_packaging_work/package_b14.py) | Incremental packager and independent extraction/checksum checks. |
| [b14_packaging_work/packaged_validation.json](implementation/b14_packaging_work/packaged_validation.json) | Saved assembly/patch, validation, diff or owner hardware evidence. |

### Accepted metadata reads — .1.6

| File | Purpose |
|---|---|
| [b14_metadata_candidate_work/assembly_input.json](implementation/b14_metadata_candidate_work/assembly_input.json) | Saved assembly/patch, validation, diff or owner hardware evidence. |
| [b14_metadata_candidate_work/audit_metadata.py](implementation/b14_metadata_candidate_work/audit_metadata.py) | Emitted instruction or placement validation. |
| [b14_metadata_candidate_work/build_metadata.py](implementation/b14_metadata_candidate_work/build_metadata.py) | Implementation builder for this accepted stage. |
| [b14_metadata_candidate_work/patch_manifest.json](implementation/b14_metadata_candidate_work/patch_manifest.json) | Saved assembly/patch, validation, diff or owner hardware evidence. |
| [b14_metadata_candidate_work/placement_results.json](implementation/b14_metadata_candidate_work/placement_results.json) | Saved assembly/patch, validation, diff or owner hardware evidence. |
| [b14_metadata_candidate_work/validate_metadata.py](implementation/b14_metadata_candidate_work/validate_metadata.py) | Emitted instruction or placement validation. |
| [b14_metadata_candidate_work/validation_results.json](implementation/b14_metadata_candidate_work/validation_results.json) | Saved assembly/patch, validation, diff or owner hardware evidence. |
| [b14_metadata_packaging_work/binary_diff.json](implementation/b14_metadata_packaging_work/binary_diff.json) | Saved assembly/patch, validation, diff or owner hardware evidence. |
| [b14_metadata_packaging_work/hardware_feedback.json](implementation/b14_metadata_packaging_work/hardware_feedback.json) | Saved assembly/patch, validation, diff or owner hardware evidence. |
| [b14_metadata_packaging_work/package_metadata.py](implementation/b14_metadata_packaging_work/package_metadata.py) | Incremental packager and independent extraction/checksum checks. |
| [b14_metadata_packaging_work/packaged_validation.json](implementation/b14_metadata_packaging_work/packaged_validation.json) | Saved assembly/patch, validation, diff or owner hardware evidence. |

### Accepted stable display — .1.7

| File | Purpose |
|---|---|
| [b14_stable_frame_candidate_work/assembly_input.json](implementation/b14_stable_frame_candidate_work/assembly_input.json) | Saved assembly/patch, validation, diff or owner hardware evidence. |
| [b14_stable_frame_candidate_work/audit_stable.py](implementation/b14_stable_frame_candidate_work/audit_stable.py) | Emitted instruction or placement validation. |
| [b14_stable_frame_candidate_work/build_stable.py](implementation/b14_stable_frame_candidate_work/build_stable.py) | Implementation builder for this accepted stage. |
| [b14_stable_frame_candidate_work/evidence_results.json](implementation/b14_stable_frame_candidate_work/evidence_results.json) | Saved assembly/patch, validation, diff or owner hardware evidence. |
| [b14_stable_frame_candidate_work/patch_manifest.json](implementation/b14_stable_frame_candidate_work/patch_manifest.json) | Saved assembly/patch, validation, diff or owner hardware evidence. |
| [b14_stable_frame_candidate_work/placement_results.json](implementation/b14_stable_frame_candidate_work/placement_results.json) | Saved assembly/patch, validation, diff or owner hardware evidence. |
| [b14_stable_frame_candidate_work/validate_stable.py](implementation/b14_stable_frame_candidate_work/validate_stable.py) | Emitted instruction or placement validation. |
| [b14_stable_frame_candidate_work/validation_results.json](implementation/b14_stable_frame_candidate_work/validation_results.json) | Saved assembly/patch, validation, diff or owner hardware evidence. |
| [b14_stable_frame_packaging_work/binary_diff.json](implementation/b14_stable_frame_packaging_work/binary_diff.json) | Saved assembly/patch, validation, diff or owner hardware evidence. |
| [b14_stable_frame_packaging_work/hardware_feedback.json](implementation/b14_stable_frame_packaging_work/hardware_feedback.json) | Saved assembly/patch, validation, diff or owner hardware evidence. |
| [b14_stable_frame_packaging_work/package_stable.py](implementation/b14_stable_frame_packaging_work/package_stable.py) | Incremental packager and independent extraction/checksum checks. |
| [b14_stable_frame_packaging_work/packaged_validation.json](implementation/b14_stable_frame_packaging_work/packaged_validation.json) | Saved assembly/patch, validation, diff or owner hardware evidence. |

### Shared dependencies

| File | Purpose |
|---|---|
| [b14_ui_candidate_work/build_display.py](implementation/b14_ui_candidate_work/build_display.py) | Assembler function imported by stable-frame builder; experimental scheduler entry point is not used. |
| [b15_candidate_work/absolute_pic_integration.json](implementation/b15_candidate_work/absolute_pic_integration.json) | B15 helper-piece ranges checked unchanged by .1.10 builder. |
| [b15_candidate_work/build_candidate_1_8.py](implementation/b15_candidate_work/build_candidate_1_8.py) | Container parsing, serialization, checksum and diff utilities imported by .1.10. |
| [b15_candidate_work/build_candidate_1_9.py](implementation/b15_candidate_work/build_candidate_1_9.py) | Bounded updater/checksum test block reused by .1.10 packager. |
| [b15_candidate_work/validate_pic_emission.py](implementation/b15_candidate_work/validate_pic_emission.py) | PIC instruction interpreter extension used by .1.10 build/tests. |
| [b7_candidate_work/validate_version_gates.py](implementation/b7_candidate_work/validate_version_gates.py) | Version-gate function extracted by package validation. |
| [b9_250_candidate_work/b9_patch_manifest.json](implementation/b9_250_candidate_work/b9_patch_manifest.json) | Pinned baseline package identity used by .1.4 packaging. |
| [b9_250_candidate_work/mips_check.py](implementation/b9_250_candidate_work/mips_check.py) | Base instruction decoder/interpreter for emitted-byte tests. |

Audit checks: all supporting files linked, Python/JSON syntax valid, root checksums refreshed, and no firmware binaries present. Original relative imports remain intact. Builds and feature tests were not rerun.
