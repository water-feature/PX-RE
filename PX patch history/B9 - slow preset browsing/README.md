# B9 - Faster preset browsing

Technical handover for the retained B9 improvement. The 250-tick version is hardware-tested and retained for now; further improvement remains open. This identifies the B9 milestone, not the latest combined project firmware.

**Firmware:** `2.2.2.1.2` (250 ticks); earlier `2.2.2.1.1` (500 ticks) is a comparison build.

**Hardware: PARTIAL SUCCESS:** The 250-tick version works much better than stock, but slowdown remains during fast browsing. The earlier 500-tick version was also tested and found to perform better than stock but slower than the 250-tick version; no measured latency or complete elimination of slowdown is established.

## What changed

Stock applies an isolated preset selection immediately, then starts a 500-service-tick countdown. Further selections replace the pending target and restart the countdown, postponing application during continuous panel input. B9 lets panel changes update the pending target without restarting a positive countdown, so the existing expiry machinery can apply the latest selection while browsing continues.

The final B9 version additionally uses **250 ticks for the panel immediate-path reload**, while nonpanel callers retain 500. It keeps existing bank/program/force/layer routing, equality suppression, idle/zero handling and global gates. MIDI program changes and stored-program SysEx retain the original reset policy; edit-buffer loading bypasses this browsing countdown. There is no new timer or RAM state and no QNX audio change.

| Version | Panel positive-count requests | Panel immediate reload | Hardware outcome |
|---|---|---|---|
| `.1.1` | Update pending target without reset | 500 ticks | Works well; some lag remained |
| **`.1.2`** | **Update pending target without reset** | **250 ticks** | **Much better than stock; fast-browsing slowdown remains** |

Both builders start from exact B6 `.0.9`. `.1.2` is validated differentially against `.1.1`, rather than requiring `.1.1` as its build input. B7’s historical `.1.0` reservation was not a delivered squash-limit implementation.

## Scope and remaining behavior

B9 improves application scheduling. It does **not** decouple preset-number/name display from sound application. Further work may include reverting to 500 ticks and investigating another approach, including responsive preset-number/name display independent of sound application. No reversion or alternative implementation has been made; those remain possible next steps rather than a selected design. Stored preset retrieval reads 4096 bytes synchronously from PIC serial flash and includes instrument metadata reconciliation; no complete runtime cost breakdown was obtained.

Expiry still marks the countdown idle rather than rearming it. A subsequent input can therefore cause an immediate load close to an expiry load. Final selection can wait the remainder of the interval plus application/main-loop delay. A shorter interval increases intermediate-load opportunities; the residual slowdown has not been shown eliminated.

## Delivered package and provenance

`PxUpdate_V2.2.2.1.2.bin`, 3151848 bytes.

SHA256:
- Package: `3e844a73a9f29bf0f1dc24929c989e0cb3946c9a307cab948e6af4c0928b5029`
- PIC: `8f3fcbccd5763324e5f0b7d9cc5941df806a9ecb46affa5c18f5f4d1b082a16c`
- QNX: `a0ee95328e908b4d1aadff6e71ca34e44d1845418bb1e8204372667ed99d62bf`
- FPGA: `54c70b9969c7bc6004c7ceb257a15ff1581ef82b1c3c1ad1eba185eacf15ad2b`

Hardware-tested parent B9 .1.1 package: `061248f2d8e4e11e9dec78d6b5c74b87d16a283c273e2eba35ae84c2e592a012`.
Regenerated from verified B6 .9 package: `438da40fee68dee6062f169e3ca9ed461bf31547f0c1f0a77279a3bc264e6e5d` and its exact extracted PIC/QNX, using only B9 behavior and version metadata. Independent differential execution against .1.1 verifies the intended additional change; no unfinished branch work incorporated.

## Exact control flow and placement

**Patch location:** PIC controller (MIPS); QNX changes are revision metadata only.

**Patch size:** Retained 250-tick version: 112 helper bytes + two 4-byte hooks = 120 emitted behavior bytes. Versus .0.9, 122 PIC bytes and three QNX metadata bytes differ (131 whole-package bytes). No payload growth or additional persistent RAM.

Positive hook **9D023550** remains `0B400361` (J 9D000D84), preserving **9D023554** `240201F4` (LI v0,500) in its delay slot. Helper replays displaced ADDU s0,s3,s0; jumps to 9D000D98 with t3=0 in the delay slot.

Immediate-path hook **9D0235E4** changes `0B408D55` (J 9D023554) to `0B400364` (J 9D000D90). Its **9D0235E8** delay slot `02708021` (ADDU s0,s3,s0) is preserved. Application has already returned at this point. Entry D90 sets t3=1; D94 restores the displaced initialization LI v0,500.

Shared classifier D98 loads the original caller RA from **SP+0x44**, proven by original SW RA at **9D0234D0**. It uses full 32-bit comparisons with the same six saved return addresses:

| Panel source | JAL wrapper | Saved return |
|---|---|---|
| Program encoder | 9D02A3C8 | 9D02A3D0 |
| Bank encoder | 9D02A800 | 9D02A808 |
| Decrement button | 9D02AAB4 | 9D02AABC |
| Increment button | 9D02BCC0 | 9D02BCC8 |
| UI program value encoder | 9D02DCE8 | 9D02DCF0 |
| UI bank value encoder | 9D02E0B8 | 9D02E0C0 |

All six baseline JAL/delay pairs and mode=2 setup are guarded by the builder. The live RA after the global getter is not used. Consecutive comparisons place the next ORI in the preceding BEQ's delay slot: the branch tests the old t2 value before that slot updates it; all six matching and nonmatching paths execute in the independent decoder.

Nonpanel fallback **DD4** jumps to **9D023558**, retaining the original 500 store. Panel **DDC** branches on t3=0 to **DEC**, with NOP delay. Positive panel **DEC** jumps to **9D02355C** with NOP delay, skipping only the countdown store. Immediate panel **DE4** jumps to **9D023558** with **LI v0,250** in the delay slot. Thus positive counters never restart, immediate panel loads reload 250, and nonpanel callers reload 500. Zero/expiry and global-gate bypass paths remain original.

Helper occupies **[9D000D84,9D000DF4)**: 28 instructions,112 bytes; two four-byte hooks give120 emitted behavior bytes. There are12 FF bytes left before E00. No PIC/application growth, new stack frame, RAM state, timer, expiry rearm or QNX behavior change. Scratch t0–t3 are dead in all16 caller continuations until overwrite/call/return. Panel immediate v0 differs (250 versus500); independent continuation analysis confirms v0 is unused until overwrite/call/return in all six panel continuations. Saved registers, original RA/SP/GP/FP and pending arguments retain the original contract.

Padding rechecked against exact B6 .9, baseline direct/literal/nearby address-construction scans and the existing PIC32MZ vector/OFF reservation evidence. B6 helper C00–D84, B3 trampoline/hook, inherited B7 adapters, vector/startup/DINIT regions and existing version-thunk bodies remain intact. Only their fifth-field metadata changes. The original 500-tick variant uses the same six source classifications and saved-return contract; its helper is described below.

## Validation

All checks PASS on actual emitted little-endian instruction words:
- 1920 wrapper matrix cases across16 direct callers, all routing modes, idle/zero/positive counters, gates and argument values; 1200 nonpanel equivalence cases.
- Six real panel handler preludes;50 actual gated counter-service cases;24 actual expiry/equality/routing cases;62 interrupt-to-zero cases in the primary suite.
- 576 differential cases against hardware-tested .1.1, and 102 reached-helper interrupt cases across all six panel callers. Pending bank/program/force/mode stores and linked application outcomes match.
- Input-first and expiry-first orderings, positive reversal back to applied selection (expiry suppressed), zero-time reversal, bank changes, both slots and mixed panel/MIDI/stored-SysEx routing. Existing possible paired applications remain; no rearm added.
- Sustained input every50 service ticks for2000 ticks: nine application calls input-first,17 expiry-first, final program41 in both layers. These are harness outcomes, not measured synth rates.
-480 inherited B6 actual-instruction regression cases. Callee-saved registers, stack canary and original saved RA checked with adversarial external volatile/home-area clobbers. All control transfers, delay slots and both exits independently decoded.

The external application/global getter/I/O calls are summarized contracts; these checks do not emulate audio, sample storage or whole physical IRQ execution. Service/expiry/getter instructions execute from payload bytes; IRQ register save/restore is a stated contract.

Package independently re-extracted and all three payloads matched emitted files. Every changed byte audited: 122 PIC bytes,3 QNX metadata bytes,131 package bytes relative to .9; 95 PIC bytes relative to .1.1. Payload sizes remain530784/1039304/1581716 bytes. Application checksum 0x8106, FPGA checksum0x7759; inherited PIC container trailer3030 retained under the established type3 contract. Actual transport arithmetic checked for130 blocks and260 valid/corrupt comparisons. Actual updater equality checks include .9, .1.1, .1.2 and other revisions; all five fields compared. FPGA entire record unchanged. M remains2.2.2 by the established convention; DSP and full PIC report2.2.2.1.2.

Reproduction/verification scripts and full reports: `b9_250_candidate_work/`. Published binary was re-read and independently verified again.

## Timing interpretation and hardware result

250 ticks nominally mean 125.0025 ms if PBCLK3 is100 MHz, PR3=50000, prescaler1 and the inherited ungated 16-bit timer assumptions hold. Actual clock/gating/interrupt/main-loop delays remain unmeasured. Final pending selection waits at most the remaining 250 eligible service ticks plus existing application/main-loop delay. Input coincident with expiry preserves the old zero/ordering behavior, including paired applications.

Sustained browsing may approximately double intermediate-load opportunity compared with 500 ticks, increasing storage/CPU work and audible interruptions. Equality suppression and linked routing remain original. MIDI program changes and stored-program SysEx retain 500 reset policy; documented edit-buffer SysEx still bypasses the browsing countdown. This version was subsequently test on hardware and found to be more responsive, with residual fast-browsing slowdown as described above.

Hardware reports are qualitative, rather than measured latency. The following consolidated regression sequence preserves the supplied test coverage:

1. Verify DSP `2.2.2.1.2`; M `2.2.2` is expected. Check isolated encoder steps and inc/dec presses, factory/user banks, linked layers and sample readiness.
2. Sustain encoder turns and button presses; compare `.1.1`, then confirm the final displayed target sounds and remains selected.
3. Cross banks, reverse rapidly and return to the sounding preset while another selection is pending. Check final bank/program and linked-layer consistency.
4. Exercise MIDI program changes, stored-program SysEx and edit-buffer librarian patches, then inherited B6 Center/loop edits, save/reload and held-note playback.

## Original 500-tick implementation - .1.1

The initial B9 helper occupies `[0x9D000D84,0x9D000DE8)`: 25 instructions/100 bytes plus the four-byte hook at `0x9D023550`. It replays `ADDU s0,s3,s0`, reads the saved caller RA from `SP+0x44`, and matches the same six panel returns above. Panel requests jump to `0x9D02355C`, skipping the countdown store; nonpanel requests resume at `0x9D023558`. The immediate-path jump at `0x9D0235E4` remains stock and reloads 500. No RAM, stack frame or payload growth is added.

Package SHA-256: `061248f2d8e4e11e9dec78d6b5c74b87d16a283c273e2eba35ae84c2e592a012`; PIC: `a5016c62412181659e397d37b763239b213f3ce305b195be85c0619edec2fd52`; QNX: `47122ddcc8fdd30aaefb51528f100148751003dfad8992614011cc088dcb8582`. The package is 3,151,848 bytes. Application checksum is `0x7F06`. Relative to `.0.9`, 108 PIC bytes, three QNX revision bytes and 116 total package bytes differ; every difference is accounted for in the original manifests.

Saved `.1.1` validation includes 1,920 wrapper cases, 1,200 nonpanel equivalence cases, six panel preludes, 50 counter-service cases, 24 expiry/routing cases, 58 interrupt-boundary cases and 480 inherited B6 instruction cases. These use decoded candidate instructions with external-call contracts, rather than full audio/IRQ emulation. The [original scripts and reports](b9_candidate_work/b9_patch_manifest.json) are retained for comparison.

## Source, evidence and packaging path

- Current source/assembly: [builder](b9_250_candidate_work/build_b9.py), [assembly input](b9_250_candidate_work/helper_assembly_input.json), [helper disassembly](b9_250_candidate_work/emitted_helper_disassembly.txt) and [patch manifest](b9_250_candidate_work/b9_patch_manifest.json).
- Instruction tests: [runner](b9_250_candidate_work/validate_instructions.py), [independent decoder/interpreter](b9_250_candidate_work/mips_check.py), [results](b9_250_candidate_work/b9_instruction_validation.json), [.1.1 differential runner](b9_250_candidate_work/validate_previous_candidate.py) and [differential results](b9_250_candidate_work/previous_candidate_validation.json).
- Placement: [verifier](b9_250_candidate_work/verify_placement.py) and [results](b9_250_candidate_work/b9_placement_validation.json).
- Packaging: [independent verifier](b9_250_candidate_work/verify_package.py), [publisher](b9_250_candidate_work/publish_b9.py), [results](b9_250_candidate_work/b9_packaged_validation.json) and [every-byte manifest](b9_250_candidate_work/b9_package_byte_manifest.json).
- Investigation: [countdown state model](b9_investigation/countdown_model.py), [model results](b9_investigation/countdown_model_results.json) and [baseline identity checks](b9_investigation/baseline_verification.json). Ghidra is not required by the supplied builder/validators. Optional Ghidra evidence collectors are retained privately rather than included in this handover bundle.
- Public inventory: [SHA256SUMS](SHA256SUMS).

Run from this folder, using Python 3 and a clean output location:

```sh
python3 b9_250_candidate_work/build_b9.py
python3 b9_250_candidate_work/validate_instructions.py
python3 b9_250_candidate_work/validate_previous_candidate.py
python3 b9_250_candidate_work/verify_placement.py
python3 b9_250_candidate_work/verify_package.py
python3 b9_250_candidate_work/publish_b9.py
python3 b9_250_candidate_work/verify_package.py PxUpdate_V2.2.2.1.2.bin
```

Private inputs expected by the unmodified scripts:

| Location | Purpose |
|---|---|
| `PxUpdate_V2.2.2.0.9.bin` | Exact B6 baseline package, SHA-256 `438da40fee68dee6062f169e3ca9ed461bf31547f0c1f0a77279a3bc264e6e5d` |
| `b6_candidate_work/pic_2.2.2.0.9.bin` | Exact extracted baseline PIC, SHA-256 `80723ffbd381e1e6cf401f09cff99591d43a07d91d00d57570fe2dea5265e2f3` |
| `b6_candidate_work/voice_2.2.2.0.9_qnx.elf` | Exact extracted baseline QNX, SHA-256 `1a562cb01a7703f4facf9a6d0b90a76f6b4da6fc5218e43ac9991a255aba0406` |
| `pic_2.2.2.0.7.bin` | Inherited B7 model input, pinned by `b7_combined_instruction_model.py` |
| `b7_candidate_work/pic_2.2.2.0.8.bin` | Placement comparison against inherited vector/startup configuration |
| `PxUpdate_V2.2.2.1.1.bin`, `b9_candidate_work/pic_2.2.2.1.1.bin` | Prior-version differential verification; recover privately or build using the retained `.1.1` tools |

The builder contains its own small MIPS assembler, emits the helper directly and packages the result; no external MIPS compiler is needed. It writes candidate PIC/QNX and `b9_250_candidate_work/package_pending_validation.bin`. The publisher requires instruction/placement/package PASS reports, then exclusively creates `PxUpdate_V2.2.2.1.2.bin`; it refuses to overwrite the published name. Run the final verifier to independently reread that file. The `.1.1` tools follow the equivalent sequence in `b9_candidate_work/`, without the previous-candidate differential step.

Container framing remains `F0`, three type 1/2/3 records, then `F7`. Each record has a 12-byte header with five revision bytes and a big-endian length, payload and two-byte trailer. The builder updates application/PIC revision metadata and application checksum, preserves the complete FPGA record, and retains the inherited PIC trailer `30 30`. No payload lengths change. M remains the three-field `2.2.2`; DSP/full PIC reports identify `.1.2`.

Firmware packages, extracted payloads, firmware disassembly and Ghidra project databases are excluded. Public helper disassembly describes only the new B9 code. These scripts document the incremental packaging path. The [direct firmware patcher](../../firmware_builder/patch_prophet_x.py) builds the final combined update directly from the exact factory input using authored generators and pinned redacted objects. See the [direct builder implementation](../../firmware_builder/direct/IMPLEMENTATION.md). The separate [compiler audit path](../../firmware_builder/source_rebuild/README.md) retains incremental source rebuilding and its original validation scope.

For this cleanup, source copies, Python/JSON syntax, documentation links, inventory checksums and saved private package identities were checked. Feature matrices, firmware builds and hardware tests were not rerun.

## Complete supporting-file inventory

Every retained supporting file is listed below. The `.1.1` directory preserves the tested 500-tick comparison and its verification path; `.1.2` contains the retained 250-tick implementation. Investigation JSON files preserve the baseline, path and placement evidence used to establish the patch. `SHA256SUMS` covers the handover and all supporting files.

| File | Purpose |
|---|---|
| [b7_candidate_work/validate_version_gates.py](b7_candidate_work/validate_version_gates.py) | Supplies gate-decoder function extracted by package verifiers. |
| [b7_combined_instruction_model.py](b7_combined_instruction_model.py) | Inherited instruction model imported by B9 regression tests. |
| [b9_250_candidate_work/b9_instruction_validation.json](b9_250_candidate_work/b9_instruction_validation.json) | Saved instruction-validation evidence. |
| [b9_250_candidate_work/b9_package_byte_manifest.json](b9_250_candidate_work/b9_package_byte_manifest.json) | Accounts for changed container bytes. |
| [b9_250_candidate_work/b9_packaged_validation.json](b9_250_candidate_work/b9_packaged_validation.json) | Saved packaging-validation evidence. |
| [b9_250_candidate_work/b9_patch_manifest.json](b9_250_candidate_work/b9_patch_manifest.json) | Exact patch locations and identities. |
| [b9_250_candidate_work/b9_placement_validation.json](b9_250_candidate_work/b9_placement_validation.json) | Saved placement-validation evidence. |
| [b9_250_candidate_work/build_b9.py](b9_250_candidate_work/build_b9.py) | Builds helper, revision edits and incremental package. |
| [b9_250_candidate_work/emitted_helper_disassembly.txt](b9_250_candidate_work/emitted_helper_disassembly.txt) | Decoded new B9 helper instructions. |
| [b9_250_candidate_work/helper_assembly_input.json](b9_250_candidate_work/helper_assembly_input.json) | Exact generated helper assembly. |
| [b9_250_candidate_work/mips_check.py](b9_250_candidate_work/mips_check.py) | Decoder/interpreter used by validation scripts. |
| [b9_250_candidate_work/previous_candidate_validation.json](b9_250_candidate_work/previous_candidate_validation.json) | Saved .1.1-to-.1.2 differential evidence. |
| [b9_250_candidate_work/publish_b9.py](b9_250_candidate_work/publish_b9.py) | Creates updater-facing output after validation passes. |
| [b9_250_candidate_work/validate_instructions.py](b9_250_candidate_work/validate_instructions.py) | Executes candidate instruction regression cases. |
| [b9_250_candidate_work/validate_previous_candidate.py](b9_250_candidate_work/validate_previous_candidate.py) | Checks .1.2 against the hardware-tested .1.1 implementation. |
| [b9_250_candidate_work/verify_package.py](b9_250_candidate_work/verify_package.py) | Independently verifies package, revisions and byte accounting. |
| [b9_250_candidate_work/verify_placement.py](b9_250_candidate_work/verify_placement.py) | Checks helper placement and protected code. |
| [b9_candidate_work/b9_instruction_validation.json](b9_candidate_work/b9_instruction_validation.json) | Saved instruction-validation evidence. |
| [b9_candidate_work/b9_package_byte_manifest.json](b9_candidate_work/b9_package_byte_manifest.json) | Accounts for changed container bytes. |
| [b9_candidate_work/b9_packaged_validation.json](b9_candidate_work/b9_packaged_validation.json) | Saved packaging-validation evidence. |
| [b9_candidate_work/b9_patch_manifest.json](b9_candidate_work/b9_patch_manifest.json) | Exact patch locations and identities. |
| [b9_candidate_work/b9_placement_validation.json](b9_candidate_work/b9_placement_validation.json) | Saved placement-validation evidence. |
| [b9_candidate_work/build_b9.py](b9_candidate_work/build_b9.py) | Builds helper, revision edits and incremental package. |
| [b9_candidate_work/emitted_helper_disassembly.txt](b9_candidate_work/emitted_helper_disassembly.txt) | Decoded new B9 helper instructions. |
| [b9_candidate_work/helper_assembly_input.json](b9_candidate_work/helper_assembly_input.json) | Exact generated helper assembly. |
| [b9_candidate_work/mips_check.py](b9_candidate_work/mips_check.py) | Decoder/interpreter used by validation scripts. |
| [b9_candidate_work/publish_b9.py](b9_candidate_work/publish_b9.py) | Creates updater-facing output after validation passes. |
| [b9_candidate_work/validate_instructions.py](b9_candidate_work/validate_instructions.py) | Executes candidate instruction regression cases. |
| [b9_candidate_work/verify_package.py](b9_candidate_work/verify_package.py) | Independently verifies package, revisions and byte accounting. |
| [b9_candidate_work/verify_placement.py](b9_candidate_work/verify_placement.py) | Checks helper placement and protected code. |
| [b9_investigation/baseline_verification.json](b9_investigation/baseline_verification.json) | Baseline package/payload identity evidence. |
| [b9_investigation/countdown_model.py](b9_investigation/countdown_model.py) | Behavioral countdown model. |
| [b9_investigation/countdown_model_results.json](b9_investigation/countdown_model_results.json) | Saved behavioral-model results. |
| [b9_investigation/countdown_placement_review.json](b9_investigation/countdown_placement_review.json) | Original helper placement evidence. |
| [b9_investigation/pass2_protected_hashes.json](b9_investigation/pass2_protected_hashes.json) | Protected function-span identities from countdown review. |
| [b9_investigation/path_byte_verification.json](b9_investigation/path_byte_verification.json) | Checks investigated paths against exact baseline bytes. |
