# B1 - Voice-steal click fix

Standalone technical handover for the original B1 implementation. B1 is implemented and hardware-confirmed. This document describes the original voice-only build; it does not identify the latest combined project firmware.

**Firmware:** `PxUpdate_V2.2.2.0.2.bin` (archived locally as `voice_2.2.2.0.2.bin`).

**Hardware: PASS:** The original voice-steal reproducer passed using this build. Exhaustive regression, concurrency and timing coverage have yet to be completed.

## Problem and hardware result

With a sample starting at a nonzero waveform level and a long amp release, a reused voice ignored the amp attack setting and clicked. Increasing attack removed ordinary note-on clicks but did not remove stolen-voice clicks. With Multi Mode off, reuse began on note 9 in 8-voice mode and note 17 in 16-voice mode. Multi Mode halved the allocation range even with panel Split/Stack off.

On 3 October 2026 the the voice-only firmware was successfully tested on hardware. The original long-release reproducer now respects amp attack: increasing attack removes the clicks. Initial additional tests were good, but exhaustive regression testing has yet to be completed.

Clicks at trimmed non-looping sample endpoints are covered separately by B5.

## Mechanism and chosen fix

Static analysis found that stock gate-on can move an envelope from idle/release to delay/attack without clearing its level buffer. Delay can fill the next block from the previous last level. A new sample can therefore start while the reused amplitude envelope retains its release level. This was the leading mechanism; the internal state was not instrumented on hardware.

To preserve continuity while downstream filter energy decays, the patch reuses the existing continuous quick release, waits for the selected voices as one group, then performs stock oscillator shutdown and fresh activation. It applies to sample, synth and mixed selected voices; it is not sample-only.

Approximate quick-release multiplier is 0.912 per sample, with idle threshold about 0.0001. Starting at level 1 normally requires four 32-sample blocks before the next status pass can mark idle: about 2.67 ms at an assumed 48 kHz, plus scheduling and shutdown. This is not measured retrigger latency or an unconditional upper bound. The separate stock sample shutdown ramp is 32 samples, about 0.667 ms at 48 kHz.

## Original verified artifacts

| Role | Archive BIN name | Flash filename | SHA-256 |
|---|---|---|---|
| Voice-only fix | `voice_2.2.2.0.2.bin` | `PxUpdate_V2.2.2.0.2.bin` | `2ad5392eb842cbcd5c2e85e65ab42c16f1fac12d16b09c417a61761a8348bcbf` |

The voice-only BIN is 3,099,064 bytes. Voice-only application header, updater comparison and DSP screen report use 2.2.2.0.2; its application checksum is F44B. The separate M field remains 2.2.2. The voice-only build retains stock PIC and FPGA payloads.

Clean input is `PxUpdate_V2.2.2.0.0.bin`, SHA-256 `a4b304b3bb48ca933ae63c99c0098698c497ebfc7c38ab2a823b5e0df4919fa9`. QNX ELF is container slice `[0xD, 0xF0DA5)`, SHA-256 `7db8a8276f0bda34d22fdd2e8744b304dc7d62f80f9189836b107a4d7b178cff`. All code and unwind addresses below are x86-64 ELF virtual addresses, not container or ELF file offsets; runtime code addresses include the ELF load bias. Container slices and helper/metadata ranges use an exclusive end. Explicit byte spans such as `rbp-0x814..-0x811` include both endpoints.

## Implementation map

**Patch location:** QNX application (x86-64).

**Patch size:** 258 bytes of replacement helpers + 47 bytes of hook spans + a 4-byte diagnostic stub; 193 bytes of replacement unwind metadata. All reuse existing image space; no application or update-file growth.

Let L be CMessageAudioLoop and E = [L+0x298]. Individual software amp envelope is envelope 1, not envelope 0. Envelope 0 participates in cutoff control.

| State | Location |
|---|---|
| Individual quick-release byte | E + voice |
| Off-pending byte | E + 0x44 + voice |
| Envelope-1 state | E + 0x6C + voice*16 |
| Envelope-1 32-float buffer | [E+0x288] + (voice*4+1)*0x80 |
| Quiet mask/mutex/condition | L+0x3644 / +0x3648 / +0x3650 |
| Oscillator-close mask/mutex/condition | L+0x3658 / +0x365C / +0x3664 |
| Global startup mutex | 0x2A57A0 |

The first scan preserves stock voice selection and collects a bitmask instead of requesting oscillator closure. One quiet request waits in a predicate loop for coordinator acknowledgement. The second scan replays stock oscillator-close handling without another quiet request. Fresh activation acquires startup before sample setup and clears the selected quick-release/off-pending bytes. No forced envelope state or level write is added. No-restart legato retains its stock acquisition. Coordinator startup acquisition moves earlier so assignment and amp/stream scanning cannot observe half-completed activation.

| Stock hook | Replacement | Bytes |
|---|---|---:|
| 0x21399 | CALL 0x49FD4, batch initialization | 7 |
| 0x21489 | JMP 0x49FE6, collect voices | 5 |
| 0x215B8 | JMP 0x4A005, group wait | 7 |
| 0x216BF | JMP 0x4A038, fresh activation | 7 |
| 0x2174C | CALL 0x4A066, conditional lock | 5 |
| 0x1B49E | JMP 0x4A071, earlier coordinator lock | 11 |
| 0x1B7E5 | Five NOPs, remove old lock call | 5 |

Replacement helpers total 258 bytes: 185 bytes at `0x49FD4..0x4A08D` and a 73-byte quiet helper at `0x8FED0..0x8FF19`. Seven hook spans total 47 bytes. DebugPrintf becomes the four-byte stub `or eax,-1; ret` at `0x49FD0`. The quiet helper replaces suppressed diagnostic strings; existing executable/readable load mappings are retained. Scratch phase byte `rbp-0x817` and mask `rbp-0x814..-0x811` are free only within the audited note-path lifetime. Frame size is unchanged.

Startup is not held across quiet or oscillator-close waits. Coordinator nesting is startup then close/quiet; handler releases wait mutexes before acquiring startup. Quieting uses one request mask for the whole selected group to avoid serial per-voice delays. Shared envelope slots 32/33 are not directly cleared or quick-released.

## Unwind and placement ownership

193 bytes of replacement unwind metadata occupy `0x89C18..0x89D09` in a suppressed diagnostic pool. New records cover the stub/hooks and quiet helper; translated LSDA preserves the handler cleanup for added calls. The frame index grows from 838 to 839 entries using existing padding; its header moves from `0x91598` to `0x91590`. Loaded segments and original .eh_frame placement stay unchanged. Indexed lookup matters because the new records lie outside the original .eh_frame.

Audited DebugPrintf references use suppressed priorities 3/5 and return -1, matching the stub. Arbitrary computed callers are not globally excluded; the stub removes any unobserved priority-0..2 logging capability. Shutdown log persistence, exception routines and unrelated log helpers are retained.

## Recorded offline validation

- Candidate-loaded selection loop: 18 cases; fresh/legato/coordinator hooks: 7 cases.
- Actual firmware FDE lookup: 3,484 cases across two load biases; pointer decoder: 6 cases; CFI boundaries: 61 checked.
- Deterministic rebuild matched the candidate; 7 invalid-input rejection cases passed.
- ELF layout checks retained PT_LOAD layout and permissions. Logger comparisons: 6 cases; separate synth branch/position tests: 47 cases.
- Owner supplied an independent review supporting displaced instructions, liveness, voice bounds, lock pairing and unwind indexing. These are analysis checks, not additional hardware trials.

## Installation and validation limits

Use the filename `PxUpdate_V2.2.2.0.2.bin` in the USB root. Keep one intended update file there and remove its macOS AppleDouble (`._PxUpdate…`) companion after copying.

Hardware confirms effectiveness on the original reproducer, not exhaustive concurrency or timing coverage. Positive additive VCA modulation can leave output audible despite envelope silence. Sample preparation under startup can block on the RAM-file reader lock; target CPU headroom and deadlines were not measured. Quieting assumes a running coordinator, one requester and valid initialized pthread objects. Generic cancellation/forced-unwind safety was not added or demonstrated. Preserve these limits without reopening unrelated hardening work.

B1 is complete for the reported bug. For future integration, preserve its hook regions, scratch lifetime, lock pairing and unwind ownership. Do not repeat the historical design investigation unless a concrete regression requires it.

## Public implementation artifacts

Firmware BINs, extracted ELFs and generated binary artifacts are excluded from this public folder. Filenames and SHA-256 hashes above identify the privately held inputs and tested output.

The original B1 implementation and recorded checks are supplied under `prophet_x_combined_application_patch/`:

- [Helper assembly](prophet_x_combined_application_patch/analysis/diagnostic_space/placed.S) and [linker layout](prophet_x_combined_application_patch/analysis/diagnostic_space/placed.ld).
- [Application patch builder](prophet_x_combined_application_patch/analysis/combined_patch/build_application_patch.py) and [patch specification](prophet_x_combined_application_patch/analysis/combined_patch/patch_spec.json).
- [Build and test instructions](prophet_x_combined_application_patch/analysis/combined_patch/README.md).
- [Candidate test results](prophet_x_combined_application_patch/analysis/combined_patch/installed_candidate_test_results.json) and [builder test results](prophet_x_combined_application_patch/analysis/combined_patch/builder_test_results.json).
- [Unwind ownership audit](prophet_x_combined_application_patch/analysis/diagnostic_space/unwind_ownership_audit.json).

The builder reproduces the pre-packaging application candidate, SHA-256 `a47fa006e7f179b5860ff4e8d7e268dc3e5136c6e5cec3a7ec85087afe9e6b02`, using a privately supplied stock application. A local comparison confirmed that this candidate and the hardware-tested voice-only ELF differ at exactly two file offsets: `0x1F4E3` and `0x250EF`, both revision bytes changing from 0 to 2. All remaining bytes match. The application builder stops before versioning and packaging; the separate [B1 packaging script](packaging/package_b1.py) performs those steps.

Validation counts are recorded historical results; the test suites were not rerun for this documentation review. Historical pass notes and duplicate audit copies are retained privately. The hardware result above is the current status.

## PxUpdate packaging verification

**PASS:** reconstruction from the public patch specification and privately held stock firmware produces a byte-for-byte match to the hardware-tested `voice_2.2.2.0.2.bin`. The final application checksum is `0xF44B`; complete FPGA and PIC records remain identical to stock. Modified and truncated input rejection checks also passed. This is a new offline packaging check, not a new hardware test.

See the [exact container format and reproduction instructions](packaging/README.md), [packaging script](packaging/package_b1.py), and [verification report](packaging/verification_report.json). Firmware inputs and rebuilt outputs remain private.

## Complete supporting-file inventory

Every retained supporting file is linked below. Implementation, imported dependencies, test fixtures and saved evidence are distinguished by purpose; not every evidence file is required to build the feature. Original script layouts are retained so their relative imports remain intact. Firmware and generated binary inputs remain private, as described above. The [root checksum inventory](SHA256SUMS) covers this handover and all retained supporting files.

| File | Purpose |
|---|---|
| [packaging/README.md](packaging/README.md) | Supporting build/placement instructions; the branch handover is the status authority. |
| [packaging/package_b1.py](packaging/package_b1.py) | Incremental packaging/publication tool. |
| [packaging/verification_report.json](packaging/verification_report.json) | Saved validation, measurement or ownership evidence; not a new test run. |
| [prophet_x_combined_application_patch/analysis/combined_patch/ProphetX_voice_fade_candidate.manifest.json](prophet_x_combined_application_patch/analysis/combined_patch/ProphetX_voice_fade_candidate.manifest.json) | Saved patch/object/packaging identity and layout evidence. |
| [prophet_x_combined_application_patch/analysis/combined_patch/README.md](prophet_x_combined_application_patch/analysis/combined_patch/README.md) | Supporting build/placement instructions; the branch handover is the status authority. |
| [prophet_x_combined_application_patch/analysis/combined_patch/build_application_patch.py](prophet_x_combined_application_patch/analysis/combined_patch/build_application_patch.py) | Build/emission/layout tool or imported build dependency. |
| [prophet_x_combined_application_patch/analysis/combined_patch/builder_test_results.json](prophet_x_combined_application_patch/analysis/combined_patch/builder_test_results.json) | Saved validation, measurement or ownership evidence; not a new test run. |
| [prophet_x_combined_application_patch/analysis/combined_patch/installed_candidate_test_results.json](prophet_x_combined_application_patch/analysis/combined_patch/installed_candidate_test_results.json) | Saved validation, measurement or ownership evidence; not a new test run. |
| [prophet_x_combined_application_patch/analysis/combined_patch/patch_spec.json](prophet_x_combined_application_patch/analysis/combined_patch/patch_spec.json) | Expected original bytes and replacement patch specification. |
| [prophet_x_combined_application_patch/analysis/combined_patch/program_headers.txt](prophet_x_combined_application_patch/analysis/combined_patch/program_headers.txt) | Saved assembly/layout evidence. |
| [prophet_x_combined_application_patch/analysis/combined_patch/test_builder.py](prophet_x_combined_application_patch/analysis/combined_patch/test_builder.py) | Validation/test or ownership audit tool; uses the private inputs described in source. |
| [prophet_x_combined_application_patch/analysis/diagnostic_space/README.md](prophet_x_combined_application_patch/analysis/diagnostic_space/README.md) | Supporting build/placement instructions; the branch handover is the status authority. |
| [prophet_x_combined_application_patch/analysis/diagnostic_space/audit_space.py](prophet_x_combined_application_patch/analysis/diagnostic_space/audit_space.py) | Validation/test or ownership audit tool; uses the private inputs described in source. |
| [prophet_x_combined_application_patch/analysis/diagnostic_space/audit_unwind_ownership.py](prophet_x_combined_application_patch/analysis/diagnostic_space/audit_unwind_ownership.py) | Validation/test or ownership audit tool; uses the private inputs described in source. |
| [prophet_x_combined_application_patch/analysis/diagnostic_space/build_unwind_trial.py](prophet_x_combined_application_patch/analysis/diagnostic_space/build_unwind_trial.py) | Build/emission/layout tool or imported build dependency. |
| [prophet_x_combined_application_patch/analysis/diagnostic_space/placed.S](prophet_x_combined_application_patch/analysis/diagnostic_space/placed.S) | Helper/shim assembly or generated target layout. |
| [prophet_x_combined_application_patch/analysis/diagnostic_space/placed.ld](prophet_x_combined_application_patch/analysis/diagnostic_space/placed.ld) | Linker placement for new helper assembly. |
| [prophet_x_combined_application_patch/analysis/diagnostic_space/placement_manifest.json](prophet_x_combined_application_patch/analysis/diagnostic_space/placement_manifest.json) | Saved patch/object/packaging identity and layout evidence. |
| [prophet_x_combined_application_patch/analysis/diagnostic_space/reference_audit.json](prophet_x_combined_application_patch/analysis/diagnostic_space/reference_audit.json) | Saved validation, measurement or ownership evidence; not a new test run. |
| [prophet_x_combined_application_patch/analysis/diagnostic_space/test_placed_activation.py](prophet_x_combined_application_patch/analysis/diagnostic_space/test_placed_activation.py) | Validation/test or ownership audit tool; uses the private inputs described in source. |
| [prophet_x_combined_application_patch/analysis/diagnostic_space/test_placed_batch.py](prophet_x_combined_application_patch/analysis/diagnostic_space/test_placed_batch.py) | Validation/test or ownership audit tool; uses the private inputs described in source. |
| [prophet_x_combined_application_patch/analysis/diagnostic_space/test_unwind_lookup.py](prophet_x_combined_application_patch/analysis/diagnostic_space/test_unwind_lookup.py) | Validation/test or ownership audit tool; uses the private inputs described in source. |
| [prophet_x_combined_application_patch/analysis/diagnostic_space/unwind_lookup_results.json](prophet_x_combined_application_patch/analysis/diagnostic_space/unwind_lookup_results.json) | Saved validation, measurement or ownership evidence; not a new test run. |
| [prophet_x_combined_application_patch/analysis/diagnostic_space/unwind_manifest.json](prophet_x_combined_application_patch/analysis/diagnostic_space/unwind_manifest.json) | Saved patch/object/packaging identity and layout evidence. |
| [prophet_x_combined_application_patch/analysis/diagnostic_space/unwind_ownership_audit.json](prophet_x_combined_application_patch/analysis/diagnostic_space/unwind_ownership_audit.json) | Saved validation, measurement or ownership evidence; not a new test run. |
