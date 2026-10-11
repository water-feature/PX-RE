# B4: eight-byte control reservation plan

3 October 2026. Continues `readme_B4_pointer_storage.md`. Proposed physical ownership transfer: `[0x80057AD8,0x80057AE0)` from the default heap to B4 control state. This report identifies stock change sites and remaining verification limits. **No bytes were patched, no reservation enacted, no firmware built.**

## Conclusion

The reservation is structurally compatible with the **recovered stock heap provider and initialization paths**. Keep heap base 0x80053AE0, reduce heap size from 0x4000 to **0x3FF8**, and make its exclusive end **0x80057AD8**. Both provider and lazy initializer defaults must change. Explicit control initialization belongs immediately after the cold-start DINIT call.

The direct recovered paths support this plan; computed/indirect bound writers and reset entry paths are not globally closed. Historical voice_sysex evidence shows no overlapping stock change sites, but its binary is unavailable here, so shared RAM ownership and current-branch compatibility remain blockers. This is a concrete source-site plan, not a patch-ready or merged-firmware certification.

## Reservation and invariant

```text
Heap:          [0x80053AE0, 0x80057AD8)   16,376 bytes
B4 pointer:     0x80057AD8                four bytes
B4 state:       0x80057ADC                four bytes
Reservation:   [0x80057AD8, 0x80057AE0)   eight bytes
```

Uncached aliases are **0xA0057AD8 / 0xA0057ADC**; physical reservation is `[0x00057AD8,0x00057AE0)`. They are the same storage, not independent words. Use the cached alias consistently unless a separate cache/coherency contract requires otherwise.

The exclusive-end rule allows break==0x80057AD8, but a positive allocation must not return or write a block extending into the reservation. Allocation metadata, terminal headers and growth zeroing must remain inside the shortened heap. The eight-byte cut preserves the allocator's eight-byte alignment and places no new storage above the original heap boundary. This does not establish a general stack bound.

## Evidence and scope

Connected Ghidra reports `ram: 9d000000 - 9d08195f`. Checked the provider and boundary initializer in Ghidra and raw instructions from the existing stock PIC payload. Checked exact direct call encodings, targeted address constructions, DINIT descriptors and recovered constant-address accesses. A supplementary constant-register scan is incomplete at joins/calls and is used only to find candidates, not to prove absence of aliases.

No second provider or explicit stock reconfiguration setter was recovered. This means **all recovered providers/paths are listed below**, not that arbitrary computed writes have been excluded. Missing xrefs are not used to approve RAM ownership.

## Heap provider: exact source change

**0x9D081848** constructs its provider descriptor at **0x80053A4C** every time it is called:

| Site | Stock operation | Planned change |
|---|---|---|
| 0x9D081854 | Stores additional descriptor word 1 at +8 | None |
| 0x9D08185C / 860 | Constructs/stores base 0x80053AE0 | None |
| **0x9D081868** | `addiu v1,v1,0x4000`, after `lui v1,0` | Change provider size to **0x3FF8** |
| 0x9D08186C / **870** | Return; **delay stores size at descriptor+4**, 0x80053A50 | Preserve the delay store and descriptor semantics |

The only recovered direct provider call is **0x9D07FA7C**, in lazy initialization. No literal function-pointer word to the provider was recovered. Provider+4 cannot be changed merely by writing RAM once: another provider invocation reconstructs the descriptor.

## Bound initialization and reconfiguration paths

Lazy initializer **0x9D07F9F0** is reached by **0x9D080BF0** when sbrk sees break==0. Entry **0x9D07FA10/14** checks that break; nonzero returns without reinitialization.

1. **Lower bound zero:** 0x9D07FA3C/40 selects fallback 0x80053AE0, constructed at **0x9D07FB3C**, a jump delay slot. Base is unchanged.
2. **Upper bound zero:** 0x9D07FA4C/50 selects the fallback at **0x9D07FB40**. Stock loads size0x4000 there, constructs base at FB44/48, and **delay 0x9D07FB50 adds base+size**. Change **0x9D07FB40 to 0x3FF8**. This is the second mandatory constant change.
3. **Nonzero preconfigured bounds:** 0x9D07FA58–78 normalizes cached/uncached aliases using `ext` and `movz`, then calls the provider. The provider base/end are read at **0x9D07FA84/88**, and **0x9D07FA94 forms end**. Requested bounds are checked against that range. An upper outside the range is replaced with provider end; it does not remain an accepted larger heap. Shrinking provider size therefore also constrains this recovered override path. Do not remove the validation or treat only the zero-default branch as relevant.
4. **Failed validation:** return without setting break; sbrk returns failure if break remains zero. It must not activate B4 or clear retained ownership opportunistically.
5. **Alias-specific output paths:** all consume the same validated provider range. The cached output is the reachable stock route for the fixed linked address 0x8003A384. Alternate raw branches remain listed because the decompiler hides them as unreachable:

| Raw stores | Destination | Role |
|---|---|---|
| 0x9D07FAF8 / FAFC / FB00 | lower / upper / break | Uncached-output branch after OR with 0xA0000000 |
| 0x9D07FB64 / FB68 / **FB70** | lower / upper / break | Cached-output branch; **FB70 is a jump delay store** |
| 0x9D07FB74 / **FB80** | lower / break | Remaining linked-address branch; **FB80 is a jump delay store**; not the reachable stock cached route |

There is no separate recovered setter resetting these bounds in mainline code. A proposed change that introduces one must satisfy the same provider/cap contract. No change is proposed to output alias selection or lower-bound construction.

## sbrk growth and why a defensive guard is needed for stronger closure

The active growth path at **0x9D080BB4–BDC** computes the candidate break, checks wrapping, loads upper at **0x9D080BCC**, compares at **0x9D080BD0**, and commits only at **0x9D080BDC**. Its signed nonpositive/shrink path uses lower bound and commits in **delay 0x9D080C3C**. Wrapper **0x9D08149C** zeroes successful growth only after sbrk returns.

Under cold-zero initialization and the recovered writers, changing provider and default size suffices: every positive allocation sees an upper no larger than the shortened provider end. **If a hidden writer preseeds break nonzero and upper larger, the lazy initializer is bypassed.** The two constant edits alone do not protect against that unresolved edge.

For a plan intended to tolerate bound reconfiguration, add a reservation-aware validation at the sbrk boundary, with **0x9D080BCC–BD4** the exact existing upper-check seam and **0x9D080BD0** the comparison to preserve. It must reject growth past physical0x57AD8 independently of a mutable upper word, validate current break/lower against the provider region, preserve cached/uncached alias semantics and preserve errno/failure behavior. An invalid current heap must fail rather than silently move break backwards or reuse live allocations. This guard's helper address and instruction replacement are **not yet laid out or validated**. It is a required defensive design/change site if computed-writer closure remains unavailable, not an implemented fix.

A hard growth guard does not make arbitrary direct RAM writes or an already corrupt free list safe. Direct/DMA writes into the proposed control bytes remain an ownership-verification blocker; their absence was not proven by the search.

## Cold initialization: exact explicit seam

Cold-start runtime at **0x9D001038/03C** sets SP, and **0x9D001040/044** sets GP. It clears `[0x8000005C,0x8003A384)` at 0x9D0010B0–C0; this does not include the control reservation.

The DINIT call is:

```text
0x9D0010D4  lui   t0,0x9D08
0x9D0010D8  addiu t0,t0,0x1090
0x9D0010DC  jalr  t0
0x9D0010E0  nop                 [delay]
0x9D0010E4  first continuation instruction
```

**Proposed explicit initialization hook:** retarget the existing **0x9D0010D4/D8** address construction to a dedicated wrapper. It calls original **0x9D081090** exactly once, then zeroes words **0x80057AD8/ADC**, then returns to **0x9D0010E4**. Preserve the caller's return state and the original DINIT calling convention. Do not simply add stores before DINIT and assume later initialization will preserve them.

No malloc is called in the recovered pre-main startup sequence before this seam. Earlier indirect hooks are fixed no-op 0x9D081950 and cache setup0x9D080D20/056C. Main is reached later through runtime0x9D0813F8, which calls **0x9D052940 at 0x9D081424**. This is a runtime initialization check, not a repetition of the state-machine startup audit.

DINIT parser **0x9D081090** processes descriptor records until the zero-base terminator at **0x9D01A84C**. The supplied 93 descriptors contain no destination intersecting the proposed reservation. Relevant reset descriptors:

| Descriptor | Zeroed region | Ownership consequence |
|---|---|---|
| **0x9D01A824** | `[0x80053A4C,0x80053A70)` | Provider descriptor plus heap break/bounds reset |
| **0x9D01A80C** | `[0x80053A70,0x80053A90)` | malloc state reset |
| **0x9D01A830** | `[0x80053AD8,0x80053ADC)` | errno reset |

The wrapper, rather than a DINIT table enlargement, supplies the new control initialization. Do not extend either descriptor through intervening owned objects or across the heap. Wrapper code placement remains unassigned and must avoid other branch ownership.

## Lifetime ownership

| Lifecycle | Pointer/state rule |
|---|---|
| Cold runtime through proposed DINIT wrapper | Both zero after DINIT; next preparation owns allocation anew |
| Initial cache setup: 0x9D0530E4 -> 0x9D079220 -> 0x9D040ED8 | Allocate once only after control initialization; preserve established pointer across subsequent calls |
| Count reloads at 0x9D01B914 and 0x9D02454C; size reload at 0x9D01B724 | Retain pointer; invalidate readiness while rebuilding, without resetting allocator or allocating again |
| Lazy bounds init0x9D07F9F0 | Do not clear the control record merely because the function was called; nonzero break makes it a no-op |
| Full DINIT/allocator-lifetime reset | Invalidate readiness and pointer together with allocator state before any reader resumes; never retain a pointer into reset allocation state |
| Clearing break alone / resetting allocator globals separately | Unsupported without a coordinated lifetime reset. Cannot preserve pointer or free a stale pointer after allocator reset |

The only recovered DINIT entry is the fixed indirect cold call at 0x9D0010DC; no direct J/JAL or literal pointer word to0x9D081090 was found. **Additional computed DINIT/reset entry paths remain unclosed.** If any exist, they must route through the control-reset wrapper or acquire equivalent coordinated ownership. This report does not claim all possible warm resets are covered.

## voice_sysex compatibility using available evidence

Actual workspace contains stock/container/PX_Main inputs and handovers, but **not voice_sysex_2.2.2.0.3.bin or its source**. Available historical evidence is readme_B4.md section10: that branch binary's SHA-256 is `bbc3c2ad26bef7310fc15cac8edee22a1792d8ced3788f7080acccc047304857`; reported PIC differences from stock are:

```text
0x9D001200–0x9D00121F
0x9D0258B4
0x9D0295B0–0x9D0295B3
0x9D051BC4
```

DINIT was reported unchanged. The proposed startup source hook0x9D0010D4/D8, provider constant0x9D081868, initializer constant0x9D07FB40 and sbrk-check seam0x9D080BCC–BD4 are **disjoint from those historical changed bytes**. The existing0x9D001200 code area is owned by voice_sysex and cannot host the new wrapper.

This establishes preliminary byte-site compatibility only. It does not show what RAM the added voice_sysex code uses, whether it assumes the full heap, or whether a newer branch revision changed ownership. Before merging, inspect the actual intended branch's added code/data for physical0x57AD8–57ADF aliases and heap assumptions, confirm its startup/DINIT changes, and assign nonoverlapping helper code. Historical unchanged DINIT does not prove the control bytes are unreferenced by injected code.

## Concrete change list and blockers

Planned source-site changes, **not performed**:

1. **0x9D081868:** provider size0x4000 ->0x3FF8; preserve size store in return delay0x9D081870.
2. **0x9D07FB40:** default upper construction size0x4000 ->0x3FF8; preserve addition in jump delay0x9D07FB50.
3. **0x9D0010D4/D8:** redirect DINIT target to a wrapper which invokes original DINIT then explicitly zeroes pointer/state and returns to0x9D0010E4.
4. **0x9D080BCC–BD4:** reservation-aware boundary validation if computed/reconfiguration writer closure cannot be established. No helper placement/encoding approved.
5. Any subsequently established allocator-reset entry must invalidate the control record as part of the same reset transaction; no additional exact reset site was established.

Unresolved blockers:

- Computed/alias bound writes and direct/DMA control-region accesses; only recovered writers/providers are closed.
- Additional DINIT/allocator-reset entries that bypass the cold wrapper.
- A reviewed, nonoverlapping code location and calling-convention/delay-slot validation for the wrapper and any defensive guard.
- Actual target voice_sysex revision/source for RAM ownership and current compatibility verification.

No unrelated audit, protocol design, patch or build follows. Reservation remains proposed until those ownership and implementation limits are resolved.
