# Firmware build and version history

The implemented chain can be traced from factory **2.2.2.0.0** to final **2.2.2.2.2**. Investigation IDs such as B1 and B16 identify investigations and their technical evidence, not release order or a continuous sequence. The tables distinguish actual ancestors from comparison builds, rejected experiments and reserved numbers.

This is a build/provenance order, not a timestamped record of every development action. In particular, the early B1/B3 artifacts were renumbered. The parent column describes the actual input or merge, rather than assuming every numerical predecessor was used.

## Path to the final build

All version numbers below have the full `2.2.2` prefix. Each feature link leads to its implementation, hardware status and packaging notes. Most builds inherit all preceding features on their stated parent line; `.0.3` is the parallel B3 line merged at `.0.7`.

| Order | Actual parent/input | Output version | Feature | Change / disposition |
|---|---|---|---|---|
| 1 | — | 2.2.2.0.0 | Factory | Factory firmware; root of the implemented chain. |
| 2 | 2.2.2.0.0 | 2.2.2.0.2 | [B1](B1%20-%20voice%20steal%20fix/README.md) | Voice steal/retrigger correction; retained B1 reference. Earlier .0.1 naming is explained below. |
| 3 | Earlier B1+B3 .0.1 artifact | 2.2.2.0.3 | [B3](B3%20-%20sysex%20channel%20fix/README.md) | B1 + SysEx channel fix. Parallel PIC-side feature line, merged into .0.7; not the input to B5 .0.5. |
| 4 | 2.2.2.0.2 | 2.2.2.0.5 | [B5](B5%20-%20sample%20end%20fade/README.md) | Original sample endpoint fade. Contains B1+B5; no B3. Later pitch-modulation bug corrected in .1.11. |
| 5 | 2.2.2.0.5 | 2.2.2.0.6 | [B8](B8%20-%20end%20escape/README.md) | End-escape correction; inherits B1+B5. |
| 6 | .0.6 application + earlier B3 PIC fix | 2.2.2.0.7 | B1 + [B3](B3%20-%20sysex%20channel%20fix/README.md) + B5 + B8 | Combined integration. Application differs from .0.6 only at its two revision bytes. The packager combines exact hash-pinned inputs and reproduces this package byte-for-byte. |
| 7 | 2.2.2.0.7 | 2.2.2.0.8 | [B7](B7%20-%20center%20can%20be%20pushed/README.md) | Start/End protection when editing both layers, plus original endpoint/Center edit protections. |
| 8 | 2.2.2.0.8 | 2.2.2.0.9 | [B6](B6%20-%20center%20moves%20window/README.md) | Center moves the window. |
| 9 | 2.2.2.0.9 | 2.2.2.1.2 | [B9](B9%20-%20slow%20preset%20browsing/README.md) | Retained 250-tick browsing delay. Built directly from .0.9; .1.1 was the earlier 500-tick comparison. Hardware improved; residual slowdown remains. |
| 10 | 2.2.2.1.2 | 2.2.2.1.4 | [B14](B14%20-%20disable%20encoder%20accel/README.md) | Remove global encoder acceleration and replay accumulated movement as signed unit events. B13 .1.3 bypassed. |
| 11 | 2.2.2.1.4 | 2.2.2.1.6 | [B14](B14%20-%20disable%20encoder%20accel/README.md) | Bulk sample metadata SPI read. Rejected .1.5 display scheduler excluded. |
| 12 | 2.2.2.1.6 | 2.2.2.1.7 | [B14](B14%20-%20disable%20encoder%20accel/README.md) | Stable primary display frames during transfer; accepted responsiveness improvement. |
| 13 | 2.2.2.1.7 | 2.2.2.1.8 | [B15](B15%20-%20stretch%20layer/README.md) | Stretch layer; retained feature, hardware confirmed. |
| 14 | 2.2.2.1.8 | 2.2.2.1.9 | [B5](B5%20-%20sample%20end%20fade/README.md) follow-up | Attempted LFO/pitch endpoint-fade correction. The endpoint-click issue remained; this application is inherited by .1.10 and corrected in .1.11. |
| 15 | 2.2.2.1.9 | 2.2.2.1.10 | [B14](B14%20-%20disable%20encoder%20accel/README.md) | Restore factory acceleration for Size/Center/Start/End encoders; preserve other B14 behavior and B15. Inherits the unresolved B5 bug. |
| 16 | 2.2.2.1.10 | 2.2.2.1.11 | [B5](B5%20-%20sample%20end%20fade/README.md) final correction | Correct endpoint clicks under pitch modulation; supersedes earlier B5 behavior. Hardware PASS. |
| 17 | 2.2.2.1.11 | 2.2.2.1.12 | [B7](B7%20-%20center%20can%20be%20pushed/README.md) follow-up | LFO-to-Center pushes Start/End; hardware working. |
| 18 | 2.2.2.1.12 | 2.2.2.1.15 | [B10](B10%20-%20window%20scroll%20clicks/README.md) | Ordinary crossfade-entry correction. Hardware clicks substantially reduced, not eliminated. .1.13/.1.14 excluded. |
| 19 | 2.2.2.1.15 | 2.2.2.2.0 | [B11b](B11%20-%20type%20name%20tweak/README.md) | Show actual instrument name after manual Type change. Hardware PASS. B10 .1.16 excluded. |
| 20 | 2.2.2.2.0 — B11b | 2.2.2.2.1 — in_place | [B16](B16%20-%20new%20sync%20divisions/README.md) | New Sync divisions: audio behavior passed, graphical window required correction. Distinct from rejected B16 offline .2.1. |
| 21 | 2.2.2.2.1 — in_place | 2.2.2.2.2 | [B16](B16%20-%20new%20sync%20divisions/README.md) | Final geometry correction. Hardware confirmed sonic feature and graphical window working. |

## Other builds and numbering exceptions

These entries explain the apparent gaps. They are not extra required steps on the final path.

| Version / artifact | Feature / investigation | Parent / relationship | Disposition |
|---|---|---|---|
| `.0.1` dummy control, SHA `854f02bd…` | Installation control | Stock audio logic with inert padding marker and revised updater gate | Stock-audio installation control; distinct from voice-fade `.0.1` and combined `.0.1`. |
| `.0.1` voice-fade, SHA `f6b5205f…` | B1 | Earlier voice correction reference | Earlier voice correction baseline; `.0.2` is the retained B1 reference. |
| `.0.1` combined, SHA `d2775bd0…` | B1+B3 | Built from the preceding voice-fade `.0.1`, adding B3 in PIC | Adds B3 to voice-fade `.0.1`. The revision script produces `.0.3` without changing feature behavior. |
| `.0.4` `dummy_pic_2.2.2.0.4.bin` | Installation test | Stock application, PIC revision `.0.4` | Stock application `.0.0`, PIC `.0.4`. Tests PIC installation/reporting; contains no feature fixes. |
| `.1.0` | B7 squash-limit investigation | Reserved after `.0.9` | No delivered implementation/package. Abandoned investigation retained in B7 handover. |
| `.1.1` B9, SHA `061248f2…` | B9 | Directly from `.0.9` | Hardware-tested 500-tick variant; 250-tick `.1.2` preferred. `.1.2` is also built directly from `.0.9`. |
| `.1.3`, SHA `52d27173…` | B13 | From `.1.2` | Withdrawn fast-boot candidate; hardware boot failure. Excluded from `.1.4` and the final chain. |
| `.1.5`, SHA `dad5f698…` | B14 | From `.1.4` | Display scheduler rejected on hardware for worse lag/tearing. `.1.6` starts again from `.1.4`. |
| `.1.13`, SHA `6a94cca8…` | B10 | From `.1.12` | Forced-fade experiment; not retained. |
| `.1.14`, SHA `8dece2ed…` | B10 | From `.1.12` | Bounded forced-wrap experiment; not retained. `.1.15` also starts from `.1.12`. |
| `.1.16`, SHA `2e01f984…` | B10 | From `.1.15` | Minimum-fade experiment; no detectable hardware improvement. B11b starts from `.1.15`. |
| `.1.1_boottrace`, SHA `9c0d96a7…` | B13 diagnostic | Actually based on `.1.15` | Later boot-trace build, unrelated to B9 `.1.1`; hardware boot failure. Helper, builders, host harness and trace decoder are documented in B13. |
| `.1.1_CONTROL_unpatched`, SHA `2534cf43…` | B13 diagnostic | `.1.15` diagnostic control | Unpatched diagnostic control; untested on hardware. |
| `.1.1_BISECT_noop`, SHA `003ea37e…` | B13 diagnostic | `.1.15` diagnostic variant | No call-site hooks; helper, unwind and memory-map changes remain. Untested on hardware. |
| `.1.1_BISECT_stamps`, SHA `61292011…` | B13 diagnostic | `.1.15` diagnostic variant | Omits the final flush hook. Untested on hardware. |
| `.2.0_B16_finer_loop_sync_offline`, SHA `fb6b739e…` | B16 | From accepted B11b `.2.0` | Rejected offline candidate reusing its parent's version number; not the accepted B11b package. |
| `.2.1_B16_finer_loop_sync_offline`, SHA `5060674c…` | B16 | Revision subtree of the rejected offline candidate | Rejected variant; not the `.2.1_in_place` ancestor of final `.2.2`. |
| `.1.17` | Numbering limit | Not a retained build | B11b moved to `.2.0` because `.1.16` was occupied and the fifth DSP display component is four bits. No `.1.17` step is required. |

[SSD expansion guide](../SSD%20expansion/README.md) is a hardware/storage procedure and requires no firmware patch. [B4 expanded user slots](B4%20-%20expand%20user%20slots%20%28abandoned%29/README.md) was abandoned after an isolated QNX implementation; it is not included in the final firmware. Original B11 category skipping closed without a patch; B11b is the delivered Type-name feature.

## Packaging and verification

The feature guides document their implementation sources, exact input versions and incremental packaging commands. The B3 [`.0.7` packager](B3%20-%20sysex%20channel%20fix/build/combined_0_7/build_combined.py) produces a byte-for-byte match from `.0.6` and `.0.3`; its [verification result](B3%20-%20sysex%20channel%20fix/build/combined_0_7/recovery_verification.json) identifies the inputs and output. The [direct firmware patcher](../firmware_builder/patch_prophet_x.py) now generates the final `.2.2` package directly from the exact factory `.0.0` input, using authored generators and pinned redacted compiler objects. It creates no historical intermediate packages. The separate [compiler audit path](../firmware_builder/source_rebuild/README.md) retains rebuilding the documented chain. See the [direct builder guide](../firmware_builder/direct/README.md) for current runtime requirements and checks; input/output hashes are in the [main README](../README.md).

Use the full package filename and SHA-256 to identify a build. Application and PIC revisions can differ, displayed revisions may retain earlier values, and several experimental packages reuse version numbers. The `.1.9` application is part of the final ancestry even though `.1.11` supersedes its endpoint-fade behavior.

Final `.2.2` retains B9’s browsing improvement and B10’s window-scroll correction, with residual slowdown and clicks respectively. B13 is excluded: both its optimization and full-trace candidates failed hardware boot, and no successful target timing capture is recorded. Its control and bisect variants remain untested on hardware.

## Archived package identities (technical provenance)

This table is for auditing locally rebuilt stages and interpreting historical evidence, not choosing a firmware download. For the accepted final output and installation instructions, use the [main README](../README.md). Firmware files are excluded from this repository. The table identifies the private reference packages; [build_version_evidence.json](build_version_evidence.json) provides component revisions, lengths and SHA-256 hashes. Copies with the same whole-package hash represent the same build.

| Version / artifact | Package filename | SHA-256 |
|---|---|---|
| 2.2.2.0.0 | `PxUpdate_V2.2.2.0.0.bin` | `a4b304b3bb48ca933ae63c99c0098698c497ebfc7c38ab2a823b5e0df4919fa9` |
| 2.2.2.0.1 — dummy control | `PxUpdate_V2.2.2.0.1.bin` | `854f02bd17ba3731d5c038602043bb5b4a02682a6b3b473f7c3f23705bff393d` |
| 2.2.2.0.1 — B1+B3 | `combined_2.2.2.0.1.bin` | `d2775bd0e017e4442ce7d5bbc7d089022a1cf8c02714d89427462938e934d166` |
| 2.2.2.0.1 — B1 | `voice_fade_2.2.2.0.1.bin` | `f6b5205fc40e635305445bb19dd1a41d12f2ee4c64b7284ccd432868ef0c5898` |
| 2.2.2.0.2 | `PxUpdate_V2.2.2.0.2.bin` | `2ad5392eb842cbcd5c2e85e65ab42c16f1fac12d16b09c417a61761a8348bcbf` |
| 2.2.2.0.3 | `voice_sysex_2.2.2.0.3.bin` | `bbc3c2ad26bef7310fc15cac8edee22a1792d8ced3788f7080acccc047304857` |
| 2.2.2.0.4 PIC / 2.2.2.0.0 app | `PxUpdate_V2.2.2.0.4.bin` | `4dbe4c8814c9637ff38530ab7f31c20432c99360a2513e2191c878dc550b7af1` |
| 2.2.2.0.5 | `voice_b5_2.2.2.0.5.bin` | `41242b0d3cde1cf208181d998176db62dcc9484e2ca74e22104f4a140845a587` |
| 2.2.2.0.6 | `PxUpdate_V2.2.2.0.6.bin` | `2cd57a89d0873ad7e81c410748e3725de6a336494f4c6af1e0110aba85b15c95` |
| 2.2.2.0.7 | `PxUpdate_V2.2.2.0.7.bin` | `2fe41c83415c1d85efd7848a31511157162528ec4a83d08045be7e8bcee2e753` |
| 2.2.2.0.8 | `PxUpdate_V2.2.2.0.8.bin` | `c7e2e03999ca4590c99c3ba18a518f93f073ee8a619c84371677c7f6cd2c8e7f` |
| 2.2.2.0.9 | `PxUpdate_V2.2.2.0.9.bin` | `438da40fee68dee6062f169e3ca9ed461bf31547f0c1f0a77279a3bc264e6e5d` |
| 2.2.2.1.1 | `PxUpdate_V2.2.2.1.1.bin` | `061248f2d8e4e11e9dec78d6b5c74b87d16a283c273e2eba35ae84c2e592a012` |
| 2.2.2.1.1 — B13 BISECT_noop | `PxUpdate_V2.2.2.1.1_BISECT_noop.bin` | `003ea37e7c4e9886ce1a760e7929a59f8a50b1960a16dcde78e72635928f4028` |
| 2.2.2.1.1 — B13 BISECT_stamps | `PxUpdate_V2.2.2.1.1_BISECT_stamps.bin` | `61292011ab113b9ded244d5e81ad4a934bfc1ac7055b6ec4ae215b76f9c153e2` |
| 2.2.2.1.1 — B13 CONTROL_unpatched | `PxUpdate_V2.2.2.1.1_CONTROL_unpatched.bin` | `2534cf435eb4af2b51acee4fa7d671dfd3078e64eb137a4db4d2ebf47d304584` |
| 2.2.2.1.1 — B13 boottrace | `PxUpdate_V2.2.2.1.1_boottrace.bin` | `9c0d96a7cc12a70a679c656ff62441f6bc5ab1b72456814481d67d841a2d0040` |
| 2.2.2.1.2 | `PxUpdate_V2.2.2.1.2.bin` | `3e844a73a9f29bf0f1dc24929c989e0cb3946c9a307cab948e6af4c0928b5029` |
| 2.2.2.1.3 — B13 withdrawn | `PxUpdate_V2.2.2.1.3.bin` | `52d27173142479dfe84bb019b551f946ef3ae09b579b82fef719d8a1e17b857a` |
| 2.2.2.1.4 | `PxUpdate_V2.2.2.1.4.bin` | `eadf12ea51991ad749155c89136fa01176578b8e936df6851c6987b728af94f4` |
| 2.2.2.1.5 | `PxUpdate_V2.2.2.1.5.bin` | `dad5f69880969114914766a5352597ccdaed62a014dcebc55290138392e1e606` |
| 2.2.2.1.6 | `PxUpdate_V2.2.2.1.6.bin` | `12ff4c8ad099010d5f9803c3418b2b7ea0ad7fa383d1d78823bfeca9c51e1618` |
| 2.2.2.1.7 | `PxUpdate_V2.2.2.1.7.bin` | `91ec37c306731743c62f10b915450f8e64bccec3260e84a9ca8938d146df7f82` |
| 2.2.2.1.8 | `PxUpdate_V2.2.2.1.8_B15_candidate.bin` | `200a2d66625f840e0de93ca83518d025aa6de6cb47b7032bfc304384f9922535` |
| 2.2.2.1.9 | `PxUpdate_V2.2.2.1.9_B15_LFO_fade_candidate.bin` | `fe1858e1da01aeae69e41799dfbdfb1471f90b0c19d34687663533438f52a2da` |
| 2.2.2.1.10 | `PxUpdate_V2.2.2.1.10_B14_sample_acceleration_candidate.bin` | `6ab00ccd1f9461ffcf5927b54b317d7644c85a3a129dff6115f8cd0cd6a6a6e3` |
| 2.2.2.1.11 | `PxUpdate_V2.2.2.1.11_B5_completion_fade_candidate.bin` | `29aff5a6cbf6d603ae86f23525454bbbcbe568c3930d65c2064ce827080c86a8` |
| 2.2.2.1.12 | `PxUpdate_V2.2.2.1.12.bin` | `9d0860d06469519a1f80feef2a2143e4a2a343605821f28f193c985398943139` |
| 2.2.2.1.13 | `PxUpdate_V2.2.2.1.13_B10_forced_linear_candidate.bin` | `6a94cca83fe13be8b9dfa0d0656519899c9e9377f7a01e715576d9a9b747bbd9` |
| 2.2.2.1.14 | `PxUpdate_V2.2.2.1.14_B10_bounded_forced_candidate.bin` | `8dece2ed026124a1281e5d95f08b0a3974fff230a9515a03f24be19a6f276a4b` |
| 2.2.2.1.15 | `PxUpdate_V2.2.2.1.15_B10_ordinary_entry_candidate.bin` | `ebb2aebbd0decdadce92ed40d257e0cb03ebbf7aecf3e05749d9533fd5603450` |
| 2.2.2.1.16 | `PxUpdate_V2.2.2.1.16_B10_minimum_fade_candidate.bin` | `2e01f9843dfc8571aef936d4f75f099f5ea80c27a05f26786df7cef5897cc617` |
| 2.2.2.2.0 | `PxUpdate_V2.2.2.2.0_B11b_real_instrument_on_Type_candidate.bin` | `89d794880697c18da66356a2fd8cb90b7302d2250574ea4664bdbc496945bc6f` |
| 2.2.2.2.0 | `PxUpdate_V2.2.2.2.0_B16_finer_loop_sync_offline_candidate.bin` | `fb6b739e40a61bcab0d3beccc7566ec28b9d9aee0b4b32471bdb952bed20916f` |
| 2.2.2.2.1 | `PxUpdate_V2.2.2.2.1_B16_in_place_candidate.bin` | `0d41efe3fcd93d16161e92ae4b9389d7d0917006a06920b7f2c8b8660e419e74` |
| 2.2.2.2.1 | `PxUpdate_V2.2.2.2.1_B16_finer_loop_sync_offline_candidate.bin` | `5060674cf7e99b96aea025ac32dea9ab874568c65c53fd8b31db166feaec77e7` |
| 2.2.2.2.2 | `PxUpdate_V2.2.2.2.2_B16_geometry_candidate.bin` | `488444589607a1b4e793a8d8f79a67c5bd50773b722c302e6d80bc1db77b4b7c` |
