# B10 - Clicks when scrolling the sample window

Technical handover for the retained B10 correction. The implementation substantially reduces clicks but remains incomplete. The later .1.16 minimum-fade experiment is excluded; the combined feature chain continues from .1.15.

**Firmware:** `2.2.2.1.15` (retained implementation).

**Hardware: PARTIAL SUCCESS:** Window-scroll clicks were substantially reduced, but residual clicks remain, especially with several notes held. The .1.16 experiment produced no detectable improvement over .1.15 in the reported hardware test.

The later `.1.16` minimum-fade experiment passed host checks but produced no detectable improvement over `.1.15` on hardware in Regular mode with Crossfade 255. It is not the retained implementation. The subsequent feature chain continues from `.1.15`.

## Problem and reproduction

Moving Center against playback with shorter loop settings can click: moving left during forward playback, or right during reverse playback. The issue was observed in Regular mode and across all three FwdRev settings. A useful reproducer is Start 0, End 999, Loop on, an approximately 250 ms window, and Crossfade 255 (though Crossfade appears to have no effect here). Around 500 ms the problem decreased; this is an observed trend, not a fixed safe threshold. Pitched mode was clean in the tested sample above approximately Crossfade 50; Sync was clean under its existing minimum constraints. 

B10 concerns ordinary window crossfade entry and handoff. B5's endpoint fade is a separate mechanism.

## Implementation

**Patch location:** QNX application (x86-64); PIC changes are two revision bytes only.

**Patch size:** 1,025 emitted helper-code bytes across two text sections (1,035-byte extent including alignment), plus 472 unwind bytes and in-place hooks/index metadata. The recorded .1.12 → .1.15 comparison changes 1,395 QNX bytes and 1,401 whole-package bytes. Payload lengths are unchanged; reader allocation grows by 16 bytes per reader, separate from patch size.

When an edit places the playhead partway into an ordinary fade, the inherited calculation can introduce an incoming contribution immediately. The retained correction starts a newly entered fade at outgoing-only audio. With N >= 2 available frames, progress is `k/(N-1)` and the final frame is exactly incoming audio. It preserves the inherited blend law, outgoing source timeline and actual handoff position.

Read stages the origin; Update commits it only after positive actual consumption. Discarded renders do not commit it. Ownership lasts only while the splice identity remains valid. Seeks suppress a new correction while preserving an already owned envelope until consumption changes its identity. Already active unowned splices and forced fade paths retain inherited behavior.

For reverse bounce, the first incoming read is aligned to `2*A-P`, matching Update's trajectory regardless of render size. This happens before LocalRead, without a duplicate read or an extra audio buffer.

Each reader gains 16 bytes at the end of its existing endpoint allocation (`0x500` → `0x510`): flags and staged geometry. Constructor initialization, Close and successful Open reset validity; the original destructor frees the extended allocation. Endpoint cloning copies only the original `0x500` bytes. The committed origin uses the existing retained-envelope start at reader offset `0x10`. There is no reader-object layout change, shared state table or allocation during Read/Update.

The authored correction is in [patch.c](implementation/b10_ordinary_entry_design_1_12/candidate_1_15/patch.c); detours are in [hooks.s](implementation/b10_ordinary_entry_design_1_12/candidate_1_15/hooks.s). [build.py](implementation/b10_ordinary_entry_design_1_12/candidate_1_15/build.py) compiles, relocates and installs them. [emission.json](implementation/b10_ordinary_entry_design_1_12/candidate_1_15/emission.json) records exact symbols, changed ranges and hashes.

The build hooks Read `0x3F840`, Update `0x41870`, Close `0x42510`, Open `0x42CD1`, endpoint allocation and the affected fade/reverse-read call sites. New text starts at `0x1012C0`; new unwind data starts at `0x1025A4`. All 899 inherited unwind entries remain, with ten new entries. ELF file size and PT_LOAD mappings remain unchanged. Inherited B5/B8/B15 code and frames remain byte-identical to `.1.12`.

## Verification and limits

Saved host results execute the emitted `.1.15` code through an x86_64 ctypes harness. They are not a simulation of the correction itself, but the geometry edits, source data and producer timing are synthetic.

- 162,528 phase trials, including 6,900 corrected entries and complete transitions. Entry and final handoff excess relative to the respective source's adjacent sample were zero. Worst transition step decreased from 20,834 to 754 PCM counts in this sweep.
- 32 lifecycle configurations, 32 source-sequence/handoff cases and 32 repeated-edit/tail cases passed. Partitioned PCM differed by at most one count.
- 96 no-edit cases, 96 preservation cases and 48 FwdRev cases passed. Storage, lifecycle, seeking and independent-reader checks passed.
- 43,528 inherited Center fixture cases passed against the emitted image; this public folder preserves its result rather than duplicating the complete inherited fixture.
- 16,000 short-distance tests establish a limit: zero available frames retain inherited behavior; one frame cannot preserve both arbitrary endpoints continuously; two frames may concentrate the entire content change into one step. The worst measured step at N=0/1/2 was 23,976 counts.

**Short fades are a possible limitation, not the established cause of the remaining hardware clicks.** The real panel-to-reader delivery path has not been reproduced by the host sweep. Multi-reader probes did not establish shared-state corruption and do not reproduce the full hardware control path.

[validation.json](implementation/b10_ordinary_entry_design_1_12/candidate_1_15/validation.json) and the related logs are preserved historical build-time records. Their `hardware: NOT VERIFIED` / `flashed: false` fields describe when those scripts ran. They do not override the later confirmed hardware result stated above. A script PASS establishes its bounded checks, not completion of B10.

## Incremental build and PxUpdate packaging

This is an exact **2.2.2.1.12 → 2.2.2.1.15** patch and packager, not a factory-only B10 installer. It deliberately does not incorporate `.1.13` or `.1.14`. Firmware is not distributed here. Supply your privately held exact inputs under `implementation/`:

| Input path relative to implementation/ | SHA-256 |
|---|---|
| `PxUpdate_V2.2.2.1.12.bin` | `9d0860d06469519a1f80feef2a2143e4a2a343605821f28f193c985398943139` |
| `b7_lfo_center_investigation/implementation_1_12/voice_2.2.2.1.12_qnx.elf` | `b411fc94d17683f49d62184e3c794f6e4eea72e7d6ea58edd1b78ff706377ced` |
| `b7_lfo_center_investigation/implementation_1_12/pic_2.2.2.1.12.bin` | Must match the PIC extracted from that exact package; package.py checks byte identity. |

Keep the supplied directory structure. Use Python 3 and clang with the x86_64 ELF target. Running the emitted-code host checks requires x86_64 Python (Rosetta on Apple Silicon), executable memory mapping and a compatible objdump. Ghidra is not required by the supplied build or package scripts.

```sh
cd implementation/b10_ordinary_entry_design_1_12/candidate_1_15
python3 build.py
python3 validate.py
python3 package.py
```

The validation command uses the preserved evidence alongside the newly emitted image. To regenerate behavioral evidence, first run `run_sweep.py` in `implementation/b10_center_sweep_1_12`, then run `run_phase.py`, `run_handoff_sweep.py`, `run_lifecycle.py`, `run_preservation.py`, `verify_sequences.py`, `verify_repeated_tail.py`, `test_storage.py` and `test_transport.py` from the candidate directory. Capture their console output to the corresponding existing logs when refreshing evidence. The sweep also expects a private `reextracted_qnx.elf` beside the baseline QNX file, byte-identical to it. Large `sweep.csv` and `phase.csv` datasets are regenerated rather than distributed. Regenerating the inherited Center fixture requires its original test environment; its saved result is included here.

[package.py](implementation/b10_ordinary_entry_design_1_12/candidate_1_15/package.py) checks the exact baseline package and extracted inputs, inserts the validated QNX application, changes only the two PIC revision immediates at `0x1394` and `0x13A0`, updates application/PIC container revisions and the application checksum, and preserves the complete FPGA record and inherited PIC trailer. It reextracts and checks the result, accounts for all 1,401 changed package bytes, and refuses to overwrite a different output.

Output: `implementation/PxUpdate_V2.2.2.1.15_B10_ordinary_entry_candidate.bin`, 3,187,784 bytes. Expected identities:

| Artifact | SHA-256 |
|---|---|
| PxUpdate `.1.15` | `ebb2aebbd0decdadce92ed40d257e0cb03ebbf7aecf3e05749d9533fd5603450` |
| QNX `.1.15` | `dd9efbcd2804e02cc4599e72d2ee90f996facce1fa06f1815a0078270566a2fa` |
| PIC `.1.15` | `be8eb8ac823a639f3024b97e01b017ef0cef5f33d086eaa71dfe55d4b0e34622` |

The package report is [package_results.json](implementation/b10_ordinary_entry_design_1_12/candidate_1_15/package_results.json). Its checksum strings represent serialized bytes. Historical validation manifests can name private firmware and regenerated datasets intentionally absent from this public folder. The root [SHA256SUMS](SHA256SUMS) is the current public-file inventory.

## Remaining investigation

Trace actual `.1.15` panel-message delivery through `WritePlaybackParams` (`0x3CA40`), `ClientProcessStream` (`0x3CB50`), Read (`0x3F840`), geometry dispatch (`0x3FC18`) and Update (`0x41870`). Correlate endpoint-bank geometry, committed cursor, direction, flags, remaining fade frames and PCM at entry/interior/handoff with resampler consumption. Establish how paired Center values, dirty controls and bank timing reach held voices. The existing host tests directly install synthetic geometry and cannot establish this timing. No further candidate should be described as resolving the hardware issue on host evidence alone.

## Supporting files

The implementation sources and scripts below preserve the accepted correction, its build/package path, synthetic test harness and recorded evidence. JSON/log paths inside historical records may point to the original private workspace. No firmware, compiled objects or experimental `.1.16` payload is included.

### Sources and tools

- [run_sweep.py](implementation/b10_center_sweep_1_12/run_sweep.py)
- [sweep.py](implementation/b10_center_sweep_1_12/sweep.py)
- [build.py](implementation/b10_ordinary_entry_design_1_12/candidate_1_15/build.py)
- [hooks.s](implementation/b10_ordinary_entry_design_1_12/candidate_1_15/hooks.s)
- [investigate_multireader.py](implementation/b10_ordinary_entry_design_1_12/candidate_1_15/investigate_multireader.py)
- [package.py](implementation/b10_ordinary_entry_design_1_12/candidate_1_15/package.py)
- [patch.c](implementation/b10_ordinary_entry_design_1_12/candidate_1_15/patch.c)
- [proposal.py](implementation/b10_ordinary_entry_design_1_12/candidate_1_15/proposal.py)
- [run_handoff_sweep.py](implementation/b10_ordinary_entry_design_1_12/candidate_1_15/run_handoff_sweep.py)
- [run_lifecycle.py](implementation/b10_ordinary_entry_design_1_12/candidate_1_15/run_lifecycle.py)
- [run_phase.py](implementation/b10_ordinary_entry_design_1_12/candidate_1_15/run_phase.py)
- [run_preservation.py](implementation/b10_ordinary_entry_design_1_12/candidate_1_15/run_preservation.py)
- [test_storage.py](implementation/b10_ordinary_entry_design_1_12/candidate_1_15/test_storage.py)
- [test_transport.py](implementation/b10_ordinary_entry_design_1_12/candidate_1_15/test_transport.py)
- [validate.py](implementation/b10_ordinary_entry_design_1_12/candidate_1_15/validate.py)
- [verify_repeated_tail.py](implementation/b10_ordinary_entry_design_1_12/candidate_1_15/verify_repeated_tail.py)
- [verify_sequences.py](implementation/b10_ordinary_entry_design_1_12/candidate_1_15/verify_sequences.py)

### Recorded evidence

- [center_follow.json](implementation/b10_ordinary_entry_design_1_12/candidate_1_15/center_follow.json)
- [emission.json](implementation/b10_ordinary_entry_design_1_12/candidate_1_15/emission.json)
- [emission.log](implementation/b10_ordinary_entry_design_1_12/candidate_1_15/emission.log)
- [handoff.log](implementation/b10_ordinary_entry_design_1_12/candidate_1_15/handoff.log)
- [handoff_summary.json](implementation/b10_ordinary_entry_design_1_12/candidate_1_15/handoff_summary.json)
- [handoff_sweep.csv](implementation/b10_ordinary_entry_design_1_12/candidate_1_15/handoff_sweep.csv)
- [identity.json](implementation/b10_ordinary_entry_design_1_12/candidate_1_15/identity.json)
- [inherited_center.log](implementation/b10_ordinary_entry_design_1_12/candidate_1_15/inherited_center.log)
- [lifecycle.json](implementation/b10_ordinary_entry_design_1_12/candidate_1_15/lifecycle.json)
- [lifecycle.log](implementation/b10_ordinary_entry_design_1_12/candidate_1_15/lifecycle.log)
- [multireader_timing.json](implementation/b10_ordinary_entry_design_1_12/candidate_1_15/multireader_timing.json)
- [multireader_timing.log](implementation/b10_ordinary_entry_design_1_12/candidate_1_15/multireader_timing.log)
- [package_results.json](implementation/b10_ordinary_entry_design_1_12/candidate_1_15/package_results.json)
- [packaging.log](implementation/b10_ordinary_entry_design_1_12/candidate_1_15/packaging.log)
- [phase.log](implementation/b10_ordinary_entry_design_1_12/candidate_1_15/phase.log)
- [phase_counts.json](implementation/b10_ordinary_entry_design_1_12/candidate_1_15/phase_counts.json)
- [phase_examples.json](implementation/b10_ordinary_entry_design_1_12/candidate_1_15/phase_examples.json)
- [phase_summary.json](implementation/b10_ordinary_entry_design_1_12/candidate_1_15/phase_summary.json)
- [preservation.json](implementation/b10_ordinary_entry_design_1_12/candidate_1_15/preservation.json)
- [preservation.log](implementation/b10_ordinary_entry_design_1_12/candidate_1_15/preservation.log)
- [repeated_tail.json](implementation/b10_ordinary_entry_design_1_12/candidate_1_15/repeated_tail.json)
- [repeated_tail.log](implementation/b10_ordinary_entry_design_1_12/candidate_1_15/repeated_tail.log)
- [sequences.log](implementation/b10_ordinary_entry_design_1_12/candidate_1_15/sequences.log)
- [short_distances.json](implementation/b10_ordinary_entry_design_1_12/candidate_1_15/short_distances.json)
- [storage.json](implementation/b10_ordinary_entry_design_1_12/candidate_1_15/storage.json)
- [storage.log](implementation/b10_ordinary_entry_design_1_12/candidate_1_15/storage.log)
- [streams.json](implementation/b10_ordinary_entry_design_1_12/candidate_1_15/streams.json)
- [transport.json](implementation/b10_ordinary_entry_design_1_12/candidate_1_15/transport.json)
- [validation.json](implementation/b10_ordinary_entry_design_1_12/candidate_1_15/validation.json)
- [validation.log](implementation/b10_ordinary_entry_design_1_12/candidate_1_15/validation.log)
- [validation_manifest.json](implementation/b10_ordinary_entry_design_1_12/candidate_1_15/validation_manifest.json)

