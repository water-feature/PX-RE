# B4 focused follow-up: reentry predicates and pointer writers

3 October 2026. Continues section 8, step 1 of readme_B4.md and readme_B4_results.md. **Step 1 remains open.** No stack bound, RAM placement, firmware build or flashing decision follows from this report.

The connected Ghidra segment remains 0x9D000000–0x9D08195F. Its 0x9D0295B0 reference still calls stock target 0x9D05EE4C. This pass used targeted Ghidra xrefs/decompilation and raw words from the existing stock PIC payload. No extraction or earlier validation matrix was repeated. Undefined functions and incomplete Ghidra xrefs were handled with specifically targeted raw instruction checks; the database and firmware were not changed.

Names: M=0x80052E18, U=M+0x1B4=0x80052FCC, P=0x800536BC, D=0x8003A27C. Default USB handler remains **0x9D06775C**.

## 1. Pot rescan: exact outer predicate and inner event

The call at **0x9D02F240 → 0x9D06E890** is reached through main-root **signal 4**, button index **6**, table entry **0x9D029228 → 0x9D02AD70**. Let B=0x80010774, the ten-byte button-record array.

The local activation predicate is:

```text
event.signal == 4
event.byte[4] == 6
event.byte[5] == 1
(B.halfword[0x1D6] == 0 || B.halfword[0x1E0] == 0)
B.halfword[0xA0] != 0
M.halfword[0x1C] != 0
```

Evidence:
* **0x9D02AD70–78:** event+5 must equal 1.
* **0x9D02AD88–98:** if B+0x1D6 is nonzero, B+0x1E0 must be zero. The taken branch-likely delay **0x9D02AD90** loads B+0xA0 when the first field is zero.
* **0x9D02ADA4:** B+0xA0 nonzero branches to 0x9D02F22C; taken delay **0x9D02ADA8** sets v0=1.
* **0x9D02F22C:** calls 0x9D04CD14; delay **0x9D02F230** stores that incoming 1 into M+0xE2. It does not store the call's return value.
* **0x9D02F234/238:** M+0x1C gate; then **0x9D02F240**, NOP delay.

These are logical fields and edge codes. No physical button names or electrical polarity were inferred.

0x9D06E890 emits 34 **sequential** synchronous signal-6 events through 0x9D07DB98. For index i, old value is unsigned halfword at 0x8000704C+0x20*i; synthetic new value is 0xFF if old<0x80, otherwise 0. It writes 600 at 0x80007046+0x20*i **after** each dispatch returns.

Wrapper **0x9D07DB98 always reaches dispatch**. Its old==new test at 0x9D07DBAC only skips the activity update at 0x9D07DBD4, not the later tail to 0x9D07E838 at 0x9D07DC0C.

Main-root signal 6 starts at **0x9D02935C**:
1. Delay **0x9D029360** supplies the event index to 0x9D06F6A4.
2. That leaf checks halfword **0x80007062+0x20*i == 0**. If false, the event returns handled.
3. If true, **0x9D029364**, taken delay **0x9D029368**, enters 0x9D0299D0 with index in s2.
4. 0x9D06E984 maps the index to a parameter. Calls at **0x9D0299E0 / 0x9D0299F0** use 0x9D06E9A0 to scale event+8 and event+6.
5. **0x9D0299FC** returns handled if the scaled values match. Otherwise configuration 0x13 and index-specific branches select the parameter/menu work.

The root's signal-6 local graph cannot reach 0x9D02F22C/240; that rescan requires the signal-4 table case. Its recovered direct M state writes all select **0x9D029118**, including these previously unlisted self-transition stores:

```text
0x9D02BDCC 0x9D02BE04 0x9D02BE84 0x9D02BEBC 0x9D02BF00 0x9D02C01C
0x9D02C090 0x9D02C0D0 0x9D02C110 0x9D02C150 0x9D02C190 0x9D02C210
0x9D02C254 0x9D02C294 0x9D02C2E0 0x9D02C318 0x9D02C35C 0x9D02C3F4
0x9D02C438 0x9D02C49C 0x9D02C4E4 0x9D02C548 0x9D02C590 0x9D02C61C
0x9D02C660 0x9D02C6A4 0x9D02C6E8 0x9D02C72C 0x9D02C770 0x9D02C7B4
0x9D02C7F8 0x9D02C83C 0x9D02C880 0x9D02C8B8
```

There are 34 stores in this recovered local set.

**Proven locally:** synchronous M→M reentry, differing event type, and root self-transition destinations. **Still conditional:** transitive parameter setters, other events/interrupts and alternative current states cannot be declared incapable of further dispatch from this local graph.

## 2. Event 18: the dispatch gate is precise, but not always consumed

Emitter **0x9D0216BC(force,desired)** first compares desired against unsigned M+0xA8 at **0x9D0216D8/DC**. Equal returns immediately. Only desired==0 reaches the tail at **0x9D021720 → 0x9D07DD18 → 0x9D07E838(M,signal 18)**.

Local dispatch predicate:

```text
old M.halfword[0xA8] != desired && desired == 0
```

Before that tail:
* If force!=0 or configuration **0x11 !=0**, stores **0x9D0216F4 / 6FC** clear M+0xA8/+0xAA and 0x9D0216F8 clears gp-0x7DCA. A second identical call is then suppressed, assuming no intervening writer.
* If force==0 and configuration 0x11==0, it refreshes UI via 0x9D01E51C **without clearing M+0xA8**, and still emits signal 18. The equality gate therefore is **not a universal consumed latch**.
* **0x9D021708** rejects nonzero desired; delay restores ra. Wrapper jump delay **0x9D07DD24** supplies the signal-18 event pointer.

Previously listed root-region calls resolve as:
* (force=0, desired=1), **no direct signal-18 emission**: **0x9D02F348, 0x9D0301DC**.
* (force=0, desired=0), conditional on old M+0xA8!=0: **0x9D02E46C, 0x9D02E668, 0x9D02CE90, 0x9D02F744, 0x9D02FAEC, 0x9D02B158, 0x9D030C8C, 0x9D030D24, 0x9D030E30, 0x9D030610, 0x9D030740, 0x9D031980, 0x9D0319A8**.

Call arguments were checked including delay slots; e.g. 0x9D02B154 sets a0=0 and **0x9D02B15C** sets a1=0, whereas **0x9D02F34C** sets a1=1.

### Inner main-root signal 18

Table entry **0x9D0291A4 → 0x9D029928**:
* If M+0x42!=0, **0x9D02992C**, taken delay **0x9D029930**, clears that field before entering **0x9D0299B8**.
* **0x9D0299C0 → 0x9D036A28(U,1,0)** sends menu signal 17.
* Otherwise, or after the menu dispatch returns, **0x9D029934 → 0x9D01E670(M)** refreshes UI and returns 0.
* There are no direct M state-pointer writes in this signal-18 local path.

For initialized U, each of the 42 selected states treats signal 17 through its superstate prefix; two prefixes call leaf **0x9D01E410** first. Menu root calls **0x9D03CE4C(U,selection,value)** at **0x9D03D85C**. For selection 1 it updates U's menu fields, calls leaf **0x9D03CE28** (0x9D03D000, a0=U in delay), then selects 0x9D03646C. Query/exit/entry/initial events on these states take their non-15 prefixes; root's initial event selects 0x9D03646C.

UI refresh 0x9D01E670's named callees **0x9D01B46C, 0x9D01B0A4, 0x9D01AEBC, 0x9D01B338, 0x9D01B9C8, 0x9D01E51C** use parameter reads/LED updates; their remaining named helpers **0x9D04D300, 0x9D04D780, 0x9D07C900, 0x9D01E118, 0x9D01E498** were inspected. They do not call 0x9D0216BC or the main dispatcher on this path.

**Conditional closure:** with M actually at main root and U in the established initialized menu set, this inner signal-18 path does not synchronously emit itself again. That conclusion comes from its handler/callees, not from assuming the emitter always clears its latch. Other current-state handlers and interrupt interleavings remain separate.

## 3. Button-driven startup reentry: corrected conditions

Let old/new be the scanner halfwords, changed=old XOR new, and id the mapped button index. Scanner **0x9D07E524** iterates nine banks of eight bit positions, accepting mapped id<53.

| Site | Logical-edge predicate | Emitted signal 4 payload |
|---|---|---|
| 0x9D07E618 | changed bit in old; mapped id<53; halfword gp-0x7F50!=0 | id, edge code 1 |
| 0x9D07E698 | changed bit in new; mapped id<53; button[id]+4==0 | id, edge code 2 |

**Only the first has the enable gate.** The first report's generalized startup-enable description must not be used for the second.

Raw ordering:
* **0x9D07E5A8**, delay of 0x9D07E5A4, stores the entire new bank snapshot at 0x80010988+2*bank **before either callback**.
* First edge updates record+0=1, +6=30 and +4=0 before its callback (0x9D07E5FC/600/608).
* Second edge sets record+0=0 at **0x9D07E688** before callback, but commits +6=0 and +4=1 **after it** at 0x9D07E6B4/6C0.
* Wrapper 0x9D07DAF8 writes the shared signal-4 event buffer at gp-0x7BF0/-0x7BEF, then dispatches M at **0x9D07DB3C**.

The pending bank snapshot is consumed before reentry, but the second edge's per-button guard is not. With stable hardware samples and no snapshot writer, a nested scan cannot rediscover the same bank edge from the already updated snapshot. Fresh hardware changes or other snapshot writers invalidate that assumption; the local loop counts do not provide a global nesting bound.

Targeted DINIT reads for these newly relevant fields:
* **0x9D019F90:** zero-initializes halfword **0x800000A0 = gp-0x7F50**.
* **0x9D019F9C:** zeros **[0x80010708,0x8001099A)**, including the button records and bank snapshots.
* Runtime enable store **0x9D05326C** sets gp-0x7F50=1 **after** main initialization and the pre-enable scanner call at 0x9D053214.

Main startup calls **0x9D0800FC(M,0)** at **0x9D0531B4**. Main initializer **0x9D023328** calls its own scanner at **0x9D0233A4** before its state store **0x9D0234AC → 0x9D029118**. It saves M at 0x9D02333C and does not gate its initialization body on incoming event type.

Thus, **if a second-edge event satisfies its guard while M still contains 0x9D023328**, ordinary dispatch calls that initializer again synchronously. This includes re-invoking **0x9D0800FC(U,0)** at 0x9D02334C although U may already have been initialized by the outer invocation. The initialized menu handlers read event+0, so this cannot be treated as a harmless ordinary event without further analysis of that startup condition. No physical input fixture or observed occurrence was claimed.

### Missing xrefs recovered by exact call encodings

Ghidra omitted callers for several undefined entries. Exact J/JAL searches for these four named functions, followed by instruction-context checks, recovered:

| Target | Concrete call PCs |
|---|---|
| 0x9D07E524 | 0x9D0233A4, **0x9D053214, 0x9D0538EC** |
| 0x9D07E704 | **0x9D0538F4** |
| 0x9D06E910 | **0x9D053874** |
| 0x9D01D250 | **0x9D053164** |

This resolves the prior claim that the pot-pending dispatcher had no known caller. At **0x9D053540–54C**, the main loop tests byte **0x8001206F==0** (s0=0x8001206C, established at 0x9D052C2C/30); the taken delay supplies 12, **0x9D053870** stores it before calling 0x9D06E910. The periodic scanner similarly tests 0x8001206E==0 at 0x9D053570–578 and stores 40 before calls 0x9D0538EC/F4. Inside 0x9D06E910, a pending flag at 0x80007056+0x20*i activates the signal-6 callback, and that flag is cleared **after** dispatch. Main-loop reachability is proven; this call itself is sequential main-loop work, not evidence of a state-handler recursion into 0x9D06E910.

Timer button events from 0x9D07E704 similarly decrement record+6 to zero before dispatching edge code 3 at **0x9D07E760**, delay **0x9D07E764**. It requires old countdown=1 and record+4==0. It has no scanner-enable test.

## 4. State-pointer writers: seven candidates resolved

All seven former a0-alias candidates are now attributable to M:

| Store | Target | Local provenance / trigger |
|---|---|---|
| 0x9D02B8D0 | 0x9D0203D0 | Root signal 4 index 51, edge code 1 |
| 0x9D02A8FC | 0x9D01EACC | Root signal 4 indices 34/35, edge code 1 |
| 0x9D02E9B4 | 0x9D021B00 | Root index-18 path through 0x9D02B0CC → 0x9D02E9A0; a0 retains M |
| 0x9D02B108 | 0x9D027648 | Root signal 4 index 17, edge code 1 |
| 0x9D02B4F0 | 0x9D0235EC | Root signal 4 index 4, edge code 1 |
| 0x9D02DFF0 | 0x9D01E800 | Root index-2 path via 0x9D02A910 → 0x9D02DFD0; a0 retains M |
| 0x9D01B81C | 0x9D023AEC | 0x9D01B61C signal 4, event+4==12, event+5==1; a0 retains its object argument |

The root's bounded tables preserve a0 on these routes. Branches and their delay slots do not replace it before the store; no intervening call is relied upon to preserve a caller-saved a0. The root entry establishes s0=M at **0x9D029150**, a branch delay. In 0x9D01B61C the object is saved in s1 at **0x9D01B644**; the specific 0x9D01B81C path retains entry a0.

Newly resolved handlers return/super-query to main root at:
* **0x9D0203D0:** 0x9D020450 / 0x9D0214E4.
* **0x9D021B00:** 0x9D021C00 / 0x9D021D18 / 0x9D021DF8 / 0x9D0222A0 / 0x9D022830 / 0x9D022DE8; self 0x9D02289C.
* **0x9D027648:** 0x9D0276C0 / 0x9D027BF8 / 0x9D028288.
* **0x9D0235EC:** 0x9D0236D4 / 0x9D023A68.

The resulting **observed M set** is:

```text
0x9D023328 0x9D029118 0x9D081948
0x9D026D54 0x9D01EACC 0x9D01C64C 0x9D01BAA8 0x9D023AEC
0x9D027294 0x9D026610 0x9D01E800 0x9D01B61C 0x9D01ABB0
0x9D0203D0 0x9D021B00 0x9D027648 0x9D0235EC
```

This is 17 observed states, not certification against every possible firmware writer.

### Menu body and object-argument follow-through

The remaining local body CFGs of the 42 selected menu states yielded only their known U→0x9D03D828 superstate stores. One previously unresolved jump in 0x9D034F88 was closed:
* **0x9D03550C:** index<14 after subtracting 28 from 0x9D031A58's result.
* **0x9D035520:** DSP indexed load; **0x9D035528:** jump; table **0x9D035530**, 14 entries.
* Intervening 0x9D035524 sets a0=4; jump delay 0x9D03552C sets a1=1. Neither modifies the jump register.
* Destinations: 0x9D0355E0, 0x9D0355CC, 0x9D0355B8, 0x9D0355A4, 0x9D035590 (twice), 0x9D03557C, 0x9D035568, 0x9D0355F4 (six times).

Object-argument follow-through also identified additional **M→U** dispatch helpers:
* **0x9D01A850:** if a2!=0, tail **0x9D01A898 → 0x9D036A28(U,26,0)**. Delays/paths at 0x9D01A87C and 0x9D01A890 supply M+0x1B4. This is menu selection, not M→M.
* **0x9D01DFB0:** if selector result from 0x9D01D4E8 != -1, tail **0x9D01DFE0 → 0x9D036A28(U,selector,0)**. Branch delay 0x9D01DFCC supplies U.
* **0x9D036A14:** tail **0x9D036A20 → 0x9D07E838(supplied object,signal17)**; jump delay stores selection from object+6. Ownership follows its caller; observed callers here supply U.

Parameter-to-menu helper **0x9D01D4E8** has a finite selector table at **0x9D01D530**, jump **0x9D01D528**, unsigned parameter bound **410** at 0x9D01D510. The 410 entries have 31 distinct branch destinations. Its special current-menu-26 route can call 0x9D01A850 and thereby dispatch U; it does not itself store a state pointer. This table returns selector values, not state-function addresses.

In the followed object-argument callees, the non-literal first-word writes recovered were the existing dispatcher's **0x9D07E898 / 0x9D07E9F0** restore/commit operations. That narrows the writer gap, but callees with unknown aliases, other argument positions, global object references and indirect target bodies still prevent whole-firmware writer closure.

## 5. Dispatcher restoration is a concrete writer

Ordinary dispatcher **0x9D07E838**:
* **0x9D07E868** caches the entry state in s4.
* Return 3 rereads object+0 in taken delay **0x9D07E888** and invokes the newly selected superstate.
* Return 2 reads transition target in taken delay **0x9D07E894**.
* Other returns reach **0x9D07E898**, which writes cached s4 back to object+0.
* **0x9D07E9F0** commits the transition state; later initial-transition processing eventually restores that dispatch's cached committed state at 0x9D07E898.

Therefore a handler's store to object+0 is not necessarily the final state after dispatch. Same-object nested dispatch can finish with one state while the outer dispatcher still has another cached state. It can be overwritten when the outer handler returns handled. For the recovered direct root signal-6 self-transitions and root signal-18 handled path, the root destination is consistent; no lost different M transition was demonstrated there. Different-state callbacks, startup and transitive dispatches remain conditional.

## 6. USB writers and additional flush callbacks

### Writer registration narrowed

* **0x9D07A7A8** clears D+0x8C in driver initialization. This is an additional writer (null), not a new callable target.
* **0x9D07AD54 / 0x9D07AD58** install D+0x88 context and D+0x8C callback, guarded by handle!=-1 and D.byte[1]!=0.
* Parent setter stores P+0xDC/+0xE0 at **0x9D06686C / 0x9D066870**. Its tail **0x9D06687C** supplies bridge 0x9D066BA8 in delay **0x9D066880**.
* Concrete caller **0x9D06CA8C** supplies 0x9D06BDA0 and context 0 (delay 0x9D06CA90). It runs when USB application state 0x8002AB38 is zero and open returns !=-1.
* Open **0x9D06678C(0,3)** returns fixed P when P+4==2 and P.byte[0xD8]==0, sets P+0xD4=1 and D8=1 (0x9D0667C4/7CC), then returns P in delay **0x9D0667D4**.
* Matched-child helper **0x9D066EB0** is leaf and preserves t3. Thus the P-in-t3 provenance of the previously identified P+0xCC writes **0x9D066F70 / 0x9D066F94** survives that direct call; those were not inferred from a generic ABI assumption.

The five P+0xCC stores and null-child configuration from the first report remain established. This narrows registrations and adds the null driver writer. It still does not certify all alternative registrations or arbitrary alias writes to callback/request fields.

### Stall and clear-stall do invoke request callbacks

Resolved vtable targets previously left transitive effects open:

| Routine | Callback PC(s) | Status before callback | Traversal |
|---|---|---|---|
| **0x9D054918**, V+0x28 | **0x9D0549F8, 0x9D054A38, 0x9D054B54** | **-3** | Request+0x0C; next read after callback |
| **0x9D054BE4**, V+0x2C | **0x9D054CCC** | **-4** | Request+0x0C; next read after callback |
| **0x9D053EC0**, V+0x34 | None | Queue flag query | Leaf, returns selected queue flag bit |

0x9D054918 endpoint zero visits OUT then IN. It sets queue flag bit 1, writes -3 in branch delays **0x9D0549F4 / 0x9D054A34 / 0x9D054B50**, calls callbacks while requests are linked, reads next at **0x9D054A00 / 0x9D054A40 / 0x9D054B5C**, then clears heads at **0x9D054A14 / 0x9D054A4C / 0x9D054B6C**.

0x9D054BE4 rejects endpoint zero before its callback loop (**0x9D054C24 → 0x9D054D14**). For nonzero endpoints, status -4 is stored in delay **0x9D054CC8**, next read at 0x9D054CD4, queue head clear at **0x9D054CE8**. Thus its observed nonzero-endpoint path is not an embedded endpoint-zero control callback path.

**Important distinction:** embedded 0x9D066270 / 0x9D0661A8 return immediately only for status **-2**. That earlier result must not be extended to -3/-4.

* Rdata callback 0x9D0661A8 can execute its flag-controlled V+0x0C/+0x4C operations for -3; then nonzero status returns without its success-only clearing.
* Rsetup callback 0x9D066270 on -3 can enter ordinary handling and tail-enqueue Rsetup at **0x9D0662F8**. For nonzero length and P.byte[0xC0]==0, **0x9D06635C**, taken delay **0x9D066360**, reaches that requeue directly.
* Enqueue accepts signed request.status<3 at **0x9D0552D8–E0**, including -3, and tests queue **bit 0**, not bit 1, at 0x9D05530C–314.
* It clears request.next at **0x9D0553D4 / 0x9D0554CC**, then appends to the still-linked head list at **0x9D055400**.
* IRQ wrapper sets D.byte[0x74]=1 at **0x9D07AB8C** and clears it only at 0x9D07ABCC. That skips the non-IRQ busy-entry path for enqueue; the busy byte alone cannot establish rejection of an IRQ callback's requeue.

**Conditional mutation hazard, not an observed firmware failure:** if a -3 traversal reaches a still-linked Rsetup, its callback takes the requeue path, and enqueue succeeds, enqueue can change the next link that the traversal reads afterwards. If the surviving list terminates at that same request, appending it can create a self-link. This is not covered by the four-callback -2 cancellation closure.

In the documented ordinary setup path, **0x9D0560A0** has already removed Rsetup before the default handler calls stall; default handler has also cancelled IN at 0x9D0677B8. Those facts remove the specific linked-control-request condition there, provided no intervening callback repopulates the queues. No other caller/configuration was proven to meet the hazard conditions. Establishing all V+0x28 callers and queue membership during those calls remains open.

Generic 0x9D07B860's -3/-4 branches still forward event 16 through P+0xDC and do not enqueue themselves; its observed registered parent handler is the known event-16 leaf. The generic-pair registration remains conditional as in the first report.

## 7. What remains open

* Startup reentry: actual logical samples/initialization history, all bank-snapshot writers, and the behavior of re-entering 0x9D023328 after U has already initialized. Snapshot consumption gives a conditional explanation, not global depth clearance.
* Main root signal 6's transitive parameter/UI callees and alternate-current-state event handling: the direct rescan feedback is eliminated, but all further nested dispatch is not.
* Callback-pointer writer exhaustiveness outside the checked registrations: P+0xCC/+0xDC, D+0x8C, replacement child lists and arbitrary queued-request callbacks, including cached/uncached aliases.
* All V+0x28 callers and their queue membership, especially whether a linked Rsetup can receive -3 and requeue in the same traversal.
* Complete state writer closure through unknown object aliases and indirect callees. The seven candidates are resolved; the observed M set is 17, U's local selected-handler set is unchanged, and dispatcher restore/commit writers are explicit.
* Per-site hierarchical targets and shared event-buffer effects across other nested dispatch routes. Ordinary signal-4/6/17/18 buffers are separate, but nested dispatch of the same signal can reuse its buffer.

No required named handler was found absent from the supplied image. No additional image/dump is identified as necessary for these code-flow questions. Remaining uncertainty is explicitly scoped above. Stop after this step-1 follow-up; no memory or build clearance.

