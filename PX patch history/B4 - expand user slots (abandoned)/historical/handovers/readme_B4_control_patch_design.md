# B4: control reservation instruction design

The historical file references listed here are not included in this public bundle: `b4_control_boundary_model.py`.

3 October 2026. Continues `readme_B4_control_reservation_plan.md`. **Design and focused model only; firmware was neither modified nor built.**

## Status and scope

This specifies an eight-byte heap-tail reservation, an explicit DINIT wrapper, and a replacement bounded-sbrk implementation. Helper placement is justified for the supplied stock PIC image. It is **not approved for merging**: the actual intended voice_sysex binary/source is absent from the workspace, and computed helper references, allocator reset entries and direct/DMA RAM ownership are not globally closed.

Connected Ghidra segment remains `ram: 9d000000 - 9d08195f`. Stock PIC SHA-256 was checked read-only: `14e9c9b9dc562b0384fc43b3c5e0eb7fea84a5792d1a19b9b3ea8276ef7646f5`. No extraction, unrelated audit, protocol design or firmware patch occurred.

## RAM contract

| Region | Owner |
|---|---|
| `0x80053AE0,0x80057AD8)` | Shortened default heap, 0x3FF8 bytes |
| `0x80057AD8` | B4 extension pointer, uint32 |
| `0x80057ADC` | B4 readiness/lifecycle state, uint32; zero means inactive |

The physical control bytes are `[0x00057AD8,0x00057AE0)`, also visible through uncached `[0xA0057AD8,0xA0057AE0)`. The pointer remains zero on allocation failure. The control record is explicitly initialized after DINIT; existing DINIT does not cover it. Neither table is moved. Readiness is separate from pointer ownership: cache reload may invalidate readiness while retaining the allocation.

## Helper-code placement and ownership justification

| Helper | Exact extent | Size |
|---|---|---|
| DINIT wrapper | `[0x9D001240,0x9D001264)` | 9 instructions, 36 bytes |
| Guarded sbrk | `[0x9D001280,0x9D0013F8)` | 94 instructions, 376 bytes |

Read-only inspection confirms **all 576 stock bytes in `[0x9D001240,0x9D001480)` are 0xFF**. DINIT begins at 0x9D001480, so neither helper reaches it. The documented other-branch helper at 0x9D001200–121F is excluded; no new code uses that area. The wrapper-to-guard gap `[0x9D001264,0x9D001280)` and remaining bytes after the guard are left unassigned.

No literal pointer word or direct J/JAL target into the proposed region was recovered. Targeted LUI/addiu-or-ori construction checks likewise recovered no such target, and Ghidra reports no xrefs to the two chosen entries. These corroborate the erased-region placement, but are **not proof against computed jump targets, external loaders, or undocumented ownership**. Thus this is a justified stock candidate with explicit limits, rather than a declaration that erased bytes alone prove safe code space.

All code is inside the supplied payload extent and uses the existing flash virtual-address region. The design adds no new processor/load-address assumption.

## Exact existing-word changes

Words below are 32-bit instruction values; a future serializer would store them little-endian. This report and model do not serialize a firmware image.

| Address | Required stock word | Proposed word | Meaning |
|---|---|---|---|
| **0x9D0010D4** | 3C089D08 | **3C089D00** | `lui t0,0x9D00` for wrapper target |
| **0x9D0010D8** | 25081090 | **25081240** | `addiu t0,t0,0x1240` |
| **0x9D07FB40** | 24844000 | **24843FF8** | Lazy default upper uses shortened size |
| **0x9D081868** | 24634000 | **24633FF8** | Provider advertises shortened size |
| **0x9D080B98** | 27BDFFE0 | **0B4004A0** | `j 0x9D001280` replaces original sbrk entry |
| **0x9D080B9C** | AFBF001C | **00000000** | NOP in replacement jump delay; helper saves ra itself |

Existing `jalr t0` at **0x9D0010DC** and its NOP delay at **0x9D0010E0** remain. Lazy-upper addition in jump delay **0x9D07FB50** remains. Provider size store in return delay **0x9D081870** remains. Original sbrk body after the replaced entry is not reused or modified; the new helper is the entire replacement function and returns to the original caller.

No external direct jump/call/branch into the old sbrk interior `[0x9D080BA0,0x9D080C60)` was recovered. Computed interior entry remains a blocker because it could bypass the replacement entry.

## DINIT wrapper convention

The cold caller invokes the wrapper through unchanged `jalr` and supplies return address **0x9D0010E4**. Wrapper saves that address in **t7**, invokes original **0x9D081090**, clears the two control words, restores ra from t7, and returns.

This is a deliberately **local calling contract**: the inspected original DINIT routine uses v1 for its return address and t0–t4 for descriptor walking; it does not write t7 and calls no other function. Its return instructions are 0x9D081104/108, with NOP delay 10C. The wrapper therefore needs **no additional stack frame**. It preserves SP, GP, s0–s7 and fp; t0/t7/ra and original DINIT's caller-saved outputs are covered by this contract. Do not reuse this technique with an arbitrary function that may clobber t7.

Both wrapper call and return delays are NOP. It invokes DINIT exactly once and zeroes control after DINIT has reset allocator bounds/state. It does not allocate or publish readiness. Normal interruption relies on the existing interrupt register-preservation convention; the wrapper does not add interrupt masking.

## Defensive guard semantics and convention

Entry a0 is a signed 32-bit increment. Return v0 is old break on success or 0xFFFFFFFF on failure. The guard uses the **same 32-byte frame** as original sbrk, saving ra at SP+0x1C and s0 at SP+0x18. Increment is saved at SP+0x10 across lazy initialization. SP is restored in the return delay. No s1–s7/fp/GP changes or additional frame is introduced. t0–t6 and v1/a0 are caller-saved clobbers; callers must obey that convention rather than assume the original smaller clobber set.

When break is zero, it calls original lazy initializer 0x9D07F9F0, whose provider/default constants are the shortened versions above. If break remains zero, return -1/errno12. The model stubs this initializer; its complete execution is not part of the instruction-model claim.

Before any commit, require:

```text
break, lower, upper all use one consistent KSEG0 or KSEG1 alias
0x00053AE0 <= physical(lower) <= physical(break)
             <= physical(upper) <= 0x00057AD8
```

Valid preconfigured sub-heaps are allowed. Mixed aliases and bounds outside this provider region are rejected. The guard does not clamp upper, repair break or clear B4 ownership on failure.

Then compute candidate with `addu` and require that its alias does not change. Positive increments must not wrap or exceed upper. Nonpositive increments must not underflow or move below lower. Zero is a valid query/unchanged commit when state is valid. Equality with the exclusive heap end is allowed; no byte there is allocated by the sbrk commit itself.

Failure behavior:

- Invalid existing bounds/aliases: **errno22**, return -1, no guard break commit. This intentionally strengthens stock behavior, including rejecting an old full-heap upper bound even for a zero query.
- Valid-state positive growth past upper, arithmetic wrap or alias crossing: **errno12**, return -1.
- Valid-state nonpositive shrink past lower, underflow or alias crossing: **errno22**, return -1.
- Success: return old break; preserve prior errno; store candidate break once.

Lazy initialization may itself write bounds/break before a subsequent rejection; that is distinct from a guard commit. No guard failure resets the heap or pointer. If a corrupt state already places break in control storage, the guard rejects it without moving it backwards.

The guard remains **unlocked**, like original sbrk. It does not solve concurrent allocator entry, stale/corrupt free-list state, direct stores, DMA writes or reset sequencing. These are explicit limits, not reasons to infer additional protection.

## Exact helper instructions

Every line gives address, encoded word, and real instruction operands. Labels in branch/jump operands resolve as follows:

```text
validate    0x9D0012B8
alias_ok    0x9D0012E0
shrink      0x9D0013A4
commit      0x9D0013BC
range_error 0x9D0013C8
enomem      0x9D0013D0
einval      0x9D0013DC
error       0x9D0013E0
done        0x9D0013E8
```

All branch and jump delay slots are NOP except **0x9D0013F4**, which restores SP during return. There are no branch-likely instructions or assembler pseudo-instructions.

```text
9D001240 03E07821 addu t7 ra zero
9D001244 0F420424 jal 0x9d081090
9D001248 00000000 nop
9D00124C 3C088005 lui t0 0x8005
9D001250 AD007AD8 sw zero 0x7ad8 t0
9D001254 AD007ADC sw zero 0x7adc t0
9D001258 01E0F821 addu ra t7 zero
9D00125C 03E00008 jr ra
9D001260 00000000 nop
9D001280 27BDFFE0 addiu sp sp -32
9D001284 AFBF001C sw ra 28 sp
9D001288 AFB00018 sw s0 24 sp
9D00128C 3C108005 lui s0 0x8005
9D001290 8E023A64 lw v0 0x3a64 s0
9D001294 14400008 bne v0 zero validate
9D001298 00000000 nop
9D00129C AFA40010 sw a0 16 sp
9D0012A0 0F41FE7C jal 0x9d07f9f0
9D0012A4 00000000 nop
9D0012A8 8E023A64 lw v0 0x3a64 s0
9D0012AC 8FA40010 lw a0 16 sp
9D0012B0 10400047 beq v0 zero enomem
9D0012B4 00000000 nop
9D0012B8 8E083A6C lw t0 0x3a6c s0
9D0012BC 8E093A68 lw t1 0x3a68 s0
9D0012C0 3C0AE000 lui t2 0xe000
9D0012C4 004A5824 and t3 v0 t2
9D0012C8 3C0C8000 lui t4 0x8000
9D0012CC 116C0004 beq t3 t4 alias_ok
9D0012D0 00000000 nop
9D0012D4 3C0CA000 lui t4 0xa000
9D0012D8 156C0040 bne t3 t4 einval
9D0012DC 00000000 nop
9D0012E0 01026026 xor t4 t0 v0
9D0012E4 018A6024 and t4 t4 t2
9D0012E8 1580003C bne t4 zero einval
9D0012EC 00000000 nop
9D0012F0 01226026 xor t4 t1 v0
9D0012F4 018A6024 and t4 t4 t2
9D0012F8 15800038 bne t4 zero einval
9D0012FC 00000000 nop
9D001300 3C0A1FFF lui t2 0x1fff
9D001304 354AFFFF ori t2 t2 0xffff
9D001308 010A4024 and t0 t0 t2
9D00130C 012A4824 and t1 t1 t2
9D001310 004A5824 and t3 v0 t2
9D001314 3C0C0005 lui t4 0x0005
9D001318 358C3AE0 ori t4 t4 0x3ae0
9D00131C 010C682B sltu t5 t0 t4
9D001320 15A0002E bne t5 zero einval
9D001324 00000000 nop
9D001328 3C0E0005 lui t6 0x0005
9D00132C 35CE7AD8 ori t6 t6 0x7ad8
9D001330 01C9682B sltu t5 t6 t1
9D001334 15A00029 bne t5 zero einval
9D001338 00000000 nop
9D00133C 0128682B sltu t5 t1 t0
9D001340 15A00026 bne t5 zero einval
9D001344 00000000 nop
9D001348 0168682B sltu t5 t3 t0
9D00134C 15A00023 bne t5 zero einval
9D001350 00000000 nop
9D001354 012B682B sltu t5 t1 t3
9D001358 15A00020 bne t5 zero einval
9D00135C 00000000 nop
9D001360 00441821 addu v1 v0 a0
9D001364 00626026 xor t4 v1 v0
9D001368 3C0EE000 lui t6 0xe000
9D00136C 018E6024 and t4 t4 t6
9D001370 15800015 bne t4 zero range_error
9D001374 00000000 nop
9D001378 006A6024 and t4 v1 t2
9D00137C 18800009 blez a0 shrink
9D001380 00000000 nop
9D001384 0062682B sltu t5 v1 v0
9D001388 15A00011 bne t5 zero enomem
9D00138C 00000000 nop
9D001390 012C682B sltu t5 t1 t4
9D001394 15A0000E bne t5 zero enomem
9D001398 00000000 nop
9D00139C 0B4004EF j commit
9D0013A0 00000000 nop
9D0013A4 0043682B sltu t5 v0 v1
9D0013A8 15A0000C bne t5 zero einval
9D0013AC 00000000 nop
9D0013B0 0188682B sltu t5 t4 t0
9D0013B4 15A00009 bne t5 zero einval
9D0013B8 00000000 nop
9D0013BC AE033A64 sw v1 0x3a64 s0
9D0013C0 0B4004FA j done
9D0013C4 00000000 nop
9D0013C8 18800004 blez a0 einval
9D0013CC 00000000 nop
9D0013D0 2403000C addiu v1 zero 12
9D0013D4 0B4004F8 j error
9D0013D8 00000000 nop
9D0013DC 24030016 addiu v1 zero 22
9D0013E0 AE033AD8 sw v1 0x3ad8 s0
9D0013E4 2402FFFF addiu v0 zero -1
9D0013E8 8FBF001C lw ra 28 sp
9D0013EC 8FB00018 lw s0 24 sp
9D0013F0 03E00008 jr ra
9D0013F4 27BD0020 addiu sp sp 32
```

## Focused boundary model

Reproducible artifact: [b4_control_boundary_model.py (`b4_control_boundary_model.py`). Run `python3 b4_control_boundary_model.py`. It never reads or writes a firmware image. It encodes the guard in memory and executes those words with MIPS branch/jump delay semantics, using a separate arithmetic/region oracle. It prints the same helper instruction encodings above. No compiler, assembler build or patched payload was produced.

**Passed: 21 named cases and 20,000 deterministic randomized valid-state cases (seed4480).** Each guard execution checks SP/s0/ra restoration and both control-word canaries. Failure and success results are compared for v0, break and errno. Lazy-call modeling deliberately clobbers a0 to check saved-increment restoration.

| Boundary case | Result |
|---|---|
| Zero increment in valid heap | Old break returned, errno unchanged |
| Grow exactly to cap | Success, break==0x80057AD8 |
| Cross cap by one / positive increment at cap | -1, errno12, break unchanged |
| Shrink exactly to lower | Success |
| Shrink below lower | -1, errno22, break unchanged |
| INT_MAX growth / INT_MIN shrink | Correct growth/shrink failure |
| Old full-heap upper0x80057AE0 | -1, errno22; no silent clamp |
| Break inside control words / upper below break / lower below provider | -1, errno22 |
| Mixed cached/uncached bounds | -1, errno22 |
| Consistent uncached heap / valid sub-heap | Success |
| Lazy success / lazy failure | Saved increment used / -1 errno12 |
| Extension preferred growth4608 | Fits empty shortened heap |
| Remaining4496: preferred4608 then minimal4496 | Preferred request fails; separate minimal request fits |
| Remaining4495: minimal4496 | Fails by one byte |

The last cases model sbrk growth requests derived from the allocator; they do not execute malloc's free-list traversal, allocation metadata or retry control flow. The DINIT wrapper's t7 contract was checked against raw original instructions, not executed by this boundary model. No full-DINIT, allocator, interrupt, hardware timing, stack-headroom or PIC/QNX activation validation is claimed. The model's simulated canaries do not prove real RAM ownership.

## Lifecycle and merge limits

Cold entry through the wrapper clears the root after resetting allocator state. Cache reloads retain pointer ownership and must not invoke the cold wrapper or allocate again. A full allocator-lifetime reset must invalidate the root before readers resume. Any computed DINIT/reset entry bypassing the wrapper needs equivalent handling; such entries remain unclosed. None is assumed solved by this patch design.

The actual intended voice_sysex binary/source is **not available in the workspace**, so **merge compatibility is unresolved**. No historical compatibility comparison was repeated. Placement avoids its documented helper area, but that does not certify current code/RAM ownership. Actual branch inputs are needed to check both helper extents, existing-word sites and physical control-word aliases before merge.

Remaining blockers:

1. Actual intended voice_sysex inputs and code/RAM ownership verification.
2. Computed references to the erased helper region or old sbrk interior, plus direct/DMA control-word writers.
3. Allocator/DINIT reset routes that bypass coordinated root invalidation.
4. Independent instruction/disassembly review and full wrapper/allocator integration validation when implementation is authorized; this focused model is not that validation.

Stop at this design. No firmware modification, build or flash recommendation follows.
