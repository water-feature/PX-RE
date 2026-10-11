# B4 PIC split addressing: coverage, instruction design and tests

3 October 2026. Baseline: `readme_B4_control_patch_design_revised.md`. Scope is PIC count/index and size addressing only. No transport negotiation, journaling, prior control/USB/startup audit, firmware modification or build.

## Outcome and implementation limits

Recovered table readers/writers and their direct caller set are enumerated below. Exact relocatable instruction bodies, encoded model words, stock replacement words, return/rejoin addresses and failure contracts accompany this report. Boundary tests pass in the existing instruction interpreter, including real stock getter callers, loader code and both direct name-index windows.

**This is not a physically placed firmware patch.** Helper PCs beginning0x9F000000 are synthetic execution labels outside the supplied payload. Their instruction bodies must be placed and relocated before implementation; no ownership clearance for new code space is inferred. Extra count/index defaults and the private population writer are designed/tested, but the validated source and invocation point for actual extended counts/indices remain unresolved. Neither stock0xFF marker nor erased count-page trailing bytes grant permission to populate97 groups.

Artifacts:

- `b4_split_addressing_harness.py`: exact instruction generation and tests; imports the existing read-only integration harness with revised DINIT entry hook enabled.
- `b4_split_addressing_instructions.txt`: every helper instruction, numeric word and synthetic PC.
- `b4_split_addressing_hooks.json`: exact stock hook words, helper names and model j/NOP words.
- `b4_split_stock_call_evidence.json`: raw call/delay/continuation windows for recovered direct callers.
- `b4_split_addressing_results.json`: recorded test outcomes.
- `b4_split_raw_inspect.py`: targeted read-only instruction listings; unknown encodings remain explicit.

Stock input SHA-256 remained `14e9c9b9dc562b0384fc43b3c5e0eb7fea84a5792d1a19b9b3ea8276ef7646f5`. Run `python3 b4_split_addressing_harness.py`. It generates text/JSON evidence, never a firmware image. The existing interpreter gained an optional `seed=False` argument for starting instruction windows with actual input saved-register values; default full-call behavior remains unchanged.

## Addresses and exact admission rules

```text
stock rows: [0x80037E90,0x8003A118), 65*17*8 bytes
stock sizes: [0x8003A118,0x8003A21C), 65*4 bytes
E+[0,0x1100): 32*17 count/index entries
E+[0x1100,0x1180): 32 size entries
root 0x80057AD8; state 0x80057ADC

row(g,c) = stock_base+8*(17*g+c)             for g0..64
         = E+8*(17*(g-65)+c)                for g65..96
size(g)  = stock_size_base+4*g              for g0..64
         = E+0x1100+4*(g-65)                for g65..96
```

Unsigned checks `g<97`, `c<17` precede address arithmetic. They also reject negative32-bit arguments. IDs97+, category17+ and group/category sentinels never become pointers. Existing group ID meaning is unchanged; this report does not alter browser mappings or parameter descriptor maximums.

Use the preceding integration design's bits LOCAL_VALID=2, EXPANDED_ACTIVE=4 and RELOAD_GATED=8. Allocation ownership stays in E; these helpers do not set/clear ownership or readiness.

- **Public access:** reject every group while RELOAD_GATED is set, including stock rows being rewritten. IDs0–64 otherwise use stock storage even with state0 or absent E. IDs65–96 require nonzero E and `(state&6)==6`.
- **Private population access:** require RELOAD_GATED. Stock rows can be written without E. Extension rows require nonzero E, but do not require LOCAL_VALID/EXPANDED_ACTIVE. This avoids making initialization depend on already published readiness.
- Public size import writes follow public rules. Private population writes follow private rules. A caller must own a serialized reload interval; these checks are not a concurrency lock or an atomic snapshot.

| Boundary | Address |
|---|---|
| ID64/category0 | 0x8003A090 |
| ID64/category16 | 0x8003A110, index word0x8003A114 |
| ID64 size | 0x8003A218 |
| ID65/category0 | E |
| ID96/category16 | E+0x10F8, index wordE+0x10FC |
| ID65/96 size | E+0x1100 / E+0x117C |

## Reader/writer coverage

This is the recovered direct/base-derived coverage, supported by Ghidra, exact direct-target scans and targeted base-construction instruction reads. It is not proof against arbitrary computed addresses or unknown interior entries. No broad RAM ownership search was repeated.

| Operation | Exact stock access instructions | Design |
|---|---|---|
| Count getter0x9D0792E0 | DSP indexed load in return delay0x9D0792FC | Entry j/NOP to count leaf; validated split load |
| Group availability0x9D079300 | DSP indexed loads0x9D079324; loop0x9D079330, sum in delay0x9D079334 | Entry replacement resolves category0 once, then sums17 `(count-1)` entries |
| Selected-name loader0x9D041048 | Arithmetic0x9D041178–18C; index read0x9D041190 | Replace arithmetic window; split load s3, rejoin0x9D041194 |
| Shared-name loader0x9D041E8C | Arithmetic0x9D041EA0–EB8; index read0x9D041EBC | Replace arithmetic window; split load s1, rejoin0x9D041EC0. **Additional direct reader beyond prior selected-name listing.** |
| Stock count/index loader0x9D040ED8 | Count stores0x9D040F40/F44/F90/0x9D041038; index stores0x9D040F64/FA8; default stores0x9D040FF8/FFC | Preserve existing stock65-row interpretation/writes. Add entry reload gate and tail initializing extra rows. Private writer API handles validated extension population |
| Same loader's table reads | 0x9D040F48/F50/F94/0x9D04103C | Remain stock-table reads; no contiguous97-row traversal introduced |
| Size initializer0x9D079A08 | Factory reset0x9D079A20; per-group store0x9D079A44; pointer increment in delay0x9D079A4C | Replace function, same32-byte frame; per-ID private size write, bounds65/97 determined by E while gated |
| Import size write | Group in s4 at0x9D01B8C0; shifted0x9D01B8DC; address0x9D01B8E8–F0; store0x9D01B8F4 | Intercept BEFORE shift, resolve s4 to split size slot, preserve v0 value; reject without store |
| Size renderer | Group s3 low byte0x9D034260; shift0x9D034280; DSP indexed read0x9D03428C | Replace address/load window with split read into a0; neutral0 on unavailable |
| Cold DINIT | Existing zero descriptor0x9D01A3B4 covers stock caches | Unchanged stock table reset; revised entry hook clears root. Extension content is invalid after allocator lifetime reset |

Count rebuild0x9D042A8C and name builder0x9D042B80 query QNX through0x9D079978/9340 and build serial scratch data; they are **not additional direct writers of these RAM tables**. Their group traversal/persistent metadata consistency remains separate. Do not classify serial page writing as a RAM table store, or assume addressing changes expand those producers.

## Caller-by-caller bounds and unavailable contracts

Stock getters have no bounds gate. Parameter-origin callers normally obtain group/category through runtime halfwords or parameter accessors. Stock descriptor maxima at0x9D047630/793C are64; category maxima at0x9D047648/7954 are16. Those nominal bounds do not protect raw getters or malformed runtime state. New leaves enforce physical0..96/0..16 and readiness independently. No caller's contextual nominal bounds are used to skip checking.

**Count result:** return count unchanged for valid rows; unavailable/invalid returns **1**, v1=0. Valid returns v1=1. Count1 is the stock empty/default convention, enabling instrument-zero behavior. Returning0 would make limiter's `count-1 & 0xFFFF` produce0xFFFF; returning-1 also corrupts unsigned/packed consumers. Existing callers do not use v1 as a status flag; status-aware entry gating can be added separately. A safe empty result does not prevent all caller side effects.

| Count call PC(s) | Input provenance / existing consumer | Required contract |
|---|---|---|
| 0x9D04D5A4 | Runtime group/category at parameter-base+0xC6/+0xCA | Limiter instrument0x64: compare requested instrument with count, otherwise return count-1 |
| 0x9D04D5F0 | +0x44/+0x48 | Limiter instrument0x23, same contract |
| 0x9D04D620 | a0/a1 chosen from current part/group/category by branches, or partB loads | Common limiter `addiu v0,-1` at0x9D04D628 then mask0xFFFF at62C; count1 yields0 |
| 0x9D04D658 | +0xE34/+0xE38 | PartB instrument0x64 compare, then common limiter |
| 0x9D04D688 | +0xDB2/+0xDB6 | PartB instrument0x23 compare, then common limiter |
| 0x9D04DED0 | +0x44/+0x48 | Setter checks selected instrument vs count using signed slt atDED8 |
| 0x9D04E024 | +0xDB2/+0xDB6 | PartB setter signed comparison atE02C |
| 0x9D04E560 | +0xC6/+0xCA | Setter comparison atE568 |
| 0x9D04E638 | +0xE34/+0xE38 | PartB setter comparison atE640 |
| 0x9D04E694 | Category loaded+0xCA; group supplied by predecessor | Setter masks count16 bits, calls limiter for parameter0x64 |
| 0x9D04E6F4 | Category+0x48; group supplied by predecessor | Same, parameter0x23 |
| 0x9D04E7A4 | Category+0xDB6; group supplied by predecessor | Same, partB parameter0x23 |
| 0x9D04E848 | Group+0xE34; category is **a1-1 in delayE84C** | Validate resulting category; zero predecessor category becomes0xFFFFFFFF and returns safe1. Preserve this stock call behavior, do not “fix” it silently |
| 0x9D0413C8 | Group parameter0x22, category0x24 | Stores count at SP+0x14, routes instrument through limiter; safe1 leads instrument0 |
| 0x9D04168C | Group0x63, category0x65 | Corresponding second-slot path, same safe1 |
| 0x9D02A6E8 / 0x9D02DE80 | Group0x22/category0x24 | State paths store count at SP+0x10 before instrument increment/decrement calls; safe1 protects arithmetic, but does not cancel subsequent messaging |
| 0x9D02D4E0 / 0x9D02E0F8 | Group0x63/category0x65 | Corresponding second-slot state paths, same contract |
| 0x9D07499C | Explicit loops group0..64, category0..16 | Count export packs count into two7-bit bytes. Unavailable1 is safe encoding; full export must be admitted only for a stable dataset |
| 0x9D0749F0 | Explicit group/category loops; old end-group65 at0x9D074AAC | Skip name export if count<2 at0x9D0749FC/A00; unavailable1 skips. Extending export bounds is separate from split lookup |

No original getter caller is assumed to handle -1 or NULL counts. New count leaf preserves all argument registers and all t-registers, whereas old getter modified a0/a1. Only v0/v1 change; RA/SP/saved registers remain intact. v1 is already clobbered by stock getter. Readiness gating must stop stateful operations before calling setters while reload is in progress: safe1 alone may otherwise reset a selected instrument to0 or allow subsequent message calls. It is a memory/result safeguard, not permission to continue a reload-time operation.

**Availability callers:** 0x9D02EB30/EB7C/EC34/EC80 receive inverse-selector group IDs; no category argument exists. They branch `blez` atEB38/EB84/EC3C/EC88 and keep searching. Return0 for invalid/inactive/gated group, otherwise exact17-category sum(count-1). The helper resolves category0 using zero, not arbitrary incoming a1. It changes only the original availability clobber set a0/a1/a2/v0/v1. New broader selector maximum/mapping must bound those search loops; addressing alone does not change them.

**Selected-name reader:** group/category in s1/s4, instrument in t1; t1==0 uses the existing placeholder path before this lookup. Preserve t1 and input group/category; invalid/unavailable supplies s3=-1. Rejoin at0x9D041194; existing sentinel branch0x9D041198 and s2 shift in delay0x9D04119C run unchanged, taking0x9D04136C and returning-1 without serial reads. Valid stored index=-1 uses the same empty path. No NULL dereference occurs.

**Shared-name reader:** input a0=group,a1=category,a2=instrument; recovered direct caller0x9D074A18 comes from export loops. Preserve a2; invalid/unavailable supplies s1=-1. Rejoin0x9D041EC0; branch0x9D041EC4 checks sentinel before its delay adds instrument at0x9D041EC8. The taken empty path0x9D042020 is unchanged. The full existing formatting path includes unaligned stores not executed by these split-window tests. Stored index=-1 is valid-empty, distinct from v1=0 public-API unavailability.

**Size population:** caller0x9D01B724 ignores the original function's unspecified return. Replacement returns v0=1 only when all addressing stores succeed,0 on admission/store failure. Coordinator must consume this status before claiming readiness. Factory size0 is initialized directly; IDs1..64 queried in stock mode,1..96 when E exists. Real0x9D079744 returns a size word without a separately recovered success signal: addressing completion is not proof of successful external queries. Unknown/error size classification remains unresolved. Do not set LOCAL_VALID here.

**Import writer:** s4 is the unshifted mapped group, v0 the returned size. There is no category. Valid public address stores the word, restores command a0=0x402C0001 and continues0x9D01B8F8. Invalid/gated/unavailable jumps to existing state-return0x9D01B6B0 with s0 unchanged; no table write, count/name rebuild or later-success path. It does not undo QNX work already initiated before the interception. Admission before that work is an essential external integration requirement, outside this addressing window.

**Renderer:** s3 is an eight-bit group ID. Valid reads preserve its actual size. Unavailable returns ordinary numeric0 in a0 and rejoins0x9D034290. This is a precisely defined neutral display surrogate, **not a successful size measurement**. A distinct dash/error label is optional UI work; it is not implemented here. No size-query-success claim follows from displaying0.

**Private writers:** count/index inputs a0=g,a1=c,a2=count,a3=index; size inputs a0=g,a1=size. Return v0=1/v1=1 on a store,0/0 without any table store on failure. Source must supply a validated count>=1 and an index=-1 or valid record index; these address helpers do not validate record demand or repair bad metadata. They preserve input arguments, t-registers, RA/SP and saved registers. No errno change. Stored count/index sentinel/default semantics remain unchanged.

## Exact instruction-level integration

All new leaf bodies use ordinary loads/stores and shifts, no DSP indexed instruction or extra stack frame. Resolver uses only its two designated scratch/result registers. Extended row arithmetic is `((17*g)-1105+c)<<3`; extended size arithmetic is `((g-65)<<2)+0x1100`. Stock arithmetic uses identical bases/offsets. Constants1105=65*17 and0x1100=32*17*8 are explicit.

The current unshared model contains637 helper instructions (2548 bytes). This is a reference design size, not a minimized production placement; it cannot be assigned to the small leftover control-helper gaps without new placement evidence.

Each hook is **j helper; NOP** over the first two listed stock words; it preserves caller RA. Model executes these words through real delay-slot semantics. Actual j encoding must be recomputed for the assigned physical helper address. Every ordinary helper transfer delay is NOP, except the availability sum branch adds the current `(count-1)` in its delay, and the size initializer restores SP in return delay. No branch-likely is introduced.

| Hook address; displaced stock words | Body / rejoin |
|---|---|
| 0x9D0792E0: 00041100,00442021 | count leaf; returns directly to caller. Original getter body/DSP return delay bypassed |
| 0x9D079300: 000430C0,000421C0 | availability leaf; resolves row, sums17, returns |
| 0x9D041178: 00518821,0234A021 | selected_index; v0/v1 scratch, s3 index; jump0x9D041194 |
| 0x9D041EA0: 00041100,00442021 | shared_index; v0/v1 scratch, s1 index; jump0x9D041EC0 |
| 0x9D01B8DC: 0014A080,3C04402C | import_size; v1/a1 scratch, valuev0/group s4 retained; success0x9D01B8F8, failure0x9D01B6B0 |
| 0x9D034280: 00132080,3C038004 | render_size; a0/v1 scratch, s3 retained; jump0x9D034290 |
| 0x9D079A08: 27BDFFE0,AFBF001C | replacement size_initialize; same32-byte frame and saved RA/s0/s1/s2 slots as stock; calls real size query and private size writer |
| 0x9D040ED8: 27BDFFE0,AFBF001C | count_entry_gate; requires RELOAD_GATED, else returns0 without writes or serial reads. Replays SP-32/RA save then jumps0x9D040EE0 |
| 0x9D041014: 8FBF001C,8FB20018 | count_defaults_tail; gates and checks E, fills544 extra count1/index-1 entries, leaves size entries intact, returns status1, replays displaced RA/s2 loads then jumps0x9D04101C |

The count tail may use t0–t3; the original count loader already clobbers these and restores its saved registers in the reused epilogue. It adds no nested call/frame. Absent E, stock count reload still succeeds. Stock count page interpretation remains65-row; counts/indices for65–96 are defaults until an explicit private population caller fills them. Repeated count reload invalidates/reinitializes extension content while preserving its allocation; readiness publication is external.

The private writers and public pointer/index/size API leaves are fully specified in the instruction artifact but have no recovered stock calls: they are new APIs to be placed and integrated. The exact external invocation/source for extended count population is not yet established. A coordinator must calculate validated prefix indices from the full candidate dataset; it cannot blindly use the stock loader's t1 after legacy/default rows, or reuse serial trailing bytes without a layout contract.

## Tests and remaining gaps

Passed120 group/category/state/root combinations: groups64/65/96/97, categories0/16/17, state0/1/7/9/15, pointerNULL/nonNULL. Each combination checks public/private addresses, count/index results, guarded writes and both direct name-index windows. Separate size read/write/import/render and availability checks cover those groups and states. Rejected writes leave RAM unchanged; successful writes are checked at their expected split destination and restored. Negative group/category values are additionally rejected.

Additional passed tests:

- Actual malloc(4480) under revised DINIT produces E; no fixed E assumed.
- Count getter preserves arguments and t-registers on ready/inactive/gated paths.
- Real0x9D04D4FC limiter with group65 yields count-1 when ready and0 when inactive/gated; no0xFFFF underflow.
- Size initializer executes real replacement prologue/epilogue and96 query/store iterations with E,64 without E; nongated entry returns0 without queries.
- Stock count loader executes its stock instructions/serial fixture through65 while gated, then extra default tail writes the544 extension entries. Nongated entry leaves RAM unchanged and performs no serial reads. Size extension retained.
- All544 private count/index entries can be populated through the actual writer instructions while gated. A valid stored index=-1 is returned as valid-empty, not dereferenced.
- Split-helper execution checks that it never writes the control reservation. Root/state stay owned by baseline lifecycle code.

Limitations: synthetic helper placement; custom interpreter; flat MMIO and external query/serial stubs; no interrupts/concurrent readers; no external-query failure signal; no actual97-group serial parser; direct name/import/render tests stop at their exact rejoins, not full application workflows. Bounds, unavailable results and private-store permission are tested; generation consistency and side-effect suppression by upstream callers are not. No stack bound or new helper ownership is claimed.

## Essential PIC/QNX consistency versus optional protocol design

**Essential regardless of implementation:** both processors must admit the same public group domain for each usable dataset; preserve IDs0–64 and meanings65–96; expand/check QNX count/pointer/size backing before new-ID access; use matching count/name/size metadata; prevent public use of uninitialized/reloading rows; reject unavailable expanded IDs before side-effecting imports or selection; classify allocation/query/population failure and reconnect/reset before expanded use. QNX's unchecked size indexing and release sentinel behavior must not receive an invalid group masquerading as an ordinary index. Count export/selector/rebuild bounds must agree with usable capacity. These are correctness invariants, not a required wire format.

**Optional choices from the previous proposal:** QNX coordinator role, named GATE/PREPARE/INSTALL/RELEASE phases, new negotiation opcodes, transaction tokens, leases, session/generation field format, status-query messages and a particular handshake. They are possible ways to satisfy the invariants, not individually proven necessary. A simpler bounded workflow may be sufficient if it demonstrably provides coherent failure/reconnect behavior. This report implements none of them. Persistence rollback requirements and journal choices are outside this task.

Stop at these addressing designs/results. Remaining focused work is physical helper placement/relocation, the validated extension-population source and exact call sites, external size-failure classification, and upstream admission/status consumption. No firmware build follows.
