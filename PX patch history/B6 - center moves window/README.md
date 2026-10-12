# B6 - Center moves the sample window

Standalone technical handover for the original B6 implementation. B6 is implemented and hardware-confirmed. Its .0.9 package builds incrementally on .0.8 and includes inherited features; it is not the latest combined project firmware.

**Firmware:** `PxUpdate_V2.2.2.0.9.bin`, built from `2.2.2.0.8`.

**Hardware: PASS:** Center-moves-window behavior was confirmed on .0.9. Individual hardware-case coverage and measured target CPU headroom were not itemized.

## Resulting behavior

When looping is enabled, a direct Center edit outside the selected Start/End window moves both endpoints equally until the requested Center is on the nearest window edge. Requests inside the window, or equal to an edge, leave the endpoints unchanged. Each selected layer is handled independently; unselected layers and the other oscillator are unchanged. Loop-off behavior remains stock.

Example in raw 0–999 coordinates: Start=200, End=600, Center=450. Request Center=650 and the window becomes 250–650. Then request Center=150 and it becomes 150–550. Moving back inside the translated window does not restore its earlier position. Requests are bounded to 999; translation preserves the raw End−Start gap and endpoint ordering at the rails.

B7 continues to push Center when an endpoint crosses it and protects endpoint ordering. B6 handles the complementary operation: direct Center movement. Custom-loop activation and existing engine/MIDI gates are preserved.

**The preserved width is a raw parameter gap, not a frame count or elapsed duration.** Sample-position mapping is exponential, so equal raw shifts can change actual loop duration and pitch. B6 adds no duration compensation and no QNX playback-geometry change. Later duration-related work is outside this implementation. In testing it was concluded that duration compensation is unnecessary for this feature as shortening size to be lower than the start/end window already provides duration compensation.

## Implementation and locations

**Patch location:** PIC controller (MIPS); QNX changes are revision metadata only.

**Patch size:** 388-byte translation helper + one 4-byte functional hook = 392 functional write-span bytes. The complete manifest covers 109 PIC words / 436 write-span bytes and 410 actual changed PIC bytes including revision/report metadata. Payload lengths are unchanged.

PIC addresses are runtime virtual addresses at base `0x9D000000`. Instruction words are stored little-endian. Ranges exclude the end. QNX version offsets below are ELF file offsets.

| Location | Implementation |
|---|---|
| `0x9D001224` | Hook word `0x0B400300`: jump to helper at `0x9D000C00` |
| `0x9D001228` | Preserve inherited `move s2,a1` delay slot |
| `[0x9D000C00, 0x9D000D84)` | 97-instruction, 388-byte Center-translation helper |
| `0x9D000D7C` | Return word `0x0B4136BF`, targeting `0x9D04DAFC` |
| `0x9D000D80` | Return delay slot `0x24020050` |

The [helper source and assembler layout](b6_investigation/assemble_layout.py) contain the emitted instruction tuples. The helper uses a 48-byte private frame and preserves arguments, saved registers and B7's captured-request slot.

Endpoints are stored expansion-first to maintain Start<=End throughout the update. Notifications precede the original Center setter continuation. Direct endpoint setters are bypassed to avoid recursive B7 pushes. A brief endpoints-first, old-Center mismatch is accepted while the operation completes.

The shared parameter setter is at `0x9D04DACC`. Start/Center/Size/End IDs are 7/15/11/9 for oscillator 1 and `0x48/0x50/0x4C/0x4A` for oscillator 2. Parameter RAM begins at `0x8000046C`, with layer-B byte stride `0xD6E`.

Placement reuses the resolved PIC32MZ2048EFG100 vector analysis: under the verified `.8` application configuration, implemented interrupt targets lie at `0x9D000200–0x9D000258`, outside `[0x9D000C00, 0x9D000E00)`. This establishes application interrupt/exception exclusion for the configuration, not vendor ownership or independence from every possible bootloader dependency. Placement is not justified merely by FF-filled bytes.

See the [patch manifest](b6_candidate_work/b6_patch_manifest.json) for all original/replacement words and reasons. It accounts for 109 PIC words and 410 differing PIC bytes, including B6 and revision metadata. Remaining PIC bytes match `.8`; inherited B3 and B7 helper regions, DINIT and other existing fixes are preserved.

## Firmware identity and packaging

| Artifact | Bytes | SHA-256 |
|---|---:|---|
| Baseline `PxUpdate_V2.2.2.0.8.bin` | 3,151,848 | `c7e2e03999ca4590c99c3ba18a518f93f073ee8a619c84371677c7f6cd2c8e7f` |
| B6 `PxUpdate_V2.2.2.0.9.bin` | 3,151,848 | `438da40fee68dee6062f169e3ca9ed461bf31547f0c1f0a77279a3bc264e6e5d` |
| B6 PIC payload | 530,784 | `80723ffbd381e1e6cf401f09cff99591d43a07d91d00d57570fe2dea5265e2f3` |
| B6 QNX payload | 1,039,304 | `1a562cb01a7703f4facf9a6d0b90a76f6b4da6fc5218e43ac9991a255aba0406` |

Application and PIC header/report revisions are 2.2.2.0.9. QNX changes only revision bytes `0x1F4E3` and `0x250EF`, from 8 to 9. Application checksum is `0x7F05`, stored `05 7F`. The complete FPGA record remains identical to `.8`, with checksum `0x7759`. The inherited PIC trailer `30 30` is preserved rather than recomputed as an application word sum.

PIC report words at `0x9D0258B4` and `0x9D051BC4` encode the first four fields as `2220`. Fifth-field report thunks occupy 12 bytes each at `0x9D001394` and `0x9D0013A0`; they add 9 to the existing `402A0000` message argument and tail-jump to the original senders. Call sites `0x9D0258C0` and `0x9D051BC8` preserve their LUI delay slots and return links. The three-component M formatter at `0x9D052FEC` encodes 2.2.2; DSP displays the full `.9` revision.

The [builder](b6_candidate_work/build_b6.py) applies guarded PIC words, QNX revision edits and application/PIC header revisions to the exact `.8` package. Payload lengths and container layout remain unchanged. The application trailer is the sum of unsigned little-endian 16-bit payload words modulo 65,536, excluding its header/trailer. The [package byte manifest](b6_candidate_work/b6_package_byte_manifest.json) records final accounting; the [independent verifier](b6_candidate_work/verify_package.py) checks delivered bytes, version gates and transport checksums.

## Supporting files and private reproduction

Source, manifests and recorded results are included; firmware and compiled/disassembly artifacts are omitted. Preserve this directory structure in a private working copy. Historical scripts expect:

- `PxUpdate_V2.2.2.0.8.bin` at the working root, matching the baseline hash above.
- Its extracted PIC payload at `b7_candidate_work/pic_2.2.2.0.8.bin`, SHA-256 `3554fc3dc413c05fd329df1d04efd1ea49e27469121b38d140b7ebdf3be2e254`.
- The earlier `.7` PIC payload at root as `pic_2.2.2.0.7.bin`, SHA-256 `94e75694df255b6e93dc1786b91dad31cc631e87224362dc2fcbf4f2e8c94bb0`, loaded by the inherited model before `.8` is bound for comparison.

The supplied [B7 model](b7_combined_instruction_model.py), [assembler definitions](b7_candidate_work/build_validate_b7.py) and [version-gate definitions](b7_candidate_work/validate_version_gates.py) are dependencies of B6's original scripts. They are supporting code, not instructions to rerun those B7 entry points.

The historical workflow uses Python 3 and starts in a fresh private workspace with no final `.9` output:

```sh
python3 b6_candidate_work/build_b6.py
python3 b6_candidate_work/validate_candidate.py
python3 b6_candidate_work/verify_package.py
python3 b6_candidate_work/publish_b6.py
```

The builder writes private candidate payloads and `package_pending_validation.bin`. Validation writes reports/listings. Publication checks saved results, creates the final `.9` file without overwriting an existing final output, and independently verifies it. Some intermediate outputs use fixed names. Keep all generated firmware outside the public repository.

These are the original incremental build tools. The [root patcher](../../patch_prophet_x.py) builds the final combined update directly from the exact factory input using authored generators and pinned redacted objects. See the [direct builder guide](../../firmware_builder/direct/README.md). The separate [compiler audit path](../../firmware_builder/source_rebuild/README.md) retains incremental source rebuilding and its original validation scope.

## Validation and hardware evidence

| Evidence | Result and scope |
|---|---|
| [B6 validation](b6_candidate_work/b6_validation_results.json) | PASS: 193,536 arithmetic/gate/layer/custom cases and 2,400 targeted entry/ABI/B7 cases, executing saved candidate instructions |
| [Inherited B7 suites](b6_candidate_work/b6_inherited_B7_results.json) | PASS: endpoint/retreat, side-effect and redispatch checks; includes 52,224 endpoint/retreat cases |
| [Final-package verification](b6_candidate_work/b6_packaged_validation_results.json) | PASS: framing, lengths, checksums, candidate equality, all five revision fields, updater gates, 130 receiver-checksum blocks and 260 valid/corrupt comparisons |
| Hardware | PASS for `.9`, owner-confirmed; detailed case-by-case coverage not recorded here |

Host checks summarize external engine/MIDI/UI/descriptor calls. They do not establish physical stack headroom, transport timing or persistence through save/reload. Hardware success does not turn those modeled checks into exhaustive physical coverage. Raw-coordinate duration/pitch drift and the brief update-order mismatch are accepted implementation properties.

## Complete supporting-file inventory

Every retained supporting file is linked below. Implementation, imported dependencies, test fixtures and saved evidence are distinguished by purpose; not every evidence file is required to build the feature. Original script layouts are retained so their relative imports remain intact. Firmware and generated binary inputs remain private, as described above. The [root checksum inventory](SHA256SUMS) covers this handover and all retained supporting files.

| File | Purpose |
|---|---|
| [b6_candidate_work/b6_build_checkpoint.json](b6_candidate_work/b6_build_checkpoint.json) | Saved validation, measurement or ownership evidence; not a new test run. |
| [b6_candidate_work/b6_inherited_B7_results.json](b6_candidate_work/b6_inherited_B7_results.json) | Saved validation, measurement or ownership evidence; not a new test run. |
| [b6_candidate_work/b6_package_byte_manifest.json](b6_candidate_work/b6_package_byte_manifest.json) | Saved patch/object/packaging identity and layout evidence. |
| [b6_candidate_work/b6_packaged_validation_results.json](b6_candidate_work/b6_packaged_validation_results.json) | Saved validation, measurement or ownership evidence; not a new test run. |
| [b6_candidate_work/b6_patch_manifest.json](b6_candidate_work/b6_patch_manifest.json) | Saved patch/object/packaging identity and layout evidence. |
| [b6_candidate_work/b6_validation_results.json](b6_candidate_work/b6_validation_results.json) | Saved validation, measurement or ownership evidence; not a new test run. |
| [b6_candidate_work/build_b6.py](b6_candidate_work/build_b6.py) | Build/emission/layout tool or imported build dependency. |
| [b6_candidate_work/publish_b6.py](b6_candidate_work/publish_b6.py) | Incremental packaging/publication tool. |
| [b6_candidate_work/validate_candidate.py](b6_candidate_work/validate_candidate.py) | Validation/test or ownership audit tool; uses the private inputs described in source. |
| [b6_candidate_work/verify_package.py](b6_candidate_work/verify_package.py) | Validation/test or ownership audit tool; uses the private inputs described in source. |
| [b6_investigation/assemble_layout.py](b6_investigation/assemble_layout.py) | Build/emission/layout tool or imported build dependency. |
| [b7_candidate_work/build_validate_b7.py](b7_candidate_work/build_validate_b7.py) | Build/emission/layout tool or imported build dependency. |
| [b7_candidate_work/validate_version_gates.py](b7_candidate_work/validate_version_gates.py) | Validation/test or ownership audit tool; uses the private inputs described in source. |
| [b7_combined_instruction_model.py](b7_combined_instruction_model.py) | Inherited PIC instruction model used by regression validation; requires its pinned private input. |
