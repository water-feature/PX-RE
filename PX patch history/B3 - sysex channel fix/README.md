# B3 - SysEx channel filtering fix

Standalone technical handover for B3. The PIC-side fix is implemented and hardware-confirmed in the original B1+B3 build and the later combined integration. These are historical feature builds, not the latest combined project firmware.

**Firmware:** `voice_sysex_2.2.2.0.3.bin`; later integration `PxUpdate_V2.2.2.0.7.bin`.

**Hardware: PASS**: Both builds were confirmed on hardware. The .0.7 test confirmed that a channel-10 SysEx dump request rejected by stock worked after installation and power cycling; exhaustive MIDI regression testing has not yet been completed.

## Problem and resulting behavior

**Patch location:** PIC controller (MIPS).

**Patch size:** 32-byte trampoline + one 4-byte hook = 36 functional write-span bytes. PIC payload length is unchanged. Revision/checksum edits are separate packaging metadata.

Queued SysEx messages were incorrectly passed through the ordinary MIDI channel matcher. Their internal field 4 normally contains 1, which the matcher interpreted as MIDI channel 2. SysEx requests could consequently be rejected depending on the configured channel and Multi Mode settings.

The patch recognizes SysEx status `F0` and supplies the primary acceptance result directly. Ordinary MIDI continues through the original matcher. Downstream SysEx framing checks, including field 4 equal to 1, remain in place.

## Implementation and placement

All PIC addresses below are runtime virtual addresses with payload base `0x9D000000`. Instruction words are shown numerically; their stored byte order is little-endian. Address ranges exclude the end.

| Location | Final implementation |
|---|---|
| `0x9D0295B0` | Replace `jal 0x9D05EE4C` with `j 0x9D001200`, word `0x0B400480` |
| `0x9D0295B4` | Preserve the existing delay-slot instruction `lbu a0,4(a1)` |
| `[0x9D001200, 0x9D001220)` | Eight-word matcher trampoline |
| `0x9D0295B8` | Resume stock execution |

Trampoline words, in order:

```text
90A30005 386300F0 10600003 00001021
0F417B93 90A40004 0B40A56E 00000000
```

The trampoline reads event status from byte 5. For `F0`, it leaves `v0=0` and returns to the stock continuation. Other statuses call the original matcher, which retains its primary/additional-channel/rejection results of 0/1/2. The preserved hook delay slot and trampoline delay slots are part of the implementation.

The functional patch occupies 32 helper bytes and one four-byte hook, without growing the payload. Placement is after startup's unconditional transfer and before DINIT descriptors beginning at `0x9D001480`. Recorded vector, DINIT and reference checks support this placement within the supplied image; they do not exclude every possible computed reference.

The [combined builder](build/build_combined_voice_fade_sysex.py) embeds the trampoline words directly; there is no separate assembly source. Preserve the helper, hook and delay slot when integrating later features.

## Firmware identities and packaging

| Artifact | Size | SHA-256 |
|---|---:|---|
| Stock `PxUpdate_V2.2.2.0.0.bin` | 3,099,064 | `a4b304b3bb48ca933ae63c99c0098698c497ebfc7c38ab2a823b5e0df4919fa9` |
| Early combined `voice_sysex_2.2.2.0.3.bin` | 3,099,064 | `bbc3c2ad26bef7310fc15cac8edee22a1792d8ced3788f7080acccc047304857` |
| Hardware-tested `PxUpdate_V2.2.2.0.7.bin` | 3,151,848 | `2fe41c83415c1d85efd7848a31511157162528ec4a83d08045be7e8bcee2e753` |

The early `.3` package has application revision 2.2.2.0.3, application checksum `0xF64B`, and PIC header/report revision 2.2.2.1.0. Its PIC payload SHA-256 is `2f746346fa1e592795fd243a9866a8019e69c2d97ab3d674204bb7f5022ef0cc`. Report immediates at `0x9D0258B4` and `0x9D051BC4` change from word `24842220` to `24842221`.

The `.7` integration preserves B3's functional patch. Its application header, compiled comparison and DSP display use 2.2.2.0.7. The PIC header/intended reports use 2.2.3.0.0, with PIC payload SHA-256 `94e75694df255b6e93dc1786b91dad31cc631e87224362dc2fcbf4f2e8c94bb0`. Relative to the early PIC payload, only three version/display bytes change: words at `0x9D0258B4` and `0x9D051BC4` become `24842230`, and the M third-component literal at `0x9D052FEC` becomes `24020003`. Hardware continued to show M 2.2.2; the owner accepted this cosmetic discrepancy. Use the package hash and functional test to identify the tested integration.

| Payload | Stock/early `.3` container offset | `.7` container offset |
|---|---|---|
| QNX application | `0xD`, length 986,520 | `0xD`, length 1,039,304 |
| PIC | `0x273055`, length 530,784 | `0x27FE85`, length 530,784 |

For PIC inspection, subtract `0x9D000000` from a virtual address and add the appropriate container payload offset. Import the extracted PIC as 32-bit little-endian MIPS and account for delay slots.

The early bundled build scripts reproduce B1+B3. Their input hashes and working-directory assumptions are documented in the build and validation inputs section below. The PIC trailer `30 30` is preserved: the inspected QNX type-3 parser consumes it without validating a container word sum. Transfer blocks have separately calculated little-endian 16-bit word checksums. Do not substitute the application checksum algorithm for this preserved trailer.

## Validation evidence

These are recorded offline results; no feature matrices were rerun during documentation cleanup.

| Check | Recorded result | Scope |
|---|---|---|
| Channel gate | PASS: 8,704 executions across 4,352 inputs | Ordinary MIDI unchanged; only F0 bypasses filtering |
| Command-6 reply | PASS: identical 4,688-byte replies in all 34 candidate channel/Multi combinations | Transport mocked; zero parameter fixture; one DSP load supplied |
| Layer differential audit | PASS: 512 pairs; identical call arguments, non-stack writes and returns | Direct callees mocked; 1,024 interpreter executions, 1,020 Unicorn crosschecks; four cases lack a completed Unicorn crosscheck |
| PIC staging | PASS: 130 blocks, 129 × 4,096 plus 2,400 bytes | Queue, serial flash, timing and UI modeled |
| Hardware | PASS, owner-reported for `.3` and `.7` | `.3` successful testing confirmed by owner; additional stock rollback reproduced failure, and `.7` install and power cycle restored the channel-10 request |

See [gate and placement results](evidence/gap_gate_result.json), [reply results](evidence/sysex_reply_result.json), [layer results](evidence/sysex_layers.json), [PIC staging results](evidence/pic_staging.json), and [revision verification](manifests/revision_0_3_verification.json). Historical `hardware_tested: false` fields describe those offline runs, not the later hardware result.

Layer auditing supports use of matcher result 0: the SysEx dispatcher at `0x9D02D710` does not consume incoming layer registers s2/s3 before restoring them. Incoming commands 2/3 enter receive state `0x9D026D54` without persisting that result; other audited commands use explicit event/global/object data.

## Installation evidence and limits

The QNX type-3 parser is at ELF address `0x24A0C`; sender workers are at `0x26738` and `0x26626`. The actual PIC firmware receiver is `0x9D0442A4`, called from updater state 3 at `0x9D025CBC`. It stages to external serial flash through erase/program helpers `0x9D0421AC` and `0x9D042340`, then reaches reset at `0x9D081790`.

Recorded emulation staged the payload exactly into modeled external range `[0x200000, 0x282000)`, including 1,696 padding bytes: 130 sector erases and 2,080 page writes. Five corrupt-block checksums retried successfully; a pre-data abort performed no writes or reset.

Firmware inputs and outputs are not distributed in this folder. Source scripts and recorded reports support investigation without bundling the full firmware.

## Build and validation inputs

These tools retain their original hash checks. Do not substitute the hardware-tested `.7` integration for a pinned early input.

| Tool | Required input / behavior |
|---|---|
| [Combined builder](build/build_combined_voice_fade_sysex.py) | Two positional paths: baseline and output. Requires historical voice baseline SHA-256 `f6b5205fc40e635305445bb19dd1a41d12f2ee4c64b7284ccd432868ef0c5898`; this differs from the later voice-only `.2` package. |
| [Revision builder](build/build_voice_sysex_revision.py) | Reads `baseline.bin` beside the script, SHA-256 `d2775bd0e017e4442ce7d5bbc7d089022a1cf8c02714d89427462938e934d166`; writes `.3` BIN and `manifest.json` beside it. |
| [Revision verifier](build/validate_voice_sysex_revision.py) | Reads that same adjacent baseline and generated `.3` package. |
| [Combined verifier](build/verify_combined_voice_fade_sysex.py) | Two positional firmware paths; run from this folder so it finds the recovered [transfer evidence](next_evidence/pic_transfer_result.json). The independent byte verifier passed against the exact-hash reconstructed early packages; see [result](next_evidence/independent_verification_recovered.json). |
| [Gap/gate](validation/validate_pic_gap_and_gate.py), [reply](validation/validate_sysex_reply.py), [QNX parser](validation/validate_pic_container_parser.py) | Positional input and output paths; inspect each script's pinned input before running. |
| [Layer audit](validation/audit_sysex_layers.py), [PIC staging](validation/validate_pic_staging_path.py) | Expect `version_sysex_work/voice_sysex_2.2.2.0.3.bin` relative to the working directory; write under `resolved_research/`. |

Build scripts require Python 3; instruction emulation additionally uses Capstone 5.0.9 and Unicorn 2.1.4. These are the recorded versions, not dependencies reinstalled or retested during documentation cleanup.

For reproduction, copy the required tools into a private working directory and supply privately held firmware inputs there. Some historical tools overwrite their named generated outputs; use a fresh private directory. Keep generated firmware outside the public repository.

The early builders cover B1+B3. The recovered exact `.7` integration builder and its successful byte-identical offline rebuild are documented in the final section below. Recorded results are retained as evidence; feature matrices were not rerun during cleanup. Offline `hardware_tested: false` fields retain their original meaning; owner-reported hardware PASS for both `.3` and `.7` is documented in the handover.

## Complete supporting-file inventory

Every retained supporting file is linked below. Implementation, imported dependencies, test fixtures and saved evidence are distinguished by purpose; not every evidence file is required to build the feature. Original script layouts are retained so their relative imports remain intact. Firmware and generated binary inputs remain private, as described above. The [root checksum inventory](SHA256SUMS) covers this handover and all retained supporting files.

| File | Purpose |
|---|---|
| [build/build_combined_voice_fade_sysex.py](build/build_combined_voice_fade_sysex.py) | Build/emission/layout tool or imported build dependency. |
| [build/build_voice_sysex_revision.py](build/build_voice_sysex_revision.py) | Build/emission/layout tool or imported build dependency. |
| [build/validate_voice_sysex_revision.py](build/validate_voice_sysex_revision.py) | Validation/test or ownership audit tool; uses the private inputs described in source. |
| [build/verify_combined_voice_fade_sysex.py](build/verify_combined_voice_fade_sysex.py) | Validation/test or ownership audit tool; uses the private inputs described in source. |
| [evidence/dinit_records.json](evidence/dinit_records.json) | Saved validation, measurement or ownership evidence; not a new test run. |
| [evidence/gap_gate_result.json](evidence/gap_gate_result.json) | Saved validation, measurement or ownership evidence; not a new test run. |
| [evidence/pic_parser_result.json](evidence/pic_parser_result.json) | Saved validation, measurement or ownership evidence; not a new test run. |
| [evidence/pic_staging.json](evidence/pic_staging.json) | Saved validation, measurement or ownership evidence; not a new test run. |
| [evidence/sysex_layer_cases.json](evidence/sysex_layer_cases.json) | Saved validation, measurement or ownership evidence; not a new test run. |
| [evidence/sysex_layers.json](evidence/sysex_layers.json) | Saved validation, measurement or ownership evidence; not a new test run. |
| [evidence/sysex_reply_cases.json](evidence/sysex_reply_cases.json) | Saved validation, measurement or ownership evidence; not a new test run. |
| [evidence/sysex_reply_result.json](evidence/sysex_reply_result.json) | Saved validation, measurement or ownership evidence; not a new test run. |
| [evidence/vector_offsets.json](evidence/vector_offsets.json) | Saved validation, measurement or ownership evidence; not a new test run. |
| [manifests/original_combined_manifest.json](manifests/original_combined_manifest.json) | Saved patch/object/packaging identity and layout evidence. |
| [manifests/original_independent_verification.json](manifests/original_independent_verification.json) | Saved validation, measurement or ownership evidence; not a new test run. |
| [manifests/revision_0_3_manifest.json](manifests/revision_0_3_manifest.json) | Saved patch/object/packaging identity and layout evidence. |
| [manifests/revision_0_3_verification.json](manifests/revision_0_3_verification.json) | Saved validation, measurement or ownership evidence; not a new test run. |
| [validation/audit_sysex_layers.py](validation/audit_sysex_layers.py) | Validation/test or ownership audit tool; uses the private inputs described in source. |
| [validation/pic_research_disasm.py](validation/pic_research_disasm.py) | Imported analysis/decoder support. |
| [validation/validate_pic_container_parser.py](validation/validate_pic_container_parser.py) | Validation/test or ownership audit tool; uses the private inputs described in source. |
| [validation/validate_pic_gap_and_gate.py](validation/validate_pic_gap_and_gate.py) | Validation/test or ownership audit tool; uses the private inputs described in source. |
| [validation/validate_pic_staging_path.py](validation/validate_pic_staging_path.py) | Validation/test or ownership audit tool; uses the private inputs described in source. |
| [validation/validate_sysex_reply.py](validation/validate_sysex_reply.py) | Validation/test or ownership audit tool; uses the private inputs described in source. |

## Recovered exact `.0.7` integration packager

Recovered from the owner’s saved files during the version-history audit. [build_combined.py](build/combined_0_7/build_combined.py) accepts the exact B8 `.0.6` package and early B1+B3 `.0.3` package as positional inputs, and refuses an existing output. Their SHA-256 hashes are pinned in the script and listed above. Firmware remains private.

```sh
python3 build/combined_0_7/build_combined.py /private/path/PxUpdate_V2.2.2.0.6.bin /private/path/voice_sysex_2.2.2.0.3.bin /private/output/PxUpdate_V2.2.2.0.7.bin
```

This copies the `.0.3` PIC record into the `.0.6` container, changes only the two application revision bytes, applies the three PIC revision/display-byte changes described above, and recalculates the application checksum. The recovered [original package manifest](build/combined_0_7/PxUpdate_V2.2.2.0.7.json) matches the privately held hardware-tested `.0.7` package hash. Its predicted M display and `combined_hardware_tested: false` are historical build-time records; the owner’s later actual M display and hardware acceptance earlier in this handover take precedence.

[validate_versions.py](build/combined_0_7/validate_versions.py) executes bounded application/PIC reporting, formatting and updater checks using Unicorn. It reads a private `PxUpdate_V2.2.2.0.7.bin` beside the script. Run in a private copy of this directory with Python 3 and Unicorn 2.1.4. The recovered script was syntax-checked during this audit; the hardware tests were not repeated and the exact builder was rerun using a reconstructed `.0.3` input whose whole-package hash matches its historical identity. Its output is byte-identical to the retained `.0.7` package. See [recovery verification](build/combined_0_7/recovery_verification.json). The earlier voice-fade and combined `.0.1` packages were also reconstructed with exact historical SHA-256 matches; these are recovered byte identities, not new hardware tests.

## Recovered early transfer evidence

[The original transfer report](next_evidence/pic_transfer_result.json) was recovered from the owner’s `voice_sysex_2.2.2.0.3/previous_build/voice_fade_and_sysex/evidence/` export. Its candidate PIC SHA-256 is `2f746346fa1e592795fd243a9866a8019e69c2d97ab3d674204bb7f5022ef0cc`, matching the early B3 PIC, rather than the unrelated `.0.4` dummy. It records 130 QNX transfer blocks and valid/corrupt PIC comparisons for changed/final blocks. Transport/sleep and receive queuing/flash programming remain outside its modeled scope.

With this dependency restored, the original independent verifier was rerun against the hash-matched reconstructed voice-fade and combined `.0.1` packages. [PASS](next_evidence/independent_verification_recovered.json): exact expected bytes, 39 changes, QNX/FPGA identity, correct transfer-tested PIC and preserved sizes/trailers. This was a bounded offline byte-verification check, not a repeat of the original emulation suite or hardware tests.
