# B4 — minimal QNX placement plan under revised scope

## Recommended implementation

Expand `CSampleGroups` to its 97×17 count/head arrays only, keep the stock 65-entry size cache, and append a 32-entry size-cache extension. Use small branch-only routing/bounds helpers in an explicitly extended RX segment. Preserve existing imports, allocation behavior, loaded addresses, dynamic tables and ordinary valid-input behavior.

The measured helper bundle is **359 bytes**. Reserve **512 bytes**, [0x9D480,0x9D680), inside the existing file gap before RW file offset0x9E2B8. Extend the existing RX PT_LOAD to cover this reservation. No file-tail movement, additional program header, dynamic-table relocation, new import, exception catcher or 2MiB file growth is needed. The former96KiB reservation and0x718-byte B4SizeOwner are superseded for this scope.

This document uses the completed findings in `readme_B4_qnx97_design.md` and `readme_B4_qnx_elf_placement_plan.md`; it does not rerun their audits or verification matrices. New work was limited to designing and assembling an isolated sizing specimen, `b4_minimal_qnx_helpers.s`, into a temporary relocatable object. That object was disassembled for sizes and deleted. It was not linked or applied to a firmware image. All firmware inputs remain unchanged.

## Retained layout and behavior

Internal IDs remain0=f00,1–8=u00–u07,9–40=p00–p31,41–64=u08–u31,65–96=u32–u63. Group97/u64 remains outside supported capacity. The existing name table already supplies these strings; leave its133 pointers and relocation entries untouched. Categories remain0–16. Display-order mapping is a separate PIC change, not a QNX renumbering.

### Count/head owner

| Relative extent | Contents |
|---|---|
| [0,0x19C4) | 97×17 uint32 counts |
| [0x19C4,0x19C8) | Four-byte alignment padding |
| [0x19C8,0x4D50) | 97×17 eight-byte node heads |

Allocate **0x4D50**, growth0x1980=6,528 bytes over stock0x33D0. Do not append validity arrays, gates, epochs, reader pins, lifecycle or worker-result metadata. Counts and null heads retain stock meaning. Nodes remain0x408 bytes with next at+0x400. Existing throwing operator new and matching delete remain in use; no null-return assumption, new exception-catching API, stock-capacity allocation fallback or node-allocation recovery is added. Allocation failure retains stock behavior. Additional memory demand is real, but measuring all competing QNX allocations is not a prerequisite imposed by this placement design.

### Minimal size-cache storage

Keep stock `gGroupSizeCache` [0x2A4A20,0x2A4C28) for groups0–64. Append **32 uint64 entries, 256 bytes**, at [0x2B1EB0,0x2B1FB0), for groups65–96. This is the minimum additional storage for the stock per-group uint64 representation. No USB cache or separate size-validity state is introduced. HD unknown retains UINT64_MAX; valid zero retains stock meaning. USB continues bypassing the HD cache. Preserve stock force/cache behavior, copy/delete invalidation timing and the existing accumulator at0x2A4C28.

Addressing is:

```
g <= 64: stock_cache + 8*g
g >= 65: extension + 8*(g-65), with g <= 96 established first
```

For preserving the existing scaled-index instructions, thunks select `extension_bias=0x2B1CA8` (=0x2B1EB0−65*8) as the base for the extension branch. This is an arithmetic bias, **not owned storage at0x2B1CA8**. It must never be dereferenced without the validated group offset. Group65 resolves to0x2B1EB0;96 to0x2B1FA8;97 is rejected before selecting/indexing. Group64 stays at0x2A4C20.

The initializer initializes the extension's32 entries to all ones, then resumes the stock65-entry initializer. Zero-filled BSS alone does not implement the stock unknown sentinel. No initialization/reload policy redesign is required.

## Exact retained integration sites

The following are carried forward from accepted instruction evidence, not rediscovered searches.

| Site | Minimal change |
|---|---|
| Allocation0x16181 | Immediate0x33D0→0x4D50; preserve new call0x16186 and owner installation |
| Constructor0x33390 | Outer pointer-array end displacement0x2288→0x3388; store at0x333AF head displacement0x1148→0x19C8; count/category strides unchanged |
| Folder accessor0x33C10 | Max group0x40→0x60; category max0x10 unchanged; scaled constant at0x33C2A0x228→0x338, final+8 load unchanged |
| Count accessor0x33C72 | Max group0x40→0x60; counts remain at owner+4*(17*g+c) |
| Index callback0x336E4 | Name-search exclusive end65→97; retain existing category recognition, sorting, allocation and insertion |
| Index aliases0x33DC9/0x33DDE | Count alias unchanged; head alias owner+0x1148→owner+0x19C8 |
| Index selection0x33DF1 and refresh end0x33E9E | Support valid groups0–96 and explicit -1 sentinel; end65→97 |
| Release heads0x33CFB/0x33D30 | Displacement0x1148→0x19C8; broad-group end at0x33D6C65→97 |
| Release selection0x33CB1 | Preserve -1/all and valid group/category selection; reject unsupported nonsentinel inputs before release |
| **Release cleanup0x33D45** | **Separate cursor correction:** reset r12d to0 before the next outer group. Five-byte replacement `45 31 E4 90 90` replaces the accepted five-byte load of the category end. Single-group scoped release has no next group; broad release starts each group's categories at0. Carry this correction explicitly, independently of group-limit changes. |
| Direct heads0x3518C/0x351CC/0x35410/0x3552D | All displacements0x1148→0x19C8; preserve worker/dictionary behavior |
| Parser end0x35216; update bound0x3535C/end0x35650 |65→97, max64→96/end65→97; workers retain original24-byte argument records |
| New-user-folder loop0x2E01E | Name-table end+0x208→+0x308; start at ID41/+0x148 and category loop remain unchanged |
| Import validator endpoint0x1542A | Name-table endpoint+0x208→+0x308; no ZIP/enumeration rewrite |
| Delete group check0x15D91 | Max64→96; preserve existing volume-bit exclusion and delete semantics |
| Count reply0x22C92–0x22C9C | Small full-width count guard before existing narrowing/send |

No replacement constructor, checked accessor API, release allocator, worker coordinator or filesystem backend is necessary. Existing functions supply these behaviors after the immediate/displacement edits and narrow guards.

### Branch-only helper hooks and continuations

The sizing source implements the following tail-jump contracts. Preserve complete instruction overwrite windows; fill unused bytes with NOPs. Helpers do not call external functions or change rsp.

| Hook | Helper behavior / stock continuation |
|---|---|
|0x7BC0 seven-byte LEA | Jump to extension initializer; replay stock-cache LEA into rax; jump0x7BC7. Only rax,rdx and flags change, as in stock initialization. |
|0x15320–0x1532B,11 complete bytes | Size front end validates unsigned group<=96 and volume<=1, keeps USB/cache-miss branch0x15340; selects cache base, sign-extends group into rcx and resumes load0x1532E. Invalid inputs return numeric0 as an unavailable bounds result, not a new checked backend status. |
|0x15278 seven-byte LEA | Select rdx stock/bias using validated r14d; resume store0x1527F. Preserve rax result. |
|0x15BB1 seven-byte LEA | Select rax stock/bias using r14d; resume0x15BB8, preserving the existing late invalidation and forced direct backend call. |
|0x15E22 seven-byte LEA | Select rax stock/bias; resume0x15E29 and stock zero store. Delete-entry bound guarantees range. |
|0x15BCA five-byte call | Redirect existing call to leaf direct-size guard, which tail-jumps0x151C0 with unchanged arguments for valid inputs. Invalid group/volume returns0. Do not route this call through the caching front end, which would change the stock refresh behavior. |
|0x15AF8 seven-byte LEA | Copy group guard checks r12d<=96 before names/cache use; replays name-table LEA and jumps0x15AFF, otherwise stock epilogue0x15AD3. No filesystem error-policy rewrite. |
|0x33CB1–0x33CC3,18 complete bytes | Release scope guard uses original esi/edx: -1 group→0x33D6C; valid group/category→0x33CC3; -1 category→0x33D8C; invalid nonsentinel→epilogue0x33D5D. |
|0x33DF1–0x33DF6,five complete bytes | Index scope guard uses ebx/ebp: all→0x33E69; scoped→0x33DFF; all categories→0x33EA8; invalid→epilogue0x33E4F. Preceding release call is also guarded, so invalid input has not freed nodes. |
|0x3535C–0x35365,nine complete bytes | Update guard replays `[rsp+8]=rax`, checks r15d/r13d, restores group comparison flags and jumps0x35365. Invalid nonsentinel→epilogue0x35483. Existing branches implement ordinary scoped/all behavior. |
|0x22C92–0x22C9C,ten complete bytes | Full uint32 count<=255 keeps opcode0x4012/value and jumps original send call0x22C9C. Otherwise sends existing0x403C,0 via that same call; no new import or capacity message. |

Flag changes in cache-base thunks are consumed/overwritten by subsequent stock comparisons/XORs before a dependent branch; update guard deliberately restores the flags required by the stock branch. Cache-store thunks are reached only with group bounds established by the front end/direct guard/copy guard/delete bound. Existing invalid-input alias-to-release-all behavior is deliberately narrowed to the explicit -1 sentinel; this is a small guard in changed code, not a synchronization redesign.

## Overflow protection retained, with concrete dependencies

1. **Table writes:** allocate and initialize all97 rows; move every pointer-table reference together; route all four size-cache references to owned storage; enforce group/category bounds before indexing. Otherwise the expansion directly writes beyond stock allocations or into the size accumulator.
2. **Metadata counts:** full-width QNX count validation before narrowing remains as a tiny reply-site guard. The accepted count-page format stores byte counts; larger or negative-as-unsigned values would otherwise alias a plausible count. No enumeration-error propagation or count-validity metadata is needed for this numeric guard.
3. **Aggregate name capacity:** the accepted expansion population preflight must still account for the instrument-zero placeholder in each category and reject total records>65,536 **before name-region writes**. The extra544 cells create additional demand in a fixed region; this is a concrete expansion dependency. Keep bounded prefix arithmetic and no-write-on-overflow, using the accepted population findings. It belongs in the expansion's PIC/population work, not this ELF-placement task. No new QNX whole-index snapshot, epoch, negotiation or journal is implied.

The new count guard reports a numeric representation overflow only. It does not claim successful backend enumeration, verified absence or recovery from arbitrary I/O errors. Existing error/retry behavior remains stock. Broader bounded retries, MB-calculation changes and size-caller failure cleanup are deferred. Per-group size width and volume representation did not grow, so those rewrites are not required to place32 extra entries.

## Measured placement and ELF changes

`b4_minimal_qnx_helper_sizes.json` and `.txt` record the new sizing specimen:

| Helper | Proposed VA | Bytes |
|---|---:|---:|
| Extension initializer |0x9D480|42|
| Size front end |0x9D4AA|49|
| Backend cache-base route |0x9D4DB|25|
| Copy cache-base route |0x9D4F4|25|
| Delete cache-base route |0x9D50D|25|
| Direct-size guard |0x9D526|18|
| Copy-group guard |0x9D538|23|
| Release scope guard |0x9D54F|40|
| Index scope guard |0x9D577|40|
| Update scope guard |0x9D59F|43|
| Count reply guard |0x9D5CA|29|

Total0x167=359 bytes, ending0x9D5E7;512-byte reservation leaves153 bytes. These sizes cover the actual minimal routing/guard/helper roles; array construction, indexing, folder creation, worker loops and release cleanup are stock edits, not omitted large helpers. The relocatable assembly specimen contains image-local PC-relative relocations, not a completed patch. Final rel32 displacement resolution does not increase instruction sizes; exceeding512 bytes for implementation corrections requires an explicit placement adjustment, not silent overlap.

The accepted segment/section map has no existing section or segment in [0x9D480,0x9E2B8). Its first512 bytes can become a **new declared extension of RX**, rather than a claimed unused cave inside an existing function. Header/interpreter bytes remain at0x40–0x217. RW file start0x9E2B8 and VA0x29E2B8 remain untouched. At4KiB granularity the reservation ends before0x9E000, within the page already containing the old RX end; it introduces no new overlap with RW. This uses accepted layout evidence, not a repeated cave search.

Required ELF changes:

| Field | Minimal value/action |
|---|---|
| RX PT_LOAD entry at file0xB0 | p_filesz and p_memsz0x9D480→0x9D680; flagsRX, offset/VA0, align0x200000 unchanged |
| RW PT_LOAD entry at file0xE8 | p_memsz0x13BF8→0x13CF8; p_filesz0x61D8, offset0x9E2B8, VA0x29E2B8, flagsRW and align unchanged |
| `.bss`, section24 | sh_size0xDA10→0xDB10; sh_addr0x2A44A0 and SHT_NOBITS unchanged |
| Dynamic `_end` value, file0x1398 |0x2B1EB0→0x2B1FB0 |
| Static `_end` value, file0xE63F8 |Same update |
| Fixed frame-cache endpoint instruction0x4EA94 |**Remain stock**, still pointing to0x2B1EB0; do not retarget it when `_end` moves |
| Feature hooks/immediates |As enumerated above; original-byte guards in eventual patch manifest |

`_edata`, `__bss_start`, original frame-stream endpoints, all program-header locations/count, `.interp`, e_entry, e_shoff/e_shnum and segment alignments remain unchanged. Existing dynsym/hash/strings, GOT/PLT, dynamic pointers, relocation targets/addends and EH header/table stay at their original locations. BSS extension follows the accepted loader/end-symbol finding; no new heap allocator policy is added.256 bytes end at0x2B1FB0, within the already-rounded4KiB RW page ending0x2B2000; ownership still requires the explicit p_memsz extension.

The minimal plan adds no section header. ELF loading uses program headers; the helper region can be described by a VA-based manifest even though it has no named section. This avoids growing or relocating the full section table. An optional helper section/symbol table for tooling is not needed for execution and would be a separate file-metadata choice. ELF length remains0xF0D98; later container payload offsets need not move. Eventual container integrity/revision updates are still ordinary build work, not performed here.

### Relocation and unwind limits

Resolve specimen references to stock continuations, cache/name symbols and new extension/bias VAs at patch construction time. Use rel32 branches and RIP-relative LEAs; for ET_DYN their displacements remain valid at a common load bias. No dynamic absolute pointers, relocation entries, imports or catch RTTI are added.

Helpers contain no new calls, pushes/pops or stack adjustments. In the one redirected existing call, the guard tail-jumps to the original backend; backend exceptions therefore traverse the original stock call site and frame. Allocation/deletion calls remain in stock bodies with their original unwind descriptions. Mid-function thunks finish before stock code makes any calls. No synchronous throwing operation is introduced at a helper PC, so a combined838+helper FDE index, relocated dynamic tables and exception landing pads are not required for this implementation.

This is **not** a claim of complete asynchronous stack-trace coverage while execution is briefly inside a thunk: those PCs lack new FDE entries. Adding profiler/signal-time unwind coverage would require suitable inherited-frame descriptions and an index/registration placement solution; it is deferred absent a concrete ordinary-operation dependency. The specimen deliberately avoids prologue-displacement thunks that change stack state, rather than relying on old FDEs to describe changed helper frames.

## Deferred changes and superseded blockers

- Filesystem/ZIP/GroupInfo outcome rewrites, mount-identity/optional-absence certification and transactional dictionary publication: retain stock behavior; extending supported names does not require those APIs.
- Reader leases, epochs, worker-result fields, coordinator/join redesign and serializing backends: retain existing ownership/scheduling; only bounds and table offsets change.
- New exception catchers/import slots, GNU-hash rebuild, expanded dynsym/dynstr/relocation tables and combined unwind header: eliminated because allocation behavior and throwing call sites remain stock.
- Whole B4SizeOwner record, USB size caching, cache readiness metadata and force-refresh changes: eliminated; use the stock sentinel and256-byte extension.
- Elaborate activation negotiation/journaling, broad checked retries and copy/size calculation hardening: deferred; bounded table addressing and aggregate expansion overflow preflight do not imply them.

Earlier reports' unavailable libc/loader binaries, allocator-capacity measurements, new catch ABI exports, mount-event producers and dictionary rollback API are therefore **not mandatory blockers for this minimal placement plan**. Preserve their findings as background without inheriting their broader scope.

## Genuine remaining work/blockers

1. This is a sized design, not a finished original-byte-guarded patch. Resolve image-local relocations, apply the exact stock instruction windows and validate the assembled helpers with stock continuation code before building. The accepted old35-case ownership model and17-case large-placement model do not certify this different implementation; their applicable bounds/end-consumer findings are reused, and their leases/epochs/catch cases are not retained requirements. No verification matrix was rerun here.
2. The eventual PIC/population implementation must retain the accepted bounded97-group addressing and name-region preflight. Omitting that check would permit an expansion-introduced fixed-region overflow. No new PIC audit is requested by this handover.
3. Actual intended voice_sysex binary/source is unavailable in this folder; merge comparison remains pending. This does not block the separate stock-based B4 test build. Start that build from clean2.2.2.0.0 with accepted QNX hash `7db8a8276f0bda34d22fdd2e8744b304dc7d62f80f9189836b107a4d7b178cff`; later reconcile actual branch hooks and RX/BSS ownership rather than replacing its QNX image wholesale.

There is no demonstrated ELF-space blocker under the revised scope: the359-byte bundle fits the existing file gap with no file growth, and the256-byte cache extension preserves stock allocations/addresses. No firmware image was modified or built. Stop at this plan.
