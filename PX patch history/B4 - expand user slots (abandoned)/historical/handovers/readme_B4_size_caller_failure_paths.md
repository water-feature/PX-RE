# B4: four size-caller failure paths

The historical file references listed here are not included in this public bundle: `b4_checked_size_callers.txt`, `b4_size_caller_failure_harness.py`, `b4_size_caller_failure_instructions.txt`, `b4_size_caller_failure_results.json`, `b4_size_failure_stock_instructions.txt`.

3 October 2026. Continues [checked operations design](readme_B4_checked_operations_design.md). Scope is the four remaining size callers, their owning operation, local staging, cleanup and status consumption. Stock firmware was read only. No firmware image was changed or built; no protocol, allocator, USB or startup audit was repeated.

## Result

All four callers belong to the **same state handler, entry `0x9D023AEC`**, and use its existing **0x170-byte frame**. Safe resource release is available at **`0x9D0244DC`**, provided the failure helper first sets `a0=0x402C0000` and restores the calculation owner's pointer/range fields where needed. The stock epilogue at **`0x9D024504–0x9D024530`** then restores the correct frame and registers.

A status branch alone is insufficient:

- The calculation paths clear and accumulate owner totals before completion. Stage totals in existing private frame space, publish them only after all required queries succeed, and restore range/selection readiness fields on failure.
- The copy path queries and copies each group before querying the next. Move its size requests into a complete preflight. Use the existing private halfword results table to hold validated zero/nonzero presence; the copy pass then consumes those values without issuing another size request.

The isolated harness demonstrates both problems and the proposed corrections. A guard-only copy counterexample sends `0x401A0001` before the second size query fails; the preflight design sends **no copy command** for the same failure sequence.

## Evidence and owner frame

Connected Ghidra exposes `ram:9d000000–9d08195f`, the accepted PIC address base. It returned “No function found at or containing address” for these owner addresses, so this pass uses the immutable stock instructions and accepted handovers, not a newly recovered Ghidra decompilation. Detailed raw words are in stock instructions (`b4_size_failure_stock_instructions.txt`); original four successor windows remain in prior evidence (`b4_checked_size_callers.txt`).

Entry `0x9D023AEC` subtracts 0x170 from SP. Saves:

| Register | Frame offset | Save site |
|---|---|---|
| ra | 0x16C | `0x9D023AF0` |
| fp | 0x168 | `0x9D023AF4` |
| s7..s0 | 0x164,160,15C,158,154,150,14C,148 | `0x9D023AF8–0x9D023B14` |

`a0` becomes owner `s0` at `0x9D023B24`; `a1` becomes event `s1` at `0x9D023B18`. The two initial memset calls are `0x9D023B28` with `sp+0x18,sp+0x9A)` (0x82 bytes), and `0x9D023B38` with `sp+0xE0,sp+0x120)` (0x40 bytes). Neither is a heap allocation.

The indexed-load switch at `0x9D023B58` uses table `0x9D023B64`. The calculation entry `0x9D023BA0` is reached through a **second** switch: event signal4 -> key12 at `0x9D0245F4/5FC` -> button edge1 at `0x9D025434/43C` -> selector0x21, table entry **`0x9D025484 = 0x9D023BA0`**. These are jumps within the same frame, not another function call.

The copy entry is event signal14 -> `0x9D02460C`, edge1, selector0x21 and owner readiness+0xDE==1, with nonzero USB total and the capacity comparison at `0x9D024638–654`. It releases existing audio resources through calls `0x9D02465C/664` to `0x9D07C114`, then enters the suspend/setup path at `0x9D02466C`. Those calls precede size preflight and are not undone by the abort helper; a guarantee of no preceding audio effects is not claimed.

### Owner fields and aliases

| Offset | Proven use in this operation |
|---|---|
| +0x00 | Handler pointer; ordinary successful copy exit switches to `0x9D029118` |
| +0xBC | UI selector used by the two button paths |
| +0xDE | Calculation/readiness classification used to admit confirmation; stock later writes1/2 or clears it |
| +0xE0 | Mode selecting folder-range setup |
| +0xE4 | Number of ranges |
| +0xE8/+0xEC | First group of the first/second range |
| +0xF0/+0xF4 | Exclusive end of the first/second range |
| +0xF8 | Accumulated USB size |
| +0xFC | Disk size selected for replacement |
| +0x100 | Available disk space after existing size arithmetic |

During the first USB scan `s4` is the current range cursor, not necessarily the root. During the disk-size scan, setup `0x9D023FF8/FFC` changes **fp to the root owner and s0 to a numeric sum**. At `0x9D0242B0`, stock restores s0 from fp before final rendering. An abort at `0x9D024260` must therefore not use its current s0 as an object pointer.

The all-folders USB path `0x9D026568` uses root s0 and sets first range `[0,1)`. Its fixed stock +0xFC/+0x100 values are 150000; this design preserves those values without assigning them a new interpretation.

## Resource ownership and exact cleanup

Calculation setup `0x9D023BA0–0x9D023BE0` and copy setup `0x9D02466C–0x9D02469C` establish:

- frame+0x12C holds MMIO base `0xBF860000`;
- write1 to `base+0x638`, followed by command `0x402C0001` through `0x9D075C1C`;
- frame+0x134 holds object `0x80052E18`;
- its +0xA0 field (`0x80052EB8`) is written -1.

The reused cleanup is:

```asm
# failure helper supplies a0 = 0x402C0000, then jumps here
0x9D0244DC: lui   v0,0x0006
0x9D0244E0: addiu v0,v0,0x1A80       # stock resume value 0x61A80
0x9D0244E4: lw    t1,0x134(sp)
0x9D0244E8: sw    v0,0xA0(t1)
0x9D0244EC: jal   0x9D075C1C
0x9D0244F0: nop
0x9D0244F4: addiu v0,zero,1
0x9D0244F8: lw    v1,0x12C(sp)
0x9D0244FC: sw    v0,0x634(v1)
0x9D024500: addu  v0,zero,zero
0x9D024504: lw    ra,0x16C(sp)
# restores fp,s7..s0 through 0x9D024528
0x9D02452C: jr    ra
0x9D024530: addiu sp,sp,0x170
```

This is the stock resume sequence, including its fixed timer/object value and MMIO CLR write. It is **not** restoration of an arbitrary previous timer value, nor emulation of MMIO electrical effects or proof that QNX has acknowledged the resume command. No guessed register peripheral name is needed.

Do not jump straight to `0x9D024500/504`: that skips resource release. Do not use `0x9D0245B4`: it changes the handler pointer and returns3. The failure path retains the existing handler pointer and returns the stock event result0. That event result is not the query's scalar/status pair; the checked query's v1 is consumed inside the handler.

## Calculation staging and rollback

Install a jump/nop at **`0x9D023BA0/BA4`** to `calc_save`. It saves root/range/readiness values before stock changes them, initializes three candidate totals to zero, replays the displaced `lui v1,0xBF86; sw v1,0x12C(sp)`, and jumps to **`0x9D023BA8`**.

Use the following frame layout **only on the calculation path**:

| Offset | New local meaning |
|---|---|
| 0x18 | Original root owner pointer |
| 0x1C,20,24,28,2C | Prior +0xE4,E8,EC,F0,F4 values |
| 0x30 | Prior unsigned16 +0xDE, saved in a word |
| 0x40,44,48 | Candidate +0xF8,FC,100 totals |

No frame growth, allocation or persistent static storage is needed. These locals are inside the existing 130-byte array. Their ownership follows **path and lifetime evidence**, not missing xrefs: calculation paths use the separate presence bytes beginning at sp+0x9C and the string buffer at sp+0xE0; the halfword array at sp+0x18 is used by the copy event in a distinct invocation. After the initial memset, neither calculation path passes sp+0x18 to another routine. The known frame locals at 0x120..0x144 and saved registers at 0x148..0x16C remain intact. The harness executes both range modes and the actual switch/frame paths. Unmodeled asynchronous access to a parent frame is not newly certified.

Change **every** pre-publication owner-total access listed below into an SP-relative access to its candidate slot. Preserve instruction opcode/target register; replace only the base register with sp and the offset. This includes branch delay slots.

| Site | Candidate slot |
|---|---|
| `0x9D023BE4`, `0x9D023D4C`, `0x9D023F50`, `0x9D023F60`, `0x9D024014` | 0x40 (USB total) |
| `0x9D023BEC`, `0x9D0240A0`, `0x9D024280`, `0x9D024288`, **`0x9D025C48`**, `0x9D026588` | 0x44 (replacement total) |
| `0x9D023CA8`, `0x9D024114`, `0x9D0242AC`, `0x9D026580` | 0x48 (available space) |

The all-folders size store formerly in delay slot `0x9D02660C` is replaced by the guarded helper store to sp+0x40 below. The alternative selection path at `0x9D025C48` must not be missed. A targeted raw-word coverage assertion checks all pre-commit lw/sw references through s0/fp to these three fields in the relevant path regions.

At **`0x9D0242B4/B8`**, install jump/nop to `calc_commit`:

```asm
lw v0,0x40(sp)
sw v0,0xF8(s0)
lw v0,0x44(sp)
sw v0,0xFC(s0)
lw v0,0x48(sp)
sw v0,0x100(s0)
jal 0x9D07E274
addu a0,zero,zero             # replay original call delay slot
j 0x9D0242BC
nop
```

Stock s0 has already been restored at `0x9D0242B0` if arriving from the disk scan. This is the common completion path, including verified-empty USB input. All required queries must have succeeded before reaching it. The subsequent classification/rendering and +0xDE publication remain stock. These are three stores, not an atomic multiword transaction; no new concurrency claim is made.

`calc_abort` loads root s0 from sp+0x18, restores +0xE4..F4 from saved values and +0xDE from sp+0x30, then executes:

```asm
lui a0,0x402C
j 0x9D0244DC
nop
```

Old totals never need rewriting: they were never modified before commit. Failure therefore preserves the prior +0xF8/+0xFC/+0x100 values even during partial progress. Range fields are temporary stock working state and are restored before return. Root handler pointer, mode and selector are unchanged. A failed initial calculation does not publish a new +0xDE==1 confirmation state.

## Exact four status-check hooks

Each listed two-word hook uses `j <helper>; nop`; all helper placements remain relocatable, unassigned. Exact generated words and original/new manifest are in [instruction design (`b4_size_caller_failure_instructions.txt`).

### 1. USB range query: `0x9D023F3C`

Replace **`0x9D023F3C/3F40`**:

```asm
beq v1,zero,calc_abort
nop
sltu v1,zero,v0               # replay original; zero is valid absence
addiu a1,sp,0x9C              # replay original
j 0x9D023F44
nop
```

Successful zero still executes stock presence-byte store in the delay slot at **`0x9D023F4C`**, then skips accumulation. Positive values accumulate only into sp+0x40. Failure executes neither the presence-byte store for that slot nor any following scan/query/publication.

### 2. Internal-disk size query: `0x9D024260`

Replace **`0x9D024260/264`**:

```asm
beq v1,zero,calc_abort
nop
lw v1,0xE8(fp)               # replay original owner alias
sltu v1,s2,v1                # replay original
j 0x9D024268
nop
```

Original branch-likely instructions **`0x9D024268/26C`** and **`0x9D024278/27C`** remain, including annulled/non-annulled loads. Replacement-size selection through `0x9D025C08–C48` is retained and staged. Success, including zero, reaches ordinary checked scalar arithmetic. Failure restores the root from the snapshot, not numeric s0, and aborts before any further disk query or publication.

### 3. Copy-loop size successor: `0x9D0246F0`

Replace **`0x9D0246F0/F4`**:

```asm
beq v1,zero,copy_abort
nop
bne v0,zero,positive
nop
j 0x9D0246F8                 # valid zero: original private halfword clear
nop
positive:
j 0x9D0248BC                 # original copy path
nop
```

`copy_abort` does not restore calculation snapshots: they do not exist in this event frame. Root remains s0. It sets a0 and jumps to `0x9D0244DC` as above; prior published totals/readiness/ranges remain intact. Private table progress is discarded with the frame.

**Required scheduling change:** this successor consumes a validated private presence result after preflight, rather than a fresh size request during copying. See the next section. A cached-result failure after a prior copy can stop subsequent commands but cannot undo the prior copy; that is not a size-query rollback guarantee.

### 4. All-folders USB size successor: `0x9D026608`

Replace **`0x9D026608/60C`**, removing the original unconditional jump and its owner-size store delay slot:

```asm
beq v1,zero,calc_abort
nop
sw v0,0x40(sp)               # candidate only, including valid zero
j 0x9D0242B4                 # commit after successful query
nop
```

The fixed candidate +0xFC/+0x100 stores at `0x9D026580/588` have already been staged. Failure restores range/readiness fields and bypasses all final classification/rendering. Successful zero follows stock empty-result classification; it is not treated as backend failure.

## Copy preflight: prevent side effects before a later size failure

Stock positive-size path sends **`0x401A|group` at `0x9D0248C8/CC`**, waits for its completion, records outcome in the private halfword table and continues at `0x9D0246FC`. Only after all groups does `0x9D02626C` start the add-on phase; that phase sends **`0x402D|group` at `0x9D026364`**. Later `0x9D024534–550` can rebuild count/name metadata, reload counts and initiate follow-up work. A failed size query must reach none of those later paths.

Install jump/nop at **`0x9D0246A0/A4`**, after existing resource setup, to `copy_size_preflight`:

1. Clear 98 halfwords in **`[sp+0x18,sp+0xDC)`**: IDs0..96 plus end sentinel97. This remains inside the same existing frame and below the independent string buffer at sp+0xE0. The upper part overlaps the calculation-only presence bytes, which are not live in this separate copy event. Clear explicitly rather than relying on the shorter stock initial memset or uninitialized end entries.
2. Iterate the same owner's ranges (+0xE4, +0xE8/+0xEC, +0xF0/+0xF4). Validate each queried group<97 before addressing. Query volume1 using the checked size operation; consume v1 immediately.
3. On success store Boolean `(size != 0)` in `sp+0x18+2*group`. **No 32-bit size narrowing occurs:** only zero/nonzero is needed by this caller. Do not start a copy here.
4. On any failure, jump to `copy_abort` while published owner fields are still unchanged and no `0x401A/0x402D` has been sent.
5. On full success replay the displaced `s2=s0; s6=0`, then jump to **`0x9D0246A8`**. The original copy loop starts from its first group.

Replace **`0x9D0246E4/E8`** with jump/nop to `copy_cached_size`, bypassing the displaced call and its original `0x9D0246EC` argument delay slot. The helper checks group<97, loads the halfword through already computed s3, requires value0/1, sets v1=1 and jumps to **`0x9D0246F0`**. Invalid address/value yields v1=0 at that same successor. The scalar v0 now represents validated presence, sufficient for the original zero/nonzero branch; the subsequent copy code never uses the full queried MB value.

During copying, original completion writes replace that group's presence value with the original outcome flag. Remaining groups retain their preflight presence values; already processed flags remain available to the original later add-on/metadata logic. No pass flag, extra heap allocation or repeated size request is needed.

This does not negotiate capacity or widen unrelated range selectors. Stock calculation's disk scan still ends at65, and its mode defaults are unchanged. The private preflight/table physically supports the checked operation's0..96 domain, but actual permitted ranges must still come from the accepted admitted-capacity/backend conditions. It relies on the already required stable dataset between preflight and copying; mutation could invalidate a cached zero/nonzero classification. No new protocol is proposed to solve that existing prerequisite.

## Harness results

Run `python3 b4_size_caller_failure_harness.py`. Artifacts: [harness (`b4_size_caller_failure_harness.py`), results (`b4_size_caller_failure_results.json`), encodings and change manifest (`b4_size_caller_failure_instructions.txt`).

The harness reuses the existing interpreter and stock ROM, adds strict emulation of the particular DSP indexed loads and little-endian SWL/SWR reached in this owner, and executes the **actual owner prologue, two switch tables, scan loops, branches/delay slots, cleanup and epilogue**. New helper instructions and site overlays exist only in memory. Checked-request outcomes are scripted at the already tested request boundary; their retry mechanics were not retested.

| Test | Observed result |
|---|---|
| USB failure after one positive reply | Two queries; old totals777/111/888, ranges/readiness/handler restored; no owner total write before failure; resume command and epilogue executed |
| Disk failure after completed32-group USB scan and9 successful disk queries | Query42 fails; partial replacement and available-space candidates discarded; all prior owner bytes through+0x103 preserved |
| Second USB range failure after progress in first range | Old +0xE4..F4 restored for mode2; prior totals/readiness preserved |
| All-folders failure after fixed candidate initialization | Constants never published; prior owner fields preserved |
| Valid USB zero | Successful stock-equivalent totals0/0/1000; normal stock classification |
| Valid all-folders zero | Successful stock-equivalent totals0/150000/150000; normal stock classification |
| Positive USB/disk calculation | Successful stock-equivalent totals60/32/936;96 queries |
| Positive all-folders result | Successful stock-equivalent totals100/150000/150000 |
| Copy size preflight: positive first result, second query fails | Two queries; **no copy/add-on command**, prior owner bytes preserved, cleanup/frame restoration completes |
| Copy preflight zero/positive success | All3 size queries precede copying; zero sends no copy, populated fixture copies groups1 and3 only; no later size query |
| Complete copy zero/positive event | Real downstream control flow/cleanup restores frame and transitions to stock root with return3; positive fixture sends copy1/3 then add-on1/3. Metadata and follow-up callees are stubbed |
| Explicit failure at cached successor `0x9D0246F0` | Safe existing cleanup with no copy for this injected first-slot failure; owner bytes preserved |
| Guard-only counterexample | First copy command already sent before second size failure: demonstrates insufficiency of a local branch without preflight |
| ID96 valid zero | One validated query; no copy; table end sentinel97 explicitly zero |

Failure tests verify no metadata producer calls, add-on command or later request after the failing operation. Complete calculation/failure invocations check callee-saved registers, GP and SP against entry values. MMIO/resource assertions check the **writes and stock resume value**, not peripheral behavior. The eight-byte B4 control record remains intact; no readiness/control redesign is introduced.

Successful calculation fixtures compare the resulting owner bytes against execution of the **unmodified stock caller instructions** with the same successful backend responses. This checks the ordinary range/zero/classification behavior rather than merely comparing the new implementation to itself.

## Remaining limits

- Helper code locations and actual merge compatibility remain unassigned, as in the accepted design. Synthetic `0x9F...` addresses are test labels only.
- UI/formatting/audio methods, QNX transport and successful copy/add-on completion are fixtures. Successful metadata/follow-up callees are stubbed; filesystem writes, metadata persistence and their own failures are not executed. A failed size preflight prevents those calls, but failure of a copy already started has no new rollback guarantee.
- Stock suspend/resume has no waited acknowledgement here. Delayed replies, interrupt interleaving, same-owner asynchronous dispatch and dataset stability retain the accepted unresolved conditions; no earlier audits were reopened.
- The frame reuse is justified for the traced calculation/copy lifetimes. It adds no stack bytes and makes no claim about global stack headroom. Existing format-buffer contracts and safe admitted owner range shapes remain prerequisites.
- This resolves the four size-status failure continuations and their pre-publication handling. It does not certify aggregate-arithmetic limits, expanded UI selection bounds, QNX backend implementation or complete firmware readiness.

Stop here. The four hooks and common abort continuation are concrete and tested; the necessary local staging/preflight changes prevent a terminal size-query failure from publishing partial totals or starting copies based on earlier replies.
