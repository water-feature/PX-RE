# B8 - Completed sample voices stay silent after endpoint edits

Standalone technical handover for the original B8 implementation. B8 is implemented and hardware-confirmed. Its incremental .0.6 package inherits B1 and original B5; later builds retain B8. This is not the latest combined project firmware.

**Firmware:** `PxUpdate_V2.2.2.0.6.bin`, built from `2.2.2.0.5`.

**Hardware: PASS:** The end-escape fix was confirmed working on hardware, with no B8 bugs reported. Saved hardware-pending labels describe the earlier offline checkpoint; exhaustive regression coverage was not reported.

With sample looping off, moving an endpoint after a held note has finished could make it play again. B8 records completion for that playback instance and keeps it silent through endpoint, pitch/rate, direction and loop edits. Edits before consumed completion remain effective. A successful intentional retrigger starts a fresh instance with current controls. Reverse playback applies the same rule at the selected Start boundary.

## Deliverables and exact baseline

- Flashable candidate: `b8_candidate_work/PxUpdate_V2.2.2.0.6.bin`, **3,151,848 bytes**, SHA-256 **`2cd57a89d0873ad7e81c410748e3725de6a336494f4c6af1e0110aba85b15c95`**.
- Combined ELF: `b8_candidate_work/voice_B1_B5_B8_candidate.elf`, **1,039,304 bytes**, SHA-256 **`85b76594924f1a8b7deffec1d81f79feb848edf6c631d0eb2b6c24f49aa393f1`**. `b8_packaged_qnx.elf` is the independently extracted identical payload.
- Exact input: preserved `b5_packaging_work/voice_b5_2.2.2.0.5.bin`, SHA-256 **`41242b0d3cde1cf208181d998176db62dcc9484e2ca74e22104f4a140845a587`**; extracted `b5_packaging_work/b5_packaged_qnx.elf`, SHA-256 **`07ff1fd635505114945fc4dcab11a212f4bc9164b1a7ab8beb681482cb7c2b35`**.

The builder consumes the exact B5 ELF above and appends B8; it does not use the voice-only image loaded in Ghidra. Existing B1/B5 hook and helper bytes are independently checked unchanged. This is an incremental implementation, rather than a standalone B8 patch for factory firmware.

**B5 baseline distinction:** `.0.5` was hardware tested, but later found to contain the endpoint-click-under-pitch-modulation bug. The B5 `.1.11` correction supersedes that B5 implementation and preserves B8. Use the [B5 handover](../B5%20-%20sample%20end%20fade/README.md) for the corrected B5 implementation. B8 `.0.6` identifies this original B8 build, rather than the project's final integrated firmware.

Package application header/file revision is `.6`. Compiled updater comparison and displayed DSP revision remain inherited **2.2.2.0.2**; the display does not identify this candidate. The `.6` header differs from that compiled gate. Established framing, big-endian length, little-endian application word checksum **0x7105**, and original FPGA/PIC complete records are preserved. The known PIC 0x3030 versus simple word sum 0x4658 discrepancy is inherited unchanged, not repaired. The saved packaging validation is offline; hardware confirmation is recorded separately above.

## Implemented state and completion rule

**Patch location:** QNX application (x86-64); inherited PIC behavior is unchanged.

**Patch size:** 4,646 machine-code bytes + 16 constant bytes + 5 alignment bytes = 4,667-byte appended code/constant payload. New unwind records use 1,324 bytes including terminator, and the active index grows by 56 bytes. ELF and update-container growth is 24,728 bytes. Incremental reader heap cost is 1,024 bytes, separate from firmware patch size.

Only one persistent reader-owned byte at **CWavReader +0x1c0** is added. Bit 0 means consumed completion; bit 1 remembers that this completed instance had a B5 envelope that must survive an unavailable return. There is **no new batch record, geometry snapshot, delay history, sequence, pointer table or tracking framework**. Both bits clear together on legitimate initialization.

Before inherited B5 Prepare can accept new controls, use the already-published B5 `published_key`, `published_boundary`, `published_start`, `published_sequence`, count and success/publication bits. Ownership requires the RAM scheduler vtable, valid slot index/stride/owner and matching reader sidecar at +0x1b8. The descriptor must belong to the active reader and current published/staged sequence. Skip this old-reader decision when Client's pending-replacement flag is set.

`u = min(slot+0x24 consumed, slot+0x18 requested)`. Require a successful matching nonlooping publication, matching count, `u > 0`, and terminal destination-frame offset `0 <= e <= requested`; latch when **u >= e**. An opaque-prefix publication additionally requires its ordinary anchor (`e >= published_start`, `u > published_start`). Direction and delay are already reflected in `e`: forward B-P, reverse P-A, plus actual delay/ordinary prefix. Exact reach qualifies. An unconsumed exhausted batch does not; an ordinary exhausted batch with e=0 qualifies after positive consumption. Entirely delayed/unanchored input does not invent a terminal descriptor.

This deliberately avoids stock UpdateLoc +0x98, cursor comparisons against edited boundaries, amplitude, speculative Read EOF and B5 fade completion. Default-mode UpdateLoc advances within file-wide bounds through padded zeros; its position does not establish selected-boundary completion. The existing publication is authoritative even when Read chose reverse from fractional follows-center geometry and stock UpdateLoc's truncated comparison would differ.

## B5 composition and reset behavior

For a completed active reader, Prepare restores working first-lane controls from the previous consumed bank and pending reader controls from the previous Read snapshots. It holds the effective rate and clears this slot's dirty-control application bits. CParams/scheduler control packet values remain available for the next note initialization. This keeps the inherited B5 requested/observed keys stable, clears stale B5 pending requests, and preserves its existing fade start/end/clock and zero tail. No inherited B5 helper is rewritten.

The Read gate runs after bank/parameter/origin bookkeeping and inherited geometry observation, before ordinary/splice/delay copying. Completed readers mark the buffer valid, clear stale opaque classification, publish terminal zero input, and branch to the existing B5 EOF/whole-request zero-fill path. Original normalization and filter histories continue normally. Endpoint, rate, reverse, follows-center, custom mode or loop edits cannot revive that instance. Tiny B5-bypassed regions receive zero source and retain their normal history drain; no new fade or early mute policy is introduced.

A completed NoteOn attempt defers the inherited B5 sidecar reset until **successful owned pending-reader Open**. Both original resampler Reset calls still execute. Failed Open or OpenStream rejection leaves completion and the old B5 envelope intact. Success (EAX=0), correct slot ownership and matching pending-reader identity invoke the existing B5 note initialization when it was deferred, then clear only that pending reader's byte. New playback can then use current requested controls. A pending swap clones existing banks/rates/selector, not the latch byte. Closing the old reader does not clear another instance's completion.

A common PlayNote epilogue guard restores the existing envelope's enabled state after inherited unavailable-return handling, using bit 1 and the original retained start/end. It does not advance the fade clock or construct another fade. Reset clears both readers' bytes in all 64 owned slots **after** inherited B5 attach establishes their sidecar pointers; constructor Reset supplies first initialization. Generic Close does not clear the byte. Destruction frees the extended allocations with their readers.

B5's 5 ms / 240 output-interval policy and inherited prediction code are unchanged. Its historical allowance for endpoint-only resurrection conflicts with the owner's clarified requirement; the combined completed-instance guards supersede that behavior. Intentional successful retriggers remain audible; endpoint extensions before consumed completion remain effective, including after speculative EOF.

## Confirmed hooks, allocation and ownership contracts

All addresses are **ELF VAs**; add 0x100000 for the loaded Ghidra image. New hooks use untouched stock neighborhoods adjacent to inherited B5 hooks, leaving every inherited hook and helper intact.

| New edit | Original bytes / target | B8 helper | Continuation / effect |
|---|---|---|---|
| Prepare JMP **0x372d4**, 7 bytes | `49 8b 7f 30 0f 28 c1` | **0xf85f0** | **0x372db**; replay scheduler load/MOVAPS; inherited B5 Prepare JMP at 0x372e5 follows |
| Read gate JMP **0x3fc2d**, 6 bytes | `89 87 94 00 00 00` | **0xf8750** | Replay origin store; normal **0x3fc33**, completed **0x40060** existing EOF/zero-fill |
| Reset JMP **0x3c8f6**, 6 bytes | `31 ed 53 48 89 fb` | **0xf88c0** | **0x3c8fc**; follows inherited attach at 0x3c8f0; replay XOR/PUSH/MOV |
| NoteOn JMP **0x3643f**, 9 bytes | `48 8b 7d 18 e8 18 7e ff ff` | **0xf8a30** | Original Reset **0x2e260** retained; normal inherited B5 observer **0x36448**, completed deferred path **0x3644f** |
| PlayNote return JMP **0x3749d**, 5 bytes | `48 8b 4c 24 48` | **0xf8d80** | **0x374a2**; follows inherited B5 return observer at 0x37496; replay stack-canary load |
| Owned Open CALL **0x3d492** | Original **0x42660** | **0xf8ee0** | **0x3d497**; forward both stack arguments; successful matching pending Open only |
| Reader allocation immediates **0x3d0fc**, **0x3d11a** | `bf c0 01 00 00` | `bf c8 01 00 00` | 0x1c0 → **0x1c8**, preserves sidecar pointer +0x1b8 |

New dispatcher **0xf8000**. Read extension access is authorized only by the actual owned original-Read return marker, sidecar/staged-reader identity and active wrapper state. Unrelated CWavReader invocations do not read +0x1c0.

The shims save/restore all 15 GPRs, flags and XMM0–15; normal Read gate replays MOV without altering incoming flags for the following JZ. Gate/Note choose their continuation via a scratch stack pointer and indirect JMP, preserving restored flags. The Open wrapper separately captures original-call volatile results, XMM and flags, forwards the two original stack arguments in order, and preserves inherited callee registers. Reset replays its extra PUSH with matching CFI. NoteOn preserves original Reset behavior and scheduler/vtable loads while selectively deferring only the B5 observer.

**Prepare→Client ordering:** inherited B5 Prepare replays the virtual CALL through RAM vtable +0x68, whose installed value remains **0x3cb50**. In that Client path, **0x3cba6** UpdateLoc consumes the old min(counts); **0x3cbf4** writes new controls; **0x3cc81** calls inherited Read wrapper; **0x3cd69** calls inherited publication wrapper. The replacement branch skips old UpdateLoc. New preflight executes before this synchronous virtual call. The combined host chain executes the new Prepare JMP → saved stock instructions → actual B5 Prepare shim → virtual Client fixture → actual B5 Read/Publish wrappers. Installed opcode/vtable checks substantiate the target ordering; the saved host tests model stock operations; the owner separately confirmed the installed fix on hardware.

## Build and ABI requirements

External address declarations explicitly use hidden visibility, producing supported direct PC-relative references; calls resolve to pinned local targets. No GOT allocation is added. The installed validator checks both instruction relocations and table-base-relative switch destinations. Reset's extra PUSH has matching unwind information.

The host runner uses a non-PIE x86-64 Mach-O executable, with Rosetta where needed. Its fixtures execute emitted B8 shims and inherited B5 machine code, while stock QNX reader/scheduler/filter/Open operations remain simulated.

## Validation results

Machine-code host tests: **38,622 checks, 8 focused groups, PASS**; `b8_integration_validation.json` records exact object/test-source hashes and captured output. Tests execute emitted B8 dispatcher/JMP shims/Open wrapper and inherited B5 machine code, including the combined Prepare chain. Coverage:

- Forward and reverse ordinary selected terminal completion; 2,624 partial/exact consumption cases; speculative EOF with pre-completion extension; count capping; terminal beyond the current batch.
- Exact whole-batch boundary with no zero suffix, including delay+ordinary exact reach; partially consumed delayed prefixes, entirely delayed batches and the next ordinary batch; exhausted e=0 input; tiny high-rate B5-bypassed region.
- Endpoint/rate/direction/loop/custom/follows-center changes after completion; whole-request zero source and normalized stereo zeros; existing envelope preserved over all 240 intervals and its finished tail. Both channel layouts and both oscillator slot ranges.
- Active loop stays active; loop→nonloop followed by terminal consumption; nonloop→loop before completion; loop request after completion stays silent. Fractional reverse-follows-center publication remains authoritative.
- Stale sequence, loop publication, invalid ordinary anchor and unowned contexts rejected. Existing opaque-prefix anchor conditions checked; no descriptor is invented for unanchored input.
- Failed Open, successful retrigger and pending swap in **all 64 slots**, reader-only latch reset, slot reuse and Reset of all 128 readers; failed completed NoteOn preserves the old envelope; unavailable return repair preserves original start/end/clock.
- Actual new JMP prologues/replays/continuations and Open stack argument forwarding; volatile/callee registers, arithmetic flags and all XMM return values checked. Read gate's incoming flags and whole-buffer zero branch checked.

Installed ELF validation: **5,719 checks, PASS**, in `b8_candidate_validation.json`: exact edit whitelist (47 original bytes change), unchanged inherited B1/B5 code/hooks, all new branch targets/replay bytes/continuations, both allocation immediates, object bytes and resolved relocations, LOAD placement/alignment, CFI at **575 shim instructions**, **9 aligned call sites**, and **2,652 index lookup/range checks** across three load biases. All **863 inherited unwind PC/FDE pairs and FDE bytes** remain unchanged; **7 new FDEs** produce **870 indexed entries**. The B1 helper 0x49fd0–0x4a08c, hook 0x1b49e, NOPs 0x1b7e5–0x1b7e9 and its FDE at 0x89c38 remain byte-identical.

Package validation: **21 independent offline checks, PASS**, plus **7 input/corruption rejection cases**. Application extraction exactly matches the validated ELF; deterministic repack matches the saved BIN; complete FPGA/PIC suffix is identical. See `b8_packaging_validation.json` and `b8_packaging_manifest.json`.

Relevant commands used, with final PASS results:

```sh
python3 b8_candidate_work/emit_b8.py
python3 b8_candidate_work/validate_b8_host.py
python3 b8_candidate_work/build_b8_candidate.py
python3 b8_candidate_work/package_b8_candidate.py
python3 b8_candidate_work/verify_b8_package.py
```

The packager refuses existing output names rather than overwriting them. Development fixture/script-construction helpers are not part of this build sequence. Baseline DSP/acoustic tests were not repeated. Hardware PASS comes from the owner’s testing, separately from these saved host results.

## Size, storage and performance cost

| Increment over tested B5 | Cost |
|---|---:|
| New machine code | **4,646 bytes** (dispatcher 1,499; six shims/wrappers 3,147) |
| Constants/alignment | 16 bytes constants + 5 bytes layout padding |
| Actual appended code/constant payload | **4,667 bytes**, at **0xf8000**; 8 KiB reservation |
| New unwind records | **1,320 bytes + 4-byte terminator**, at **0xfa000**; 4 KiB reservation |
| Active unwind index | **6,972 bytes**, at **0xfb000**; 8 KiB reservation; +56 actual index bytes |
| RX mapping growth | **24,576 bytes**, ending **0xfd000**; remains disjoint from inherited RW mapping |
| ELF and update-container growth | **24,728 bytes** |
| Incremental heap | **1,024 bytes**: 128 readers × 8 allocation bytes |
| Total extra heap versus stock | **18,432 bytes**, including inherited B5 storage |
| Largest new capture/forwarding stack allocation | **408 bytes**, excluding return addresses and called functions' frames |

The two reader bits occupy one byte; alignment accounts for the remaining allocation growth. No audio buffer is added. New per-block work comprises the preflight and common return guard; each new Read also passes the gate. Each simple full-register shim transfers approximately 768 bytes of saved/restored GPR/flags/XMM state, excluding dispatcher spills. Original source-copy/zero-fill, normalization and B5 predictor/filter code are retained. Reset scans 128 readers; Open/Note guards run on initialization rather than per sample.

The measured host preflight was approximately **0.024 microseconds/call** over 200,000 calls, including fixture capture copying, under Rosetta. This is a helper-only host observation, **not target timing or the cost of the full installed shim chain**. No quantitative target CPU utilization/headroom measurement is recorded.

## Hardware status and regression scenarios

Tested working on hardware. No new device test was performed during this documentation cleanup, and no instrumented target CPU measurement is recorded.

The regression scenarios are:

1. Loop off: hold forward playback until silent, extend End and change rate/direction/loop. The completed instance stays silent. Repeat in reverse by moving Start.
2. Retrigger intentionally: the new note plays with current settings. Endpoint extensions before consumed completion remain effective, including after speculative Read exhaustion.
3. Exercise delayed starts, short/high-rate regions, quick repeats and slot reuse, both oscillators and stereo layouts.
4. Start looping, disable it and allow completion, then enable looping while held. The completed instance stays silent; edits made before completion remain effective.
5. Retain B5's smooth tail and B1's voice-steal/retrigger behavior during sustained polyphony.

The publication rule deliberately requires an ordinary terminal anchor. Unanchored legacy splice/error input does not fabricate completion. The inherited follows-center rounding mismatch is unchanged. Saved host fixtures do not execute the complete stock QNX reader or prove every legacy splice/ping-pong transition.

## Supporting files and packaging path

- [Adapters and completion logic](b8_candidate_work/b8_adapters.c), [shim assembly](b8_candidate_work/b8_hooks.s) and [object emitter](b8_candidate_work/emit_b8.py).
- [Candidate builder](b8_candidate_work/build_b8_candidate.py), [installed validator](b8_candidate_work/validate_b8_candidate.py), [patch manifest](b8_candidate_work/b8_candidate_manifest.json) and [installed validation](b8_candidate_work/b8_candidate_validation.json).
- [Host runner](b8_candidate_work/validate_b8_host.py), [integration tests](b8_candidate_work/b8_integration_tests.c), [stock-operation fixtures](b8_candidate_work/b8_wrapper_fixture.s) and [host results](b8_candidate_work/b8_integration_validation.json).
- [Packager](b8_candidate_work/package_b8_candidate.py), [independent package verifier](b8_candidate_work/verify_b8_package.py), [packaging manifest](b8_candidate_work/b8_packaging_manifest.json) and [packaging results](b8_candidate_work/b8_packaging_validation.json).
- The local `b5_candidate_work/`, `b5_packaging_work/` and root Python helpers supply the imported B5 ELF, object, unwind and container utilities. [SHA256SUMS](SHA256SUMS) inventories the public files.

Run the five commands in the validation section from this folder. The preserved scripts expect private inputs at `b5_packaging_work/voice_b5_2.2.2.0.5.bin` and `b5_packaging_work/b5_packaged_qnx.elf`, with the exact hashes above. Generate inherited B5 objects using `python3 b5_candidate_work/emit_b5_objects.py` before emitting B8. The source scripts require Python 3, Clang with x86-64 ELF support, and compatible objdump/DWARF tools; the host fixture additionally requires the macOS x86-64 execution environment described above. Matching compiler output matters because saved checkpoints pin object/source identities.

The builder creates `b8_candidate_work/voice_B1_B5_B8_candidate.elf`; the packager replaces the baseline application payload, sets the application header to `2.2.2.0.6`, updates its length and little-endian word checksum, and retains complete FPGA/PIC records. It produces `b8_candidate_work/PxUpdate_V2.2.2.0.6.bin`, checks deterministic repacking/extraction and rejects existing output names. The displayed/compiled `.0.2` gate remains inherited; identify the artifact by its package header and SHA-256. The known stock PIC trailer discrepancy is preserved, rather than recalculated.

Full firmware, ELF images, object files and generated binary payloads are excluded from this public folder. The scripts document the incremental packaging path. The [root patcher](../../patch_prophet_x.py) now compiles B8 from these sources as part of the retained factory-to-final chain. See the [source build guide](../../firmware_builder/README.md) for the tested toolchain and source-review option.

For this cleanup, copied source identities, Python/JSON syntax, document links, checksums and the saved private `.0.6` package identity were checked. Compilation, feature tests and hardware testing were not rerun.

## Complete supporting-file inventory

Every retained supporting file is linked below. Implementation, imported dependencies, test fixtures and saved evidence are distinguished by purpose; not every evidence file is required to build the feature. Original script layouts are retained so their relative imports remain intact. Firmware and generated binary inputs remain private, as described above. The [root checksum inventory](SHA256SUMS) covers this handover and all retained supporting files.

Copies of B5 sources and reports support inherited implementation/regression investigation. They are dependencies or provenance evidence, rather than additional B7/B8 features.

| File | Purpose |
|---|---|
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
| [b5_packaging_work/b5_packaging_manifest.json](b5_packaging_work/b5_packaging_manifest.json) | Saved patch/object/packaging identity and layout evidence. |
| [b5_packaging_work/b5_packaging_validation.json](b5_packaging_work/b5_packaging_validation.json) | Saved validation, measurement or ownership evidence; not a new test run. |
| [b5_packaging_work/documentation_packaging_verification.json](b5_packaging_work/documentation_packaging_verification.json) | Saved validation, measurement or ownership evidence; not a new test run. |
| [b5_packaging_work/package_b5_test.py](b5_packaging_work/package_b5_test.py) | Incremental packaging/publication tool. |
| [b5_packaging_work/verify_b5_test.py](b5_packaging_work/verify_b5_test.py) | Validation/test or ownership audit tool; uses the private inputs described in source. |
| [b8_candidate_work/b8_adapters.c](b8_candidate_work/b8_adapters.c) | Feature implementation or design probe compiled by supplied tools. |
| [b8_candidate_work/b8_candidate_cfi_rows.json](b8_candidate_work/b8_candidate_cfi_rows.json) | Decoded unwind rows used to audit installed shim behavior. |
| [b8_candidate_work/b8_candidate_manifest.json](b8_candidate_work/b8_candidate_manifest.json) | Saved patch/object/packaging identity and layout evidence. |
| [b8_candidate_work/b8_candidate_validation.json](b8_candidate_work/b8_candidate_validation.json) | Saved validation, measurement or ownership evidence; not a new test run. |
| [b8_candidate_work/b8_hooks.s](b8_candidate_work/b8_hooks.s) | Helper/shim assembly or generated target layout. |
| [b8_candidate_work/b8_integration_tests.c](b8_candidate_work/b8_integration_tests.c) | Test/stock-operation fixture. |
| [b8_candidate_work/b8_integration_validation.json](b8_candidate_work/b8_integration_validation.json) | Saved validation, measurement or ownership evidence; not a new test run. |
| [b8_candidate_work/b8_objects_manifest.json](b8_candidate_work/b8_objects_manifest.json) | Saved patch/object/packaging identity and layout evidence. |
| [b8_candidate_work/b8_offsets.generated.h](b8_candidate_work/b8_offsets.generated.h) | Generated structure/offset or policy definitions used by source/tests. |
| [b8_candidate_work/b8_packaging_manifest.json](b8_candidate_work/b8_packaging_manifest.json) | Saved patch/object/packaging identity and layout evidence. |
| [b8_candidate_work/b8_packaging_validation.json](b8_candidate_work/b8_packaging_validation.json) | Saved validation, measurement or ownership evidence; not a new test run. |
| [b8_candidate_work/b8_wrapper_fixture.s](b8_candidate_work/b8_wrapper_fixture.s) | Assembly fixture for validation; binary include paths require private generated inputs. |
| [b8_candidate_work/build_b8_candidate.py](b8_candidate_work/build_b8_candidate.py) | Build/emission/layout tool or imported build dependency. |
| [b8_candidate_work/emit_b8.py](b8_candidate_work/emit_b8.py) | Build/emission/layout tool or imported build dependency. |
| [b8_candidate_work/package_b8_candidate.py](b8_candidate_work/package_b8_candidate.py) | Incremental packaging/publication tool. |
| [b8_candidate_work/validate_b8_candidate.py](b8_candidate_work/validate_b8_candidate.py) | Validation/test or ownership audit tool; uses the private inputs described in source. |
| [b8_candidate_work/validate_b8_host.py](b8_candidate_work/validate_b8_host.py) | Validation/test or ownership audit tool; uses the private inputs described in source. |
| [b8_candidate_work/verify_b8_package.py](b8_candidate_work/verify_b8_package.py) | Validation/test or ownership audit tool; uses the private inputs described in source. |
| [patch_b4_minimal_qnx.py](patch_b4_minimal_qnx.py) | Inherited ELF parser imported by object/build utilities; its B4 entry point is not part of this feature. |
