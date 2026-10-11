# B15 - Stretch Layer Lock

Standalone technical handover for B15. Stretch Layer Lock is implemented and hardware-confirmed; later builds carry it forward. The initial feature package is not the latest combined project firmware.

**Firmware:** `2.2.2.1.8` (initial B15 package).

**Hardware: PASS** The feature has been successfully tested on hardware.

The LFO-to-Instrument-Frequency endpoint-click investigation appended to the retained implementation report belongs to B5. Its failed 2.2.2.1.9 candidate does not mean B15 failed.

## Original problem and hardware behaviour

Stock Stretch selects the currently held key. With no key held, it retains the existing Stretch Key; it does not capture the last released note. Stock velocity capture selects the highest layer rather than the layer actually played, and turning Sample Vel during Stretch does not change the Stretch sample.

Sample Vel offers On and the instrument's existing layers. The internal descriptor maximum of 16 is not the menu's selectable layer count. QNX sends layer-count metadata to PIC, which dynamically clamps the selection.

## Implemented behaviour

- Enabling Stretch with a held key captures its actual played velocity layer and key.
- With no held key, enabling selects the highest available layer at the retained Stretch Key. No prior velocity-layer history is restored.
- Vel displays the actual selected Stretch layer. Turning Vel selects another layer while preserving the key.
- Stretch Key edits retain the numeric target layer; target and actual resolution are separate.
- On leaves the Stretch sample and target unchanged. Disabling Stretch reveals the stored ordinary Sample Vel setting.
- Explicit edits immediately update the stored Sample Vel parameter. Capture/display feedback does not change it.
- A/B and both instruments retain independent state and layer limits.
- Early Vel turns awaiting fresh capture/key/group feedback may be dropped. This was explicitly accepted to reduce code size. Current feedback restores the truthful actual-layer display.

## Final design

**Patch location:** Both PIC controller (MIPS) and QNX application (x86-64). PIC handles capture/UI/state; QNX implements the playback-side layer behavior.

**Patch size:** PIC: 2,616 used bytes in 2,660 allocated bytes across four regions. QNX: 3,921 new text bytes and 1,256 unwind bytes, with a 7,164-byte active combined unwind index. The update grows 35,936 bytes versus .1.7 because the QNX artifact grows; PIC length is unchanged. Runtime state/heap costs are listed separately below.

PIC edits are immediate and absolute. QNX resolves the selected handler and sends display-only actual-layer feedback; feedback never writes the stored Sample Vel parameter. A transient PIC cursor handles encoder edits while Stretch is active, including the special On/capture states. There are no reverse parameter mirrors, queued relative-edit commands or new persistence waits.

Capture snapshots the held key’s accepted layer before panic/note clearing, then commits after the final Stretch Key is stored. This also avoids rereading Instrument 2’s velocity after clearing its notes. QNX tracks accepted note handlers per pair/key, rather than inferring the layer from raw MIDI velocity. With no held key it resolves the highest available layer at the retained key.

## Final placement and state

| Region | Used / capacity |
| --- | --- |
| Main cave 9d0002a0–9d000c00 | 2,396 / 2,400 bytes |
| Capture 9d07a210–9d07a258 | 52 / 72 bytes |
| Setters 9d07a4f8–9d07a56c | 112 / 116 bytes |
| Formatter 9d07a408–9d07a450 | 56 / 72 bytes |
| Total | 2,616 / 2,660 bytes |

The extra spans reuse inherited disabled B14 acceleration code. Live shared exits/helpers remain intact. Audit limits concerning arbitrary computed ingress are documented in the original report. No PIC payload extension or bootloader change was used.

PIC runtime state occupies 64 bytes at 80057aa0–80057ae0. Both heap providers were reduced from 0x4000 to 0x3fc0 at 9d081868 and 9d07fb40. Both changes are present in the fitted/package image. Startup clears and all decoded DINIT destinations were checked for overlap; whole-program indirect accesses and runtime stack high-water were not exhaustively proved.

Feedback uses per-pair 32-bit epochs and ordered framing to reject old contexts. Display-only feedback cannot overwrite stored preset parameters. Preset load/import/defaults/reset/compare/restore invalidate context; bulk replay resolves at its end without newly introduced waits or failure returns.

## Validation and package

Retained reports describe emitted MIPS execution with adversarial ABI clobbers, actual setter/serialization paths, QNX sanitizer/component checks, fitted formatter checks, 28 seeded lifecycle cases, placement/heap evidence, package extraction/checksums and modeled updater checks. Dependencies such as physical transport, interrupt delivery and some stock runtime functions remain modeled. See the original implementation report for exact scope and remaining audit limits.

Initial package: PxUpdate_V2.2.2.1.8_B15_candidate.bin

SHA-256: 200a2d66625f840e0de93ca83518d025aa6de6cb47b7032bfc304384f9922535

## Implementation map

PIC virtual addresses are distinguished from QNX ELF virtual addresses below. All ranges end exclusively. Exact hook/replay bytes and relocated destinations are in `absolute_pic_integration.json`; QNX detours are in `absolute_qnx_integration_results.json`.

| PIC hook / entry | Purpose |
|---|---|
| `0x9D04DACC`, `0x9D04FA6C` | Absolute setter and encoder entry |
| `0x9D075C1C` | Outgoing transport interception |
| `0x9D0511A4`, `0x9D029118` | Incoming feedback and main-loop display service |
| `0x9D05F7F4` | Actual-layer formatting |
| `0x9D035748`, `0x9D035F2C`, `0x9D031DA0` | Effective Sample Vel getter calls |
| `0x9D02AE50`, `0x9D02F26C` | Held-note capture before clearing |
| `0x9D02AE94`, `0x9D02F2BC` | Capture commit after final key storage |
| `0x9D02F2A8` | Removes Instrument 2's post-clear velocity reread |
| `0x9D04E230`, `0x9D04E250`, `0x9D04E0FC`, `0x9D04E11C` | Per-bank setter routing |
| `0x9D07C368`, `0x9D040418`, `0x9D0744CC`, `0x9D046E4C` | Replay, load, import and edit-apply lifecycle |
| `0x9D04CD14`, `0x9D07C2AC`, `0x9D04FEB4`, `0x9D04FFC4`, `0x9D052D0C` | Defaults, reset, compare, restore and cold initialization |

| QNX ELF hook | Purpose |
|---|---|
| `0x1E050` | Message adapter entry |
| `0x23B2D` | Accepted note handler observer |
| `0x23A3A` | Note-attempt invalidation |
| `0x22280` | Group context clear |
| `0x22344` | Defers legacy group selection to the common resolver |

QNX implementation lives in `b15_absolute_core.c/.h`, `b15_absolute_qnx_adapter.c` and `b15_qnx_thunks.s`. New text is 3,921 bytes at the `0x100000` reservation, with 1,256 unwind bytes and 24 new FDEs; all 870 inherited FDEs are preserved. The active index is 7,164 bytes, RX ends at `0x105000`, and runtime state occupies `[0x2B1EC0,0x2B21C0)` (768 bytes). QNX ELF length is 1,075,240 bytes. The original fixed-frame cache endpoint is preserved.

PIC's four 16-byte records contain per-pair epochs, actual layer, transient cursor, dirty display flag, capture tag and exhaustion guard. Unused record tails also hold ordered feedback staging and bulk depth. Feedback is framed as epoch low/high (`0x4058`, `0x4059`) then actual layer (`0x404A`); the receiver requires the current pair epoch and correct framing. Epoch/context changes invalidate stale messages. Commands and exact field operations are implemented in the adapter and PIC emitter, rather than introducing preset fields.

## Hardware and validation boundaries

**Hardware PASS:** the owner confirmed B15 working well on 8 October 2026. Original saved component reports contain creation-time labels such as `NOT RELEASE`, `INCOMPLETE`, `ready_for_hardware: false` or hardware pending. These describe their build stages; the `.1.8` package identity and owner acceptance above establish the delivered artifact. The historical filename `pic_B15_absolute_INCOMPLETE.bin` is also the fitted input actually consumed by the accepted packager.

Host validation executes emitted MIPS hooks with adversarial ABI clobbers, stock setter/parameter serialization paths, paired native QNX policy/adapter code, formatter guards and 28 seeded lifecycle cases. The lifecycle roots include replay/load/import/edit-apply/defaults/reset/compare/restore plus bypass and startup routes. Physical transport, flash/device completion and parts of stock runtime behavior remain modeled. No-reply target waits, actual IRQ nesting/delivery, every lifecycle input and runtime stack high-water are not exhaustively covered.

Both heap reservations are essential: reverting either `0x3FC0` provider can make the heap cover B15 state. Startup clear bounds and all 93 fitted DINIT records were checked for overlap. Raw pointer/immediate inventories and nearby address constructions found no additional identified state placement, but arbitrary indirect/computed pointers, generic runtime copy destinations, DMA and all possible allocator-bound overrides were not closed. Owner hardware acceptance does not claim those theoretical audits complete.

Focused hardware scenarios cover held/no-held capture, actual layer display, Vel edits including On, key edits across varying layer counts, both instruments and A/B/Both, group changes, save/recall/import/default/reset/compare/restore and rejection of stale feedback. Early Vel edits while awaiting fresh feedback may be dropped as accepted behavior; subsequent feedback restores the actual display.

## Package identity and incremental packaging

| Artifact | Bytes | SHA-256 |
|---|---:|---|
| Baseline `.1.7` package | 3,151,848 | `91ec37c306731743c62f10b915450f8e64bccec3260e84a9ca8938d146df7f82` |
| `.1.8` B15 package | 3,187,784 | `200a2d66625f840e0de93ca83518d025aa6de6cb47b7032bfc304384f9922535` |
| `.1.8` PIC | 530,784 | `d141de4ceaf9a754a3c3db193bacdc0ce6757cdabc9beeb3dcdba0ea49bb85e1` |
| `.1.8` QNX | 1,075,240 | `b819511abcace5c271d13145bbc3499fafed8f442af91d7343663cd71c3892c7` |

`build_candidate_1_8.py` consumes exact `.1.7`, the fitted PIC and retained QNX ELF, then sets application/PIC headers and embedded metadata to `.1.8`. QNX file offsets `0x1F4E3` and `0x250EF` change from `.1.7` to `.1.8`; PIC report immediates at `0x1394` and `0x13A0` change 7 → 8. Application checksum is `0xB7E4` (trailer `e4 b7`); complete FPGA record is unchanged, and inherited PIC trailer `30 30` is retained. The three-field M display remains inherited.

The package grows 35,936 bytes because the retained QNX artifact grows; PIC payload length does not change. Saved results account for 2,680 differing PIC bytes and 36,764 differing-or-added QNX bytes versus `.1.7`. Container positional differences include shifted unchanged later records and must not be mistaken for additional feature edits.

Package checks include parse/serialize/re-extraction identity, fitted regions/heap words, 16 actual bounded version-gate cases and 130 PIC blocks with 260 valid/corrupt checksum comparisons. Firmware images are private; the package SHA-256 was rechecked during this cleanup.

## Recovered source and build workflow

All source and evidence are under `implementation/`, preserving sibling directory imports. The principal tools are:

- `b15_candidate_work/build_pic_absolute.py`: emits the final absolute helper plan.
- `b15_candidate_work/build_pic_integrated.py`: scatters it into the four owned ranges, installs detours and both heap reservations.
- `b15_candidate_work/build_qnx_absolute.py`: compiles the core/adapter/thunks and integrates code, state and unwind metadata.
- `b15_candidate_work/build_candidate_1_8.py`: packages retained integrated components and independently checks the container/updater contract.

From a prepared private working copy, the final component/packaging steps are:

```sh
cd implementation
python3 b15_candidate_work/build_pic_absolute.py
python3 b15_candidate_work/build_pic_integrated.py
python3 b15_candidate_work/build_qnx_absolute.py
python3 b15_candidate_work/build_candidate_1_8.py
```

These commands document the incremental workflow, rather than a portable clean rebuild claim. They require exact private `.1.7` package/PIC/QNX inputs, saved placement PASS evidence, generated helper payloads and the matching compiler. Scripts retain their original checkpoint writes; run only in a private working copy and review output paths.

Required private locations include `PxUpdate_V2.2.2.1.7.bin`, `b14_stable_frame_packaging_work/pic_2.2.2.1.7.bin`, and `b14_stable_frame_packaging_work/voice_2.2.2.1.7_qnx.elf`. The baseline QNX hash is `4bcac9801d1d9f8306271a7ab42bb93e5e8fa9462664e16c6889ffcd050ea635`. The emitted fitted PIC and unpackaged QNX expected by the original packager are pinned in `candidate_1_8_results.json`.

Python 3 and Clang with x86-64 ELF support are required. The QNX builder uses freestanding position-independent code and explicit relocation resolution. The paired host validator additionally needs a regenerated `absolute_pair_bridge.dylib` compiled from the supplied bridge, test adapter and core sources; the original host setup is macOS. Native component checks use the supplied C harness with stock dependencies simulated.

`pre_immediate_store/build_pic_helpers.py` is retained because the final emitter extracts and transforms specific helper-source sections from it. Its earlier design entry point is not part of the final workflow. Likewise, inherited B14 assembler functions, the B9 MIPS interpreter, ELF/unwind utilities and the B7 gate decoder are dependencies; their unrelated main entry points are not B15 build steps.

Some placement/integration audits expect original proprietary exports `b15_investigation/placement_closure_evidence.txt` and `qnx_1_7_disassembly.txt`. Those exports remain private; saved results preserve the original evidence. Historical unplaced component tests also expect generated payload files. Use `B15_PLACED=1` for the applicable fitted-image tests, as their source specifies; the Python scripts that set it internally already select the fitted image. Saved test JSON is evidence, not a promise that every historical driver runs using only this public bundle.

The [root patcher](../../patch_prophet_x.py) now rebuilds the retained intermediate chain from the exact factory update, including B15 and its follow-ups, and verifies the final package. See the [source build guide](../../firmware_builder/README.md) for source review and retaining intermediate packages and validation reports.

## Relationship to later fixes

B15 is retained in later builds. The `.1.9` and `.1.11` endpoint-click investigations concern **B5**, rather than B15’s Stretch policy. The definitive B5 `.1.11` correction supersedes the inherited pitch-modulation endpoint behavior; see the [B5 handover](../B5%20-%20sample%20end%20fade/README.md). The `.1.10` encoder acceleration refinement is documented under [B14](../B14%20-%20disable%20encoder%20accel/README.md). Those follow-ups are not duplicated in this B15 source bundle.

## Complete supporting-file inventory

Every retained file is linked below. Saved evidence and imported dependencies are distinguished from final implementation entry points. Duplicate progress reports, superseded full designs, frozen duplicate artifacts and unrelated B5 investigations are retained privately. No firmware, objects, native executables/libraries, generated binary fragments or proprietary disassembly exports are included. [SHA256SUMS](SHA256SUMS) covers the handover and supporting files.

### Final PIC implementation

| File | Purpose |
|---|---|
| [b15_candidate_work/build_pic_absolute.py](implementation/b15_candidate_work/build_pic_absolute.py) | Final PIC helper emitter; imports selected prior helper sections. |
| [b15_candidate_work/build_pic_integrated.py](implementation/b15_candidate_work/build_pic_integrated.py) | Final fitted placement, detours and heap reservations. |
| [b15_candidate_work/build_pic_helpers.py](implementation/b15_candidate_work/build_pic_helpers.py) | Shared ELF parser used by the QNX build utilities. |
| [b15_candidate_work/pic_absolute_assembly.json](implementation/b15_candidate_work/pic_absolute_assembly.json) | Saved assembly, patch, validation or ownership evidence; stage labels retain original meaning. |
| [b15_candidate_work/pic_absolute_results.json](implementation/b15_candidate_work/pic_absolute_results.json) | Saved assembly, patch, validation or ownership evidence; stage labels retain original meaning. |
| [b15_candidate_work/absolute_pic_integration.json](implementation/b15_candidate_work/absolute_pic_integration.json) | Saved assembly, patch, validation or ownership evidence; stage labels retain original meaning. |

### QNX implementation and native harnesses

| File | Purpose |
|---|---|
| [b15_candidate_work/b15_absolute_core.c](implementation/b15_candidate_work/b15_absolute_core.c) | Core/adapter/thunk implementation or native test fixture. |
| [b15_candidate_work/b15_absolute_core.h](implementation/b15_candidate_work/b15_absolute_core.h) | Core/adapter/thunk implementation or native test fixture. |
| [b15_candidate_work/b15_absolute_qnx_adapter.c](implementation/b15_candidate_work/b15_absolute_qnx_adapter.c) | Core/adapter/thunk implementation or native test fixture. |
| [b15_candidate_work/b15_qnx_thunks.s](implementation/b15_candidate_work/b15_qnx_thunks.s) | Core/adapter/thunk implementation or native test fixture. |
| [b15_candidate_work/build_qnx_absolute.py](implementation/b15_candidate_work/build_qnx_absolute.py) | QNX object compiler, relocation, state and unwind integration. |
| [b15_candidate_work/absolute_qnx_integration_results.json](implementation/b15_candidate_work/absolute_qnx_integration_results.json) | Saved assembly, patch, validation or ownership evidence; stage labels retain original meaning. |
| [b15_candidate_work/test_absolute_qnx_adapter.c](implementation/b15_candidate_work/test_absolute_qnx_adapter.c) | Core/adapter/thunk implementation or native test fixture. |
| [b15_candidate_work/absolute_pair_bridge.c](implementation/b15_candidate_work/absolute_pair_bridge.c) | Core/adapter/thunk implementation or native test fixture. |

### Packaging

| File | Purpose |
|---|---|
| [b15_candidate_work/build_candidate_1_8.py](implementation/b15_candidate_work/build_candidate_1_8.py) | Incremental package creation and updater/checksum verification. |
| [b15_candidate_work/candidate_1_8_results.json](implementation/b15_candidate_work/candidate_1_8_results.json) | Saved assembly, patch, validation or ownership evidence; stage labels retain original meaning. |

### Validation, evidence and shared dependencies

| File | Purpose |
|---|---|
| [b14_candidate_work/build_b14.py](implementation/b14_candidate_work/build_b14.py) | Shared ELF parser used by the QNX build utilities. |
| [b14_ui_candidate_work/build_display.py](implementation/b14_ui_candidate_work/build_display.py) | Shared ELF parser used by the QNX build utilities. |
| [b15_candidate_work/absolute_formatter_callers_results.json](implementation/b15_candidate_work/absolute_formatter_callers_results.json) | Saved assembly, patch, validation or ownership evidence; stage labels retain original meaning. |
| [b15_candidate_work/absolute_formatter_results.txt](implementation/b15_candidate_work/absolute_formatter_results.txt) | Saved fitted formatter test results. |
| [b15_candidate_work/absolute_heap_ownership_evidence.json](implementation/b15_candidate_work/absolute_heap_ownership_evidence.json) | Saved assembly, patch, validation or ownership evidence; stage labels retain original meaning. |
| [b15_candidate_work/absolute_integration_audit.json](implementation/b15_candidate_work/absolute_integration_audit.json) | Saved assembly, patch, validation or ownership evidence; stage labels retain original meaning. |
| [b15_candidate_work/absolute_lifecycle_results.json](implementation/b15_candidate_work/absolute_lifecycle_results.json) | Saved assembly, patch, validation or ownership evidence; stage labels retain original meaning. |
| [b15_candidate_work/absolute_pair_results.json](implementation/b15_candidate_work/absolute_pair_results.json) | Saved assembly, patch, validation or ownership evidence; stage labels retain original meaning. |
| [b15_candidate_work/absolute_pic_placed_execution.json](implementation/b15_candidate_work/absolute_pic_placed_execution.json) | Saved assembly, patch, validation or ownership evidence; stage labels retain original meaning. |
| [b15_candidate_work/absolute_placement_results.json](implementation/b15_candidate_work/absolute_placement_results.json) | Saved assembly, patch, validation or ownership evidence; stage labels retain original meaning. |
| [b15_candidate_work/absolute_stock_setter_results.json](implementation/b15_candidate_work/absolute_stock_setter_results.json) | Saved assembly, patch, validation or ownership evidence; stage labels retain original meaning. |
| [b15_candidate_work/audit_absolute_integration.py](implementation/b15_candidate_work/audit_absolute_integration.py) | Component, fitted-image or ownership validation tool; private inputs may be required. |
| [b15_candidate_work/audit_absolute_placement.py](implementation/b15_candidate_work/audit_absolute_placement.py) | Component, fitted-image or ownership validation tool; private inputs may be required. |
| [b15_candidate_work/audit_pic_size.py](implementation/b15_candidate_work/audit_pic_size.py) | Component, fitted-image or ownership validation tool; private inputs may be required. |
| [b15_candidate_work/pre_immediate_store/build_pic_helpers.py](implementation/b15_candidate_work/pre_immediate_store/build_pic_helpers.py) | Source-section dependency extracted by final emitter; earlier entry point unused. |
| [b15_candidate_work/validate_absolute_formatter.py](implementation/b15_candidate_work/validate_absolute_formatter.py) | Component, fitted-image or ownership validation tool; private inputs may be required. |
| [b15_candidate_work/validate_absolute_formatter_callers.py](implementation/b15_candidate_work/validate_absolute_formatter_callers.py) | Component, fitted-image or ownership validation tool; private inputs may be required. |
| [b15_candidate_work/validate_absolute_lifecycle.py](implementation/b15_candidate_work/validate_absolute_lifecycle.py) | Component, fitted-image or ownership validation tool; private inputs may be required. |
| [b15_candidate_work/validate_absolute_pair.py](implementation/b15_candidate_work/validate_absolute_pair.py) | Component, fitted-image or ownership validation tool; private inputs may be required. |
| [b15_candidate_work/validate_absolute_stock_setter.py](implementation/b15_candidate_work/validate_absolute_stock_setter.py) | Component, fitted-image or ownership validation tool; private inputs may be required. |
| [b15_candidate_work/validate_pic_absolute.py](implementation/b15_candidate_work/validate_pic_absolute.py) | Component, fitted-image or ownership validation tool; private inputs may be required. |
| [b15_candidate_work/validate_pic_emission.py](implementation/b15_candidate_work/validate_pic_emission.py) | Component, fitted-image or ownership validation tool; private inputs may be required. |
| [b15_candidate_work/validate_pic_operations.py](implementation/b15_candidate_work/validate_pic_operations.py) | Component, fitted-image or ownership validation tool; private inputs may be required. |
| [b5_elf_placement_check.py](implementation/b5_elf_placement_check.py) | Shared ELF parser used by the QNX build utilities. |
| [b7_candidate_work/validate_version_gates.py](implementation/b7_candidate_work/validate_version_gates.py) | Component, fitted-image or ownership validation tool; private inputs may be required. |
| [b9_250_candidate_work/mips_check.py](implementation/b9_250_candidate_work/mips_check.py) | Shared ELF parser used by the QNX build utilities. |
| [qnx_elf.py](implementation/qnx_elf.py) | Shared ELF parser used by the QNX build utilities. |

Cleanup checks: source-copy identities, Python/JSON syntax, all handover links, inventory checksums and private `.1.8` package identity PASS. Firmware builds, full test drivers and hardware tests were not rerun.
