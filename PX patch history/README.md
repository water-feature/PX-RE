# Firmware build and version history

The tables trace the firmware builds from factory **2.2.2.0.0** to final **2.2.2.2.2**, with comparison builds, rejected experiments and reserved numbers listed separately. IDs such as B1 and B16 link each investigation to its technical evidence.

Builds are ordered by their inputs and merges. The early B1/B3 artifacts were renumbered; the parent column records which versions each build actually used.

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

The feature guides document their implementation sources, exact input versions and incremental packaging commands. The B3 [`.0.7` packager](B3%20-%20sysex%20channel%20fix/build/combined_0_7/build_combined.py) produces a byte-for-byte match from `.0.6` and `.0.3`; its [verification result](B3%20-%20sysex%20channel%20fix/build/combined_0_7/recovery_verification.json) identifies the inputs and output. The [direct firmware patcher](../firmware_builder/patch_prophet_x.py) now generates the final `.2.2` package directly from the exact factory `.0.0` input, using authored generators and pinned redacted compiler objects. It creates no historical intermediate packages. The separate [compiler audit path](../firmware_builder/source_rebuild/README.md) retains rebuilding the documented chain. See the [direct builder implementation](../firmware_builder/direct/IMPLEMENTATION.md) for current runtime requirements and checks; input/output hashes are in the [main README](../README.md).

Use the full package filename and SHA-256 to identify a build. Application and PIC revisions can differ, displayed revisions may retain earlier values, and several experimental packages reuse version numbers. The `.1.9` application is part of the final ancestry even though `.1.11` supersedes its endpoint-fade behavior.

Final `.2.2` retains B9’s browsing improvement and B10’s window-scroll correction, with residual slowdown and clicks respectively. B13 is excluded: both its optimization and full-trace candidates failed hardware boot, and no successful target timing capture is recorded. Its control and bisect variants remain untested on hardware.

Historical package and component hashes are recorded in [build_version_evidence.json](build_version_evidence.json).
