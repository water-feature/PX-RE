# Branch 4 — selectors, RAM ownership and name metadata, pass 3

2 October 2026. Clean official Prophet X 2.2.2.0.0, continuing passes 1 and 2. Static inspection and execution of selected actual PIC instructions under Unicorn; no modified firmware emitted or hardware tested.

## Outcome

64 user groups remains a representable development target (97 total groups, IDs 0..96). It requires coordinated changes beyond raising parameter maxima. The existing selector mappings collapse every ID above 64; the group/category table cannot grow in place; instrument names occupy a separate fixed 4 MiB serial-memory region. Increasing SSD capacity alone does not increase that metadata region.

## Selector and import dependencies

Actual helper 0x9D080E2C maps internal IDs to browsing order; 0x9D080E60 reverses that order. Executing both proves a permutation/inverse for IDs 0..64, with IDs 65,96,127,128,132,255 all collapsing to 64.

| Internal IDs | Stock display IDs | Meaning |
|---|---|---|
| 0..8 | 0..8 | Factory and users 1..8 |
| 9..40 | 33..64 | Purchased 1..32 |
| 41..64 | 9..32 | Users 9..32 |

Group knob paths around 0x9D02EAE8..0x9D02EC94 use these helpers plus the descriptor maxima and group/category availability query 0x9D079300. Raising maxima alone therefore cannot expose the new groups correctly.

Import destination calls at 0x9D01B8A0, 0x9D01B8B8 and 0x9D01B8C8 use display selection+1 through the inverse helper. Import then refreshes the size cache and calls count rebuild 0x9D042A8C, name rebuild 0x9D042B80 and runtime initialization 0x9D040ED8. Import table renderer 0x9D034200 also uses the inverse helper. Its independent selection bounds still need a full audit.

For a 64-user target preserving all old internal preset IDs, a proposed display order is factory 0, users 1..64, purchased 65..96. Internal users 41..96 would map to display 9..64; purchased internal IDs 9..40 would map to display 65..96. This requires rewritten mapping logic, not just a changed upper bound.

The label-pointer table at 0x9D063F60 already contains 132 valid labels indexed by internal ID minus one: User 1..8, Purchased 1..32, User 9..100. All pointers/strings were decoded and asserted. Label presence alone proves neither UI bounds nor supported storage.

## Exact RAM collision and relocation candidate

| Region, exclusive end | Size | Ownership |
|---|---:|---|
| 0x80037E90..0x8003A118 | 8840 bytes | 65 × 17 × 8 count/index cache |
| 0x8003A118..0x8003A21C | 260 bytes | 65 × 4 group-size cache |
| 0x8003A21C..0x8003A33C | 288 bytes | Other startup-initialized data |
| 0x8003A33C..0x8003A384 | 72 bytes | Other startup-initialized data |

The first extra group row starts exactly at the size-cache base. A memory test demonstrates the overwrite; this is not a hypothetical distant collision. Size-cache initialization around 0x9D0799A0 queries groups 1..64 through 0x9D079744. Import writes it around 0x9D01B8EC, and the import renderer reads it around 0x9D034288. Both caches must grow together and their references must move.

Startup initialization routine 0x9D081090 consumes descriptors at 0x9D001480. The parser recovered 93 descriptors, ending at 0x9D01A84C. The zero descriptor at 0x9D01A3B4 covers RAM 0x80037D30..0x8003A21C. Further copied/zeroed objects follow, including uncached aliases at 0xA003A390..0xA003A450 and a large copied region beginning 0x8003A450. Thus adjacent memory is owned.

Startup sets SP to 0x8007FFF0 and GP to 0x80007FF0. The inspected default heap setup uses base 0x80053AE0 and size 0x4000, ending at 0x80057AE0. A candidate contiguous relocation at 0x80058000 would need 13,580 bytes for 97-group count/index and size caches, ending at 0x8005B50C. **This is a candidate only:** stack high-water, alternate heap configuration, indirect references and reserved memory have not been proven. No absence-of-reference claim establishes that it is safe.

The accompanying address scan is conservative linear constant propagation over short instruction windows, not complete control-flow/data-flow analysis. It aids reference discovery and can include false positives and miss indirect constructions.

## Instrument-name region and capacity

Name builder 0x9D042B80 starts at serial address 0xC00000 and stops at 0x1000000, a 4 MiB interval. It builds 64-byte records containing 22 name bytes, 22 description bytes, two metadata bytes and padding. Each category includes its instrument-zero placeholder plus the reported instruments. Records are buffered in 4 KiB blocks and programmed as 256-byte pages. Reader 0x9D041E8C uses the count/index cache's second word and a 64-byte record stride into the same region.

This gives **65,536 records shared across all groups and categories**, not per group. Empty categories still consume one placeholder: 1105 records for stock 65 groups; 1649 for 97 groups. The builder's capacity branch at 0x9D042D64 stops traversal at the region boundary. No explicit overflow error was identified within this routine. Caller behavior and interaction with count/index reconstruction when traversal truncates remain unresolved.

The actual builder instructions were executed with mocked count/name replies, UI calls and serial erase/program operations. Only the group-loop bound at 0x9D042D9C was varied in emulator memory; translation blocks were flushed after changes. No BIN was changed.

| Total groups | Instruments per category | Requested records | Built records | Result |
|---:|---:|---:|---:|---|
| 65 | 0 | 1105 | 1105 | Complete |
| 97 | 0 | 1649 | 1649 | Complete |
| 97 | 1 | 3298 | 3298 | Complete |
| 97 | 255 | 422144 | 65536 | Capacity truncation |

The saturated test wrote 16,384 mocked pages from 0xC00000 through 0xFFFF00. This proves the inspected code's capacity behavior, not serial device geometry, erase acceptance, full import transactions or hardware timing. Physical flash ownership outside the region remains unverified.

## Evidence and next development gate

verify_pic_metadata.py passed actual remapper/inverse tests, all 132 labels, name-builder cases and exact cache collision. inspect_pic_layout.py parses startup descriptors; scan_pic_addresses.py supplies reference candidates. JSON outputs and these scripts are in the evidence archive. Inputs are the unchanged pic.bin and pic.dis extracted in earlier passes; their hashes are recorded in the handover.

Before a patch build: complete import/global-selection and NRPN bounds; prove and reserve a PIC RAM relocation including startup initialization; enumerate every reader/writer of both caches; verify count/index/name reconstruction under capacity overflow; finish matching QNX allocation/cache changes from pass 1; then design coordinated edits and regression cases preserving old IDs and old count-page compatibility. No build or flash has been performed.
