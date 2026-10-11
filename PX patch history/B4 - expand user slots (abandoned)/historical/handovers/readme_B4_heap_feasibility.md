# B4: permanent heap-extension feasibility

Prepared 3 October 2026. Continues `readme_B4_storage_options.md`, assessing only the permanent 4,480-byte allocation. No firmware/database changes, RAM reservation, build, startup-reentry tracing or USB tracing were performed.

## Decision

**The recovered evidence does not rule out the heap allocation, but does not clear it for implementation.** The significant new finding is that the only recovered stock malloc caller is the sort's large-element branch, and the only recovered sort caller supplies element size 4. That path does not allocate. Allocator concurrency is therefore a conditional concern rather than demonstrated contention on the known MIDI path.

The main blockers are a proven persistent root for the pointer/activation state, closure of computed allocator-entry aliases, and a PIC/QNX activation protocol. No existing spare RAM word pair or stock capacity-negotiation mechanism was established. These gaps must not be filled by assigning an apparently unused address or assuming QNX automatically follows PIC limits.

## Evidence and limits

Connected Ghidra reports `ram: 9d000000 - 9d08195f`, matching the supplied PIC base and extent. Used targeted decompilation/xrefs and raw little-endian instruction checks from the existing `stock_pic_2.2.2.0.0.bin`. Raw checks include argument-setting delay slots. No extraction or validation matrix was repeated.

Direct-call inventories below cover exact J/JAL encodings in the supplied payload. Literal pointer-word and immediate low-half construction checks found no additional references to the named allocator entries. These checks strengthen the recovered inventory; they are **not whole-program proof against arbitrary computed addresses, interior entry points, executable RAM or external registrations**. There is no device heap high-water measurement in these handovers or this pass.

## 1. Allocator ownership, locking and interrupt use

| Function | Proven local behavior |
|---|---|
| **0x9D07EB84** | malloc-like allocator. Mutable global free-list/sentinel state around 0x80053A70–8F; returned user pointer is block-header+8. NULL on exhaustion. |
| **0x9D0817C0** | free-like function. NULL is ignored; clears allocation flag at pointer-4 and may move the allocation cursor at 0x80053A7C to pointer-8. Does not itself shrink the break. |
| **0x9D08149C** | Calls sbrk at 0x9D0814AC; on successful positive growth, zeroes the newly obtained bytes through 0x9D080F4C. Returns -1 on sbrk failure. |
| **0x9D080B98** | Bounded sbrk. Break at 0x80053A64, upper at 0x80053A68, lower at 0x80053A6C. Updates break only after arithmetic/range checks. Sets errno at 0x80053AD8: 12 for growth failure, 22 for invalid shrink. |
| **0x9D07F9F0** | Lazy heap-bound initialization when break is zero. Uses defaults 0x80053AE0/0x80057AE0 and validates/normalizes against the provider. |
| **0x9D081848** | Provider constructs descriptor at 0x80053A4C: base 0x80053AE0, size 0x4000, additional word 1. Stores at 0x9D081854/860 and return-delay 0x9D081870. |

**Locking:** malloc, free, sbrk and its zeroing wrapper contain no interrupt-mask operation, CP0 operation, LL/SC pair or lock-helper call in their recovered bodies. They mutate shared state through ordinary loads/stores. The named APIs are not intrinsically protected against concurrent allocator entry. The sbrk boundary check is not a lock.

**Recovered call chain:**

```text
0x9D05F1F4 -> sort 0x9D07EE10
    conditional 0x9D07F044 -> malloc 0x9D07EB84
        0x9D07EC7C / 0x9D07ED54 -> 0x9D08149C
            0x9D0814AC -> sbrk 0x9D080B98
                lazy 0x9D080BF0 -> 0x9D07F9F0
                    0x9D07FA7C -> provider 0x9D081848
    conditional 0x9D07F00C -> free 0x9D0817C0
```

The prior B4 report already establishes MIDI interrupt reachability of 0x9D05F1F4. No interrupt-path audit was repeated. Its arguments are a1=25 elements and **a2=4 bytes per element**. Sort checks **`sltiu v0,a2,800` at 0x9D07EE40**, then branches to malloc at 0x9D07EE4C only if that test is false. Its delay saves the comparator, not a new element size. The allocation call's delay **0x9D07F048** supplies `a0=a2+1`.

Therefore **the known interrupt sort does not enter malloc or free**. Heap demand depends on element size, not on 25×4 array bytes. It would be incorrect to budget a 100-byte allocation for this caller or declare allocator reentry merely because the sort is interrupt-reachable.

If an additional caller uses element size >=800, allocation is temporary: malloc(size+1), sort, then free at 0x9D07F00C. Allocation failure returns from sort without sorting. The recovered sole caller does not take this branch. Other computed callers would require separate arguments/lifetime evidence.

## 2. Capacity and competing demand

Allocator block spacing is:

```text
rounded_block = (request + 15) & ~7
minimal_growth = rounded_block + 8
preferred_growth = (rounded_block + 0x87) & ~0x7F
```

For request 4480 (0x1180):

- Rounded allocated block: **4488 (0x1188)**, including its eight-byte header.
- Preferred break growth: **4608 (0x1200)**, including terminal metadata and residual free space.
- Retry growth if preferred growth fails: **4496 (0x1190)**.
- Default remaining uncommitted space after preferred first growth: **11,776 bytes**. The residual free block may also be reusable; uncommitted space is not the same as total allocatable capacity.

These figures are **exact arithmetic derived from the recovered implementation**, conditional on the default empty heap and a positive well-formed request. They are not device measurements, worst-case fragmentation bounds or estimates of all firmware demand. An occupied/fragmented heap can satisfy a request from existing free space or fail despite sufficient aggregate free bytes.

| Demand | Established bound and lifetime | Evidence classification |
|---|---|---|
| Proposed extension | 4480 requested bytes, retained until PIC cold restart; preferred first growth 4608 bytes | Exact implementation-derived conditional cost |
| Known MIDI sort | **0 heap bytes**, size-4 local-buffer branch | Exact bound for the recovered caller |
| Large-element sort branch | request=element_size+1; temporary until sort returns | Exact formula; unreachable from the known caller; no global caller-size bound |
| Other stock malloc/free/sbrk calls | None additionally recovered by xrefs/exact direct calls | Inventory result, not a universal zero-demand proof |
| Measured total simultaneous demand | **Unavailable** | No hardware high-water or allocator trace |

**Conditional capacity conclusion:** under the recovered direct-call inventory, default bounds and no previously allocated blocks, the extension fits comfortably; the known stock sort adds no simultaneous heap demand. No supplied measurement establishes a whole-firmware demand bound. Do not sum unreachable hypothetical allocations into a claimed measured maximum, or call the remaining bytes proven spare memory.

## 3. Lifetime and initialization point

The proposed allocation must be **once per PIC cold-start lifetime**, retained across cache reload/import/index rebuild, and not tied to a menu-state initializer or per-group query. Repeated cache initialization must reuse it. Neither allocation nor free belongs in a group accessor or interrupt handler.

The concrete cache-lifecycle seam is:

```text
main 0x9D0530E4 -> 0x9D079220
    0x9D079228 -> count/index initialization 0x9D040ED8
```

This is before the later main state-machine initialization, without needing to retrace that initializer. Additional direct 0x9D040ED8 callers are **0x9D01B914** and **0x9D02454C**; those are reload paths, not justification to allocate repeatedly. Size initialization has a direct caller at **0x9D01B724 -> 0x9D079A08**.

**Proposed allocation site:** a one-time preparation operation at the main lifecycle seam immediately before the 0x9D0530E4 call, once an owned root is available. malloc lazily initializes its own state/bounds; no eager heap setup call is required by the recovered implementation. This identifies where preparation belongs, not a patch encoding or approved hook.

Initialization/publication sequence would be:

1. Explicitly initialize the owned root to pointer=NULL, inactive/stock capacity.
2. Perform one main-context allocation. Preserve/restore interrupt state around allocator mutation unless computed interrupt allocator-entry closure is established. Do not hold interrupts disabled across serial reads, QNX waits or cache rebuilding. Existing evidence does not establish a permitted masking duration.
3. If NULL, leave the root inactive and continue stock initialization.
4. If successful, initialize the 544 new count/index entries to count=1/index=-1. Initialize all 32 size entries to a defined unavailable/default state pending successful population; do not publish unknown size values as real measurements.
5. Retain the pointer while inactive. Run coherent extended count/index and size population through split addressing, with common bounds and name-capacity checks.
6. Publish expanded capacity only after local readiness and QNX agreement. Use an explicit publication order so an interrupt reader cannot see active=true before valid pointer/data.

The stock serial count marker 0xFF distinguishes legacy/extended stock layouts; it is not an established runtime 65/97-group negotiation mechanism. Enlarging loop bounds alone would not supply agreement or readiness.

## 4. Pointer and activation ownership — unresolved root

**No existing stock-owned spare location was established for a persistent pointer and activation flag.** The heap-bound words, malloc sentinels/cursors, errno and provider descriptor are owned by the allocator/runtime. They cannot be repurposed. Existing table slots retain their group meanings. DINIT coverage or a missing xref is not proof of a spare word.

A newly allocated block can own additional control metadata, but placing the pointer/flag inside that block alone creates a root-discovery problem: accessors still need a persistent way to find it, including the NULL/failure case. Assuming malloc always returns 0x80053AE8 is not an acceptable root without proving first-allocation order and default bounds. Reading or repurposing allocator links as the feature's root would couple the feature to mutable allocator internals and was not established as safe.

If eight bytes of control metadata are added to the allocation, request=4488; rounded block=4496, minimal growth=4504, preferred growth remains 4608. This arithmetic does **not** solve root ownership.

Required next evidence is an explicitly owned root field whose lifetime spans the cache lifecycle, including all initialization/reset writers and aliases, or a separately authorized creation of dedicated static control storage with a proven memory contract. This report assigns no absolute address to such storage. **Requirement 3 is not satisfied by the present evidence and remains a blocker.**

## 5. Coherent PIC/QNX failure behavior — required design, not stock behavior

The handovers establish group count request 0x4012 and size request 0x4037, and separate QNX group tables/limits. They do not establish a capability/activation transaction carrying successful PIC extension allocation. No coherent stock fallback follows automatically from malloc returning NULL.

A viable failure design requires **one negotiated active count, 65 or 97, distinct from physical backing capacity**:

- Both sides begin with active_count=65. QNX may have physical backing for 97, but must keep its public selection/import/index/release behavior at 65 until agreement.
- PIC prepares local extension data while inactive, then participates in an explicitly defined readiness/activation transaction. Both sides gate consumers during transition; lost responses must not produce unilateral activation.
- If allocation or population fails, or QNX readiness cannot be established, both remain at 65. Count-page/name rebuilding must not persist partially expanded metadata. Groups65–96 must not be selected, indexed or sent to unchecked stock consumers.
- Preset/SysEx/import values above the active limit require one documented rejection/sanitization policy. Existing IDs0–64 retain their meanings. Already stored expanded metadata must remain recoverable; fallback must not silently rewrite it into a truncated stock index.
- A QNX restart/reconnection must restore agreement before expanded traffic resumes. If a later rebuild fails, gate access and coordinate fallback; do not free a block still reachable by readers.

The transport messages, transition gating, timeout/restart semantics and QNX active-count state are **not identified existing mechanisms**. They are required implementation work/evidence. QNX remains a separate allocation/lifecycle owner; this PIC heap analysis does not prove its expanded backing feasible. Name-region overflow/rollback remains an independent blocker already documented, not reinvestigated here.

## Stop point and blockers

The permanent allocation is **conditionally capacity-feasible on the recovered direct graph**, and the suspected MIDI-sort heap competition is excluded for its known caller. It is neither ruled out nor approved.

Before implementation:

1. Establish a persistent owned root for pointer/readiness; no address has been cleared here.
2. Close computed/interior allocator entry paths and bounds configuration sufficiently to choose safe allocation exclusion and first-allocation assumptions. The allocator has no intrinsic lock.
3. Establish local initialization/readiness and complete split reader/writer routing across initial load and reloads.
4. Identify/design a real PIC/QNX active-capacity agreement, including failure, timeout, restart and expanded persistent metadata handling.
5. If global allocator-entry closure cannot be obtained, obtain allocation/lifetime traces for relevant workloads; treat measured high-water values as observed bounds, not universal maxima.

No additional firmware image is currently shown necessary: the relevant named allocator code is present. Missing ownership/protocol evidence cannot be replaced by guessed RAM locations or inferred runtime measurements. Stop with this feasibility report; no firmware modification or build follows.
