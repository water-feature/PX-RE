# Branch 4 — user sample group expansion, pass 1

2 October 2026, Australia/Brisbane. Read current handover version 16 and analyzed clean official 2.2.2.0.0. No firmware patch or hardware test.

## Result

**Verified:** QNX actively indexes 65 group IDs (factory + 32 add-on + 32 user), but its existing name table has 133 entries and already names 100 user folders. More storage alone does not extend the active tables. Expansion requires coordinated allocation, indexing, cache and PIC changes. Presence of extra names is not proof of working extended support.

## Exact ID map

| QNX ID | Directory | Meaning |
|---|---|---|
| 0 | f00 | Factory |
| 1–8 | u00–u07 | First 8 user groups |
| 9–40 | p00–p31 | 32 add-on groups |
| 41–64 | u08–u31 | Remaining active user groups |
| 65–132 | u32–u99 | Existing names outside active bounds |

The gpGroupNames symbol at VA 0x2A0160 is 0x428 bytes = 133 pointers, not merely a coincidental run of strings. All 133 pointers were decoded and checked. Appending groups after ID 64 preserves all existing IDs. Do not replace this with a simple factory/add-on/user contiguous mapping: it would change old IDs.

## QNX bounds and memory ownership

- CSampleGroups constructor VA 0x33390 initializes 65 rows of 17 category counts and 65 rows of 17 folder pointers. Count array uses 65*17*4 = 4420 bytes, padded to pointer-array offset 0x1148. Pointer array uses 65*17*8 = 8840 bytes. Total allocated object is 0x33D0 (13264) at allocation VA 0x16181. Extending constructor loops without moving the pointer array would overlap counts and pointers; moving the pointer array also requires updating every accessor.
- GetSampleGroupFolder 0x33C10 and GetNumInstrumentsInFolder 0x33C70 reject unsigned group IDs above 0x40 and categories above 0x10. Group lookup uses row index group*17+category.
- Indexer callback scans gpGroupNames but stops at 0x41, around 0x336E4. Thus u32+ does not become indexed even when a full /hd traversal sees it.
- IndexSampleGroupFiles 0x33DB0 uses the same bounds and its all-groups size loop ends at 0x41 (0x33E9E). ReleaseSampleGroupFilesIndex 0x33CA0 also contains 65/17 iteration limits.
- gGroupSizeCache VA 0x2A4A20 has symbol size 0x208 = 65*8. GetFolderContentsSize 0x15320 indexes it directly with the caller's group ID and no local range check. Letting ID 65 through elsewhere without resizing/relocating this cache reads past its end.
- MakeNewUserFolders 0x2DFE0 walks gpGroupNames indices 41–64 (begin +0x148, end +0x208), creating the later u08–u31 namespace. Extra-name presence does not make it create u32+.
- CInstrumentDictionary::Find(group,category,instrument) 0x116C0 compares three 32-bit stored fields at node offsets 0x54, 0x58, 0x5C. This dictionary lookup does not impose a five-bit/32-group representation itself.

## One group traced across the interprocessor link

**Verified count/discovery path:** PIC function 0x9D079978 assembles message 0x4012 with group in the payload's high byte and category in the low byte: (0x4012<<16)|(group<<8)|category. QNX dispatcher routes message 0x4012 at 0x1F4A3 to 0x22C6A, extracts high-byte group and low-byte category, stores them at this+0x3754/+0x3758, and calls GetNumInstrumentsInFolder. That function addresses row group*17+category. The row was populated by the callback matching the directory name against gpGroupNames. Thus group 41 selects u08; group 64 selects u31; group 65 has the name u32 but is rejected at the accessor.

PIC count rebuild function starting 0x9D042A8C calls that request for 65 groups x 17 categories, storing byte counts beginning at RAM 0x80010DAD, with limits 0x41 and 0x11 at 0x9D042B08/0x9D042B04. It subsequently writes a 4 KiB range at 0x5FD000..0x5FDFFF through helper 0x9D042340. Destination medium, exact record ownership, restore path and safe relocation are not yet established. This is a further fixed PIC table/persistence dependency, not simply a menu maximum.

**Verified size path:** PIC 0x9D079744 sends message 0x4037 with low 14 bits of group and bit 15 selecting volume. QNX 0x22DAE decodes those same fields and returns size MB through 0x4037/0x4038. PIC storage-accounting loop ends at group-count 0x41 (0x9D0242A4). This particular transport has ample bit width, but the backing size cache still needs expansion.

**Name request candidate:** PIC 0x9D079534 packs a group/category request under 0x4021 and sends an instrument index under 0x4039. QNX 0x20077 handles 0x4039 using the cached group/category. Full 0x4021 handler and UI callers need follow-up before treating this as a complete selector-to-playing-sample trace.

## Target-count implications

64 user groups would use 97 total IDs, highest ID 96. 100 user groups would use 133 total IDs, highest ID 132. The existing high-byte discovery transport can represent both; any seven-bit program/NRPN field that stores the same flattened ID could represent only through 127. Therefore 100 user groups is a name-table capacity, not a validated target. Under a seven-bit flattened-ID constraint the mathematical ceiling would be 95 user groups (1+32+95=128 total). Whether presets use that representation remains unknown; do not assume the ceiling applies.

A 64-user-group experiment is a reasonable candidate **after** preset and PIC table ownership tracing. No target is selected or patch sites approved in this pass.

## Next required tracing

1. Identify actual PIC sample group selector helpers, limits and labels; map User 9 to internal ID 41 and verify selection into the audio sample switch.
2. Trace saved program loading/writing, SysEx and NRPN group fields, including invalid-value clamping. Establish whether groups 128–132 are encodable.
3. Resolve the PIC byte-count table's allocation boundaries and the 0x5FD000 persistent record, all readers and rebuild triggers.
4. Audit import, delete, group-name dumps, startup cache invalidation and all QNX size-cache references before drafting changes.
5. Build offline tests for old-ID preservation and the first extra group only after the full path is mapped.

## Reproducible evidence

Clean BIN SHA-256 a4b304b3bb48ca933ae63c99c0098698c497ebfc7c38ab2a823b5e0df4919fa9. QNX payload SHA-256 7db8a8276f0bda34d22fdd2e8744b304dc7d62f80f9189836b107a4d7b178cff. PIC payload SHA-256 14e9c9b9dc562b0384fc43b3c5e0eb7fea84a5792d1a19b9b3ea8276ef7646f5.

verify_group_layout.py checks the stock hash, every name-table pointer, key actual instruction bytes, allocated object size and symbol sizes. It passed. Evidence ZIP includes stock disassemblies and the decoded map. These are static findings; no claim of hardware viability or complete patch coverage.
