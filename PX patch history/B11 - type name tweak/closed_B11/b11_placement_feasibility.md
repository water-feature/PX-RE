# B11: in-place placement assessment

Investigation date: 9 October 2026. No firmware, package or Ghidra database changes.

## Verdict

**B11's single-bank search can fit in place: 276 emitted bytes replace 276 bytes of identified Type code, with zero additional storage.** The earlier estimate of 296–368 *new* bytes is not a requirement; it assumed an added wrapper and retained duplicated navigation code.

**The complete requested B11 behavior is still not certified feasible.** The 276-byte candidate assumes a valid stock group and initialized cache and searches one parameter bank. Linked-layer semantics, cache validity and a few ownership-boundary instructions remain unresolved. There is no headroom in this particular layout for additional checks or independent linked-layer searches. This report establishes a concrete space-fit candidate, not an installable patch or a proof that all requirements fit.

Five existing patch routines offer **20 bytes of counted compactions**, in separate four-byte fragments, subject to the ownership checks below. No existing patch needs to be compacted for the demonstrated 276-byte candidate. These fragments are not a verified contiguous 20-byte allocation.

## Scope and baseline

Read only `b11_findings.md` as project input. All new firmware evidence came from the active Ghidra program. No package, PIC file, patch script or additional handover was read. Scratch artifacts were written only under `b11_placement_scratch/`.

Ghidra still reports one raw block, `9D000000–9D08195F`, size `0x81960`. Baseline revision **2.2.2.1.15** remains user-established rather than independently hash-verified. No older baseline is assumed.

No global reference repair was attempted. Instruction listings, actual defined data values and normal/stale reference aliases were compared where necessary. Rebased/decompiler references are still inconsistent, so empty reference lists are not used as proof of free space.

## Positive ownership evidence for the Type blocks

All ranges below are half-open. Every four-byte word in them has a recovered instruction in the enclosing Type handler listing; none is an FF-gap claim.

| Existing range | Bytes | Existing role |
|---|---:|---|
| `[9D02A74C,9D02A7BC)` | 112 | Instrument dispatch, Instrument 1 Group/category routing, positive setter, refresh, shared UI update |
| `[9D02D428,9D02D484)` | 92 | Instrument 2 Group/category routing, positive setter, refresh, branch to shared UI |
| `[9D02DD08,9D02DD2C)` | 36 | Instrument 2 negative setter and refresh branch |
| `[9D02DEF8,9D02DF1C)` | 36 | Instrument 1 negative setter and refresh branch |
| **Total** | **276** | Existing occupied code to rewrite, not spare storage |

The dedicated Type encoder is computed-dispatch case 16:

```asm
9D0292F4  sll   v0,v0,2
9D0292F8  addiu v1,v1,-0x6cf8 ; table base 9D029308
9D0292FC  lwx   v0,v0(v1)
9D029300  jr    v0
9D029304   nop
9D029348  .word 9D02A74C     ; entry retained at its existing address
```

Every word in the four ranges was queried for incoming references. Reported entries are:

| Target | Reported incoming source |
|---|---|
| `9D02A74C` | table word `9D029348`; computed dispatch `9D029300` |
| `9D02D428` | branch `9D02A750` |
| `9D02DD08` | branch `9D02D440` |
| `9D02DEF8` | branch `9D02A770` |
| `9D02A794` | branch `9D02DF14` |
| `9D02D464` | branch `9D02DD24` |
| `9D02A7B0` | branch `9D02D47C` |

All reported interior code references originate in these same rewritten blocks. The external dispatch entry is retained. The same word-address queries at the stale `AA...` aliases returned no references. That alias result is supplementary, not a negative ownership proof.

All 10,356 currently defined Ghidra data items were inspected for decoded full-address pointers into the ranges. The only such defined pointer was `9D029348 -> 9D02A74C`. This covers defined data only, not unidentified raw words, partial addresses, computed offsets or deliberately constructed addresses.

Predecessors of two blocks explicitly branch away:

```asm
9D02D420  j      9D02A37C
9D02D424   addiu a0,s0,8     ; no fallthrough into 9D02D428
...
9D02DEF0  j      9D02A370
9D02DEF4   nop              ; no fallthrough into 9D02DEF8
```

The available listing omits the immediate predecessor words at `9D02A748` and `9D02DD00/04`. In particular, `9D02DCF8` calls the returning UI updater, so its following omitted instructions must be decoded before ruling out another route into `9D02DD08`. Missing listings do not make these bytes free or irrelevant. This remains a local ownership-audit blocker.

The candidate preserves the shared UI instruction sequence at `9D02A7AC–9D02A7B8` and its existing return/fallthrough address `9D02A7BC`. No claim is made about the omitted words beyond that boundary; they are neither overwritten nor allocated.

## Concrete 276-byte layout

Scratch source/encoder: `b11_placement_scratch/measure_in_place.py`.

Emitted listing: `b11_placement_scratch/in_place_listing.txt`.

Four isolated scratch fragments were emitted; the script never opens or modifies a firmware image. It asserts each fragment's start/end, the original shared UI address, branch displacement ranges and JAL regions.

| New role | Placement | Bytes |
|---|---|---:|
| Instrument 1 entry, shared parameter addressing/direction setup, original shared UI update | `[9D02A74C,9D02A7BC)` | 112 |
| Instrument 2 entry, cache row calculation, bounded scan | `[9D02D428,9D02D484)` | 92 |
| Direction normalization, Factory branch, setter preparation | `[9D02DD08,9D02DD2C)` | 36 |
| Original setter invocation, shared three-channel refresh loop, UI continuation branch | `[9D02DEF8,9D02DF1C)` | 36 |
| **Measured emitted total** | Same four existing ranges | **276** |
| **Added helper/adapters/trampolines/alignment** | None outside these ranges | **0** |
| **Remaining space within the layout** | None | **0** |

The entry retains `s0` as UI object and `s1` as event pointer. It uses `s2/s3` as refresh-loop state; these are already saved/restored by the enclosing handler's frame. This avoids an additional wrapper frame and return machinery:

```asm
9D02912C  sw s2,0x24(sp)
9D029128  sw s3,0x28(sp)
...
9D0291D4  lw s3,0x28(sp)
9D0291D8  lw s2,0x24(sp)
```

`a2` holds `0x24` or `0x65` throughout the call-free search. `a1` holds the existing UI layer/edit value. The selected parameter bank is addressed exactly as the recovered getter: base `8000046C`, alternate-bank offset `0xD6E` when `(layer & 0xFFFD) != 0`, category offset `2*a2`, group at category pointer minus four bytes.

Both category maxima are now verified from defined program data:

```text
9D047648: DAT_9d047648 = 0010h
9D047954: DAT_9d047954 = 0010h
```

Thus a shared literal 16 replaces four separate descriptor-load sequences in this baseline, without changing their value.

Direction is normalized to the existing contract: positive event => +1; zero or negative => -1. The candidate does not change upstream genuine-event filtering.

The shared count scan reads the existing expanded table's first word, accepting count >=2. It advances strictly in one direction, checks category range before accessing the record, and stops at the stock clamped boundary. It performs at most 16 alternative-category reads for a valid starting category; the 17-candidate cap is therefore met without a separate counter. All-empty/no-forward-match returns to UI refresh without invoking the setter.

```asm
; Scratch candidate, not installed
9D02D444  addu  t4,t4,t0       ; t4 was group<<4; add group
9D02D448  sll   t4,t4,3
9D02D44C  lui   t5,0x8003
9D02D450  addiu t5,t5,0x7e90
9D02D454  addu  t5,t5,t4       ; row base = 80037E90 + group*136
9D02D458  addu  t3,t3,a3       ; candidate += direction
9D02D45C  sltiu t4,t3,17
9D02D460  beq   t4,zero,9D02DF00
9D02D464   sll  t4,t3,3
9D02D468  addu  t4,t5,t4
9D02D46C  lw    t4,0(t4)
9D02D470  sltiu t4,t4,2        ; placeholder-inclusive empty count is 1
9D02D474  bne   t4,zero,9D02D458
9D02D478   nop
9D02D47C  b     9D02DD24
9D02D480   subu a3,t3,t2      ; signed target-current delta
```

The Factory branch uses the unchanged +/-1 delta. Populated nonfactory results use a larger signed delta. Both invoke the existing thunk `9D04FA6C`, including its existing patch interceptor and downstream instrument selection. No category or instrument parameter is directly written by the search.

```asm
9D02DD14  beq   t0,zero,9D02DD24 ; Factory -> stock relative setter
9D02DD18   move t3,t2
...
9D02DD24  b     9D02DEF8
9D02DD28   sw   v0,0x10(sp)      ; fifth argument = max 16
9D02DEF8  jal   9D04FA6C
9D02DEFC   clear a0
```

The Group-mode branches remain to `9D02EBE8` and `9D02EAE8`, with their original branch-likely semantics and layer load in the delay slot. Generic setters, preset recall, Group search and other patches are not replaced.

Refresh calls remain ordered `0,1,2` for Instrument 1 and `3,4,5` for Instrument 2. `9D03EC34` was recovered in full and only writes `1` to `80053930 + 4*channel`. It clobbers `a0/v0` and preserves the new loop state:

```asm
9D03EC34  sll   a0,a0,2
9D03EC38  lui   v0,0x8005
9D03EC3C  addiu v0,v0,0x3930
9D03EC40  addu  a0,a0,v0
9D03EC44  li    v0,1
9D03EC48  jr    ra
9D03EC4C   sw   v0,0(a0)
```

The new loop uses six instructions (24 bytes), replacing two separate three-call sequences and their Instrument 2 join branch. Sharing setup, using the enclosing frame and packing work into bridge delay slots make the four-fragment layout possible. The complete emitted-word listing is the size evidence; no FF allocation is involved.

### Measurement and verification limits

The available clang lacks a MIPS backend. As in the first investigation, emission used a small explicit MIPS32 subset encoder, not a production assembler.

A separate decoding/execution path in the scratch script interprets the emitted words, including ordinary and annulled branch-likely delay slots. **1,088 cases passed** over both instruments, layers 0 and 1, all 17 starting categories, both directions, six population patterns, Factory bypass and Group routing. It checks setter arguments/max, refresh order, flag stores and <=16 category reads.

The actual setter, refresh and UI calls are mocked. These checks do not establish hardware timing, live cache validity, setter internals or linked-layer behavior, and they do not replace independent assembler verification.

## Concrete existing-patch compactions

These are instruction-equivalent proposals, not modifications. Counts are from four-byte MIPS instructions; these alternative routines were **not emitted or installed**. Keep each public entry fixed and retarget only proven internal branches when repacking a routine.

| Occupied routine | Concrete change | Original -> compacted | Counted recovery |
|---|---|---:|---:|
| `[9D0002DC,9D000364)` | Put `li t2,0x6B7` in the group-bank branch's empty delay slot | 136 -> 132 | 4 |
| `[9D000744,9D000774)` | Combine adjacent `sp += 0x20; sp -= 0x38` into `sp -= 0x18` after all temporary-frame loads | 48 -> 44 | 4 |
| `[9D001394,9D0013A0)` | Put the `a0 += 15` adjustment into the existing tail jump's delay slot | 12 -> 8 | 4 |
| `[9D0013AC,9D0013DC)` | Put saved-ra store in jump-to-stock-prologue delay slot; compact/repoint the local early-return branches | 48 -> 44 | 4 |
| `[9D001424,9D001448)` | Put saved-ra store in jump-to-stock-body delay slot | 36 -> 32 | 4 |
| **Total, scattered** | No behavioral feature removal | **280 -> 260** | **20** |

Examples:

```asm
; 9D000318..9D00032B: five existing instructions
li    t2,0x6b7
andi  t3,a0,1
beq   t3,zero,bank_done
 nop
addu  t1,t1,t2

; Four equivalent instructions: same t1/t2/t3 at bank_done
andi  t3,a0,1
beq   t3,zero,bank_done
 li   t2,0x6b7
addu  t1,t1,t2

; Existing 9D000764/768, after temporary-frame restores
addiu sp,sp,0x20
addiu sp,sp,-0x38
; Equivalent net stack adjustment
addiu sp,sp,-0x18

; Existing 9D001394..9D00139F
addiu a0,a0,15
j     9D075C1C
 nop
; Two instructions, same tail-call arguments and ra
j     9D075C1C
 addiu a0,a0,15

; Existing prologue tail, used by 9D0013AC and 9D001424
sw    ra,frame_offset(sp)
j     stock_body
 nop
; Same stack write before stock_body executes
j     stock_body
 sw   ra,frame_offset(sp)
```

Positive ownership evidence for these routines:

| Routine entry | Known outside caller/entry |
|---|---|
| `9D0002DC` | `9D035748`, `9D035F2C` |
| `9D000744` | `9D029118` |
| `9D001394` | `9D0258C0` |
| `9D0013AC` | thunk at `9D03ED0C` |
| `9D001424` | thunk at `9D07E408` |

Every word of these routines was queried for incoming references. The reported outside code entries are the public entries above. `9D00035C`, `9D0013D4` and `9D001438` have local branch entries that must be retargeted when shortening their owners. Their returns/tail jumps prevent fallthrough into any newly shortened tail. Defined full-address data-pointer inspection found no pointer into their interiors. No IRQ masking, EHB sequences, generation counters, messages, loads with potential side effects or saved-register contracts need be removed.

This evidence identifies the code to compact; it does not certify arbitrary reuse of all 20 resulting bytes. They are five separate four-byte tails. They cannot hold a useful independent search helper without further repacking/relocation, whose branch/address dependencies would require another audit. At this stage **20 bytes are candidate recovery, not 20 bytes of verified contiguous headroom**.

### Rejected shortcut: repack the generic patch wrapper blindly

`[9D0009A8,9D000AE0)` has at least two obvious delay-slot fills (nominal eight-byte saving), but incoming references include:

```text
9D05A7CC -> 9D000A04 [DATA]
9D05B028 -> 9D000A04 [DATA]
```

The actual defined values at both sources are `00000A04`, not `9D000A04`, with preceding values `00060404`. These may be false rebased scalar references or offset-based addressing; their consumers were not established. Do not dismiss them, alter the data or count eight reclaimable bytes without resolving their meaning. This routine is excluded from the 20-byte tally.

## Remaining requirements affecting the verdict

1. **Linked layers:** the candidate reproduces the getter's bank choice but does one search. If edit value 2 causes the setter to update both banks, different groups/categories can require different deltas. A primary Factory group with an alternate nonfactory group is a concrete case where a single bypass decision is insufficient for independent semantics. Establish whether Type can enter this mode and what stock linked editing promises. The 276-byte sketch is not claimed correct for it.
2. **Valid group/cache lifecycle:** the sketch assumes group 0..64 and an initialized expanded count table. It has no group-bound or generation check. The previous investigation's count getter and invalidation/rebuild blockers remain. This is a sizing assumption, not permission to ship unchecked accesses.
3. **Local predecessor ownership:** decode `9D02A748`, `9D02DD00/04` and their predecessor routes. Confirm no unrelated fallthrough enters a repurposed internal block. The preserved UI continuation at `9D02A7BC` avoids rewriting its omitted instructions.
4. **Reference quality:** the dispatch table value and category max values are now confirmed, and public entries remain fixed. Raw/untyped offset or computed entries still need appropriate verification before installation. A global reanalysis is unnecessary solely to demonstrate the byte layout.
5. **Independent toolchain and actual setter behavior:** verify encoding with a MIPS assembler and trace the actual setter/instrument adjustment before treating the scratch candidate as behavior-preserving firmware.

**Final feasibility classification:** in-place storage is demonstrated for the single-bank algorithm; no new PIC space is intrinsically required for that case. Full requested behavior and exclusive ownership are not yet proven, so implementation remains a no-go pending the specific checks above. Do not compact previous fixes merely to satisfy the obsolete added-wrapper estimate.
