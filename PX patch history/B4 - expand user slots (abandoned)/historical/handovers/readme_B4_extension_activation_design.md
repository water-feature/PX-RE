# B4 extension allocation, addressing and PIC/QNX activation

3 October 2026. Current control baseline: `readme_B4_control_patch_design_revised.md`, verified by `readme_B4_control_entry_hook_test_results.md`. This specifies the next integration design using existing B4 evidence. No firmware modification/build, control ownership search, or USB/startup audit was performed. Addresses below are established integration anchors; where an exact interception instruction or new transport field remains unknown, that is stated rather than invented.

## Recommended implementation

Retain the two stock PIC tables. Allocate one permanent 4,480-byte extension per allocator lifetime, route IDs65–96 through it, and expose 97 groups only after valid local population, QNX preparation and a session-scoped activation barrier. Keep stock-capacity mode available on both sides. A failed negotiation after a possibly committed transition requires quiescence and reconciliation, not unilateral fallback.

Treat persistent name/count rebuilding as a separate transaction. Preflight the entire candidate name set before any serial overwrite, and require durable recoverable backing before destructive rebuilding. Increasing table bounds alone cannot provide rollback.

## Baseline and local control state

The DINIT entry hook at 0x9D081090 clears readiness at **0x80057ADC**, then pointer at **0x80057AD8**, before original DINIT executes. It resumes at 0x9D081098 without recursion or changed register contract. Shortened heap is `[0x80053AE0,0x80057AD8)`; guarded sbrk and provider/default changes remain unchanged. Allocator-only lifetime resets still need equivalent coordinated invalidation; cache reload must not reset ownership.

Define the second control word as a bitfield for this design; the baseline's zero-inactive meaning is preserved:

| Bit | Proposed meaning |
|---|---|
| 0 | ALLOC_ATTEMPTED: one lifetime attempt has begun/completed |
| 1 | LOCAL_VALID: extension count/index and size content belong to the validated current dataset |
| 2 | EXPANDED_ACTIVE: local admission of IDs65–96 is enabled for the agreed session/dataset |
| 3 | RELOAD_GATED: cache-dependent consumers are quiesced for population/transition |
| 4 | LOCAL_FAILED: allocation or current population failed; diagnostic distinction, not readiness |

All unassigned bits stay zero. These are proposed definitions, not stock fields. An extension is usable only with nonzero pointer, LOCAL_VALID and EXPANDED_ACTIVE set, and RELOAD_GATED clear. A pointer alone never implies readiness. Pointer remains retained across reload/fallback; LOCAL_VALID may be cleared without losing ownership. No session identifier or metadata generation is packed into unexplained spare bits: durable/session protocol storage needs separately owned state, still unresolved.

Flag mutation must be serialized with readers and event delivery. Ordinary load/modify/store is not a concurrent update primitive. The design does not infer interrupt safety from the existing allocator tests.

## One-time allocation and population

**Main-context preparation seam:** immediately before main's cache initialization call at **0x9D0530E4 -> 0x9D079220**, whose count initializer call is **0x9D079228 -> 0x9D040ED8**. This is an insertion requirement, not a specified replacement instruction/trampoline encoding.

1. Gate relevant consumers. If ALLOC_ATTEMPTED is already set, reuse the retained pointer or take stock fallback; do not allocate again. Set ALLOC_ATTEMPTED before calling malloc to prevent accidental duplicate preparation. Do not place this operation in the reload functions or an interrupt accessor.
2. Call real malloc **0x9D07EB84**, a0=4480. Existing tests establish first preferred growth4608 and returned payload alignment, but the design must use the returned pointer, never assume 0x80053AE8. Allocator-entry exclusion must be provided; do not hold interrupts masked across serial/QNX I/O. Exact exclusion mechanism and permitted duration remain a blocker.
3. On NULL, retain pointer0, set LOCAL_FAILED, leave LOCAL_VALID/EXPANDED_ACTIVE clear. Continue only a jointly agreed stock-capacity initialization. Do not retry on each reconnect/reload. A new allocator lifetime or separately authorized retry policy is needed for another attempt.
4. On success, initialize all 544 count/index entries with **count=1, index=-1**, preserving documented stock defaults. Size entries start zero as internal unpopulated values. Gate size consumers until queries succeed, so zero is not exposed as a measured size. Fill defaults before storing the pointer; publish ownership with an aligned pointer store while readiness remains clear.
5. Populate all extension rows and 32 size entries from one validated dataset. An empty/missing folder is a successful empty result only when the backend explicitly identifies it as such. Timeout, malformed response and an unknown size are failures, not empty data. Validate index/name-region demand as below. Mark LOCAL_VALID only after the whole extension succeeds.
6. Complete the coordinated activation barrier before setting EXPANDED_ACTIVE and releasing gates. On population failure retain the allocation, clear LOCAL_VALID/EXPANDED_ACTIVE, set LOCAL_FAILED and restore/repopulate coherent stock data before fallback. Never free a block reachable by readers.

Allocating once does not mean populating once. Reloads reuse E, initialize defaults and repopulate it while gated. No malloc/free in lookup, selection, import, or rebuild loops.

The existing 0xFF serial count-page marker distinguishes historical layouts; it is not evidence of 97-group capability. Do not consume erased trailing bytes as new group counts, or infer readiness from names already present in gpGroupNames.

## Split addressing and capacity gates

Let E be the returned pointer:

```text
E + [0x0000,0x1100) : 32*17 count/index entries, eight bytes each
E + [0x1100,0x1180) : 32 size entries, four bytes each

row(g,c):
  validate category 0..16 and ordinary group ID first
  0<=g<=64: 0x80037E90 + 8*(17*g+c)
  65<=g<=96: E + 8*(17*(g-65)+c)

size(g):
  0<=g<=64: 0x8003A118 + 4*g
  65<=g<=96: E + 0x1100 + 4*(g-65)
```

ID65 row/category0 starts E; ID96/category16 starts E+0x10F8. ID65 size starts E+0x1100; ID96 size starts E+0x117C. Neither path crosses E+0x1180. Reject negative/oversized groups before subtraction/multiplication. Handle caller-specific sentinels separately, particularly QNX release semantics; no sentinel is an array index.

Use separate internal population and public access contracts: population may access allocated IDs65–96 while inactive and gated; public consumers require expanded readiness. This avoids a circular dependency in which initialization cannot write rows until already active. Public stock-table addresses remain identical. During destructive stock reload, gate stock cache-dependent readers too; preserving their addresses does not make partially rewritten contents coherent.

Internal IDs remain 0–96 with the established folder map. Browsing ordinals are separate: proposed order is factory, 64 users, 32 purchased. For ordinal b, map 0->0, 1..8->b, 9..64->b+32, 65..96->b-56. Inverse map: IDs0..8 unchanged, IDs9..40 ->g+56, IDs41..96 ->g-32. Stock mode retains stock mapping. This proposed browsing order is a product decision to confirm, not a storage requirement.

## Readiness during reloads

A reload begins by stopping admissions for cache-dependent work and draining/cancelling old-generation requests through established application mechanisms; their exact hook sites are unresolved. It then clears EXPANDED_ACTIVE and LOCAL_VALID and sets RELOAD_GATED, retaining E and ALLOC_ATTEMPTED. Clearing local readiness does not itself announce stock mode to QNX.

Count reload anchors are **0x9D01B914** and **0x9D02454C -> 0x9D040ED8**. Size reload is **0x9D01B724 -> 0x9D079A08**. These must join one reload coordinator rather than independently setting readiness on individual loop completion. Initial size initialization also participates; its startup caller/ordering must be established before activation can be placed at an exact instruction.

Validate both stock and extension data against the same dataset generation, plus QNX readiness and durable name/count generation. An incomplete count-only or size-only reload cannot publish expansion. On success rerun activation barrier for the new generation; on failure keep gates until old coherent data is restored or joint stock fallback is acknowledged.

Existing name-buffer invalidations in 0x9D079220 remain name-cache operations. They are not the new readiness state or a substitute for global cache gating.

## PIC/QNX activation and reconnection

This is a **new protocol requirement**, not an existing recovered transaction. Established messages 0x4012/count and 0x4037/size carry IDs but do not negotiate capacity. Choose new message IDs/format only after dispatcher ownership and versioning evidence; none is assigned here.

QNX is the coordinator. Each exchange must identify protocol version, connection incarnation, candidate dataset generation, active count65/97, and transaction identity. PIC advertises allocated/local-valid capacity; QNX advertises successfully expanded backing and validated dataset. Any reply from an older session/generation must be rejected. Neither side advertises 97 solely because physical backing exists.

Recommended barrier:

1. **GATE:** both sides stop ordinary cache-dependent traffic, drain prior requests and acknowledge quiescence. Private population requests remain allowed and are distinguishable from public expanded traffic.
2. **PREPARE:** validate backing and candidate generation on both sides. PIC reports local readiness only after all rows/sizes succeed; QNX prepares all relevant objects/cache bounds. Both acknowledge the same candidate count/generation, while public capacity remains uncommitted.
3. **INSTALL:** coordinator sends a session-scoped installation token. PIC installs the candidate admission rules while public sources remain gated and acknowledges. QNX installs matching rules only after that acknowledgement. These are installed states, not permission for autonomous PIC user/IRQ paths to generate expanded work.
4. **RELEASE:** open sources only after both installed states are confirmed. A receiver must be prepared for the agreed generation before a source is released. The final acknowledgement may be lost; protocol must be idempotent and status-queryable, with source gates retained until reconciliation. There is no claim that a finite handshake gives simultaneous atomic mode switching under arbitrary message loss.

Timeout before installation can abort to acknowledged stock preparation. Timeout after possible installation means **unknown transaction state**: keep public sources gated, query/reconcile state or reset the session. Do not independently choose65 while the peer might still accept/emit97. A device may be temporarily unavailable during reconciliation; that is safer than incoherent group interpretation.

On disconnect, invalidate expanded admission, gate cache-dependent remote work, and reject old replies; retain PIC allocation. On reconnect create a fresh session and revalidate QNX backing/dataset/local caches before releasing any expanded work. QNX restart must recreate expanded objects, not trust its former acknowledgement. PIC DINIT restart clears E/flags and requires a new lifetime allocation/handshake. Reconnection alone must never allocate a second extension.

**Stock fallback:** prepare/acknowledge count65 and coherent stock dataset under the same gates, then release stock traffic. QNX may retain physical capacity97 but must gate selection/import/index/release and expanded requests at65. PIC must gate getters, direct reads, limits, sanitization and outgoing requests consistently. IDs65–96 in loaded presets/SysEx/import require an explicit unavailable/reject policy, preserving persisted original IDs; do not silently overwrite stored IDs with factory0 or rebuild persistent metadata to a truncated layout merely because allocation failed. Runtime UI behavior for an unavailable expanded preset remains an unresolved product decision.

A legacy peer cannot acknowledge the new protocol: default to65 only after a verified legacy-safe initialization/session policy, or remain gated. Never send unsupported negotiation opcodes speculatively without establishing legacy dispatcher behavior. An expanded-only preset/metadata set must remain recoverable for later capable sessions.

## Name-region capacity and rollback

Existing region `[0xC00000,0x1000000)` holds 65,536 fixed64-byte records, shared across all groups/categories. Count page at0x5FD000 fits 97*17+1=1650 bytes; that does not imply names fit. Builder 0x9D042B80 stops at capacity, while initializer/index consumers can exceed it in existing evidence.

Before any count/name serial write, enumerate the immutable candidate dataset using exactly the builder's record emission rules, including instrument-zero placeholders. Empty97-group categories alone consume1649 records. Use checked wide arithmetic for total demand and prefix indices; require total<=65536, and every actual record access satisfy `0xC00000 + 64*index <= 0xFFFFC0`. Category default index=-1 remains a sentinel. Validate instrument offsets against emitted category count; do not just check a category's first index. Do not infer the complete count convention solely from count=1 defaults.

If preflight detects overflow, abort **before writing**: leave old serial image/count page and committed dataset unchanged, restore/reload old RAM, and retain previous coherent capacity if still available. Otherwise jointly fall back to65 only after independently validating the stock candidate's demand; stock itself can overflow, so65 is not an automatic cure. No partial selection of the first65536 records, silent truncation or out-of-region reads is permitted.

Preflight avoids capacity rollback after destructive writing, but it does not cover I/O errors, power interruption or dataset mutation. Recommended transactional backing is a durable QNX-owned snapshot/journal of the prior serial name region and count page, tied to a generation and verified before overwrite. Candidate enumeration must be pinned or version-checked through commit. Write names, verify them, write corresponding count/index metadata, verify it, then commit the generation and activate; do not treat the existing 0xFF marker as a commit record.

If a write/verification fails, restore both names and counts from the old verified snapshot and reload matching RAM before releasing traffic. If restoration fails, remain gated/unavailable and retain recovery data; do not expose partially rebuilt stock mode. A persisted pending transaction must be detected and recovered before startup cache loads can expose mixed metadata. Exact journal storage, serial restoration API, generation/commit format, reconnect recovery ordering, and QNX filesystem durability guarantees are **unresolved**. No spare serial region, additional PIC staging RAM or extra heap allocation is assumed. Without such backing/commit evidence, a destructive rebuild cannot be claimed rollback-safe and is blocked.

## Exact known integration anchors

These are the established sites from `readme_B4.md`/heap evidence, not a new claim of exhaustive direct/alias coverage or an instruction-level patch plan.

| PIC site | Required integration |
|---|---|
| 0x9D0530E4; 0x9D079220/9228 | One-time preparation before main call; cache lifecycle coordinator |
| 0x9D040ED8; bases 0x9D040EEC/EF0; stores0x9D040F40/F44/0x9D041038; bounds0x9D040FC8/FD0 | Decode validated metadata generation and populate split rows; replace contiguous-end traversal |
| 0x9D0792E0 / 0x9D079300 | Range-checked split getter/availability, public readiness gating |
| 0x9D041184/188/190 | Direct name-display index lookup must use split addressing too |
| 0x9D079A08; count0x9D079A30 | Split size writes, population status, generation-aware completion |
| Around0x9D01B8EC / 0x9D034288 | Import size write / render size read; route and gate direct accesses |
| 0x9D01B914 / 0x9D02454C; 0x9D01B724 | Count/size reload calls join one coordinator |
| 0x9D042A8C; limits0x9D042B04/B08 | Count persistence uses agreed candidate count and transaction |
| 0x9D042B80; bound0x9D042D9C; stop0x9D042D64 | Name preflight/emission consistency; reject overflow; transactional writes |
| 0x9D041E8C | Name reader receives validated index/instrument range; retain defensive serial-end check |
| 0x9D047630 / 0x9D04793C; 0x9D04D4FC / 0x9D04DACC / 0x9D04D6D4 | Physical max96 plus dynamic public-capacity gates; limiter, setter and bulk sanitizer agree |
| 0x9D080E2C / 0x9D080E60 | Active-mode browsing permutation and inverse |
| 0x9D01B7C4 / 0x9D01B9B8 | Import cursor active bounds63/95 and matching mapping |
| 0x9D079978 / 0x9D079744 | Existing count/size request encoding; session/public gates and completion-failure classification |

| QNX ELF site | Required integration |
|---|---|
| Allocation0x16181; constructor0x33390 | Physical97-row object: counts97*17*4=0x19C4, aligned pointer offset0x19C8, pointers97*17*8=0x3388, total0x4D50; allocation failure leaves mode65 or gated |
| Accessors0x33C10 / 0x33C70 | Physical bound96 and dynamic active limit; same row layout |
| Index callback around0x336E4; refresh0x33E9E | Agreed generation/group count, no uncontrolled97 scan while mode65 |
| MakeNewUserFolders0x2DFE0 | Preserve existing folders; extend user folder creation throughu63 under agreed policy |
| gpGroupNames0x2A0160 | Existing133-name map retained, names65–96 already mapped; names alone do not grant capability |
| gGroupSizeCache0x2A4A20; getter0x15320 | Physical97*8=0x308 backing with explicit relocation/ownership and active bounds; do not grow in place without reservation |
| Startup0x7BC0, old endpoint0x2A4C28; updates around0x15BC2/0x15E22 | New backing initializer endpoint and every cache writer together |
| Import validator0x15350; endpoint0x1542A | Active search65/97; new endpoint displacement0x308 only for expanded mode |
| Release0x33CA0; comparison0x33CB1; sentinel0x33D6C | Expanded physical range and active policy without turning out-of-range IDs into broad release; preserve explicit sentinel semantics |
| Dispatcher0x220E8..0x222C3; handlers0x22C6A /0x22DAE | Sample/count/size gates and session validation; new negotiation dispatch seam/opcodes still unidentified |

QNX object's calculated0x4D50 layout preserves constructor's observed count/pointer organization and alignment; it is a design calculation, not a tested allocation or clearance of new storage. No unrelated stock release-loop bug is changed.

## Unresolved decisions and implementation blockers

1. Exact allocation hook encoding, initialization completion seam, reader gating/draining mechanisms and allocator exclusion duration/primitive.
2. Exhaustiveness of split consumers and caller-specific sentinel/error return contracts; precise instructions around the two “around” PIC/QNX sites need targeted review before patch design.
3. Protocol opcodes, owning session/generation state, legacy-peer behavior, idempotent reconciliation and reset/disconnect event integration. No existing message is assumed to provide these.
4. Durable QNX backing for97 objects/cache and name/count journal, generation format, serial write/restore operations, preflight count-emission semantics and crash recovery before public cache use.
5. User-facing policy for expanded presets/imports in stock fallback and proposed browser order. Allocation retry is intentionally once per lifetime here; any other policy needs explicit lifecycle design.
6. Existing allocator-only/interior reset and branch merge limits remain; actual current voice_sysex inputs are still missing. No control/USB/startup audit is repeated or declared closed.

The existing harness verifies allocation/control retention, not this new addressing, activation protocol or persistent transaction. These require focused models/tests after their contracts and exact hook sites are resolved. Stop at this integration specification; no firmware build or flashing recommendation follows.
