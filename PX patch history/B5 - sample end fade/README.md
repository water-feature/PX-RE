# B5 - Non-looping sample endpoint fade

Technical handover for B5 and its final pitch-modulation correction. B5 is implemented and hardware-confirmed. The corrected .1.11 implementation supersedes the original .0.5 build; these versions identify B5 milestones, not the latest combined project firmware.

**Firmware:** `2.2.2.1.11` (corrected implementation); `PxUpdate_V2.2.2.0.5.bin` is historical and contains the pitch-modulation bug.

**Hardware: PASS:** The .1.11 endpoint-click correction under pitch modulation passed hardware testing. 

The .0.5 source, build tools and reports are retained to explain the original implementation; use the corrected .1.11 implementation for B5.

The final correction is documented in the “Endpoint clicks under pitch modulation” section below. Rebuilding corrected B5 source requires both linked source diffs in addition to the historical C files. The exact `.1.11` binary patch recipe targets the incremental `.1.10` baseline.

**Historical standalone package:** `voice_b5_2.2.2.0.5.bin`, using updater-facing filename `PxUpdate_V2.2.2.0.5.bin`. It contains B1 plus the original B5, with stock PIC and FPGA payloads. B3 is not part of this package. The later `.7` integration includes B1, B3, original B5 and B8, and also predates the `.1.11` correction.

## Original implementation and retained fade policy

**Patch location:** QNX application (x86-64). The .1.11 PIC changes are version metadata only.

**Patch size:** Original .0.5: 11,269 code/constant bytes, 3,028 unwind bytes including terminator, and a 6,916-byte combined unwind index; reservations are 12/4/8 KiB respectively. Final .1.11 correction adds 130 helper bytes within inherited reservations, with no image-length growth; versus .1.10, 285 QNX bytes and two PIC revision bytes differ (291 whole-package bytes).

Non-looping sample playback could click at its selected end in forward playback or selected start in reverse playback while the amp envelope remained open. The reader stopped supplying source audio and filled with zeros while interpolation/filter history continued at the existing gain.

B5 applies one shared output fade after interpolation and oscillator filtering, before gain routing. Both work channels receive the same envelope. The default duration is 5 ms: 240 output intervals at the firmware's 48 kHz output rate. It predicts the first output influenced by terminal input and completes the fade at the preceding 32-output block boundary, up to 31 outputs early.

Looping playback bypasses B5. So do selected regions whose total playback duration is at most the configured fade duration: eligibility requires source length greater than `240 * rate` at the default setting. Invalid rates bypass prediction. When startup or a late control change leaves less time, the available ramp is shortened and normalized to start at unity; playback is not extended to manufacture a full fade.

Rate and selected-start/end requests are deferred only during the audible ramp, for at most its configured output duration. Latest request wins. Direction, seeks and loop-mode changes remain immediate. Error or unavailable-output returns release an active hold without advancing the rendered clock. No raw PCM, resampler ring or filter history is rewritten. The later `.1.11` correction below preserves this fade policy while fixing rate-modulated endpoint prediction/completion.

An unchanged completed configuration stays at zero gain to prevent tail rebound. In standalone B5, changing effective endpoints can permit playback to resume through the original lifecycle. B8 subsequently prevents completed-note resurrection; that later behavior must not be attributed to standalone B5.

## Historical .0.5 implementation files and ownership

- [b5_core.c](b5_candidate_work/b5_core.c): eligibility, endpoint prediction, fade clock/gain, hold and completion policy.
- [b5_adapters.c](b5_candidate_work/b5_adapters.c): reader ownership, endpoint banks, normalized batch identity, consumed-input timing and output application.
- [emit_b5_objects.py](b5_candidate_work/emit_b5_objects.py): generated ABI shims, headers and standalone objects. The shared duration comes from [b5_fade_prototype.py](b5_fade_prototype.py).
- [build_b5_candidate.py](b5_candidate_work/build_b5_candidate.py) and [validate_b5_candidate.py](b5_candidate_work/validate_b5_candidate.py): guarded installation, relocation, layout and unwind verification.

Eight JMP observers cover forward and reverse reads, geometry, Prepare, NoteOn, Reset, PlayNote return and ordinary EOF. Four CALL wrappers observe Read, left Load, Filter and normalization. All addresses below are original QNX x86-64 ELF virtual addresses; ranges exclude the end. They are not container offsets. The historical Ghidra import adds `0x100000`.

| Hook | ELF address | Purpose |
|---|---|---|
| Forward / reverse | `0x405BD` / `0x40474` | Observe ordinary source spans |
| Geometry | `0x3FBE9` | Observe final selected bounds |
| Prepare | `0x372E5` | Apply effective held rate and preview reader context |
| NoteOn / Reset | `0x36448` / `0x3C8F0` | Reset/attach owned state |
| PlayNote return / EOF | `0x37496` / `0x40060` | Release unavailable-output holds; observe terminal input |
| Read / left Load | `0x3CC81` / `0x37363` | Track actual consumed audio and resampler input |
| Filter / normalization | `0x37446` / `0x3CD69` | Apply output gain; publish normalized batch identity |

During a held Read, the consumed endpoint bank stays held through the next UpdateLoc. Latest requests are restored only into the new producer bank. Reader swaps clone the endpoint banks, rates and selector; both readers share slot-owned B5 state. A pending length/channel change invalidates the old hold before the swap.

Raw Read metadata is provisional. Normalization publishes metadata only for the owned float-buffer pair; Load matches the actual pointer, offset and copied count. Speculative reads, start-delay zeros and shortage zeros do not commit fade time. The predictor models the physical 1024-float resampler ring and future Loads, including overwrite/wrap behavior, over a 304-output default horizon. A conservative bound skips exact prediction only when terminal influence is safely beyond that horizon. Stereo bookkeeping divergence cancels the forecast/hold.

State uses 256 bytes per stream: 176 core bytes and 80 bridge bytes. There are 64 streams and two eight-byte reader extensions per stream, totaling 17,408 extra heap bytes. Slot allocation grows from `0xC00` to `0x4C00`; each owned reader grows from `0x1B8` to `0x1C0`. No allocation occurs in the audio loop. Unrelated readers are excluded before extension access by checking the owned Read wrapper return address.

## Installed ELF layout

| Region | Start | Actual size | Reservation |
|---|---|---:|---:|
| Code and constants | `0xF1000` | 11,269 | 12,288 |
| New unwind records | `0xF4000` | 3,028 including terminator | 4,096 |
| Combined unwind index | `0xF5000` | 6,916 | 8,192 |

Extended RX ends at `0xF7000`; replacement section names and the aligned section table follow. The original eight program headers, original payload locations, original 37 section indices and original EH frame pointer are retained. RX sizes and the active unwind-index location/sizes are updated.

The combined index preserves all 839 inherited absolute PC/FDE pairs and adds 24 records, totaling 863. Original FDE bytes and B1 hook/helper/unwind ownership remain unchanged. Exactly 100 original bytes change within 19 whitelisted ranges. See the [candidate manifest](b5_candidate_work/b5_candidate_manifest.json) for guarded edits, bindings, relocations and complete function ranges.

## Historical .0.5 firmware identities

| Artifact | Bytes | SHA-256 |
|---|---:|---|
| Base `voice_2.2.2.0.2.bin` | 3,099,064 | `2ad5392eb842cbcd5c2e85e65ab42c16f1fac12d16b09c417a61761a8348bcbf` |
| Extracted base QNX ELF | 986,520 | `651f0ac3339f4f41a4c0bc562cdf4c72df821d85aad3f689e700612b8c8b05e7` |
| B5 candidate QNX ELF | 1,014,576 | `07ff1fd635505114945fc4dcab11a212f4bc9164b1a7ab8beb681482cb7c2b35` |
| B5 `.5` update | 3,127,120 | `41242b0d3cde1cf208181d998176db62dcc9484e2ca74e22104f4a140845a587` |

The package header and updater-facing filename identify 2.2.2.0.5. The pinned application retains compiled revision comparison and DSP display 2.2.2.0.2. DSP `.2` therefore does not distinguish B5 from the voice-only base; use the package hash. This intentional header/display distinction is part of the tested artifact.

## Historical .0.5 packaging and reproduction

The container uses `F0`, three records, then `F7`. Each record has a 12-byte header: type, `7B`, five numeric revision bytes, `7A`, and a four-byte big-endian payload length; a two-byte trailer follows its payload.

The [packager](b5_packaging_work/package_b5_test.py) replaces the application with the exact B5 candidate, updates its length and final header revision byte from 2 to 5, and recomputes its checksum. The checksum sums unsigned little-endian 16-bit payload words modulo 65,536, excluding header/trailer; this even-length payload needs no trailing-byte rule. Result: `0x3404`, stored as `04 34`. Payload growth is 28,056 bytes. The complete FPGA and PIC records shift by that amount and remain byte-identical to the base. The PIC trailer `30 30` is preserved verbatim despite differing from the simple word sum `0x4658`.

Work in a private copy of this directory. Preserve its root helpers and sibling `b5_candidate_work/` and `b5_packaging_work/` directories. Supply your own `voice_2.2.2.0.2.bin` and extracted `voice_2.2.2.0.2_qnx.elf` at that private root. B1's documentation explains how to reproduce the voice-only base from privately held stock firmware.

```sh
python3 b5_candidate_work/emit_b5_objects.py
python3 b5_candidate_work/build_b5_candidate.py
python3 b5_packaging_work/package_b5_test.py
python3 b5_packaging_work/verify_b5_test.py
```

Object emission requires Clang, GNU-compatible objdump and the Python dependencies imported by the supplied helpers. Compiler output can depend on toolchain version; the saved object/source hashes are enforced by the builder. An exact source-to-object rebuild was not rerun during documentation cleanup. The candidate builder runs structural validation itself; `validate_b5_candidate.py` supplies its imported validator rather than a separate standalone command.

`emit_b5_candidate.py` is included for its imported utilities; use the complete object emitter above, not that earlier staging entry point. `patch_b4_minimal_qnx.py` supplies the imported ELF parser; its B4 main program is not part of B5. Generated headers, shim assembly and the [object manifest](b5_candidate_work/b5_objects_manifest.json) are included. Full firmware and compiled objects are excluded. Some tools write fixed output names; use a fresh private working directory. The packager refuses existing delivery outputs.

**Packaging reconstruction PASS:** during this documentation review, the supplied packager reproduced the original private `.5` package byte-for-byte from the pinned base and candidate. The independent verifier passed all 21 checks. See the [new verification report](b5_packaging_work/documentation_packaging_verification.json), [historical packaging manifest](b5_packaging_work/b5_packaging_manifest.json) and [historical validation](b5_packaging_work/b5_packaging_validation.json). This check did not rerun source compilation or hardware testing.

## Historical validation and evidence limits

| Evidence | Recorded result |
|---|---|
| [Candidate structural validation](b5_candidate_work/b5_candidate_validation.json) | PASS: 7,036 checks, 60 code and 24 frame relocations, 1,142 instruction/CFA checks, 21 aligned call sites, 2,733 index boundary/bias checks |
| [Adapter integration](b5_candidate_work/b5_integration_validation.json) | PASS: 1,166 checks across nine groups; actual resolved object code in a host fixture, stock QNX routines simulated |
| [Object structure](b5_candidate_work/b5_object_structure_validation.json) | PASS: shim/wrapper unwind and stack checks |
| [Fade prototype](b5_fade_prototype_results.json) | Recorded host-model evidence; not hardware execution |
| Historical packaging | PASS: 21 independent checks, seven rejection cases and deterministic comparison |
| Documentation packaging reconstruction | PASS: exact original `.5` bytes reproduced; 21 independent checks |
| Original `.5` hardware test | PASS for the initial reported use case; superseded by the subsequently identified pitch-modulation bug and `.1.11` correction |

Original JSON pending/hardware-false fields describe their offline checkpoints and remain unchanged. Later owner confirmation supersedes those status labels for installation and the reported audible defect. That original hardware result covers only the initial reported use case, not the later pitch-modulation defect; it does not measure real-time headroom or prove every concurrency, unwinder or control-transition scenario.

Carried loop-to-off splices can have opaque source history; B5 preserves the inherited transition when a reliable linear endpoint forecast is unavailable. Arbitrary seeks, direction changes and parameter edits are not all made clickless. Positive additive VCA modulation, general voice behavior and unrelated playback policies are not redefined by this endpoint fade.

The inherited compiled `.2` updater gate can skip reinstalling the voice-only `.2` base. The recorded rollback route uses official stock `.0` before voice `.2`; a B5-specific hardware rollback trial is not established by these reports. No further installation, recovery or firmware modification was performed for this documentation review.

## Endpoint clicks under pitch modulation — final correction in 2.2.2.1.11

**Patch location and size:** QNX; 130 helper bytes within the inherited reservation, 285 changed QNX bytes versus .1.10. PIC changes are two revision bytes only; no image-length growth.

**Hardware PASS, owner report dated 8 October 2026:** `.1.11` resolves the reported LFO-modulated sample endpoint clicks. Individual cases from the hardware sequence were not separately reported. This is part of B5 even though the working files were historically stored under `b15_candidate_work/`.

Pitch modulation exposed two rate-sensitive conditions. Buffered endpoint metadata was required to match the current playback rate exactly, although its source-region coordinates remained valid. Also, after the fade completed, a rate-only change could clear its completed-silence state. Because the fade finishes before terminal source/filter influence, removing that state could restore nonzero audio when there was no remaining opportunity to fade again. Tiny rate steps, including approximately one part per million in the modeled fixture, were sufficient.

The final implementation includes both changes:

- Endpoint identity compares selected bounds, direction and loop state independently of rate. Prediction still uses the actual current playback rate; exact control-rate comparisons and active-ramp holds remain in place.
- Core apply and adapter GEOM preserve completed-fade silence for rate-only changes to the same source region, while updating the effective playback rate. Genuine region/direction/loop changes retain cancellation. Note/reset, pre-completion holds and B8's completed-reader lifecycle remain intact.

Fade maximum remains 5 ms and existing tiny-region eligibility is unchanged. Sample encoder acceleration is identical to the `.1.10` baseline; PIC changes are only two revision bytes and FPGA is unchanged. This correction does not globally ignore rate changes or introduce a new audio envelope.

### Patch locations and source semantics

The [helper assembly](b15_candidate_work/lfo_endpoint_investigation/completion_fix/helpers.s) and [builder](b15_candidate_work/lfo_endpoint_investigation/completion_fix/build.py) are the exact `.1.11` binary recipe. The [completion source diff](b15_candidate_work/lfo_endpoint_investigation/completion_fix/source_change.diff) records equivalent source semantics; it must be combined with the [inherited endpoint-identity diff](b15_candidate_work/lfo_endpoint_investigation/source_change.diff) when rebuilding from the original B5 C source. The root `b5_core.c` and `b5_adapters.c` remain the original `.5` sources; they are not silently relabeled as final `.1.11` sources.

| Location | Final correction |
|---|---|
| `0xF3C40` | Completed-region apply helper |
| `0xF3C90` | Completed-region GEOM helper |
| `0xF122C`, `0xF126E` | Calls redirected to the apply helper |
| `0xF1BC2` | Six-byte GEOM hook window redirected to the GEOM helper |

These are QNX ELF addresses in the inherited layout used by the builder. Helpers occupy 130 bytes within the inherited B5 code reservation. Two new FDEs cover the leaf and dispatch contexts; all 895 inherited FDE records stay byte-identical and the combined index has 897 entries. There is no heap, stack or image-length growth. The [build report](b15_candidate_work/lfo_endpoint_investigation/completion_fix/build_results.json) records guarded windows, allowed edit ranges, hashes and CFI verification.

### Version, packaging and evidence

| Artifact | Identity |
|---|---|
| Baseline package | `2.2.2.1.10`, SHA-256 `6ab00ccd1f9461ffcf5927b54b317d7644c85a3a129dff6115f8cd0cd6a6a6e3` |
| Baseline QNX | SHA-256 `7322f41979a70d72b740b1a967770f71ef706822343d2582eab0b08caea69ddc` |
| Unpackaged corrected QNX | SHA-256 `30663f135c4ad75c43ad7a8252f7d932adce0164138071c8ba32f6f11051e906` |
| Final package | `PxUpdate_V2.2.2.1.11_B5_completion_fade_candidate.bin`, 3,187,784 bytes |
| Final package SHA-256 | `29aff5a6cbf6d603ae86f23525454bbbcbe568c3930d65c2064ce827080c86a8` |

Compared with `.1.10`, the final package changes 285 QNX bytes, two PIC bytes and 291 total package bytes. Packaged QNX differs from the validated corrected ELF only at its two version bytes. The [packaging script](b15_candidate_work/lfo_endpoint_investigation/completion_fix/package.py) sets QNX file offsets `0x1F4E3`/`0x250EF` to `0x1B`/11, updates application/PIC headers to 2.2.2.1.11, updates PIC report-thunk immediates at payload offsets `0x1394`/`0x13A0` from 10 to 11, recalculates the application checksum, and preserves the FPGA record and PIC trailer.

Recorded checks:

- [Completion reproducer](b15_candidate_work/lfo_endpoint_investigation/check_completion.py) and [results](b15_candidate_work/lfo_endpoint_investigation/completion_results.json): 54 checks across six sequences establishing the rate-only completion cancellation mechanism in emitted `.1.10` code, with modeled stock audio/loading.
- [Corrected validation](b15_candidate_work/lfo_endpoint_investigation/completion_fix/validation_results.json): 2,174 candidate checks, including 48 completion sequences across two slots, mono/stereo, forward/reverse, tiny rate steps and deferred changes, lifecycle/cancellation, 32–241-frame eligibility and nine inherited groups. The 2,173-check baseline comparison establishes the regression fixture.
- [Package verification](b15_candidate_work/lfo_endpoint_investigation/completion_fix/package_results.json): component identity, round-trip, exact changed-byte accounting, 16 modeled version-gate cases and 260 checksum accept/reject comparisons over 130 PIC blocks.

Host fixtures execute fitted B5/B8 code and wrappers with modeled stock reader/loading/filter operations. They do not execute a full preset or complete QNX signal path. Original reports' hardware-pending fields describe their pre-hardware dates; the later owner-reported `.1.11` PASS above is the acoustic result. No feature suites or hardware tests were rerun for this documentation merge.

### Private incremental reproduction

Preserve the supplied `b15_candidate_work/lfo_endpoint_investigation/completion_fix/` hierarchy in a private copy of this B5 directory. The original scripts locate the workspace root by traversing this hierarchy. Supply `.1.10` privately under `b14_sample_acceleration_work/` using the exact names referenced in the scripts. Existing B5 ELF helpers and manifests are supplied in this folder; additional shared packaging helpers are included as `b15_candidate_work/build_candidate_1_8.py` and `build_candidate_1_9.py`.

From the private `completion_fix/` directory:

```sh
python3 build.py
python3 validate.py
python3 package.py
```

Assembly requires Clang's x86-64 target. Validation uses macOS x86-64 host fixtures and may require Rosetta on Apple Silicon; it is not a portable target-QNX test runner. The included parent fixtures, generated offsets, extra tests and B5 wrapper fixture are dependencies. Generated executables and firmware must stay private. The separate parent `check_completion.py` is optional investigation evidence, not a required packaging step.

[SHA256SUMS](SHA256SUMS) covers the files distributed in this public B5 folder. It is a publication inventory, not the historical checksum list containing private generated firmware. As with the other branches, these incremental tools explain the implementation; they are not a standalone stock-to-B5-only packager or the planned factory-to-final project packager.

### Hardware regression recipe

The original `.1.11` sequence uses an init patch with a single sample oscillator, looping off, a region longer than 5 ms, long release, and a slow sawtooth targeting Inst1Freq. Compare depths 0, 1 and larger values, then isolate and repeat on Inst2Freq. Completed playback should remain silent without a returning click/burst while pitch tracks modulation before completion.

Additional cases cover LFO slope/reset and triangle/sine; low/high pitch and slow/faster modulation; mono/stereo and forward/reverse; active/post-endpoint geometry and loop edits; long release, repeated notes, voice stealing, preset reload/reset and linked layers. Compare regions below/around/above 5 ms without expecting new tiny-region eligibility, and confirm inherited sample-encoder acceleration remains unchanged. In the integrated B8 lifecycle, retrigger a completed reader rather than expecting an endpoint edit to restart it.

These describe the retained test recipe, not a claim that every case was separately reported. Testing on hardware was successful but not yet comprehensive.

## Complete supporting-file inventory

Every retained supporting file is linked below. Implementation, imported dependencies, test fixtures and saved evidence are distinguished by purpose; not every evidence file is required to build the feature. Original script layouts are retained so their relative imports remain intact. Firmware and generated binary inputs remain private, as described above. The [root checksum inventory](SHA256SUMS) covers this handover and all retained supporting files.

| File | Purpose |
|---|---|
| [b15_candidate_work/build_candidate_1_8.py](b15_candidate_work/build_candidate_1_8.py) | Build/emission/layout tool or imported build dependency. |
| [b15_candidate_work/build_candidate_1_9.py](b15_candidate_work/build_candidate_1_9.py) | Build/emission/layout tool or imported build dependency. |
| [b15_candidate_work/lfo_endpoint_investigation/b5_offsets.generated.h](b15_candidate_work/lfo_endpoint_investigation/b5_offsets.generated.h) | Generated structure/offset or policy definitions used by source/tests. |
| [b15_candidate_work/lfo_endpoint_investigation/check_completion.py](b15_candidate_work/lfo_endpoint_investigation/check_completion.py) | Validation/test or ownership audit tool; uses the private inputs described in source. |
| [b15_candidate_work/lfo_endpoint_investigation/completion_fix/build.py](b15_candidate_work/lfo_endpoint_investigation/completion_fix/build.py) | Build/emission/layout tool or imported build dependency. |
| [b15_candidate_work/lfo_endpoint_investigation/completion_fix/build_results.json](b15_candidate_work/lfo_endpoint_investigation/completion_fix/build_results.json) | Saved validation, measurement or ownership evidence; not a new test run. |
| [b15_candidate_work/lfo_endpoint_investigation/completion_fix/extra_tests.c](b15_candidate_work/lfo_endpoint_investigation/completion_fix/extra_tests.c) | Test/stock-operation fixture. |
| [b15_candidate_work/lfo_endpoint_investigation/completion_fix/helpers.s](b15_candidate_work/lfo_endpoint_investigation/completion_fix/helpers.s) | Helper/shim assembly or generated target layout. |
| [b15_candidate_work/lfo_endpoint_investigation/completion_fix/package.py](b15_candidate_work/lfo_endpoint_investigation/completion_fix/package.py) | Incremental packaging/publication tool. |
| [b15_candidate_work/lfo_endpoint_investigation/completion_fix/package_results.json](b15_candidate_work/lfo_endpoint_investigation/completion_fix/package_results.json) | Saved validation, measurement or ownership evidence; not a new test run. |
| [b15_candidate_work/lfo_endpoint_investigation/completion_fix/source_change.diff](b15_candidate_work/lfo_endpoint_investigation/completion_fix/source_change.diff) | Semantic source changes for the endpoint/pitch-modulation correction. |
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
| [b5_elf_placement_results.json](b5_elf_placement_results.json) | Saved validation, measurement or ownership evidence; not a new test run. |
| [b5_fade_prototype.py](b5_fade_prototype.py) | B5 fade policy and prediction constants used by emitters and regression tests. |
| [b5_fade_prototype_results.json](b5_fade_prototype_results.json) | Saved validation, measurement or ownership evidence; not a new test run. |
| [b5_packaging_work/b5_packaging_manifest.json](b5_packaging_work/b5_packaging_manifest.json) | Saved patch/object/packaging identity and layout evidence. |
| [b5_packaging_work/b5_packaging_validation.json](b5_packaging_work/b5_packaging_validation.json) | Saved validation, measurement or ownership evidence; not a new test run. |
| [b5_packaging_work/documentation_packaging_verification.json](b5_packaging_work/documentation_packaging_verification.json) | Saved validation, measurement or ownership evidence; not a new test run. |
| [b5_packaging_work/package_b5_test.py](b5_packaging_work/package_b5_test.py) | Incremental packaging/publication tool. |
| [b5_packaging_work/verify_b5_test.py](b5_packaging_work/verify_b5_test.py) | Validation/test or ownership audit tool; uses the private inputs described in source. |
| [patch_b4_minimal_qnx.py](patch_b4_minimal_qnx.py) | Inherited ELF parser imported by object/build utilities; its B4 entry point is not part of this feature. |
| [test_b5_fade_prototype.py](test_b5_fade_prototype.py) | Validation/test or ownership audit tool; uses the private inputs described in source. |
