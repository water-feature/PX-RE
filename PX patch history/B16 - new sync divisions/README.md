# B16 - Finer Loop Sync divisions

Technical handover for the completed B16 implementation and graphical-window correction. B16 is implemented and hardware-confirmed in the final combined project firmware.

**Firmware:** `2.2.2.2.2` (final combined package); `.2.1` is the preceding in-place implementation.

**Hardware: PASS** The sonic feature and corrected graphical window have been successfully tested on hardware. This does not establish that every suggested MIDI/recovery test was individually performed.

Adds 1/32 Step and 1/64 Step below the existing 1/16 Step minimum. PIC handles selection, labels, storage/transport validation and graphical geometry; QNX supplies shorter audio loop durations. Existing minimum-loop and crossfade bumpers remain unchanged.

## Version and package identity 

The retained implementation adds the divisions on exact B11b `.2.0` as `.2.1`, then applies the final PIC graphical correction as **`.2.2`**. Both stages are incremental; `.2.2` preserves the `.2.1` QNX audio mapping and selector behavior.

| Artifact | SHA-256 |
|---|---|
| **Final `.2.2` package** | `488444589607a1b4e793a8d8f79a67c5bd50773b722c302e6d80bc1db77b4b7c` |
| Final PIC | `8964e630a929e608aa0d3f368f55b97718e7cbf8ef79afbd5ee21e71fc40822a` |
| Final QNX | `23175d047f8ac0bace3566f2da0a49f920d43d699de03635cdf20836c3f0838a` |
| `.2.1` source package | `0d41efe3fcd93d16161e92ae4b9389d7d0917006a06920b7f2c8b8660e419e74` |
| B11b `.2.0` baseline package | `89d794880697c18da66356a2fd8cb90b7302d2250574ea4664bdbc496945bc6f` |
| B11b `.2.0` PIC | `caa2a19d9a246aaeded2debd6b373490fee06f035d101373c24ec188456f6612` |
| B11b `.2.0` QNX | `dcc77bdaff17f99288182ffb4927e85dcb76de597f8c5906a4078df8f5b14d16` |

Final filename: `PxUpdate_V2.2.2.2.2_B16_geometry_candidate.bin`, **3,187,784 bytes**. The original final source, builders and saved machine-readable results are now recovered and inventoried below. Source and evidence are public; full firmware and generated binary artifacts are private.

## Encoding and editing contract

Sync IDs are `0x1d` and `0x5e`. Raw 0–15 preserve their original meaning; raw 16 = 1/32 Step, raw 17 = 1/64 Step. Relative logical order is `[17,16,0,1,...,15]`. Absolute setters, stored presets and wire representation retain raw encodings. Both Layers derives the result from Layer A, then uses existing setter layer handling.

The common editor supports 13 identified Sync-capable relative routes (dedicated, generic and MIDI). Its replacement uses a compact ID gate and rank conversion, retaining the pinned signed-add/clamp helper. For valid raw values, rank is raw+2 for raw<16, otherwise (raw+2) XOR 19. Inverse is rank-2 for rank>=2, otherwise rank XOR 17.

Register allocation avoids changing s0/s1/s2, eliminating redundant saves/restores. Caller-saved state survives only because the pinned clamp helper writes v0/v1; this dependency must be rechecked when rebasing. The B11 wrapper, 32-byte frame, RA at SP+0x1c and maximum argument at SP+0x30 remain.

## In-place PIC layout

**Patch location:** Both PIC controller (MIPS) and QNX application (x86-64). PIC supplies selection/labels/validation/geometry; QNX supplies the shorter audio-loop mapping.

**Patch size:** Initial .2.1 PIC layout reuses the 156-byte editor and 88-byte display region, plus two 2-byte bound fields. QNX mapping uses 136 code bytes + 20 constant bytes and a 7-byte hook, with associated unwind/index edits. Final .2.2 geometry correction writes 132 instruction bytes in existing PIC blocks; versus .2.1, 113 functional PIC bytes differ (120 whole-package bytes including metadata). Neither stage grows the payloads.

| Range / address | Change |
|---|---|
| `0x9d04fa74–0x9d04fb10` | 152 active bytes plus 4-byte unreachable NOP inside original 156-byte editor |
| `0x9d060278–0x9d060298` | 32-byte label formatter entry |
| `0x9d062074–0x9d062088` | Two ten-byte NUL-terminated labels |
| `0x9d062088–0x9d06209a` | 18 unsigned byte offsets replacing 16 word pointers |
| `0x9d06209a–0x9d06209c` | Alignment |
| `0x9d06209c–0x9d0620ac` | 16-byte append/epilogue continuation |
| `0x9d0475f4`, `0x9d047900` | Sync maximum halfwords 15→17; default remains zero |

Display uses 88/96 bytes; remaining eight bytes are not borrowed. Original division strings and separate table/formatter at `0x9d062034` / `0x9d060718` remain. Display lookup requires validated raw 0–17; arbitrary corrupt/unchecked values were not made safe.

## QNX audio mapping

Existing mapper hook is ELF file offset `0x1ae55–0x1ae5c` (Ghidra address `0x0011ae55`); helper file offset `0x101700–0x10179c` (Ghidra `0x00201700`), 136 code bytes plus 20 constant bytes. Old values replay displaced code and retain original mapping, modulation scale and clamps. New values interpolate across 1/64, 1/32 and 1/16 with the existing runtime multiplier, then rejoin BPM/duration handling.

FDE at `0x10277c–0x1027b4`; index count at `0x103008`; added index entry at `0x104c74–0x104c7c`. Related unwind/section sizes change; PT_LOAD records and image length remain unchanged. Final geometry correction requires no QNX functional change, only version metadata.

## Placement and compatibility

The retained PIC implementation replaces only established occupied editor/display/renderer ranges. It does not allocate the unexplained `[0x9D000E00,0x9D000EC0)` interval, compact B6/B9, extend the PIC image or modify bootloader code. Historical alternate layouts and allocation reviews are archived privately.

Old presets retain their raw0–15 meanings. New raw16/17 presets are **not fully backward compatible**: inspected older PIC recall resets them to default0, while older QNX clamps them to15. A matched B16-aware PIC/QNX pair is required. Absolute storage and transport keep raw values; only relative editing permutes the logical order.

Recovery independence was not proved. The owner accepted the same general recovery uncertainty as other application patches; hardware feature acceptance does not establish bootloader/dependency isolation. Display lookup assumes validated raw0–17 and does not harden arbitrary corrupt RAM.

## Final graphical window implementation

**Patch location and size:** PIC; 132 instruction bytes written within existing renderer blocks, with 113 actual functional byte differences versus .2.1. QNX audio mapping is inherited unchanged; its revision metadata is updated.

The actual PIC renderer `0x9d03ad9c` reads object width ID +0xb4, raw parameter RAM and shared metadata maximum. It does not use QNX loop duration for this width.

Legacy half-width: `floor(246*(raw+1)/(2*(maximum+1)))`. With maximum 17, raw 16/17 produced 116/123 pixels. Old values also became slightly narrower. The page configuration `0x9d03ce4c` assigns instrument offset+0x1d, identifying both Sync IDs.

The final `.2.2` implementation changes only occupied renderer blocks `0x9d03b0a0–0x9d03b104` and `0x9d03b55c–0x9d03b57c`; residual bytes through `0x9d03b5b0` remain unchanged. It restores old denominator 32 for Sync raw 0–15. New raw 16 uses 246/64 => half-width 3 pixels; raw 17 uses 246/128 => 1 pixel. Legacy 1/16 is 7 pixels, 1/8 is 15 pixels. This preserves schematic legacy geometry, not a new exact duration visualization.

Center/Start/End clipping and drawing calls stay unchanged. Non-Sync arithmetic and ID0x0b exception retain quotient/remainder and zero-denominator trap. The implementation uses 33 words/132 bytes across original 184-byte blocks. Independent assembly and scoped comparisons passed. User subsequently confirmed the corrected build worked great and feature was complete.

## Validation record and limits

.2.1 independent verification: Ghidra 12.1.4, MIPS:LE:32:default, assembled/disassembled 51 proposed words. Scoped execution: 151,488 Sync cases, 72,114 non-Sync comparisons, 12,624 BPM comparisons, 30 setter context cases; 2,592 executions from all 13 relative call boundaries. Display: 54 executions. Absolute validator: 131,072 cases; preset validator: 256; transport packer: 108.

QNX host/Rosetta execution: 524,752 old bit-exact and 65,594 new mapping cases, eight BPM and thirty runtime-scale checks. All 910 indexed FDEs validated structurally. 130 PIC transport blocks passed checksum arithmetic, including 260 valid/corrupt comparisons; re-extraction/trailers/layout validated.

.2.1 total baseline package diff was 428 bytes: 230 PIC functional, 190 QNX functional, 2 PIC version, 2 QNX version, 2 header, 2 checksum. This is **not the final .2.2 diff**.

Final `.2.2` emitted-byte validation checks all 33 words, 16,330 width cases and 3,024 additional cases executing original getters, clipping and drawing-call argument construction. Only final drawing I/O is intercepted in the latter checks. Exact byte accounting preserves all QNX audio/unwind code and PIC code outside geometry/version scope. Hardware confirmation covers sonic behavior and the corrected graphical feature; full individual MIDI/storage/recovery test coverage is not inferred.

## Final packaging and byte accounting

Relative to exact `.2.1`, `.2.2` changes **120 package bytes**: 113 PIC geometry bytes, four component revision bytes, two record-header revision bytes and one application checksum byte. The occupied functional write spans total 132 instruction bytes; unchanged values within those spans are not counted as differing bytes.

PIC revision immediates at `0x9D001394` and `0x9D0013A0` change 1 → 2. QNX file offsets `0x1F4E3` and `0x250EF` change to packed reply `0x40139222` and final component2. Application/PIC headers become `2.2.2.2.2`; the inherited three-field M display remains unchanged. Application checksum is `0xAA51`. Complete FPGA record, all component lengths/record positions and PIC trailer `30 30` are preserved.

Saved final checks include 18 version-gate cases, both PIC report routes, 130 receiver blocks with 260 valid/corrupt checksum comparisons, and exact saved-package re-extraction. Original `.2.1` source files are checked unchanged. These are offline checks; the owner’s hardware acceptance is recorded separately above.

## Source and incremental build workflow

All supporting files live under `implementation/`, retaining their original sibling paths. The final `.2.2` builder and geometry validator are under `b16_finer_loop_sync_resolution/geometry_candidate/`. With exact private inputs prepared, run from `implementation/`:

```sh
python3 b16_finer_loop_sync_resolution/geometry_candidate/build.py
```

The builder validates the 33 reviewed words, runs emitted geometry checks, applies revision metadata, checks preserved scope and updater/checksum behavior, and exclusively creates `geometry_candidate/PxUpdate_V2.2.2.2.2_B16_geometry_candidate.bin`. It also produces final PIC/QNX, emitted-word and validation reports. Use a fresh private output directory: the retained reports/output filenames may already exist and exclusive writes refuse replacement.

Required private inputs:

| Location relative to `implementation/` | Purpose |
|---|---|
| `b16_finer_loop_sync_resolution/in_place_candidate/pic_2.2.2.2.1_B16_in_place.bin` | Exact source PIC, SHA-256 `b7d59c09d57e2b9c18146e51b517404a8deba5cfcc5291d8a17f88904fe53e59` |
| `b16_finer_loop_sync_resolution/in_place_candidate/voice_2.2.2.2.1_B16_in_place_qnx.elf` | Exact source QNX, SHA-256 `34b775ebff3af113ffa12592e71f51136037a64fdb50a6810c11b62c008b5fa2` |
| `b16_finer_loop_sync_resolution/in_place_candidate/PxUpdate_V2.2.2.2.1_B16_in_place_candidate.bin` | Exact source package, hash above |
| `b11b_implementation_2_2_2_2_0/pic_2.2.2.2.0_B11b.bin` | Baseline PIC for original getter/geometry comparisons, hash above |

Python3 is required for the final geometry step; it reuses saved independent word verification and does not need a fresh Ghidra run. The optional Java word-verification scripts require Ghidra. The `.2.1` QNX rebuild/native mapper tests additionally use Clang x86-64 ELF assembly and a macOS x86-64/Rosetta host harness.

The `.2.1` original integration path is preserved in `in_place_validation/integrate.py`, with preflight/dependency checkers, expected words and QNX helper/native test source. It reads exact B11b `.2.0` package/PIC/QNX inputs, builds the accepted in-place PIC implementation and QNX helper, then packages `.2.1`. It also requires the original `offline_candidate/` preservation checkpoint to match every historical file; those private old candidates are excluded here. Consequently that historical driver needs private checkpoint restoration or a reviewed adaptation before a clean public reproduction. The final `.2.2` step does not depend on restoring that full historical checkpoint.

`offline_candidate/build.py`, `validate.py` and `mips_tools.py` are retained because the accepted builders import their ELF/container/decoder functions and QNX assembly block. Their earlier candidate main entry points are not part of the retained workflow. Likewise `safety_review/tight_editor_probe.py` supplies the editor interpreter/model, and `geometry_review/proposal_probe.py` supplies the tested geometry interpreter. Original directory names describe provenance rather than current release status.

The [root patcher](../../patch_prophet_x.py) now rebuilds the retained chain from the exact `2.2.2.0.0` update through `2.2.2.2.2`, including both retained B16 stages. The [source build guide](../../firmware_builder/README.md) explains source review, compiler requirements and keeping intermediate packages and reports. The B16 bundle documents its feature implementation and the original incremental packaging path.

## Complete supporting-file inventory

Every retained supporting file is linked below. Rejected candidate binaries, Ghidra projects, proprietary disassembly exports, superseded reports and duplicate archive metadata remain private. No firmware packages, extracted components, objects, executables or helper binaries are included. [SHA256SUMS](SHA256SUMS) covers the handover and support files.

### Final .2.2 implementation and results

| File | Purpose |
|---|---|
| [b16_finer_loop_sync_resolution/geometry_candidate/INDEPENDENT_WORD_VERIFICATION.txt](implementation/b16_finer_loop_sync_resolution/geometry_candidate/INDEPENDENT_WORD_VERIFICATION.txt) | Exact new instruction words, assembly verification or caller-route evidence. |
| [b16_finer_loop_sync_resolution/geometry_candidate/build.py](implementation/b16_finer_loop_sync_resolution/geometry_candidate/build.py) | Original builder or imported build/ELF/container utilities; entry-point scope described above. |
| [b16_finer_loop_sync_resolution/geometry_candidate/emitted_words.tsv](implementation/b16_finer_loop_sync_resolution/geometry_candidate/emitted_words.tsv) | Exact new instruction words, assembly verification or caller-route evidence. |
| [b16_finer_loop_sync_resolution/geometry_candidate/geometry_results.json](implementation/b16_finer_loop_sync_resolution/geometry_candidate/geometry_results.json) | Saved emitted-byte, mapper, geometry, preflight or dependency validation. |
| [b16_finer_loop_sync_resolution/geometry_candidate/validate_geometry.py](implementation/b16_finer_loop_sync_resolution/geometry_candidate/validate_geometry.py) | Scoped emitted-instruction validator or inherited decoder/model dependency. |
| [b16_finer_loop_sync_resolution/geometry_candidate/validation_results.json](implementation/b16_finer_loop_sync_resolution/geometry_candidate/validation_results.json) | Saved emitted-byte, mapper, geometry, preflight or dependency validation. |
| [b16_finer_loop_sync_resolution/geometry_review/PROPOSED_ASSEMBLY_CHECK.txt](implementation/b16_finer_loop_sync_resolution/geometry_review/PROPOSED_ASSEMBLY_CHECK.txt) | Exact new instruction words, assembly verification or caller-route evidence. |
| [b16_finer_loop_sync_resolution/geometry_review/VerifyGeometryWords.java](implementation/b16_finer_loop_sync_resolution/geometry_review/VerifyGeometryWords.java) | Optional independent Ghidra word verification. |
| [b16_finer_loop_sync_resolution/geometry_review/proposal_probe.py](implementation/b16_finer_loop_sync_resolution/geometry_review/proposal_probe.py) | Scoped emitted-instruction validator or inherited decoder/model dependency. |
| [b16_finer_loop_sync_resolution/geometry_review/proposal_results.json](implementation/b16_finer_loop_sync_resolution/geometry_review/proposal_results.json) | Saved emitted-byte, mapper, geometry, preflight or dependency validation. |
| [b16_finer_loop_sync_resolution/geometry_review/proposed_words.tsv](implementation/b16_finer_loop_sync_resolution/geometry_review/proposed_words.tsv) | Exact new instruction words, assembly verification or caller-route evidence. |

### Accepted .2.1 selector/audio implementation and tests

| File | Purpose |
|---|---|
| [b16_finer_loop_sync_resolution/in_place_candidate/integration_results.json](implementation/b16_finer_loop_sync_resolution/in_place_candidate/integration_results.json) | Saved emitted-byte, mapper, geometry, preflight or dependency validation. |
| [b16_finer_loop_sync_resolution/in_place_candidate/native_mapper_results.json](implementation/b16_finer_loop_sync_resolution/in_place_candidate/native_mapper_results.json) | Saved emitted-byte, mapper, geometry, preflight or dependency validation. |
| [b16_finer_loop_sync_resolution/in_place_candidate/native_mapper_test.cpp](implementation/b16_finer_loop_sync_resolution/in_place_candidate/native_mapper_test.cpp) | QNX helper assembly or native mapper test fixture. |
| [b16_finer_loop_sync_resolution/in_place_candidate/native_wrapper.s](implementation/b16_finer_loop_sync_resolution/in_place_candidate/native_wrapper.s) | QNX helper assembly or native mapper test fixture. |
| [b16_finer_loop_sync_resolution/in_place_candidate/qnx_helper.s](implementation/b16_finer_loop_sync_resolution/in_place_candidate/qnx_helper.s) | QNX helper assembly or native mapper test fixture. |
| [b16_finer_loop_sync_resolution/in_place_validation/GHIDRA_WORD_VERIFICATION.txt](implementation/b16_finer_loop_sync_resolution/in_place_validation/GHIDRA_WORD_VERIFICATION.txt) | Exact new instruction words, assembly verification or caller-route evidence. |
| [b16_finer_loop_sync_resolution/in_place_validation/VerifyB16Words.java](implementation/b16_finer_loop_sync_resolution/in_place_validation/VerifyB16Words.java) | Optional independent Ghidra word verification. |
| [b16_finer_loop_sync_resolution/in_place_validation/dependencies.py](implementation/b16_finer_loop_sync_resolution/in_place_validation/dependencies.py) | Scoped emitted-instruction validator or inherited decoder/model dependency. |
| [b16_finer_loop_sync_resolution/in_place_validation/dependency_results.json](implementation/b16_finer_loop_sync_resolution/in_place_validation/dependency_results.json) | Saved emitted-byte, mapper, geometry, preflight or dependency validation. |
| [b16_finer_loop_sync_resolution/in_place_validation/expected_words.tsv](implementation/b16_finer_loop_sync_resolution/in_place_validation/expected_words.tsv) | Exact new instruction words, assembly verification or caller-route evidence. |
| [b16_finer_loop_sync_resolution/in_place_validation/integrate.py](implementation/b16_finer_loop_sync_resolution/in_place_validation/integrate.py) | Original builder or imported build/ELF/container utilities; entry-point scope described above. |
| [b16_finer_loop_sync_resolution/in_place_validation/preflight.py](implementation/b16_finer_loop_sync_resolution/in_place_validation/preflight.py) | Scoped emitted-instruction validator or inherited decoder/model dependency. |
| [b16_finer_loop_sync_resolution/in_place_validation/preflight_results.json](implementation/b16_finer_loop_sync_resolution/in_place_validation/preflight_results.json) | Saved emitted-byte, mapper, geometry, preflight or dependency validation. |

### Imported utilities and checkpoints

| File | Purpose |
|---|---|
| [b16_finer_loop_sync_resolution/offline_candidate/build.py](implementation/b16_finer_loop_sync_resolution/offline_candidate/build.py) | Original builder or imported build/ELF/container utilities; entry-point scope described above. |
| [b16_finer_loop_sync_resolution/offline_candidate/mips_tools.py](implementation/b16_finer_loop_sync_resolution/offline_candidate/mips_tools.py) | Scoped emitted-instruction validator or inherited decoder/model dependency. |
| [b16_finer_loop_sync_resolution/offline_candidate/native_mapper_test.cpp](implementation/b16_finer_loop_sync_resolution/offline_candidate/native_mapper_test.cpp) | QNX helper assembly or native mapper test fixture. |
| [b16_finer_loop_sync_resolution/offline_candidate/native_wrapper.s](implementation/b16_finer_loop_sync_resolution/offline_candidate/native_wrapper.s) | QNX helper assembly or native mapper test fixture. |
| [b16_finer_loop_sync_resolution/offline_candidate/qnx_helper.s](implementation/b16_finer_loop_sync_resolution/offline_candidate/qnx_helper.s) | QNX helper assembly or native mapper test fixture. |
| [b16_finer_loop_sync_resolution/offline_candidate/validate.py](implementation/b16_finer_loop_sync_resolution/offline_candidate/validate.py) | Scoped emitted-instruction validator or inherited decoder/model dependency. |
| [b16_finer_loop_sync_resolution/safety_review/candidate_preservation.json](implementation/b16_finer_loop_sync_resolution/safety_review/candidate_preservation.json) | Historical .2.1 integration preservation checkpoint; includes private prior files. |
| [b16_finer_loop_sync_resolution/safety_review/tight_editor_probe.py](implementation/b16_finer_loop_sync_resolution/safety_review/tight_editor_probe.py) | Scoped emitted-instruction validator or inherited decoder/model dependency. |

### Shared caller and gate evidence

| File | Purpose |
|---|---|
| [b16_finer_loop_sync_resolution/ENCODER_CALLERS.tsv](implementation/b16_finer_loop_sync_resolution/ENCODER_CALLERS.tsv) | Exact new instruction words, assembly verification or caller-route evidence. |
| [b7_candidate_work/validate_version_gates.py](implementation/b7_candidate_work/validate_version_gates.py) | Scoped emitted-instruction validator or inherited decoder/model dependency. |

Cleanup checks: recovered source identities, Python/JSON syntax, links, checksum inventory and the private final `.2.2` package identity PASS. Builds, feature matrices and hardware tests were not rerun.
