# B11 investigation findings

Placement follow-up: see [b11_placement_feasibility.md](b11_placement_feasibility.md). A newer 276-byte in-place scratch layout supersedes this document's added-wrapper size estimate for the single-bank case; full behavior and ownership verification remain incomplete.

Date: 9 October 2026. Investigation only; no firmware modifications, hooks, version bump or flashable package.

## Decision

A small shared directional search looks practical in code size, but **implementation feasibility is not yet established**. The cache builder proves placeholder-inclusive counts, and the four dedicated Type call sites are recovered. A standalone search sketch emits **112 bytes**. No PIC placement has been verified, and the count getter, group availability helper and portions of the setter remain inaccessible through the current Ghidra function coverage. Do not implement from this report without resolving those blockers.

This is an evidence report with explicit outstanding work, not a completed certification of the requested count and placement contracts.

## Sources and loaded binary identity

The only project document read was `handover_B11_hide_empty_categories.md`. Other project-file contents, including patch histories and packaging scripts, were not read. Subsequent investigation used the active Ghidra program. Filename searches were separately authorized by the user.

The first active program was the Prophet X x86-64 QNX application. It was subsequently replaced by a raw PIC image. After the user rebased it, Ghidra reports:

```text
ram: 9d000000 - 9d08195f
mapped size: 0x81960 = 530,784 bytes
```

The recovered listing is MIPS32, with four-byte instructions and branch delay slots. The user specified **2.2.2.1.15** as the intended baseline. Its revision is **user-established, not independently binary-verified**. The exposed Ghidra tools do not return the program filename, imported-file hash or language metadata. A string search for `2.2` returned no defined strings. No assumption of 2.2.2.1.7 is made.

The authorized filename search located:

```text
b10_ordinary_entry_design_1_12/candidate_1_15/reextracted_pic.bin
PxUpdate_V2.2.2.1.15_B10_ordinary_entry_candidate.bin
```

These names are provenance leads, not proof that the active Ghidra program matches the package.

### Ghidra coverage limitation

`decompile_function_by_address` and `disassemble_function` both report no function at/containing:

```text
9D0792E0  count getter
9D079300  group availability helper
9D04FA74  relative setter body
9D04DAD4  absolute setter body
9D04D4FC  parameter validation/clamping routine
9D01E334  instrument selection source
```

The Type routes are available as chunks of `FUN_9d029120`, even though querying their addresses directly reports no containing function. Consequently, a failed function lookup does not establish absent code or available space.

There are also inconsistent reference/decompiler results after the zero-base import and rebase. For example, the listing at `9D079228` says `jal 9D040ED8`, while decompilation says `func_0xaa040ed8()`. Calls from `9D07499C` and `9D0749F0` appear in xrefs to `AA0792E0`, but their disassembly targets `9D0792E0`. No `AA...` region is mapped. The listing is preferred for those instructions; xref completeness and decompiled control flow cannot be trusted for ownership proofs.

## 1. Count/cache contract

### Verified cache construction

The live expanded table starts at `80037E90`. For valid stock IDs:

```c
record = 0x80037E90 + 8 * (group * 17 + category);
record[0] = N + 1;                         // 32-bit count
record[1] = N > 0 ? cumulative_index : -1; // 32-bit name-record index
```

Group stride is `0x88`; total extent is `[80037E90, 8003A118)`, or `0x2288` bytes (65*17*8). The cumulative index advances by the placeholder-inclusive count, including for empty categories.

Supporting instructions in `9D040ED8`:

```asm
9D040EEC  lui    t5,0x8003
9D040EF0  addiu  s0,t5,0x7e90
...
9D040F84  jal    9D040A4C       ; persistent count-byte reader
9D040F88   move  a3,s2
9D040F8C  addiu  v0,v0,1        ; add instrument-zero placeholder
9D040F90  sw     v0,0(a2)
9D040F94  lw     v1,0(a2)
9D040F98  sltiu  v0,v0,2
9D040F9C  move   a0,t4          ; t4 = -1
9D040FA0  movz   a0,t1,v0       ; use cumulative index for count >= 2
9D040FA4  addiu  t0,t0,1
9D040FA8  sw     a0,4(a2)
9D040FAC  addu   t1,t1,v1
9D040FB0  bne    t0,t3,9D040F74 ; t3 = 17
9D040FB4   addiu a2,a2,8
...
9D040FC4   addiu t8,t8,0x88
```

Therefore a valid empty record is `{1, 0xFFFFFFFF}`, and a populated record has count >= 2 and a cumulative index. A zero/nonzero count test is wrong for this table.

The legacy count-page format initially covers groups 0..40. A first-byte `0xFF` marker selects the extended groups 0..64 format and consumes a second byte as the first count. Groups beyond the available format are explicitly filled with the same representation as empty categories:

```asm
9D040F00  li     t9,0x28
...
9D040F3C  beq    v0,t6,9D04102C ; t6 = 0xFF, first byte only
...
9D040FE4  li     a1,1
9D040FE8  li     a0,-1
9D040FF8  sw     a1,0(v0)
9D040FFC  sw     a0,4(v0)
...
9D04102C  jal    9D040A4C
9D041030   addiu a3,a3,2
9D041034  addiu  v0,v0,1
9D041038  sw     v0,0x7e90(t7)
9D041040  j      9D040F50
9D041044   li    t9,0x40
```

Unavailable legacy rows and genuinely empty rows are thus indistinguishable in this expanded table. An ordinary non-marker count byte of `0xFF` would become 256; do not globally interpret `0xFF` as unavailable without tracing its context.

No validity/generation field is established in the two-word record. **Stale entries and rebuild concurrency remain unverified.** The builder alone cannot establish when navigation is allowed, whether updates are atomic from the browser's perspective, or whether another invalidation convention exists.

### Rebuild and communication

`9D042A8C` requests all 65*17 raw counts via `9D079978`, writes one byte per result to `80010DAD + group*17 + category`, sets `80010DAC=0xFF`, then rewrites persistent page `[5FD000,5FE000)`. This is a staging buffer, not proof of a second continuously valid live table. Other flash operations also use this buffer; B11 must not read it as a permanent count table.

`9D079978` is a communicating, blocking request helper, not suitable for per-candidate navigation:

```asm
9D079988  lui    s0,0x4012
9D07998C  or     a1,a1,s0
9D079990  sll    a0,a0,8
9D079994  or     s0,a1,a0       ; 40120000 | group<<8 | category
9D07999C  sh     zero,-0x7e02(gp)
9D0799A8  sw     v0,-0x7dfc(gp) ; timeout = 0xC8
9D0799AC  jal    9D075C1C
...
9D0799C8  lhu    v0,-0x7e02(gp) ; wait for reply
...
9D0799D8  lhu    v0,-0x7e04(gp) ; returned count
...
9D0799F4  sw     s1,-0x7dfc(gp) ; retry on timeout
9D0799F8  jal    9D075C1C
```

`9D079340` is also unsuitable: its recovered code changes the selected group/category communication state (`0x4021` request), requests instrument names (`0x4020`), waits/retries and overwrites name/parameter buffers. For instrument zero it locally constructs a placeholder. The name rebuild at `9D042B80` iterates instrument indices 0 through N inclusive, corroborating the placeholder model.

### Exact getter status

The exact implementation of `9D0792E0` was **not recovered**. Its caller at `9D074954` treats its result as placeholder-inclusive:

```asm
9D0749EC  move   a0,s6         ; group
9D0749F0  jal    9D0792E0
9D0749F4   move  a1,s4         ; category
9D0749F8  move   s5,v0
9D0749FC  sltiu  v0,v0,2
9D074A00  bne    v0,zero,9D074A94 ; skip <=1
...
9D074A88  addiu  s2,s2,1
9D074A8C  bne    s5,s2,9D074A14 ; iterate indices 0..count-1
```

This is strong caller evidence, but it is not a substitute for the getter's body. Its bounds behavior, side effects, and unavailable/stale handling remain blockers. A direct expanded-table load is intrinsically read-only and avoids transport, but is safe only after lifecycle validity is established.

`9D079300` was not recovered. Its exact availability/search contract cannot be asserted from the handover alone.

## 2. Type navigation and candidate hooks

The dedicated handler is a computed-dispatch chunk of `FUN_9d029120`, at `9D02A74C`. It selects Instrument 1 when `lhu 6(a0)==0`, otherwise Instrument 2. `lhu 0x20(a0)==1` selects Group navigation; category handling follows otherwise. Direction comes from signed event value at `8(a1)`; positive goes forward and nonpositive goes to the negative route. Existing dispatch/event filtering must continue to decide whether an event represents a genuine detent.

```asm
9D02A74C  lhu    v0,6(a0)
9D02A750  bne    v0,zero,9D02D428
9D02A754   lhu   v1,0x20(a0)
9D02A75C  sh     v0,0x74(a0)  ; preceding v0=1
9D02A764  beql   v1,v0,9D02EBE8
9D02A768   lhu   a0,0x44(a0)
9D02A76C  lw     v0,8(a1)
9D02A770  blez   v0,9D02DEF8
9D02A774   lhu   a1,0x44(a0)
```

All four calls use the same relative setter thunk, `9D04FA6C`:

| Instrument/direction | Candidate hook | Original instruction | Delay slot retained | Return continuation |
|---|---|---|---|---|
| 1 forward | `9D02A78C` | `jal 9D04FA6C` | `9D02A790: li a3,1` | `9D02A794` |
| 1 reverse | `9D02DF0C` | `jal 9D04FA6C` | `9D02DF10: li a3,-1` | `9D02DF14`, jumps to `9D02A794` |
| 2 forward | `9D02D45C` | `jal 9D04FA6C` | `9D02D460: li a3,1` | `9D02D464` |
| 2 reverse | `9D02DD1C` | `jal 9D04FA6C` | `9D02DD20: li a3,-1` | `9D02DD24`, jumps to `9D02D464` |

Call contract recovered at these sites:

```text
a0 = 0
a1 = unsigned halfword from UI object +0x44 (layer/edit selection)
a2 = category parameter 0x24 or 0x65
a3 = fixed +1 or -1, set in the JAL delay slot
[entry sp+0x10] = descriptor maximum
ra = call site + 8
s0 = UI object; s1 = event pointer in enclosing handler
```

Instrument 1 loads its maximum from `9D047648`; Instrument 2 from `9D047954`. Those loads are verified; the underlying halfword values were not exposed by the available tools. The handover specifies max 16.

```asm
; Instrument 1 positive
9D02A778  lui    v0,0x9d04
9D02A77C  lhu    v0,0x7648(v0)
9D02A780  clear  a0
9D02A784  sw     v0,0x10(sp)
9D02A788  li     a2,0x24
9D02A78C  jal    9D04FA6C
9D02A790   li    a3,1

; Instrument 2 negative
9D02DD08  lui    v0,0x9d04
9D02DD0C  lhu    v0,0x7954(v0)
9D02DD10  clear  a0
9D02DD14  sw     v0,0x10(sp)
9D02DD18  li     a2,0x65
9D02DD1C  jal    9D04FA6C
9D02DD20   li    a3,-1
```

The thunk chain is already patched code and must be preserved:

```asm
9D04FA6C  j      9D0005D8
9D04FA70   nop
9D0005D8  bne    a0,zero,9D0006CC
9D0005DC   li    t0,0x1c
9D0005E0  beq    a2,t0,9D0005F0
9D0005E4   li    t0,0x5d
9D0005E8  bne    a2,t0,9D0006CC
9D0005EC   nop
9D0006CC  addiu  sp,sp,-0x20
9D0006D0  j      9D04FA74
9D0006D4   sw    ra,0x1c(sp)
```

Category parameters bypass the special `0x1C/0x5D` handling, but B11 must call the existing thunk rather than remove or repurpose it.

### Boundary behavior

The relative-setter decompilation calls `9D0816E0(current, delta, maximum)`. Its complete listing proves **clamping, not wrapping**:

```asm
9D0816E0  addu   v0,a1,a0
9D0816E4  bltz   v0,9D0816F4
9D0816E8   slt   v1,a2,v0
9D0816EC  jr     ra
9D0816F0   movn  v0,a2,v1
9D0816F4  jr     ra
9D0816F8   clear v0
```

For max 16 this yields `clamp(current+delta,0,16)`. B11 must stop searching at the endpoint, rather than wrap 16 to 0 or 0 to 16. If no populated category exists in the requested direction, retain the current selection even if another populated category exists in the opposite direction.

### Parameter sources and downstream instrument selection

`9D04D300(layer,param)` reads a halfword at:

```c
0x8000046C + 2*(param + (((layer & 0xFFFD) != 0) ? 0x6B7 : 0))
```

For the first parameter bank:

| Instrument | Group | Instrument number | Category |
|---|---|---|---|
| 1 | `800004B0` | `800004B2` | `800004B4` |
| 2 | `80000532` | `80000534` | `80000536` |

The alternate bank is offset `0xD6E`: Instrument 1 at `8000121E/1220/1222`, Instrument 2 at `800012A0/12A2/12A4`.

The absolute setter thunk is `9D04DACC -> 9D07A4F8`. Its category path ultimately reaches `9D04DAD4` through `9D07A540`:

```asm
9D04DACC  j      9D07A4F8
9D04DAD0   nop
9D07A540  addiu  sp,sp,-0x30
9D07A544  j      9D04DAD4
9D07A548   sw    ra,0x2c(sp)
```

The merged setter decompilation shows category/group changes obtaining an instrument selection via `9D01E334`, validating it through `9D04D4FC`, comparing with `9D0792E0`, and calling `9D041048(layer,instrument)` to refresh instrument metadata. It also contains related sample state updates and notifications. Because bodies and some references are incomplete, the exact final instrument-index adjustment is not certified here. In particular, apparent off-by-one expressions in the decompiler must be checked against instructions before implementation.

Returning a larger signed category delta into the original relative setter is preferable to writing category RAM or replacing its downstream logic. On a failed search, skip the setter entirely so the instrument selection also remains unchanged. Existing UI refresh continuations may still run.

Layer/edit value 2 appears to cause both parameter banks to be updated in the setter decompilation. **Linked-layer behavior is an additional integration blocker:** if their groups differ, one shared delta may not satisfy independent filtering and Factory preservation. The UI object's allowed values at these exact Type routes must be established before selecting a single-bank adapter contract.

Group routes (`9D02EBE8` and `9D02EAE8`) branch before these four category calls. Hooking only the four JALs avoids changing those routes or generic preset/soft-control callers. Instrument 1's post-call refresh uses `9D03EC34(0/1/2)`; Instrument 2 uses `(3/4/5)` before the shared UI refresh.

## 3. Shared bounded search

Recommended structure, conditional on cache validity and layer semantics:

1. Four existing category JALs target one wrapper; retain their original delay slots.
2. Wrapper preserves the original setter arguments, return address and fifth stack argument.
3. Resolve current group/category through existing parameter getters and the established layer contract.
4. Factory group 0 tail-calls the original relative setter with the original arguments.
5. For valid nonfactory group 1..64, scan strictly in the requested direction, without wrapping. Read the existing expanded cache, accepting a candidate only when its verified count represents real instruments (`N+1 >= 2`).
6. Return `candidate-original` to the original relative setter. Exhaustion or boundary without a match returns without invoking the setter.

```c
delta = 0;
candidate = current;
for (unsigned attempts = 0; attempts < 17; ++attempts) {
    candidate += direction; // direction must be exactly +1 or -1
    if ((unsigned)candidate >= 17) break;
    if (cache[group][candidate].count >= 2) {
        delta = candidate - current;
        break;
    }
}
```

With clamping boundaries, at most 16 in-range alternative categories can actually be inspected; the explicit 17-iteration cap satisfies the requested limit. An all-empty group causes zero selection change. A recalled empty category is only reconsidered on subsequent manual Type navigation. No new persistent RAM, tables, preset fields, messages or loading operations are required by this design.

The measured sketch below assumes initialized, valid expanded records. It does not distinguish stale/unavailable records beyond the representations established above and is not approved as an installable implementation.

## 4. Byte budget and scratch measurement

The available Apple clang lists no MIPS backend. Neither a MIPS cross-assembler nor Python Keystone/Capstone was available in the checked environment. Therefore the scratch measurement used an explicit Python encoder for the small fixed MIPS32 instruction subset, not a production cross-toolchain.

Scratch files are isolated at `/private/tmp/b11_investigation/`:

```text
measure.py  fixed instruction encoder and source sketch
helper.bin  112 emitted bytes
helper.txt  instruction/word listing
```

No scratch bytes were installed into firmware or Ghidra. The binary size is measured; instruction correctness has not been independently checked by another assembler/disassembler or hardware execution.

Sketch contract: `a0=group`, `a1=current category`, `a2=+1/-1`; returns signed delta in `v0`. Clobbers `t0..t4`; leaves argument registers, saved registers, gp, sp and ra unchanged. It rejects group >=65 and current >=17. Factory bypass and direction validation are caller obligations. No stack frame or calls are used in the search.

| Component | Bytes | Evidence/status |
|---|---:|---|
| Shared guarded search | **112** | Measured: 28 explicitly encoded 4-byte instructions |
| One common parameter/Factory/setter wrapper | 176–224 | Estimate: 44–56 instructions; not assembled |
| Additional validity/layer handling allowance | 8–32 | Estimate only; may be insufficient if linked layers need separate searches |
| Four call-site replacements | 16 modified bytes | Four existing 4-byte JALs; no added storage, delay slots retained |
| Separate per-site adapters | 0 | Conditional on the common wrapper contract holding |
| Extra trampolines | 0 | Conditional on verified placement in the same MIPS J/JAL region and preserving the calls |
| Four-byte alignment | 0 at aligned placement; up to 3 otherwise | No placement selected |
| **Provisional new storage** | **296–368**, plus up to 3 alignment bytes | 112 measured; remainder estimated; not a measured integration total |

This is a concrete sizing envelope, not proof that the final patch fits. A direct cache predicate may be smaller after removing redundant guards; lifecycle checks or linked-layer support may increase size. No previous fix may be weakened to achieve the envelope.

Measured helper listing:

```asm
0000  2c8b0041  sltiu t3,a0,65
0004  11600016  beq   t3,zero,done
0008  00001021   addu v0,zero,zero
000c  2cab0011  sltiu t3,a1,17
0010  11600013  beq   t3,zero,done
0014  00a05021   addu t2,a1,zero
0018  00044100  sll   t0,a0,4
001c  01044021  addu  t0,t0,a0
0020  000840c0  sll   t0,t0,3
0024  3c098003  lui   t1,0x8003
0028  25297e90  addiu t1,t1,0x7e90
002c  01094021  addu  t0,t0,t1
0030  24090011  addiu t1,zero,17
loop:
0034  01465021  addu  t2,t2,a2
0038  2d4b0011  sltiu t3,t2,17
003c  11600008  beq   t3,zero,done
0040  000a58c0   sll  t3,t2,3
0044  010b5821  addu  t3,t0,t3
0048  8d6c0000  lw    t4,0(t3)
004c  2d8c0002  sltiu t4,t4,2
0050  11800005  beq   t4,zero,found
0054  2529ffff   addiu t1,t1,-1
0058  1520fff6  bne   t1,zero,loop
005c  00000000   nop
done:
0060  03e00008  jr    ra
0064  00000000   nop
found:
0068  03e00008  jr    ra
006c  01451023   subu v0,t2,a1
```

## 5. Placement evidence

**No sufficient verified free space has been established. No placement is proposed.** This is not a finding that no space exists; the ownership audit could not be completed.

The raw memory block ends at `9D08195F`. Nothing establishes an executable, packaged extension beyond that boundary. Undefined areas inside it cannot be treated as caves. The Type handler itself demonstrates computed control flow:

```asm
9D0292F4  sll   v0,v0,2
9D0292F8  addiu v1,v1,-0x6cf8 ; table at 9D029308
9D0292FC  lwx   v0,v0(v1)
9D029300  jr    v0
9D029304   nop
```

The Type target at `9D02A74C` has a table data reference from `9D029348` and a computed-jump reference from `9D029300`, despite having no containing function in direct queries. Missing function definitions and xrefs are therefore demonstrably inadequate ownership evidence.

The existing patch code at `9D0005D8`, `9D0006CC`, `9D04FA6C` and `9D07A4F8` is occupied. It is not available for B11. No FF run was accepted as free space, and no existing patch was proposed for removal, compression or repurposing.

Any future placement must establish all of: exact original bytes; function/data ownership; direct entries and references; predecessor fallthrough and delay slots; table/computed targets; address-taken code; patch allocations; and packaging coverage. The present inconsistent Ghidra references prevent a reliable negative-reference conclusion.

## Remaining blockers and next investigation steps

1. Establish active-image filename/hash and match it to the user's 2.2.2.1.15 baseline. The name alone is insufficient.
2. Repair/recreate analysis at the correct base so listing, references and decompiler targets agree. A clean import at `9D000000` from the outset is preferable if stale rebased analysis cannot be cleared. Preserve the current program for comparison.
3. Disassemble/define the missing getter `9D0792E0` and availability helper `9D079300`; verify their complete bodies, argument bounds, return contracts, writes and calls.
4. Complete the cache lifecycle trace: initialization, refresh completion, stale data, invalidation and browser access during rebuild. Do not use the shared flash staging buffer as a shortcut.
5. Recover `9D04FA74`, `9D04DAD4`, `9D04D4FC` and `9D01E334` as complete instruction paths. Confirm descriptor max values and the exact downstream instrument correction for both instruments and both parameter banks.
6. Establish allowed UI layer/edit values at the four hooks, including linked-layer behavior and mixed Factory/nonfactory groups. This can materially change wrapper semantics and size.
7. Assemble the complete wrapper/search against those verified contracts with a MIPS toolchain, independently inspect emitted instructions, and measure the actual integrated size.
8. Audit candidate placements against all ownership/control-flow criteria above. No implementation should proceed until sufficient verified space exists without disturbing previous fixes.

Stopped at investigation. The output is this findings file and isolated scratch sizing artifacts only.
