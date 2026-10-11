# B4 — concrete QNX ELF placement plan

## Recommendation and evidence status

Extend the existing RX PT_LOAD by a declared 0x18000-byte reservation, shift the original file tail by 0x200000, and extend the existing RW zero-fill tail. Keep every original loaded virtual address, eight program headers, `.interp`, entry point, GOT and PLT address unchanged. Place B4SizeOwner exactly at [0x2B1EB0,0x2B25C8). Reserve another 24 bytes immediately after it for three exception-helper import slots. This plan adds no executable segment or program header.

This is an ELF placement design, not a patched ELF, linked firmware or firmware build. It uses `readme_B4_qnx97_design.md` as the implementation baseline. The release-category cursor correction remains a **separate required cleanup change**: reset the category cursor for each released group. Increasing the group bound alone does not perform that cleanup. Its accepted evidence was not reinvestigated.

Evidence levels: stock header/symbol/relocation values and the unwinder endpoint consumer are directly observed; segment mapping and zero fill are supported by the ELF ABI and QNX documentation; actual execution on this device's loader/runtime remains untested. No PIC, allocator, USB or startup audit was repeated. Representative standalone objects were compiled solely to measure helper code/metadata, then deleted from temporary storage; no firmware input was changed or linked.

Stock input is the accepted QNX slice `[0xD,0xF0DA5)` in `PxUpdate_V2.2.2.0.0.bin`, length0xF0D98, SHA-256 `7db8a8276f0bda34d22fdd2e8744b304dc7d62f80f9189836b107a4d7b178cff`. It is ELF64 x86-64 **ET_DYN**, entry0x81A0, interpreter `/usr/lib/ldqnx-64.so.2`. Listed virtual addresses are ELF-relative; runtime addresses are load bias plus VA.

Evidence artifacts: `b4_qnx_elf_placement_evidence.json`, `b4_qnx_elf_placement_end_references.txt`, `b4_qnx_elf_placement_relocations.txt`, `b4_qnx_elf_placement_unwind.txt`, representative sizing files and `b4_qnx_elf_placement_model_results.json`.

## BSS reservation, end symbols and runtime consumers

Stock RW PT_LOAD has VA0x29E2B8, file offset0x9E2B8, filesz0x61D8 and memsz0x13BF8. Its initialized end is0x2A4490 and memory end0x2B1EB0. `.bss` starts0x2A44A0, size0xDA10; the 16-byte gap after initialized data is also inside the segment's zero-fill tail.

B4SizeOwner is contiguous after existing BSS, aligned to eight bytes and does not overlap any original section or PT_LOAD range. Increasing **p_memsz**, rather than merely changing a section header, places it in the loader's zero-filled RW mapping. ELF defines the additional bytes beyond p_filesz as zero and requires offset/VA alignment congruence. [ELF program-loading specification](https://gabi.xinuos.com/elf/07-pheader.html). QNX describes loading the execution view formed by segments; this supports using PT_LOAD as the mapping authority, although the cited current documentation is not a test of this device's loader. [QNX ELF format](https://www.qnx.com/developers/docs/8.0/com.qnx.doc.neutrino.sys_arch/topic/dll_HOWUSED.html).

Two variants are distinguished:

| Variant | RW p_memsz | `.bss` size | `_end` |
|---|---:|---:|---:|
| SizeOwner only, accepted proposed reservation | 0x14310 | 0xE128 | 0x2B25C8 |
| Recommended, plus 3×8-byte import slots | 0x14328 | 0xE140 | 0x2B25E0 |

The SizeOwner's 0x718-byte extent remains unchanged in the recommended variant. Exception import slots occupy [0x2B25C8,0x2B25E0), outside the control/cache record. They are relocation-initialized BSS, not initialized file bytes. Dynamic relocation initializes these slots before application initialization; the B4 record initializer must clear exactly its own0x718 bytes and must never zero the adjacent import slots. Whole-tail clearing after relocation would erase the resolved function pointers. Do not grow RW p_filesz: that would turn existing BSS into file-backed data and require a different layout. For 4KiB mapping pages, the mapped RW end rounds from0x2B2000 to0x2B3000; the reservation crosses into one additional page. Page granularity is a supported QNX expectation, not measured device state. [QNX virtual-memory and heap documentation](https://www.qnx.com/developers/docs/6.5.0SP1/com.qnx.doc.ide.userguide/topic/memory_AboutVirtualMem_.html).

Observed symbols:

| Symbol | Stock value | Required action |
|---|---:|---|
| `_end` | 0x2B1EB0 | Update canonical dynsym and static symtab value to0x2B25E0 |
| `_edata` | 0x2A4490 | Preserve: initialized data does not move or grow |
| `__bss_start` | 0x2A4490 | Preserve its existing boundary convention, including the 16-byte gap |
| `__TMC_END__` | 0x2A4490 | Preserve clone-table ownership boundary |
| `__FRAME_END__` | 0x9B8C8 | Preserve original frame-stream endpoint; new frame stream is separate |

`_end` appears in stock dynsym entry file0x1390 (value field0x1398) and static symtab entry0xE63F0 (value field0xE63F8). No stock relocation targets the proposed record/import-slot range or has an addend equal to the old `_end`. No brk/sbrk symbol was found in the executable's symbol tables; malloc and mmap are undefined imports. This does **not** establish internals of unavailable shared libraries. QNX's documented malloc heap obtains arenas through mmap, so a Linux-style assumption that malloc starts at a hardcoded `_end` is unwarranted. [QNX heap mapping](https://www.qnx.com/developers/docs/6.5.0SP1/com.qnx.doc.ide.userguide/topic/memory_AboutVirtualMem_.html). Imported libraries can resolve the newly updated dynamic `_end`; their exact behavior remains a runtime validation requirement.

### Critical fixed-array endpoint: preserve the stock instruction

At0x4EA94, `_Unwind_IteratePhdrCallback` contains bytes `4C 8D 05 15 34 26 00`, resolving to0x2B1EB0. This address happens to be `_end`, but the instruction is the endpoint of a **fixed frame-header cache**, not a heap initializer:

- 0x4EA8D sets rcx=0x2B1D30 (`frame_hdr_cache+0x30`).
- 0x4EAA0/0x4EAA8/0x4EAB0 initialize/link records.
- 0x4EAB4 adds0x30; 0x4EAB8/0x4EABB compare with r8 and continue until equality.
- Stock difference0x2B1EB0−0x2B1D30=0x180, exactly eight strides.

**Do not retarget 0x4EA94 to the new `_end`.** Its displacement stays byte-for-byte stock. The SizeOwner-only new endpoint differs by a nonmultiple of0x30, as does the recommended endpoint; changing the instruction would prevent the equality loop terminating within its intended cache and corrupt subsequent memory. Updating ELF symbol values does not automatically change this already-resolved RIP-relative instruction. Label this bound as the original frame-cache end in the patch manifest, even if a disassembler previously displayed `_end`.

This establishes the known direct endpoint consumer's compatibility, not absence of every possible computed pointer consumer. No target loader/libc image or process-map dump is available here. Loader zero-fill and heap nonoverlap are ABI-supported; a claim of device-runtime verification would exceed the evidence.

## Executable placement and file transformation

Do not insert a ninth program header: the eight 56-byte headers occupy [0x40,0x200), immediately followed by `.interp` at0x200. Do not treat the old0xE38 file gap before RW as sufficient helper space. Instead use this exact reserved RX map (file offset equals VA):

| Range, half-open | Reservation | Capacity |
|---|---|---:|
| 0x9D480–0xA5480 | `.b4.text` helpers/stubs | 0x8000 |
| 0xA5480–0xA6480 | `.b4.rodata`, constants/LSDA | 0x1000 |
| 0xA6480–0xA8480 | `.b4.eh_frame`, new CIE/FDE stream | 0x2000 |
| 0xA8480–0xAA480 | replacement combined `.eh_frame_hdr` | 0x2000 |
| 0xAA480–0xAC480 | relocated/expanded `.dynsym` | 0x2000 |
| 0xAC480–0xAD480 | relocated/expanded `.dynstr` | 0x1000 |
| 0xAD480–0xAE480 | rebuilt `.gnu.hash` | 0x1000 |
| 0xAE480–0xB3480 | relocated/expanded `.rela.dyn` | 0x5000 |
| 0xB3480–0xB5480 | declared RX reserve | 0x2000 |

RX p_filesz=p_memsz becomes0xB5480. The new executable range remains well below RW VA0x29E2B8. Constants and metadata are readable/executable as in the original combined RX segment; no writable-executable allocation is introduced.

File-tail rule: move all original file bytes `[0x9E2B8,0xF0D98)` to `[0x29E2B8,0x2F0D98)`, exactly +0x200000, preserving original loaded VAs. Declare the inserted area after original RX end as reservation/padding; the old gap has no section listed in the accepted section map and is not relied upon as a stock code cave. New helpers/metadata occupy the above RX reservation; leave remaining gap through0x29E2B8 as file padding. Keep original RX bytes below0x9D480 except explicitly authorized feature hooks and metadata-field changes.

Both PT_LOAD p_align values remain0x200000. Moving RW file offset by exactly that alignment preserves offset/VA congruence without assuming the loader accepts a smaller alignment. This is deliberately a larger file-layout transformation: about2MiB of file growth for96KiB of new mapped RX reservation. Padding need not become additional mapped memory; do not increase RX p_memsz to the new RW file offset.

A compact alternative could reduce p_align and shift by a smaller multiple of the target page size, but that would require target-loader/page-alignment evidence not available here. Adding another PT_LOAD would require relocating the program-header table and its PT_PHDR/aux-vector expectations. Neither alternative is recommended for this stock-preserving layout.

## Representative sizes and code budget

Specimens use host clang targeting x86_64 ELF, -Oz, PIC, unwind tables; they are ABI/layout sizing evidence, **not QNX compiler output or completed helpers**. Inputs are `b4_qnx_elf_representative_helpers.c` and `b4_qnx_elf_representative_exception.cpp`; disassembly/sizes are retained in the corresponding sizing text files. Temporary objects were removed. No final ELF was linked.

| Specimen | Code bytes |
|---|---:|
| Exact0x53E0 constructor zeroing | 0x14 |
| Bounds/state/full-width count check, already owned | 0x40 |
| Checked decimal-MB conversion | 0x29 |
| Reader-pin acquisition | 0x35 |
| Owned release with explicit sentinels and category restart | 0xC8 |
| Allocation catch wrapper | 0x2C |
| Compiler-generated terminate helper | 0x0B |

First five total0x17A=378 bytes; exception specimen adds0x37=55 bytes, total433 before alignment/stubs. Their frame streams total0x148 bytes; allocation specimen LSDA is0x18. Three six-byte import jump stubs would add18 code bytes while preserving five-byte call sites. Final relocation/alignment, complete gates, size/index walkers, dictionary coordination and failure continuations add more.

Proposed code sub-budgets: first0x2000 for core/accessors/allocator/stubs; next0x2000 for checked index/population helpers; next0x2000 for checked size/backend callbacks; next0x1000 for workers; final0x1000 for caller adapters/trampolines. These are **capacity limits**, not measured final totals. Reject placement if any partition or metadata stream exceeds its reservation; enlarge/replan explicitly rather than overwrite the next area. The small measured specimens support avoiding a tiny stock gap, but do not prove the whole implementation fits32KiB.

The sizing allocator catches any exception from the narrowly scoped stock new call and maps it to backend failure; no RTTI import is needed. Mandatory owner allocation retains the baseline's deliberate startup-failure policy. An implementation choosing typed bad_alloc filtering/rethrow instead requires additional verified RTTI/unwind imports and a revised slot/table budget.

## Relocations, imports and dynamic metadata

Preserve existing loaded VAs, PLT/GOT addresses, original symbol indices and stock relocation targets/addends. File-offset changes do not justify changing virtual relocation addresses. Resolve intra-image helper calls and data references statically using PC-relative encodings; for ET_DYN, do not embed an unrelocated absolute0x2B1EB0 pointer.

The exception specimen requires `_Znwm` (already imported), `__gxx_personality_v0` (already imported), plus three presently absent dynamic symbols:

| New dynsym index | Name | New RW import slot |
|---:|---|---:|
| 187 | `__cxa_begin_catch` | 0x2B25C8 |
| 188 | `__cxa_end_catch` | 0x2B25D0 |
| 189 | `_ZSt9terminatev` | 0x2B25D8 |

Actual exports and version/ABI compatibility in the device's C++ runtime must be verified before adoption. The Linux-target sizing specimen cannot certify them. Append undefined global function entries to the relocated dynsym; preserve the original187 entries and indices. New dynsym used size0x11D0; dynstr size0x8A4 after the three names. No new DT_NEEDED library is proposed. Use eager R_X86_64_GLOB_DAT relocations for the three slots, symbol indices as above, addend0. Full relocated `.rela.dyn` used size becomes0x45D8; preserve original entries/order and append the three entries. Keep existing DT_RELACOUNT0x2AC describing the unchanged initial relative prefix. Stock `.rela.plt` and DT_JMPREL are unchanged. Calls go through local RIP-relative indirect jump stubs to the new slots, avoiding changes to old PLT and lazy-binding machinery.

Rebuild GNU hash for the enlarged table. A concrete minimal construction uses one bucket, original symoffset179, one64-bit bloom word, shift6, and chains for indices179…189; preserve indices and regenerate hashes/bloom/end-chain marker. Used hash size0x48. This avoids reordering original symbols to satisfy bucket-contiguous chains. Undefined imports remain undefined and are resolved through dependencies; do not export fabricated definitions. GNU-hash loader acceptance must be checked on the actual ldqnx version.

Update dynamic entries **in place** in existing `.dynamic` (VA0x29F838, relocated file offset0x29F838): DT_SYMTAB→0xAA480; DT_STRTAB→0xAC480; DT_STRSZ→0x8A4; DT_GNU_HASH→0xAD480; DT_RELA→0xAE480; DT_RELASZ→0x45D8. Keep DT_SYMENT24, DT_RELAENT24, DT_JMPREL, DT_PLTGOT, DT_PLTRELSZ, DT_NEEDED name offsets and all init/fini pointers unchanged. Existing dynstr strings and offsets are preserved as a prefix. No DT_TEXTREL is required: new resolved pointers are in RW, and no loader writes to RX metadata.

Canonical `_end` dynsym value is changed in the copied table: old entry-relative offset0x10F8; new entry at0xAB578, value field0xAB580. The old unreferenced dynsym mirror may be updated at0x1398 for consistency but is not the loader's canonical table. Static `_end` value field moves to file0x2E63F8 after the tail shift and becomes0x2B25E0. Preserve the frame-cache instruction at0x4EA94. New section/symbol ownership records for SizeOwner/import slots must describe their separate extents; no external dynamic export is necessary for private helpers.

Object relocations such as R_X86_64_PLT32 and R_X86_64_PC32 are link-time work: resolve existing new/delete calls to stock PLT, helper-to-helper calls to new PCs, and FDE/LSDA references to final VAs. Reuse the existing relocated personality pointer at VA0x2A0008 for an indirect pcrel CIE personality encoding rather than creating another writable personality slot. All trampoline windows must contain complete stock instructions, with displaced RIP-relative operands re-encoded. No final helper encodings/hook windows are certified by this placement plan.

## Exception/unwind integration

The stock unwinder explicitly scans PT_LOAD ranges and the existing PT_GNU_EH_FRAME header (evidence0x4EB28…0x4EC08), so extending RX and updating that existing header makes helper PCs discoverable without an extra program header. Stock header bytes decode to version1, pcrel sdata4 frame pointer, udata4 FDE count, datarel sdata4 table; count838.

Keep original `.eh_frame` stream and original FDEs at their VAs. Emit a separately terminated new CIE/FDE stream at0xA6480 covering every new function/landing pad/trampoline that changes frame state. Do not simply append after the original zero terminator and expect discovery. Put allocation LSDA in0xA5480 reservation, and encode correct personality/LSDA references. Preserve SysV callee-saved registers and stack alignment; accurately describe pushes, stack changes, saved-register locations and restored states. A catch/terminate specimen is not valid merely because its call displacements fit.

Rebuild a **combined indexed** frame header at0xA8480: decode the838 old PC/FDE pairs relative to original header0x91598, retain their absolute ELF VAs, add each new helper's initial-PC/FDE pair, sort by initial PC and re-encode every pair relative to new header base. Preserve version/encoding bytes; encode header `.eh_frame` pointer to original0x92FD8, since the indexed table independently points to both streams. New FDEs refer to their own new CIEs. New header used size=12+8*(838+k), where k is the actual added FDE count; reserved0x2000 permits at most184 additional pairs. Sample seven-function header size is0x1A74. Actual count must be emitted from final records, not hardcoded from specimens.

Update the existing PT_GNU_EH_FRAME at file0x190: p_offset=p_vaddr=p_paddr=0xA8480; p_filesz=p_memsz=actual combined header length; flagsR, align4 unchanged. Update section14 `.eh_frame_hdr` accordingly. Original indexed FDEs remain necessary, including for unmodified functions. Entry redirection alone does not make original frame descriptions suitable for displaced prologues; add exact trampoline coverage and retain the original FDEs for any remaining original body. No runtime __register_frame allocation path is proposed.

The existing fixed frame-header cache retains its original size and endpoint. New helpers belong to the existing executable object, so this layout does not add a cache object per helper. Execution of a real allocation exception through the combined index, LSDA, imported catch functions and back into checked failure is still required before implementation is accepted.

## Exact ELF/header changes

Program-header entry offsets below are stock file offsets and remain in place:

| Entry / file offset | Changes |
|---|---|
| PHDR0 /0x40 | None: offset/VA0x40, size0x1C0 |
| INTERP1 /0x78 | None: offset/VA0x200, size0x17 |
| RX LOAD2 /0xB0 | filesz and memsz0x9D480→0xB5480; other fields unchanged |
| RW LOAD3 /0xE8 | p_offset0x9E2B8→0x29E2B8; memsz0x13BF8→0x14328; VA/paddr0x29E2B8, filesz0x61D8, align0x200000, flagsRW unchanged |
| DYNAMIC4 /0x120 | p_offset0x9F838→0x29F838; VA/paddr/size unchanged |
| NOTE5 /0x158 | None |
| EH_FRAME6 /0x190 | New combined-header address/offset/actual size as above |
| RELRO7 /0x1C8 | p_offset0x9E2B8→0x29E2B8; VA/paddr0x29E2B8 and size0x1D48 unchanged |

New import slots are outside the original RELRO range, like writable GOT-style storage; eagerly relocated then privately owned. Do not claim they become read-only automatically. Expanding RELRO across the entire mutable library/cache state would be incorrect.

ELF e_entry0x81A0, e_phoff0x40, e_phnum8 and e_phentsize56 stay unchanged. Original section header indices remain stable. All original section file offsets≥0x9E2B8 move by+0x200000 unless that section is explicitly relocated into new RX metadata. Addresses of original loaded sections stay fixed; nonloaded debug sections likewise move in file only. `.bss` remains SHT_NOBITS, same VA, grows to0xE140; its conventional file offset moves with the tail but allocates no file contents. Original `.dynsym`, `.dynstr`, `.gnu.hash`, `.rela.dyn`, `.eh_frame_hdr` section headers receive the new address/offset/actual sizes specified above; link/info fields retain original symbol-table relationships. Keep original `.eh_frame` header intact.

Append three section headers: index37 `.b4.text` (PROGBITS, AX, align16), index38 `.b4.rodata` (PROGBITS, A, align8), index39 `.b4.eh_frame` (PROGBITS, A, align8). Their sh_addr/sh_offset are the reservation starts above; sh_size is actual emitted size within the reservation. Keep37 original section indices, including shstrtab index34. No sections for unused padding are necessary.

Concrete nonloaded table placement: reserve [0x2F0DA0,0x2F1DA0) for the replacement shstrtab, containing original0x15A bytes plus the three new section names (used size0x17B). Set section34 offset0x2F0DA0, size0x17B. Place the40-entry section-header table at0x2F1DA0: e_shoff0x2F1DA0, e_shnum40, e_shentsize64, e_shstrndx34; table ends0x2F27A0. The copied old section-header table is stale nonloaded bytes and no longer referenced. Recommended final ELF length0x2F27A0 (assuming no optional static-symbol additions). If private symbols are added to symtab/strtab, reserve and relocate those explicitly and recalculate the tail/table plan; they cannot grow over adjacent original tables.

Container reconstruction, lengths/checksums and install-time size acceptance are **not performed here**. This layout's approximately2MiB growth must be supported by the eventual packaging path before adoption. Do not splice a longer ELF into a fixed-length container slice or move later payloads without updating their documented framing. That requirement is a blocker, not permission for a firmware build.

## Tests, assumptions and remaining blockers

`b4_qnx_elf_placement_model.py` passes17 focused metadata checks: stock identity, header/interpreter preservation, reservation adjacency, VA/file segment nonoverlap, stock alignment congruence, exact SizeOwner/import-slot extents, RW zero-tail coverage, retained frame-cache endpoint, failure of naïve endpoint retargeting, metadata capacities, combined header capacity and signed-relative reach. It creates no ELF output. Representative object disassembly gives concrete specimen sizes, not final linked sizes.

Supported assumptions: target uses the observed ldqnx interpreter and ELF execution view; extending existing mappings follows ELF p_filesz/p_memsz semantics; load bias is applied consistently for ET_DYN; original virtual addresses and relative relocation addends remain valid; imported malloc follows QNX's documented mapped-arena model rather than an assumed fixed break. These assumptions need target-runtime confirmation and are not equivalent to a device test.

Remaining blockers are specific:

1. Actual device ldqnx/libc/libc++ binaries or target execution evidence: confirm added zero-fill mapping, no conflicting fixed mapping, dynamic `_end` consumers, GNU-hash/import resolution and catch/terminate ABI. Shared-library absence prevents claiming runtime closure.
2. Full implementation sizes and emitted relocation/FDE/LSDA records; all partitions have hard limits. Host Linux-target specimens cannot establish the QNX toolchain's exception ABI or final output.
3. Packaging/install support for the longer ELF while preserving later container components. The larger alignment-preserving layout is recommended conditionally on that support; no firmware was created.
4. Actual intended voice_sysex target binary/source is absent from this working folder, and this folder is not a Git checkout. Historical overlap results are accepted background only. Actual merge comparison remains pending.
5. Existing implementation blockers in the QNX97 design—checked backend/lifetime integration—remain carried forward; placement does not resolve those semantics.

The separate B4 test build must eventually begin with clean stock2.2.2.0.0, identified by the accepted hash. Maintain a VA-based patch manifest with original-byte guards, reservation ownership, segment/table transformations and helper sizes. For a later voice_sysex merge, reapply/reconcile that transformation to the actual target and compare its ELF extents, symbol/import tables and hooks; do not copy the stock-expanded ELF over the branch's QNX image. Protect its code/data ownership and fail on conflicts. No current merge compatibility certification is claimed.
