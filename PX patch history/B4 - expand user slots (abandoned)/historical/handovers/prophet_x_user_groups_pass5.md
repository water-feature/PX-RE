# Branch 4 — group reference coverage and hidden QNX bounds, pass 5

2 October 2026. Clean official 2.2.2.0.0. Continues the separate group-expansion audit; eventual integration remains voice_sysex. No firmware emitted or flashed.

## New verified dependencies

1. **Import archive validation:** LibraryCopy_ValidateFolder at QNX VA 0x15350 searches gpGroupNames through a pointer endpoint formed at 0x1542A: r12=r15+0x208. This is 65 eight-byte entries, despite the table containing 133 names. Matching an additional name cannot succeed merely because it already exists in the table. For the 97-total-group target, the endpoint displacement would be 0x308, preserving every old internal ID.
2. **Release semantics:** CSampleGroups::ReleaseSampleGroupFilesIndex at 0x33CA0 compares group against 0x40 at 0x33CB1. Unsigned above-limit arguments enter the broad-release branch at 0x33D6C, which sets group range 0..64 and category range 0..16. This also supports the destructor's negative sentinel arguments. Group 65 is therefore not treated as a rejected individual group. Expansion must distinguish valid new IDs from sentinel/all-group behavior and expand the intended full range, while changing the pointer-array offset in this routine together with the object layout.
3. **Size-cache initialization:** startup function 0x7BC0 initializes from gGroupSizeCache at 0x2A4A20 until the address 0x2A4C28, currently the next symbol. This is an address-endpoint limit. Relocating/resizing the cache without updating this initializer leaves its new tail uninitialized.
4. **Post-index size refresh:** IndexSampleGroupFiles loop at 0x33E90..0x33EA1 queries groups 1..64 and ends when EBX reaches 0x41 (comparison at 0x33E9E). Its all-group indexing path therefore contains a separate refresh bound.
5. **Additional cache consumers:** LibraryCopy_DoLibraryUpdate writes the size-cache entry at 0x15BC2 after invalidation; LibraryCopy_DeleteGroup references the cache around 0x15E22. The generated map also covers delete-category/instrument and dispatch-side name-table references. These consumers must be included in relocation coverage.

## Actual instruction tests

verify_qnx_import_bound.py maps ELF load segments and runs the actual x86-64 QNX validator. Only external strcpy, strrchr and strcmp calls are mocked with their string semantics. Inputs are fixture archive paths and matching destination names; output pointers are null. The real group/full-category tables and validator code run under Unicorn.

Twenty-two cases pass for the stock 65-entry endpoint and hypothetical 97-entry endpoint (the displacement is changed only in emulator memory). Stock accepts tested original groups and rejects u32/u63/u64/u99/x00. The hypothetical endpoint additionally accepts u32 and u63, while still rejecting u64/u99/x00. This proves this validator's bound behavior, not archive extraction or a full import transaction.

verify_qnx_release_bound.py executes the actual release routine against a zero-pointer object fixture. Group 64/category0 clears one count and one pointer. Group65/category0 enters the broad branch and clears the first 17 entries instead of targeting group65. Negative group/category sentinel arguments produce the same 17 writes in this fixture. The category cursor is not reset as the outer group loop advances in the inspected stock code; this is recorded as observed behavior, not a proposed fix to an unrelated stock defect. No linked list deletion, real object destructor or full index lifecycle is exercised. This test directly demonstrates why an above-limit comparison can have side effects instead of simply rejecting a value.

## Reproducible coverage map

build_group_coverage.py produced group_coverage_map.json from the unchanged ELF and PIC payload:

| Coverage item | Results | Meaning |
|---|---:|---|
| QNX seed references | 28 | RIP-relative references into group names, size cache, count/index pointers |
| QNX relevant function records | 29 | Includes constructor/destructor aliases at shared addresses |
| QNX relevant direct edges | 2085 | Calls and jumps in/from selected functions, including the large dispatcher |
| QNX indirect call sites in selected functions | 51 | Candidates requiring resolution, not 51 proven unknown destinations |
| PIC helper direct-edge candidates | 961 | Includes 555 generic getter and 351 generic setter references |
| PIC group-parameter literal candidates | 165 | Immediate 0x22/0x63 constructions; parameter role still needs classification |
| PIC aligned raw-pointer candidates | 0 | No exact full-word seed pointers found; constructed/indirect references still exist |

QNX analysis decodes executable sections with Capstone, uses ELF function sizes for ownership, and records RIP-relative effective addresses. PIC analysis enumerates aligned instruction words throughout the payload; data can resemble code, so its edges and parameter literals are explicitly candidates until code ownership is verified. Both tools preserve full addresses, owners and instructions for review.

This map is a discovery inventory, **not a whole-program coverage proof**. It misses propagated QNX addresses, PIC addresses assembled in registers, values fetched from tables, and indirect control-flow relationships unless separately traced. Numeric candidates are not patch instructions. The earlier linear PIC address scan remains complementary.

## Coverage status and next work

| Path | Current evidence | Remaining gap |
|---|---|---|
| Oscillator group controls | PIC parameter limits, availability queries and order mappings traced | Classify generic setter/getter candidates and every alternate UI path |
| Preset/SysEx storage | Inspected byte formats and sanitizers tested in pass 2 | Full transactions and NRPN mapping/limits |
| Import destination | PIC cursor bounds and QNX validator endpoint tested | Initializers, remaining navigation/global state, archive lifecycle |
| Index lifecycle | Allocations, accessors, indexer and release branch identified | Full release/rebuild/destructor tests; all object-field offsets |
| Group sizes | 28 seed references include initialization/read/invalidation paths | Complete relocation references, aliases and indirect uses |
| Instrument names | Builder capacity, index reconstruction and reader overflow tested | Coherent capacity guard and failure/rollback design |
| PIC relocation | Default heap boundary verified | Worst-case stack/interrupt bounds and definitive reservation |
| voice_sysex merge | Current inspected sites disjoint in pass 4 | Full future patch-set and merged behavioral verification |

Next priority: resolve the generic PIC group-parameter candidates and the NRPN handler, then follow index lifecycle and cache relocation references through all callers. The standalone build remains gated by technical coverage and memory ownership. No claim is made that every 64/65-related assumption has now been found.
