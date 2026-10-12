# B7 - Endpoint edits push Center, linked ordering, and Center modulation

Technical handover for B7 and its LFO-to-Center follow-up. Both implementations are complete and hardware-confirmed. The abandoned loop-window squash investigation is retained as evidence and produced no squash-limit firmware. These are feature milestones, not the latest combined project firmware.

**Firmware:** `2.2.2.0.8` (original PIC fixes); `2.2.2.1.12` (QNX Center-modulation follow-up).

**Hardware: PASS (owner-reported)** The original Center-push and linked-layer Start/End ordering fixes, plus the .1.12 follow-up, were confirmed working. Individual physical regression cases and stack-margin measurements were not separately reported.

## Original fix - 2.2.2.0.8

**Patch location:** PIC for the original .0.8 endpoint/linked-layer fixes; QNX for the .1.12 LFO-to-Center follow-up.

**Patch size:** Original PIC fix: 300 helper-code bytes + 48 hook bytes = 348 functional write-span bytes (helpers occupy a 372-byte extent with untouched gaps). QNX follow-up: 859 code/constant bytes + a 12-byte hook, 188 unwind bytes and 16 added index bytes, all within inherited reservations; versus .1.11, 951 QNX bytes and two PIC revision bytes differ. No payload growth.

Start/End edits that strictly cross Center push stored Center to the accepted endpoint when looping is enabled. Retreat leaves Center where it was pushed; equality does not push. Loop-off edits retain Center. The same patch fixes stock linked-layer endpoint ordering: an absolute linked request is evaluated independently against each layer's own opposite endpoint, preserving Start<=End even when A/B have unequal windows.

B7 does not make manual Center move endpoints. That is B6, introduced subsequently in `.0.9`. B7's original `.0.8` implementation preserves stock direct-Center and Size behavior. Raw sample coordinates and descriptor limits remain stock.

### Start > End bug when editing both layers

**Fixed in 2.2.2.0.8; owner-confirmed hardware PASS.** In stock firmware, editing Start or End with both layers selected could invert one layer's window when A and B had different endpoint limits. Start could exceed End, or End could fall below Start.

The patch preserves the original absolute requested value and evaluates it independently against each layer's own opposite endpoint. A retains its stock ordering checks; B receives an ordering check before descriptor limiting, storage and notification. A's accepted/clamped value is not substituted for B's original request. Both layers retain `Start <= End`; equality is allowed. This protection applies with looping on or off and is separate from the loop-on Center-push behavior.

For example, if A has End=800 and B has End=400, a linked Start request of 600 can be accepted as 600 in A while B is limited to its own End of 400. B must not inherit A's accepted 600 and become inverted. This illustrates the per-layer rule, rather than an additional reported hardware fixture.

The request-capture hook is at `0x9D04DAF4`; the B-ordering hook is at `0x9D04DFA0`, entering helper `0x9D001240`. The validation below covers unequal layer windows, both endpoint directions, linked versus individual edits and retreat. The owner confirmed the ordering fix working on hardware.

### PIC patch map

PIC addresses are runtime virtual addresses with base `0x9D000000`; instruction words are stored little-endian. Ranges exclude the end.

| Hook | Destination / purpose |
|---|---|
| `0x9D04DAF4` | `0x9D001220`, capture original full-width absolute request |
| `0x9D04DFA0` | `0x9D001240`, order layer-B request before limiting/storage |
| `0x9D04DE68` | `0x9D0012C0`, layer-A endpoint adapter |
| `0x9D04DFBC` | `0x9D0012F0`, layer-B endpoint adapter |
| `0x9D04DCC4`, `0x9D04E2D0`, `0x9D04E420`, `0x9D04E4D4` | Jump to `0x9D04E4EC`, preserving original NOP delay slots |
| `0x9D04DBFC`, `0x9D04DDE8`, `0x9D04E45C`, `0x9D04E498` | Jump to `0x9D04E4B0`, preserving original NOP delay slots |

The four main hooks preserve their original delay-slot operations, including endpoint storage. Inserted helper ranges:

| Helper | Range | Bytes |
|---|---|---:|
| Request capture | `[0x9D001220, 0x9D00122C)` | 12 |
| B ordering | `[0x9D001240, 0x9D00129C)` | 92 |
| A adapter | `[0x9D0012C0, 0x9D0012E8)` | 40 |
| B adapter | `[0x9D0012F0, 0x9D001318)` | 40 |
| Shared Center push | `[0x9D001320, 0x9D001394)` | 116 |

These total 75 instructions/300 code bytes within a 372-byte extent including untouched gaps. Twelve hook words occupy 48 bytes. Placement is within `[0x9D001220, 0x9D001480)`, preserving B3 at `[0x9D001200, 0x9D001220)` and DINIT at `0x9D001480`. Payload length is unchanged.

The original 32-bit `a3` request is saved at existing frame `SP+0x10`, beyond the four-argument home area and before saved registers at `+0x14`. Recursive setters use separate 48-byte frames. Layer B uses its own accepted request before descriptor limiting, storage and notification. Center storage/output precedes the corresponding endpoint output; A completes before B. Existing custom-loop calls and engine/MIDI gates are preserved. Inhibited output still permits ordered storage and Center push.

The [builder/assembler](b7_candidate_work/build_validate_b7.py), [assembly input](b7_candidate_work/b7_assembly_input.txt), [instruction model](b7_combined_instruction_model.py) and [patch manifest](b7_candidate_work/b7_patch_manifest.json) describe the exact implementation. The manifest accounts for 90 PIC words and 340 differing bytes: inserted code, 12 site words and three revision words. QNX changes only its two revision bytes; B1/B5/B8 implementation bytes are preserved.

### Firmware identity and packaging

| Artifact | Identity |
|---|---|
| Baseline `.0.7` package | SHA-256 `2fe41c83415c1d85efd7848a31511157162528ec4a83d08045be7e8bcee2e753` |
| B7 `PxUpdate_V2.2.2.0.8.bin` | 3,151,848 bytes; SHA-256 `c7e2e03999ca4590c99c3ba18a518f93f073ee8a619c84371677c7f6cd2c8e7f` |
| `.0.8` PIC payload | SHA-256 `3554fc3dc413c05fd329df1d04efd1ea49e27469121b38d140b7ebdf3be2e254` |
| `.0.8` QNX payload | SHA-256 `6e0e22ec75036411f7ada1418939e13a684bf144898dd7745ae608e550a65de8` |

Application header, updater comparison and DSP report use 2.2.2.0.8. PIC header/reports use the independently assigned 2.2.4.0.0; intended M formatting is 2.2.4. QNX ELF file offsets `0x1F4E3` and `0x250EF` change from 7 to 8. PIC report words at `0x9D0258B4`/`0x9D051BC4` become `24842240`; M argument at `0x9D052FEC` becomes `24020004`.

The builder packages the existing three-record F0/F7 container without payload growth. Application checksum is `0x7D05`, stored `05 7D`; FPGA checksum is unchanged `0x7759`. The complete FPGA record is unchanged. PIC trailer `30 30` is retained under the established type-3 parser contract; PIC transfer blocks receive separate little-endian 16-bit word checksums.

### Recorded validation and hardware result

- [Instruction validation](b7_candidate_work/b7_validation_results.json): 52,224 endpoint cases, each followed by retreat; 1,632 direct-Center equivalence checks; 48 custom-side-effect comparisons; 1,280 linked-vs-single-part comparisons; 24 Size/custom-control checks.
- [Version verification](b7_candidate_work/b7_version_validation_results.json): decoded application/PIC gates, reply packing and report/formatter arguments.
- [Package verification](b7_candidate_work/b7_packaged_validation_results.json): exact byte accounting, framing, checksums, unchanged inherited regions, 130 PIC blocks and 260 valid/corrupt checksum comparisons.
- **Hardware PASS:** the supplied branch handover records owner confirmation that Center push and linked ordering both work. The original pre-hardware reports retain historical pending labels.

Host execution uses saved candidate instructions and an independent decoder/oracle; external descriptor/UI/MIDI routines use contract summaries. These results do not prove every transport, ISR, persistence or physical stack-headroom scenario.

## Center modulation follow-up - 2.2.2.1.12

**Patch location and size:** QNX; 859 code/constant bytes, a 12-byte hook, 188 unwind bytes and 16 added index bytes within inherited reservations. PIC changes are two revision bytes only; no payload growth.

LFO Center modulation bypassed manual PIC translation, so playback confined Center within unchanged effective endpoints. The final follow-up adds a stateless QNX producer adjustment. With Loop on, primary Center modulation crossing the effective ordered Start/End window translates both effective endpoints equally in raw coordinates. Each pass starts from stored parameters and current modulation: endpoints return as modulation retreats. There is no remembered translated window or preset write.

Only two playback-bank values are written. Both Center lanes, direction, Size modes, manual B6/B7 behavior and inherited B5/B8 completion fixes remain. Loop off, zero primary Center modulation (including signed zero), in-window/equality cases, nonfinite modulation and inverted effective endpoints retain the existing bank. Endpoint modulation participates in the effective window, but endpoint modulation alone with zero primary Center modulation does not trigger translation. Raw translation does not imply constant frame duration under exponential mapping.

### Source, hook and layout

The [C helper](b7_lfo_center_investigation/design_probe.c) and [assembly thunk](b7_lfo_center_investigation/design_thunk.s) are the reviewed payload source. Their original “probe” names describe development tooling; the integrated code is the payload recorded by the [measurement](b7_lfo_center_investigation/measurement.json) and [integration manifest](b7_lfo_center_investigation/implementation_1_12/integration.json).

A single guarded QNX hook at ELF `0x1A87B` replaces 12 bytes and jumps to `0x101168`. Displaced instructions replay before continuation `0x1A887`. Code/constants occupy 859 bytes at `[0x100F60, 0x1012BB)`; unwind records occupy 188 bytes at `[0x1024E8, 0x1025A4)`. The index adds 16 bytes. All fit existing owned B15 reservations; no ELF/package-length or heap growth occurs.

Flags, volatile GP/XMM registers and callee-saved registers are preserved. Added stack depth through getter entry is 456 bytes; physical thread margin remains unmeasured. Original realigned-frame unwind expressions and all 897 inherited FDEs remain unchanged; the total becomes 899.

### Versions and evidence

| Artifact | Identity |
|---|---|
| Baseline `.1.11` package | SHA-256 `29aff5a6cbf6d603ae86f23525454bbbcbe568c3930d65c2064ce827080c86a8` |
| Baseline QNX | SHA-256 `45ee5d94dddb785f0ffa6e3514d42f05671811a669c5f638414d0cd668d66640` |
| Final `PxUpdate_V2.2.2.1.12.bin` | 3,187,784 bytes; SHA-256 `9d0860d06469519a1f80feef2a2143e4a2a343605821f28f193c985398943139` |
| Final QNX | SHA-256 `b411fc94d17683f49d62184e3c794f6e4eea72e7d6ea58edd1b78ff706377ced` |
| Final PIC | SHA-256 `955839db90f004eb893225e41183c11808f6447bdd5c839b4c0a5d88081d3a3a` |

Application/PIC headers and full reports use 2.2.2.1.12; M retains its inherited three-component 2.2.2 format. PIC changes only its two fifth-field revision bytes, 11→12. FPGA is byte-identical. Application checksum trailer bytes are `9D 6F` (`0x6F9D`); FPGA trailer is `59 77`; PIC trailer remains `30 30`. Differences versus `.1.11`: 951 QNX bytes, two PIC bytes and 957 total package bytes.

- [Integrated validation](b7_lfo_center_investigation/implementation_1_12/validation.json): PASS, 43,528 emitted saved-ELF cases, including 6,872 pushes and 36,656 bypasses; 43,528 captured register/flag comparisons; 217,640 geometry-model comparisons; 435,280 stock Read/UpdateLoc geometry-slice checks.
- Inherited regression: PASS, 2,174 completion/core/GEOM/B8/lifecycle/tiny-region/wrapper checks using emitted `.1.12` bytes and modeled stock dependencies.
- [Package checks](b7_lfo_center_investigation/implementation_1_12/package_results.json): PASS, re-extracted component equality, application/FPGA checksums, 18 updater gate cases, 130 PIC blocks and 260 valid/corrupt comparisons.
- **Hardware PASS, owner report dated 8 October 2026:** `.1.12` tested and working. Individual test-sequence cases were not separately reported.

These host fixtures use fake engine/reader objects and entry/exit adapters, not a complete QNX playback or threading environment. Hardware success covers the reported behavior; complete runtime coverage and physical stack margin remain NOT VERIFIED.

## Loop-window squashing - investigation retained, no implementation

**Abandoned on 8 October 2026.** Inward Start/End edits can compress the effective loop, including in Sync mode. Note that this behaviour is present on factory firmware too. The investigated enhancement would stop inward endpoints before compression, retain outward movement and existing push behavior, and allow modest conservative early stopping. Neither original B7 nor `.1.12` implements that enhancement. Stateless Center translation does not solve endpoint squashing.

The full uploaded investigation history remains under `abandoned_squash_limit/`, including all supplied revisions. The [latest revision](abandoned_squash_limit/revision_08.md) contains the final calculation and coverage findings; earlier proposals are historical rather than active build instructions.

The investigation progressed through these approaches:

1. **PIC-local mapped Size limit:** attractive for Regular mode, but PIC lacked complete per-sample/rate geometry for Pitched and Sync. Raw parameter distance was insufficient to preserve effective loop length across modes.
2. **Cached QNX required width:** calculate a conservative requirement in QNX, return it to PIC, and bound inward edits without blocking the setter. It required complete selectable sample/header coverage, independent layer/oscillator association, retained/pending voice accounting, cache invalidation and transport freshness. Rejected/equal edits must not accidentally activate Custom mode; native-to-Custom transitions also require compatibility checks.
3. **Playback-rate cap reservations of 4/8/32:** these are real playback-branch bounds, but reserving them could consume excessive window width. The final proposal superseded cap-based endpoint reservation with tighter paired sample/rate calculations.
4. **Exact pre-clipping geometry:** Read has the requested integer length before `0x3FAA6`; UpdateLoc has its counterpart before `0x41A3B`. A pure geometry helper could reproduce that arithmetic for explicit contexts. Pairing each sample length with its own rate avoids artificial excess from combining unrelated maxima. It still cannot cheaply guarantee useful protection for every possible future note, pitch/tempo/modulation change or unloaded alternative without defined coverage and timely refresh.

The latest design recommended cached required width from paired context geometry, keeping Regular and per-sample Pitched calculations and using actual rates plus a verified future-note envelope for Sync. Wider requirements can be physically genuine: a scalar protecting a much faster future note cannot also guarantee narrow-window travel for the current slower note. Restricting protection to a declared note/pitch domain would be a separate behavior choice; it was not adopted.

Reported arithmetic examples include 7,200 alternating inward edits and 14,400 paired-context comparisons with zero decreases in fixed synthetic contexts. Earlier cap-based calculations reported 48,000 requests and 288,000 comparisons. These were in-memory checks with no saved script/result artifact; they are not independently reproducible validation, measured instrument usability or hardware evidence.

Unresolved at abandonment: real paired sample-header/reachability coverage, silent/unloaded alternatives, static pitch/selection factoring, retained old/pending rate lifetimes, tempo/modulation scope, cache publication/invalidation ordering and practical travel. No patch, reserved-output `.1.0` package or squash-limit hardware result exists. Historical instructions to continue analysis or reserve `.1.0` in the retained revisions are superseded by abandonment.

### Investigation archive

- [Initial design](abandoned_squash_limit/revision_00.md)
- [Revision 1](abandoned_squash_limit/revision_01.md)
- [Revision 2](abandoned_squash_limit/revision_02.md)
- [Revision 3](abandoned_squash_limit/revision_03.md)
- [Revision 4](abandoned_squash_limit/revision_04.md)
- [Revision 6](abandoned_squash_limit/revision_06.md)
- [Revision 7](abandoned_squash_limit/revision_07.md)
- [Revision 8 / final findings](abandoned_squash_limit/revision_08.md)

Revision 5 was not supplied. All available revisions are retained without treating their superseded proposals as implemented features.

## Supporting tools and private reproduction

Firmware, compiled objects and firmware disassemblies are excluded. Original implementation notes are preserved privately; the squash design history remains public intentionally. [SHA256SUMS](SHA256SUMS) is the inventory of files distributed in this B7 folder.

For the original `.0.8` chain, use a fresh private copy with `.0.7` BIN and extracted PIC at the root under the filenames expected by the model. The builder is `b7_candidate_work/build_validate_b7.py`; `validate_version_gates.py` and `validate_packaged_b7.py` independently check the resulting package. These scripts use Python 3 and their own bounded MIPS assembler/decoder; no Ghidra is required for executing that historical workflow.

For `.1.12`, preserve `b7_lfo_center_investigation/implementation_1_12/` and supply the exact private `.1.11` components under `b15_candidate_work/lfo_endpoint_investigation/completion_fix/`. The original workflow runs `build.py`, `validate.py`, then `package.py` from the `.1.12` directory. Shared B5 ELF/parser and regression fixtures plus packaging helpers are included under their original relative paths.

The `.1.12` builder pins reviewed `design_payload.bin` and `design_frames.bin` against the original checksum list under `b7_lfo_center_investigation/`. These generated blobs are omitted from publication; `measure_design.py`, C/thunk source, measurement and design-validation reports document their generation and identity. Recreating them requires matching compiler output and private firmware. The inherited runner also uses generated B5 fixture sources whose `.incbin` paths must correspond to the private workspace. Host validation uses macOS x86-64 fixtures and may require Rosetta on Apple Silicon. Optional design validation references a historical trace file not included here; it is not a newly portable standalone test system.

These tools explain the incremental implementation and its dependencies. The [direct firmware patcher](../../firmware_builder/patch_prophet_x.py) builds the final combined update directly from the exact factory input using authored generators and pinned redacted objects. See the [direct builder implementation](../../firmware_builder/direct/IMPLEMENTATION.md). The separate [compiler audit path](../../firmware_builder/source_rebuild/README.md) retains incremental source rebuilding and its original validation scope.

## Complete supporting-file inventory

Every retained supporting file is linked below. Implementation, imported dependencies, test fixtures and saved evidence are distinguished by purpose; not every evidence file is required to build the feature. Original script layouts are retained so their relative imports remain intact. Firmware and generated binary inputs remain private, as described above. The [root checksum inventory](SHA256SUMS) covers this handover and all retained supporting files.

The squash investigation revisions are intentionally retained despite the absence of a deployed squash patch. The nested `HISTORICAL_SHA256SUMS` is an original build checkpoint and includes private generated artifacts; the root inventory describes the public bundle.

Copies of B5 sources and reports support inherited implementation/regression investigation. They are dependencies or provenance evidence, rather than additional B7/B8 features.

| File | Purpose |
|---|---|
| [abandoned_squash_limit/revision_00.md](abandoned_squash_limit/revision_00.md) | Historical squash investigation explicitly retained by request; no deployed patch. |
| [abandoned_squash_limit/revision_01.md](abandoned_squash_limit/revision_01.md) | Historical squash investigation explicitly retained by request; no deployed patch. |
| [abandoned_squash_limit/revision_02.md](abandoned_squash_limit/revision_02.md) | Historical squash investigation explicitly retained by request; no deployed patch. |
| [abandoned_squash_limit/revision_03.md](abandoned_squash_limit/revision_03.md) | Historical squash investigation explicitly retained by request; no deployed patch. |
| [abandoned_squash_limit/revision_04.md](abandoned_squash_limit/revision_04.md) | Historical squash investigation explicitly retained by request; no deployed patch. |
| [abandoned_squash_limit/revision_06.md](abandoned_squash_limit/revision_06.md) | Historical squash investigation explicitly retained by request; no deployed patch. |
| [abandoned_squash_limit/revision_07.md](abandoned_squash_limit/revision_07.md) | Historical squash investigation explicitly retained by request; no deployed patch. |
| [abandoned_squash_limit/revision_08.md](abandoned_squash_limit/revision_08.md) | Historical squash investigation explicitly retained by request; no deployed patch. |
| [b15_candidate_work/build_candidate_1_8.py](b15_candidate_work/build_candidate_1_8.py) | Build/emission/layout tool or imported build dependency. |
| [b15_candidate_work/build_candidate_1_9.py](b15_candidate_work/build_candidate_1_9.py) | Build/emission/layout tool or imported build dependency. |
| [b15_candidate_work/lfo_endpoint_investigation/b5_offsets.generated.h](b15_candidate_work/lfo_endpoint_investigation/b5_offsets.generated.h) | Generated structure/offset or policy definitions used by source/tests. |
| [b15_candidate_work/lfo_endpoint_investigation/check_completion.py](b15_candidate_work/lfo_endpoint_investigation/check_completion.py) | Validation/test or ownership audit tool; uses the private inputs described in source. |
| [b15_candidate_work/lfo_endpoint_investigation/completion_fix/build.py](b15_candidate_work/lfo_endpoint_investigation/completion_fix/build.py) | Build/emission/layout tool or imported build dependency. |
| [b15_candidate_work/lfo_endpoint_investigation/completion_fix/build_results.json](b15_candidate_work/lfo_endpoint_investigation/completion_fix/build_results.json) | Saved validation, measurement or ownership evidence; not a new test run. |
| [b15_candidate_work/lfo_endpoint_investigation/completion_fix/extra_tests.c](b15_candidate_work/lfo_endpoint_investigation/completion_fix/extra_tests.c) | Test/stock-operation fixture. |
| [b15_candidate_work/lfo_endpoint_investigation/completion_fix/fixed_image.s](b15_candidate_work/lfo_endpoint_investigation/completion_fix/fixed_image.s) | Assembly fixture for validation; binary include paths require private generated inputs. |
| [b15_candidate_work/lfo_endpoint_investigation/completion_fix/fixture.c](b15_candidate_work/lfo_endpoint_investigation/completion_fix/fixture.c) | Test/stock-operation fixture. |
| [b15_candidate_work/lfo_endpoint_investigation/completion_fix/helpers.s](b15_candidate_work/lfo_endpoint_investigation/completion_fix/helpers.s) | Helper/shim assembly or generated target layout. |
| [b15_candidate_work/lfo_endpoint_investigation/completion_fix/package.py](b15_candidate_work/lfo_endpoint_investigation/completion_fix/package.py) | Incremental packaging/publication tool. |
| [b15_candidate_work/lfo_endpoint_investigation/completion_fix/package_results.json](b15_candidate_work/lfo_endpoint_investigation/completion_fix/package_results.json) | Saved validation, measurement or ownership evidence; not a new test run. |
| [b15_candidate_work/lfo_endpoint_investigation/completion_fix/source_change.diff](b15_candidate_work/lfo_endpoint_investigation/completion_fix/source_change.diff) | Semantic source changes for the endpoint/pitch-modulation correction. |
| [b15_candidate_work/lfo_endpoint_investigation/completion_fix/tests.c](b15_candidate_work/lfo_endpoint_investigation/completion_fix/tests.c) | Test/stock-operation fixture. |
| [b15_candidate_work/lfo_endpoint_investigation/completion_fix/validate.py](b15_candidate_work/lfo_endpoint_investigation/completion_fix/validate.py) | Validation/test or ownership audit tool; uses the private inputs described in source. |
| [b15_candidate_work/lfo_endpoint_investigation/completion_fix/validation_results.json](b15_candidate_work/lfo_endpoint_investigation/completion_fix/validation_results.json) | Saved validation, measurement or ownership evidence; not a new test run. |
| [b15_candidate_work/lfo_endpoint_investigation/completion_reproduce.c](b15_candidate_work/lfo_endpoint_investigation/completion_reproduce.c) | Test/stock-operation fixture. |
| [b15_candidate_work/lfo_endpoint_investigation/completion_results.json](b15_candidate_work/lfo_endpoint_investigation/completion_results.json) | Saved validation, measurement or ownership evidence; not a new test run. |
| [b15_candidate_work/lfo_endpoint_investigation/inherited_fixture.c](b15_candidate_work/lfo_endpoint_investigation/inherited_fixture.c) | Test/stock-operation fixture. |
| [b15_candidate_work/lfo_endpoint_investigation/source_change.diff](b15_candidate_work/lfo_endpoint_investigation/source_change.diff) | Semantic source changes for the endpoint/pitch-modulation correction. |
| [b5_candidate_work/b5_adapters.c](b5_candidate_work/b5_adapters.c) | Feature implementation or design probe compiled by supplied tools. |
| [b5_candidate_work/b5_candidate_manifest.json](b5_candidate_work/b5_candidate_manifest.json) | Saved patch/object/packaging identity and layout evidence. |
| [b5_candidate_work/b5_candidate_validation.json](b5_candidate_work/b5_candidate_validation.json) | Saved validation, measurement or ownership evidence; not a new test run. |
| [b5_candidate_work/b5_core.c](b5_candidate_work/b5_core.c) | Feature implementation or design probe compiled by supplied tools. |
| [b5_candidate_work/b5_core.generated.h](b5_candidate_work/b5_core.generated.h) | Generated structure/offset or policy definitions used by source/tests. |
| [b5_candidate_work/b5_hooks.objects.s](b5_candidate_work/b5_hooks.objects.s) | Helper/shim assembly or generated target layout. |
| [b5_candidate_work/b5_integration_validation.json](b5_candidate_work/b5_integration_validation.json) | Saved validation, measurement or ownership evidence; not a new test run. |
| [b5_candidate_work/b5_object_structure_validation.json](b5_candidate_work/b5_object_structure_validation.json) | Saved validation, measurement or ownership evidence; not a new test run. |
| [b5_candidate_work/b5_objects_manifest.json](b5_candidate_work/b5_objects_manifest.json) | Saved patch/object/packaging identity and layout evidence. |
| [b5_candidate_work/b5_policy.generated.h](b5_candidate_work/b5_policy.generated.h) | Generated structure/offset or policy definitions used by source/tests. |
| [b5_candidate_work/b5_wrapper_fixture.s](b5_candidate_work/b5_wrapper_fixture.s) | Assembly fixture for validation; binary include paths require private generated inputs. |
| [b5_candidate_work/build_b5_candidate.py](b5_candidate_work/build_b5_candidate.py) | Build/emission/layout tool or imported build dependency. |
| [b5_candidate_work/emit_b5_candidate.py](b5_candidate_work/emit_b5_candidate.py) | Inherited object parser/layout utilities; its historical candidate entry point is not required by every branch. |
| [b5_candidate_work/emit_b5_objects.py](b5_candidate_work/emit_b5_objects.py) | Build/emission/layout tool or imported build dependency. |
| [b5_candidate_work/validate_b5_candidate.py](b5_candidate_work/validate_b5_candidate.py) | Validation/test or ownership audit tool; uses the private inputs described in source. |
| [b5_elf_placement_check.py](b5_elf_placement_check.py) | ELF/unwind parser and index utilities imported by build/validation scripts. |
| [b5_fade_prototype.py](b5_fade_prototype.py) | B5 fade policy and prediction constants used by emitters and regression tests. |
| [b7_candidate_work/b7_assembly_input.txt](b7_candidate_work/b7_assembly_input.txt) | Saved assembly/layout evidence. |
| [b7_candidate_work/b7_packaged_validation_results.json](b7_candidate_work/b7_packaged_validation_results.json) | Saved validation, measurement or ownership evidence; not a new test run. |
| [b7_candidate_work/b7_patch_manifest.json](b7_candidate_work/b7_patch_manifest.json) | Saved patch/object/packaging identity and layout evidence. |
| [b7_candidate_work/b7_validation_results.json](b7_candidate_work/b7_validation_results.json) | Saved validation, measurement or ownership evidence; not a new test run. |
| [b7_candidate_work/b7_version_validation_results.json](b7_candidate_work/b7_version_validation_results.json) | Saved validation, measurement or ownership evidence; not a new test run. |
| [b7_candidate_work/build_validate_b7.py](b7_candidate_work/build_validate_b7.py) | Build/emission/layout tool or imported build dependency. |
| [b7_candidate_work/validate_packaged_b7.py](b7_candidate_work/validate_packaged_b7.py) | Validation/test or ownership audit tool; uses the private inputs described in source. |
| [b7_candidate_work/validate_version_gates.py](b7_candidate_work/validate_version_gates.py) | Validation/test or ownership audit tool; uses the private inputs described in source. |
| [b7_combined_instruction_model.py](b7_combined_instruction_model.py) | Inherited PIC instruction model used by regression validation; requires its pinned private input. |
| [b7_lfo_center_investigation/HISTORICAL_SHA256SUMS](b7_lfo_center_investigation/HISTORICAL_SHA256SUMS) | Original build checkpoint hashes, including private generated inputs; retained for builder identity checks. |
| [b7_lfo_center_investigation/design_probe.c](b7_lfo_center_investigation/design_probe.c) | Feature implementation or design probe compiled by supplied tools. |
| [b7_lfo_center_investigation/design_thunk.s](b7_lfo_center_investigation/design_thunk.s) | Helper/shim assembly or generated target layout. |
| [b7_lfo_center_investigation/design_validation.json](b7_lfo_center_investigation/design_validation.json) | Saved validation, measurement or ownership evidence; not a new test run. |
| [b7_lfo_center_investigation/implementation_1_12/build.py](b7_lfo_center_investigation/implementation_1_12/build.py) | Build/emission/layout tool or imported build dependency. |
| [b7_lfo_center_investigation/implementation_1_12/integration.json](b7_lfo_center_investigation/implementation_1_12/integration.json) | Saved validation, measurement or ownership evidence; not a new test run. |
| [b7_lfo_center_investigation/implementation_1_12/package.py](b7_lfo_center_investigation/implementation_1_12/package.py) | Incremental packaging/publication tool. |
| [b7_lfo_center_investigation/implementation_1_12/package_results.json](b7_lfo_center_investigation/implementation_1_12/package_results.json) | Saved validation, measurement or ownership evidence; not a new test run. |
| [b7_lfo_center_investigation/implementation_1_12/validate.py](b7_lfo_center_investigation/implementation_1_12/validate.py) | Validation/test or ownership audit tool; uses the private inputs described in source. |
| [b7_lfo_center_investigation/implementation_1_12/validation.json](b7_lfo_center_investigation/implementation_1_12/validation.json) | Saved validation, measurement or ownership evidence; not a new test run. |
| [b7_lfo_center_investigation/measure_design.py](b7_lfo_center_investigation/measure_design.py) | Build/emission/layout tool or imported build dependency. |
| [b7_lfo_center_investigation/measurement.json](b7_lfo_center_investigation/measurement.json) | Saved validation, measurement or ownership evidence; not a new test run. |
| [b7_lfo_center_investigation/probe_getter.s](b7_lfo_center_investigation/probe_getter.s) | Helper/shim assembly or generated target layout. |
| [b7_lfo_center_investigation/probe_tests.c](b7_lfo_center_investigation/probe_tests.c) | Test/stock-operation fixture. |
| [b7_lfo_center_investigation/validate_design.py](b7_lfo_center_investigation/validate_design.py) | Validation/test or ownership audit tool; uses the private inputs described in source. |
| [qnx_elf.py](qnx_elf.py) | Shared ELF parser used by object/build utilities. |
