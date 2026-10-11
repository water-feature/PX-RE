# B4 - Expanded user sample slots (abandoned)

Technical handover for the abandoned B4 investigation. The isolated QNX component was implemented; PIC expansion remained at design/interpreter-harness stage. B4 is excluded from the combined firmware chain.

**Firmware:** No packaged B4 update. The isolated QNX candidate targets factory `2.2.2.0.0`.

**Hardware: NOT TESTED**: The QNX component passed 149 focused native-code checks with mocked system boundaries. No completed combined update or hardware validation is established.

## Sources and reproduction

- [QNX patcher](source/patch_b4_minimal_qnx.py), [helper assembly](source/b4_minimal_qnx_helpers.s) and [validator](source/validate_b4_minimal_qnx.py) reproduce the isolated QNX candidate from the exact factory input. Commands and input hashes are in the main guide.
- [Patch manifest](validation/b4_minimal_qnx_patch_manifest.json), [validation results](validation/b4_minimal_qnx_validation_results.json) and [helper sizes](validation/b4_minimal_qnx_helper_sizes.json) retain the original implementation evidence.
- [Split-addressing harness](source/b4_split_addressing_harness.py), [control interpreter](source/b4_control_integration_harness.py) and [raw instruction reader](source/b4_split_raw_inspect.py) provide the modeled PIC checks. The interpreter reads the included [control design](historical/handovers/readme_B4_control_patch_design.md).
- [Control boundary model](source/b4_control_boundary_model.py) and [population model](source/b4_extension_population_model.py) support the documented PIC design. Saved results, split hook words and instruction listings are under `validation/`.

For PIC harnesses, set `B4_PRIVATE_INPUTS` to a private directory containing `stock_pic_2.2.2.0.0.bin` with SHA-256 `14e9c9b9dc562b0384fc43b3c5e0eb7fea84a5792d1a19b9b3ea8276ef7646f5`. If unset, inputs are read from the current directory. Run from a private output directory so regenerated reports stay outside the public bundle. The control interpreter uses `--entry-hook` to select the revised entry-hook overlay. PIC helper locations are synthetic; these tests do not produce an installable update.

## Layout

- `source/`: QNX implementation and PIC design/test utilities.
- `validation/`: original manifests, results and focused instruction evidence.
- `historical/handovers/`: earlier designs and findings; the current guide governs scope.
- `historical/passes/` and `historical/workspace/`: earlier analysis scripts and results. Some proposals were superseded.
- `support_manifest.json` and `SHA256SUMS`: inventory of the published files. Original source hashes in historical reports describe their original checkpoints.

Factory and patched firmware, ELF files, object files and bulk disassemblies are excluded. Reproduction requires privately supplied stock firmware. The QNX validator executes isolated native x86-64 code with mocked system boundaries; its saved results do not establish QNX runtime or hardware compatibility.

## Read this first: current scope and authority

The goal is **64 user sample groups,97 total internal groups**, preserving existing IDs and ordinary stock behavior. This document is authoritative for resumption. `readme_B4_minimal_qnx_placement_plan.md` defines the implemented QNX scope; `readme_B4_minimal_qnx_implementation.md` records its implementation evidence. Older documents are evidence/proposals, not additional implementation requirements.

Retain required storage, addressing, bounds, indexing, folder and initialization changes; protection against expansion-induced table/count/name-region overflow; and small understood corrections in already changed code. The QNX release-category cursor correction is explicitly retained, separately from increasing the group limit.

Defer general filesystem/ZIP/GroupInfo error-handling rewrites; reader leases, worker synchronization redesign and epochs; new exception-catching APIs/imports; elaborate activation negotiation/journaling; broad retry, copy and arithmetic hardening. An old “blocker” is not automatically mandatory. Carry a deferred change forward only with an identified concrete expansion dependency. Do not restart PIC allocator/USB/startup/ownership audits or earlier validation matrices.

**Build requirements:** eventually produce a separate B4 test update from clean 2.2.2.0.0 containing this feature only. Later merge with the actual intended `voice_sysex` branch while preserving that feature's code and storage ownership. No update has been packaged in this workspace. No flashing instructions are authorized. Stock inputs must remain unchanged. Creation of the isolated QNX ELF was explicitly authorized; further packaging is a separate assignment.

## Current task boundary

The last concrete completed assignment was minimal QNX implementation/validation. PIC implementation remains proposed, as distinguished below.

## Inputs, IDs and addresses

| Input | Path / accepted identity |
|---|---|
| Clean container | `PxUpdate_V2.2.2.0.0.bin`;3,099,064 bytes; SHA256 `a4b304b3bb48ca933ae63c99c0098698c497ebfc7c38ab2a823b5e0df4919fa9` |
| Stock QNX | Container slice[0xD,0xF0DA5),986,520 bytes; SHA256 `7db8a8276f0bda34d22fdd2e8744b304dc7d62f80f9189836b107a4d7b178cff`; ELF64 x86-64 ET_DYN, entry0x81A0; interpreter `/usr/lib/ldqnx-64.so.2` |
| Stock PIC | `stock_pic_2.2.2.0.0.bin`;530,784 bytes/0x81960; SHA256 `14e9c9b9dc562b0384fc43b3c5e0eb7fea84a5792d1a19b9b3ea8276ef7646f5`; already extracted, do not extract again |

PIC is the accepted32-bit little-endian MIPS/DSP payload based at0x9D000000, through0x9D08195F. QNX addresses are ELF VAs, not PIC/container offsets. Verify the connected program/base if Ghidra is needed; do not import another guessed processor/address image.

IDs:0=f00;1–8=u00–u07;9–40=p00–p31;41–64=u08–u31;65–96=u32–u63. Existing QNX name table has133 names, including97/u64, but supported capacity ends at96. Categories0–16. Existing SysEx/NRPN representations can carry96; do not revive an assumed7-bit group-ID ceiling.

## QNX: implemented, tested component

**Patch location:** QNX application implemented; PIC side remains a design/interpreter model, with no placed firmware implementation.

**Patch size:** QNX: 359 helper-code bytes in a 512-byte RX reservation; 473 actual changed ELF bytes including hooks and layout metadata. ELF length is unchanged. PIC: no installed patch size; synthetic harness helpers are not a deployable allocation.

The table records the original implementation hashes. Public sources are in `source/`; saved manifests and results are in `validation/`. Portable input handling changes some source hashes; `SHA256SUMS` identifies the published files. The candidate ELF is excluded from the public bundle.

| Artifact | SHA256 |
|---|---|
| `patch_b4_minimal_qnx.py` | `d181c457b088daf11528d7a0ea08edeff1709742e7b1e76cd9756f5dc8c272d4` |
| `b4_minimal_qnx_helpers.s` | `dc6f0abf054b62595ce79d8f8b29244162aab8565245cb8dc8118088c6797b64` |
| `b4_minimal_qnx_patch_manifest.json` | `5d1af7fbc9d07ea42c4c1a21a2c846ceadce664bc21e7c8d6cdc9de876d35af0` |
| `b4_minimal_qnx_validation.elf` | `8e207287d78130dcb60470b16e14464be237fa3d89a755e193d92e3568e4f50a` |
| `validate_b4_minimal_qnx.py` | `ca984aba197c43a98ea2f52519e242f53eb95816cd9d1a0764445a99620c47e0` |
| `b4_minimal_qnx_validation_results.json` | `210670dc402518fcf74959f9098cecef83c02fafde61ae209739a9b6b8bec6f8` |

The patcher uses accepted input hashes, original instruction/field guards and a zero-byte guard over the full512-byte helper reservation. It resolves32 image-local relocations, emits40 manifest entries and changes473 actual bytes. Regeneration matched the isolated ELF byte-for-byte. It refuses nonstock input, input/output aliasing and overwriting existing outputs. Do not apply it directly to a modified voice_sysex image.

Implemented layouts:

- CSampleGroups allocation0x4D50 at0x16181: counts[0,0x19C4),padding4,heads[0x19C8,0x4D50). Growth6,528 bytes. Constructor/count/head/accessor/index/parser/update/release references changed together. No validity/lease/worker metadata.
- Stock size cache0x2A4A20–0x2A4C28 retains groups0–64. New32 uint64 entries at0x2B1EB0–0x2B1FB0,256 bytes, initialize to UINT64_MAX. Groups65–96 split to the extension; stock accumulator stays0x2A4C28. No USB cache or changed force behavior.
- Helpers[0x9D480,0x9D5E7),359 bytes, inside declared512-byte RX extension ending0x9D680. No file growth, additional program headers, dynamic-table relocation, imports or new throwing calls.
- RX filesz/memsz0x9D680; RW memsz0x13CF8; `.bss` size0xDB10; dynamic/static `_end`0x2B1FB0. Original VAs, file segment offsets, alignments, headers/.interp/dynamic tables remain unchanged.
- **Frame-cache instruction0x4EA94 remains stock and points to0x2B1EB0.** It is a fixed-array endpoint, not the new BSS end. Never retarget it when changing `_end`.
- Group bounds0–96/category0–16; explicit -1 release/index/update sentinels retained; invalid nonsentinels rejected. New-folder/import-name endpoints cover97 names.
- Full-width count reply guard accepts0–255 before wire narrowing; other counts send existing0x403C,0. This is numeric overflow protection, not a checked filesystem API.
- **Separate release correction0x33D45:** `44 8B 64 24 04`→`45 31 E4 90 90`, reset category cursor before next released group.

Accepted validation:149 focused checks execute actual mapped x86-64 stock/patched code under Rosetta. Boundaries64/65/96/97, categories0/16/17, explicit sentinels, real linked-list release, sorted index callback, cache initialization/routing/copy/delete continuations, count representation limits, selected stock differentials and negative patch guards pass.

Limits: mocked filesystem/GroupInfo/traversal and transport boundaries; host-backed new/recording delete; no QNX kernel/ldqnx/runtime permission test, allocation exception, live workers or complete ZIP import. Count harness uses the real owner frame/count body/send/epilogue while bypassing unrelated dispatcher setup in memory. Mocks are absent from the emitted ELF. Do not claim this activates PIC97 groups.

Reproduction, only when needed—not to rerun completed checks during handover review:

```sh
# Run from the B4 folder; keep all inputs and generated firmware private.
python3 source/patch_b4_minimal_qnx.py \
  --input /path/to/private-workspace/PxUpdate_V2.2.2.0.0.bin \
  --output /path/to/private-workspace/b4_minimal_repro.elf \
  --manifest /path/to/private-workspace/b4_minimal_repro_manifest.json
python3-intel64 source/validate_b4_minimal_qnx.py \
  /path/to/private-workspace/b4_minimal_repro.elf \
  --input /path/to/private-workspace/PxUpdate_V2.2.2.0.0.bin \
  --manifest /path/to/private-workspace/b4_minimal_repro_manifest.json \
  --results /path/to/private-workspace/b4_minimal_repro_results.json
```

Use fresh filenames; existing outputs are refused. Host clang's x86-64 ELF assembler is required. The native validation harness needs x86-64 Python (for example, `python3-intel64` under Rosetta on macOS). These commands do not package an update.

## PIC: accepted findings, not a placed implementation

No stock PIC image is patched. Existing PIC work consists of instruction designs and memory-only/model overlays. Synthetic0x9F000000 helper labels are **not** executable placement approvals.

### Storage and control proposal

Keep stock count/index rows[0x80037E90,0x8003A118),65×17×8 bytes, and stock sizes[0x8003A118,0x8003A21C),65×4. Additional32 groups require one4,480-byte/0x1180 extension E:

```
E+[0,0x1100): 32*17 pairs (uint32 count,uint32 prefix index)
E+[0x1100,0x1180): 32 uint32 size entries
```

Proposed persistent control record: pointer0x80057AD8, state0x80057ADC; physical[0x57AD8,0x57AE0), uncached aliases0xA0057AD8/ADC. It is transferred from the heap, not presumed spare RAM. Proposed heap[0x80053AE0,0x80057AD8),0x3FF8 bytes. Provider size at0x9D081868 and default size at0x9D07FB40 must exclude these bytes **before allocation**. Stock malloc0x9D07EB84 returnsNULL on exhaustion; free0x9D0817C0; sbrk0x9D080B98. No unproven stack headroom is used.

Current control baseline is the revised **original DINIT-entry interception**, not the obsolete cold-call wrapper: hook0x9D081090/94 to0x9D001240, clear state then pointer, replay `addu v1,ra,zero` and `lui t0,0x9D00`, resume0x9D081098. Cold target construction0x9D0010D4/D8 stays stock. Proposed seven-word trampoline occupies0x9D001240–125C. Guarded-sbrk candidate begins0x9D001280. These designs have not been written into a PIC binary.

Accepted integration results in `b4_control_entry_hook_results.json`: actual stock DINIT/malloc/sbrk/free executed through interpreter overlays; allocation4480 succeeded, exhaustion and direct-DINIT invalidation passed; all32 DINIT register effects and non-control memory matched stock. Recorded E=0x80053AE8 is an observed allocation example, **not a fixed address**. The historical cold-only-hook negative control is obsolete. Allocator-only/interior resets would need invalidation if introduced/established on the relevant lifetime path; the simulated reset hazard does not prove an extra stock caller.

The94-word defensive sbrk guard and broad lifetime/ownership audit requirements are not automatically mandatory under narrowed scope. Before retaining that guard, identify the concrete reserved-byte exclusion dependency it addresses beyond the changed provider/default paths. Do not restart a broad allocator audit to satisfy historical prose.

### Split addressing and consumers

For g0–64 use stock tables;65–96 use E offsets based on g−65. Check unsigned g<97,c<17 before arithmetic. Invalid/unavailable count returns1 (PIC includes instrument0), not0/−1; unavailable index is−1 and size is0. Preserve stock IDs even if browsing order changes.

Exact known PIC integration anchors:

| Role | Stock locations |
|---|---|
| Count getter /availability |0x9D0792E0 /0x9D079300 |
| Direct selected-name index | arithmetic0x9D041178–18C, load0x9D041190 |
| Additional shared-name index | arithmetic0x9D041EA0–EB8, load0x9D041EBC |
| Stock count/index loader |0x9D040ED8; defaults0x9D040FF8/FFC; marked-slot handling0x9D04102C–1044 |
| Size initialization |0x9D079A08; loop count0x9D079A30; store0x9D079A44 and delay increment0x9D079A4C |
| Import size store | intercept before shift0x9D01B8DC; address/store0x9D01B8E8–F4 |
| Renderer size read |0x9D034280 /0x9D03428C |
| Group parameter maxima |0x9D047630 /0x9D04793C, stock64→96 when expansion usable |
| Limiter/bulk sanitizer |0x9D04D4FC /0x9D04D6D4; setter0x9D04DACC |
| Selector permutations |0x9D080E2C /0x9D080E60; existing mappings collapse larger IDs to64 |
| Import cursor limits |0x9D01B7C4 /0x9D01B9B8, target95 where cursor+1 mapping requires it |
| Count/name export bounds |0x9D07499C /0x9D0749F0, end0x9D074AAC |

`b4_split_addressing_harness.py`, `b4_split_addressing_hooks.json`, `b4_split_addressing_instructions.txt` contain the exact modeled helpers/hook words. Accepted120 boundary-state rows passed, including real stock getter callers, direct name windows, loader and size initialization. It uses synthetic helper locations and older proposed readiness bits; neither the PCs nor every bit/protocol policy is binding for minimal implementation. The supporting interpreter modules are included in `source/`. To regenerate this evidence, set `B4_PRIVATE_INPUTS` to the private directory holding the exact stock PIC, change into a private output directory, and run the published `source/b4_split_addressing_harness.py` by its path. Generated instruction and hook files go to the current directory; the script prints the result JSON. It does not emit a firmware image.

### Population, persistent page and overflow

Use existing count request0x9D079978/opcode0x4012. QNX returns N real instruments; PIC count=N+1. Category prefix advances byN+1, including the instrument-zero placeholder even in an empty cell. Nonempty index uses matching global prefix; empty index is−1. Count collection and name emission must agree; do not restart prefix at65.

Count page remains4KiB at[0x5FD000,0x5FE000). Legacy unmarked layout has41×17 bytes; stock0xFF-marked layout has65×17. A proposed appended97 layout uses1650 bytes including marker, preserving the first65 groups. **0xFF does not distinguish65 from97.** Do not treat erased/trailing bytes as valid extra counts or change the loader to read97 solely on that marker. Qualification of expanded metadata across cold boot/reload remains an implementation decision; a live97-group reconstruction is a proposal, not implemented persistence.

Numeric bounds are concrete expansion requirements: raw counts0–255 before byte serialization; total name demand<=65,536 records; prefix/range checks before serial writes. Accepted population tests reject malformed/out-of-range counts and overflow with zero modeled serial operations, admit exact capacity and preserve earlier-group prefixes. These results are in `b4_extension_population_results.json`; do not re-run them just to reconfirm settled arithmetic.

Integration anchors: count generator0x9D042A8C, category/group bounds0x9D042B04/B08, query0x9D042B14, byte store0x9D042B28, pre-erase boundary0x9D042B38; existing count commit0x9D042B3C–5C. Name builder0x9D042B80 queries at0x9D042CA0; group loop0x9D042DC8; caller reload0x9D042DCC. Import sequence0x9D01B904/B90C/B914 invokes count generation, name building, reload. Insert expansion preflight before destructive writes and ensure producer/loader/split rows use matching counts. Reusing one collected snapshot is an accepted design proposal, not a placed coordinator.

Sizes use existing requests0x9D079744/opcodes0x4037/0x4038, decimalMB. General checked-backend, retry, four size-caller abort rewrites and transactional rollback are deferred. Do not promise backend enumeration validity from a delivered scalar.

## Remaining implementation sequence and gaps

1. Await a new implementation assignment. 
2. Implement/review the minimal owned PIC root/extension lifetime and its exact placement. Preserve stock tables, exclude control bytes before allocation and fail without exposing uninitialized extra IDs. QNX now supports0–96; PIC may remain locally stock-limited on allocation failure without requiring new capacity negotiation or dynamic QNX table rollback.
3. Physically place/relocate split helpers, then implement all listed readers/writers and parameter/selector/import/export bounds together. Synthetic helper PCs cannot be used in a real image. Confirm candidate space ownership only where required for the chosen helpers, not a new whole-firmware audit.
4. Implement matching97-group population/count/name handling with pre-write overflow rejection; decide how old65-group pages and cold/reload expanded qualification are distinguished. No automatic journal/new protocol requirement follows.
5. Validate the implemented PIC component with actual stock continuations and applicable failure/readiness boundaries, then combine components for the separate stock-based test build when packaging is explicitly assigned. QNX already passes its isolated checks; do not repeat those without a relevant change.
6. Obtain actual voice_sysex target inputs before merge comparison. Their absence blocks **merge certification**, not standalone B4 implementation.

Genuine gaps are unplaced/unimplemented PIC code, exact allocation/publication/reload integration and count-page qualification. Target QNX execution/live import-worker integration remains untested, as recorded above. Absent general error APIs, exception exports, transaction/journal machinery, measured universal stack bound or new QNX synchronization design are **not automatically blockers**.

## Superseded documents: use as evidence only

- `readme_B4_qnx97_design.md`: its counts/head/site evidence survives;0x53E0 object,0x718 SizeOwner, validity arrays, gates/epochs/worker redesign and checked filesystem APIs do not.
- `readme_B4_qnx_elf_placement_plan.md`: fixed frame-cache endpoint finding survives;96KiB RX, relocated dynamic tables, import slots, combined unwind header and2MiB growth are superseded.
- `readme_B4_extension_activation_design.md`: storage/failure-consistency anchors may be useful; elaborate session activation, capacity agreement and journaling are deferred proposals.
- `readme_B4_checked_operations_design.md` /`readme_B4_size_caller_failure_paths.md`: numeric overflow evidence remains relevant; broad checked backend/retry/caller-abort designs are not mandatory current implementation.
- Original `readme_B4_control_patch_design.md`: cold-call-only DINIT hook is superseded by `readme_B4_control_patch_design_revised.md`. Revised controls are still a PIC proposal/overlay, not patched firmware.
- Startup/USB/reentry/stack investigations and historical `voice_sysex` comparison remain background. Do not reopen them to resume97-group work.

## Completion log / next update

- Minimal QNX component complete: isolated guarded ELF,149 native-code checks; artifact identities recorded above.
- Current handover created without repeating tests/analysis.
- PIC work is currently paused. On completion of a future assigned task, update implemented-versus-proposed status, artifacts/hashes, validation limits and remaining work here.
