# B4 — minimal QNX implementation and validation

## Delivered result

Implemented the authoritative scope in `readme_B4_minimal_qnx_placement_plan.md`. The implementation expands QNX to97 total groups, preserves existing IDs and ordinary supported-input behavior, routes32 extra size entries into owned BSS, adds narrow bounds/count-representation guards and carries forward the release-category cursor correction separately.

Artifacts:

- `patch_b4_minimal_qnx.py` — reproducible, stock-only patcher with original-byte guards.
- `b4_minimal_qnx_helpers.s` — implemented helper source; only image-local branches/LEAs, no new calls/imports/stack adjustments.
- `b4_minimal_qnx_patch_manifest.json` —40 guarded entries, resolved helper map and32 resolved relocations, original/replacement bytes, input/output/source/helper hashes.
- `b4_minimal_qnx_validation.elf` — authorized isolated patched ELF; **not an update container**.
- `validate_b4_minimal_qnx.py` — native x86-64 integration harness.
- `b4_minimal_qnx_validation_results.json` —149 passing checks and explicit limitations.

No stock input was modified. No firmware update was packaged and no deferred hardening was implemented. Broader designs remain superseded.

## Identity and reproducibility

| Item | Value |
|---|---|
| Stock container | `PxUpdate_V2.2.2.0.0.bin` |
| Stock container SHA-256 | `a4b304b3bb48ca933ae63c99c0098698c497ebfc7c38ab2a823b5e0df4919fa9` |
| Stock QNX ELF SHA-256 | `7db8a8276f0bda34d22fdd2e8744b304dc7d62f80f9189836b107a4d7b178cff` |
| Patched isolated ELF SHA-256 | `8e207287d78130dcb60470b16e14464be237fa3d89a755e193d92e3568e4f50a` |
| Resolved helper bytes SHA-256 | `7b0e9db031364b553542631229eb1ecc6c99a2561570661b7eecd3d6561f8078` |
| ELF size |986,520 bytes, unchanged |
| Helper size/reservation |359/512 bytes |
| Bytes differing from stock |473 |

The patcher accepts the exact stock container or the exact stock ELF. It verifies the accepted SHA-256 before patching, validates every original instruction/field and the entire zero-filled512-byte helper reservation, resolves all object relocations, checks for overlapping/unmanifested edits and verifies the fixed frame-cache instruction remains stock. Outputs and input must be distinct; outputs use exclusive creation and existing files are not overwritten. All guards and relocation work complete in memory before output creation.

Assembly uses clang's x86-64 ELF assembler. No C++ toolchain/runtime linkage is added. Temporary relocatable objects are deleted; the emitted ELF is produced by guarded byte edits, not a full firmware build. The manifest records source/helper hashes. The harness regenerates the patch in memory and verifies byte-for-byte reproducibility.

Example reproduction with new output filenames:

```sh
python3 patch_b4_minimal_qnx.py \
  --output /private/tmp/b4_minimal_repro.elf \
  --manifest /private/tmp/b4_minimal_repro_manifest.json
python3-intel64 validate_b4_minimal_qnx.py /private/tmp/b4_minimal_repro.elf
```

The harness needs an x86-64 Python runtime; this host supplies `python3-intel64` under Rosetta. It checks the supplied ELF against the delivered manifest before executing. This command executes isolated code with boundary mocks; it does not launch QNX or package an update.

## Patch manifest summary

Exact guarded hex bytes and file offsets for every entry are in `b4_minimal_qnx_patch_manifest.json`. Addresses below are ELF virtual addresses; loaded addresses are a common load bias plus VA.

### Arrays, indexing and folder changes

Owner allocation0x16181 changes0x33D0→0x4D50. Counts occupy[0,0x19C4), four-byte padding[0x19C4,0x19C8), and heads[0x19C8,0x4D50). Growth is6,528 bytes. Existing new/delete behavior and0x408-byte nodes are retained. The constructor initializes the complete count/head arrays; its unused alignment padding remains untouched as stock does, rather than being treated as a control field.

| Sites | Implemented changes |
|---|---|
|0x33390 /0x333AF | Constructor outer end0x2288→0x3388; head base0x1148→0x19C8 |
|0x33C10 /0x33C72 | Accessor max group64→96; categories still0–16 |
|0x33C2A | Scaled head-base constant0x228→0x338; existing final+8 retained |
|0x336E4 | Index name-search end65→97 |
|0x33DDE | Head alias owner+0x19C8; count alias unchanged |
|0x33E9E | Post-index size-refresh end65→97 |
|0x33CFB /0x33D30 /0x33D6C | Release head base changes and end65→97 |
|0x3518C /0x351CC /0x35410 /0x3552D | All enumerated direct head loads use+0x19C8 |
|0x35216 /0x35650 | Parser/update group-loop ends65→97 |
|0x2E01E | User-folder endpoint+0x208→+0x308; starting ID41 and stock folder/category behavior retained |
|0x1542A | Import name-search endpoint+0x208→+0x308 |
|0x15D91 | Delete max group64→96 |

**Separate cleanup correction at0x33D45:** replace `44 8B 64 24 04` with `45 31 E4 90 90`, resetting the category cursor before the next released group. This is an explicit behavioral fix in the changed routine, not an effect of increasing the group limit. The actual-stock negative control frees the first fixture group only; the patched routine frees both.

### Helper placement and hooks

| Helper / VA | Bytes | Hook |
|---|---:|---:|
| Extension initialization /0x9D480 |42|0x7BC0 |
| Size front end /0x9D4AA |49|0x15320 |
| Size-store base /0x9D4DB |25|0x15278 |
| Copy cache base /0x9D4F4 |25|0x15BB1 |
| Delete cache base /0x9D50D |25|0x15E22 |
| Direct-size guard /0x9D526 |18|call0x15BCA |
| Copy group guard /0x9D538 |23|0x15AF8 |
| Release scope guard /0x9D54F |40|0x33CB1 |
| Index scope guard /0x9D577 |40|0x33DF1 |
| Update scope guard /0x9D59F |43|0x3535C |
| Count reply guard /0x9D5CA |29|0x22C92 |

Helpers end at0x9D5E7 within reserved[0x9D480,0x9D680). They preserve the planned register/stock-continuation contracts. The redirected direct-size call remains a call, followed by a tail jump into the original backend; it does not use the caching front end. This preserves the copy operation's force-walk behavior. Scope guards preserve explicit -1 sentinels and reject out-of-range nonsentinel group/category inputs. Count replies retain0x4012 for full-width values0–255; larger/negative-as-unsigned counts send existing0x403C,0 before any successful narrowing.

Size-cache routing keeps groups0–64 at0x2A4A20+8*g and routes65–96 to0x2B1EB0+8*(g−65). Extension-bias0x2B1CA8 is only an arithmetic base for the unchanged scaled-index instruction, never independently dereferenced. All32 extension entries initialize to UINT64_MAX. Stock zero, unknown sentinel, USB bypass, force/cache behavior and copy/delete store timing remain unchanged.

### ELF memory/end edits

| Field / file offset | Old→new |
|---|---|
| RX p_filesz /0xD0 |0x9D480→0x9D680 |
| RX p_memsz /0xD8 |0x9D480→0x9D680 |
| RW p_memsz /0x110 |0x13BF8→0x13CF8 |
| `.bss` sh_size, section24 |0xDA10→0xDB10 |
| Dynamic `_end` value /0x1398 |0x2B1EB0→0x2B1FB0 |
| Static `_end` value /0xE63F8 |0x2B1EB0→0x2B1FB0 |

The extension is exactly[0x2B1EB0,0x2B1FB0),256 bytes. Program headers/count, `.interp`, original loaded VAs, RW file offset/filesz, alignments, dynamic tables, imports, relocations, existing unwind header and file length remain unchanged. The helper reservation is explicitly zero-byte guarded. No additional section header or executable allocation policy is introduced.

**Fixed frame-cache endpoint0x4EA94 remains `4C 8D 05 15 34 26 00`, still resolving to0x2B1EB0.** The patcher enforces this separately; updating `_end` does not retarget that instruction.

## Validation results

149 focused checks passed against the actual isolated stock/patched machine code. This is native x86-64 execution under Rosetta, not an interpretation of a semantic model. Tests use freshly mapped ELF PT_LOAD contents, apply the relative/data-import substitutions required by the harness, and invoke the existing functions/continuations.

Coverage includes:

- Real constructor array initialization and end canaries; unchanged padding behavior.
- Real extension-plus-stock initializers; all97 unknown cache entries and intact neighboring accumulator/extension-end words.
- Count/folder accessors at groups64/65/96, categories0/16; group97, category17 and other negative bounds.
- Real linked-list release/delete-call continuations, two-node chains, invalid-input no-mutation checks and explicit all-category/all-group sentinels. All-group behavior ignores category as stock does.
- Release-cursor negative control against stock and corrected cleanup across multiple groups.
- HD hit/miss/store routing, valid zero, retained cached-force behavior, USB bypass, delete zero stores and copy invalidation/direct backend refresh for64/65/96. Invalid group97 cannot write cache storage.
- Real index owner/release/refresh body and aliases for scoped, all-category and all-group requests; invalid index requests retain live nodes. Empty full walks refresh throughu63.
- Real index callback allocation/sorted insertion at64/65/96 and rejection of97. Synthetic `.grp` fixtures produce ordered instrument chains.
- Update guards and actual empty-index continuations; unchanged worker argument layout.
- Real new-user-folder name loop, using mocked directory calls, spanningu08–u63 with56 group paths.
- Count guard, stock send serialization and owner epilogue for counts0/255/256/65536/UINT32_MAX, groups64/65/96 and categories0/16.
- Stock differential tests for supported count replies, count accessor, size zero/nonzero results and index paths at group64.
- Deterministic patch regeneration; altered allocation/helper/end/frame-end bytes rejected; nonstock ELF rejected; stock container hash still unchanged.

No patch implementation failure remains in these cases. Two retained stock behaviors are explicitly recognized by the fixtures: the constructor does not clear its padding, and direct force refresh obtains its value through the walker rather than the GroupInfo fast path. The tests do not reinterpret those behaviors as hardening requirements.

### Execution limits

Filesystem/GroupInfo/ZIP outcomes are not rewritten. The harness supplies host-backed new, a recording/nonfreeing delete, mocked traversal/GroupInfo/copy/delete/directory boundaries, and a mock transport vtable. Real array operations, callback sorting, stock prologues/epilogues, cache accesses and reply serialization execute. The count entry shim preserves the actual HandleMessage frame but bypasses unrelated playback/dispatcher setup before entering the actual count request body. These substitutions exist only in harness memory and are never written to the output ELF.

This is not execution under the device's QNX kernel/ldqnx/libc/libc++, and the mapping harness does not enforce the actual loader's segment permissions/alignment policy. Allocation failure/exception unwinding, asynchronous backtraces at thunk PCs, worker scheduling and real filesystem/transport activity were not executed. The import validator endpoint and parser direct-load edits are byte-guarded implementation changes; a complete ZIP-import operation and live parse-worker/dictionary workload are not claimed as validated.

## Remaining integration work

1. Integrate with the minimal PIC97-group addressing/population work and retain the accepted fixed name-region bound/prefix preflight before writes. This QNX implementation alone does not activate the extra groups on PIC. No capacity negotiation or journaling is added.
2. Run the applicable end-to-end import/index/reload and loader checks when the components are combined. Preserve ordinary allocation/error behavior; validation limits do not mandate the deferred filesystem, leases, retries or exception-catching designs.
3. Keep the separate B4 test build based on clean2.2.2.0.0. The isolated ELF here is a stock-based component artifact, not a packaged test update.
4. Compare the actual intended voice_sysex binary/source before merging. Those branch inputs remain unavailable; historical overlap evidence is not current merge certification. Reconcile hook bytes and code/BSS ownership rather than replacing its QNX image wholesale.

No firmware packaging or flashing instructions follow. Stop at this implementation report.
