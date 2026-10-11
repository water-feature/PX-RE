# B4 results — section 8, step 1 only

Date: 2 October 2026. Source: readme_B4.md and the connected Ghidra program, with targeted reads of the existing stock_pic_2.2.2.0.0.bin for raw instruction/data checks. No firmware, Ghidra metadata, or original handover was changed. No extraction, validation matrix, stack budgeting, RAM reservation, patching, building or flashing was performed.

## Loaded-program check and evidence limits

The connected program has one segment, named ram, spanning **0x9D000000–0x9D08195F** inclusive: the documented PIC base and supplied payload extent. Ghidra's reference at **0x9D0295B0** is an unconditional call to **0x9D05EE4C**, consistent with the stock hook rather than the documented modified jump to 0x9D001200. It is suitable for this investigation. The connector does not expose a program filename or complete byte export; this is range/instruction corroboration, not a new SHA-256 certification of the loaded database.

The source payload identity is the one documented in the handover: 530,784 bytes, SHA-256 14e9c9b9dc562b0384fc43b3c5e0eb7fea84a5792d1a19b9b3ea8276ef7646f5. Addresses below are PIC virtual addresses, not container offsets.

Ghidra decompilation/disassembly was used where functions exist, notably 0x9D055A9C, 0x9D066BA8, 0x9D0661A8, 0x9D07E838 and 0x9D07EE10. Several relevant entries are undefined; asking for 0x9D06675C also misleadingly selects an earlier unrelated function. Those cases were checked against raw words, literal tables, branch conditions and delay slots. A small temporary basic-MIPS decoder retained unknown DSP/COP0 words explicitly; unknown words were not treated as NOPs. A targeted CFG walk was used to enumerate candidate stores, not to certify register aliases or whole-program closure. Ghidra xref absence is not proof of absence.

**Proven** below means a concrete instruction, table entry or registration establishes the edge. **Conditional** means the edge holds for the observed initialized objects/configuration and stated guards. **Candidate** means ownership or reachability still needs proof.

## 1. USB ownership and callback sources

Use these object names:

| Name | Address / relationship |
|---|---|
| D, USB driver | 0x8003A27C |
| P, USB parent | 0x800536BC |
| Rsetup | P+0x84 = 0x80053740 |
| Rdata | P+0x60 = 0x8005371C |
| V, driver vtable | 0x800538E0 |
| Request layout used here | callback +0x0C; status +8; owner +0x14; next +0x18 |

Initializer **0x9D0663F8** accepts controller index 0, a non-null config and non-null config+0x20. Its saved parent register is established at 0x9D066430/434. Config **0x9D07F2FC** supplies child count 1 at +0x18, child pointer 0x9D07F49C at +0x1C, and V at +0x30. Stores 0x9D0664A8/4AC install the child count/pointer. **0x9D0664DC, the delay slot of the call at 0x9D0664D8**, installs V into P+0xE8.

| Callback source | Observed target | Registration / ownership evidence |
|---|---|---|
| D+0x8C; context D+0x88 | 0x9D066BA8; P | Existing setter chain 0x9D066840 → V+8 = 0x9D07AD3C; handover's established registration |
| P+0xDC; context P+0xE0 | 0x9D06BDA0; context 0 | Existing 0x9D066840 registration |
| Rsetup+0x0C = P+0x90 | **0x9D066270** | Literal construction 0x9D066464/468; store 0x9D06646C |
| Rdata+0x0C = P+0x6C | **0x9D0661A8** | Literal construction 0x9D066470/474; store 0x9D066478 |
| Rsetup+0x14 = P+0x98 | P | Store 0x9D0664C4 |
| Rdata+0x14 = P+0x74 | P | Store 0x9D0664C8 |
| Generic request+0x0C | 0x9D07B860 / 0x9D07B8FC | Established stores 0x9D07BAA8 / 0x9D07BC40, owner request+0x14 |

Rsetup's buffer points at P+0x20 (0x9D066460), initial length is 0x40 (0x9D0664B8), status is zero (0x9D0664C0), and flags are initialized at 0x9D0664BC. These are embedded request objects, not two further unrelated callback fields.

### Important handover correction: default handler address

The default P+0xCC handler is **0x9D06775C**, not 0x9D06675C:

```text
0x9D066338  3C029D06  lui   v0,0x9D06
0x9D06633C  2442775C  addiu v0,v0,0x775C
0x9D066348  AE0200CC  sw    v0,0xCC(s0)
```

Entry 0x9D06775C tests event a1 == 13. The taken branch-likely delay at **0x9D067764** computes handle<<4; code at 0x9D067784–794 derives P+handle*0xF0. Decompilation starting at 0x9D067770 loses that input computation.

## 2. USB IRQ/request sites

IRQ **0x9D052498 → 0x9D07AB60 → 0x9D055A9C**. Event calls **0x9D055B30, 0x9D055B4C, 0x9D055B74, 0x9D055B8C** read D+0x8C: conditionally 0x9D066BA8 under the observed registration.

All nine named request sites read request+0x0C and pass the request in a0. Some decompiler output omits arguments; the register instructions take precedence.

| Call PC | Request/queue context | Relevant ordering / delay evidence |
|---|---|---|
| 0x9D055C90 | Endpoint 0 OUT completion | Queue head advanced in branch delay 0x9D055C8C; call delay 0x9D055C94 sets a0=t6 |
| 0x9D055E7C | Nonzero endpoint OUT completion | Head advanced at 0x9D055E6C branch delay; a0=t6 |
| 0x9D055F14 | Nonzero endpoint IN cancellation | Head advanced at 0x9D055F08; request status -2 |
| 0x9D055F60 | Nonzero endpoint IN completion | Head advanced at 0x9D055F50; status zero; head reread after callback at 0x9D055F6C |
| 0x9D056020 | OUT cancellation path | Head advanced at **0x9D055FDC**, delay of 0x9D055FD8; a0=t6 at 0x9D056014 |
| 0x9D0560A4 | Endpoint 0 OUT setup reception | Status 2, length 8; head advanced in **0x9D0560A0** delay |
| 0x9D0562A4 | Endpoint 0 IN state 6 completion | Length/status cleared; IN head at queue+0x10 advanced in **0x9D0562A0** delay |
| 0x9D0562C8 | Endpoint 0 IN state 7 completion | IN head advanced at 0x9D0562BC; status zero in **0x9D0562C4** delay |
| 0x9D0562F4 | Endpoint 0 OUT paired status completion | Length/status cleared; OUT head advanced in **0x9D0562F0** delay |

Queue registration explains conditional targets; the slot alone does not give a universal finite set. Enqueue **0x9D05529C** indexes D+0x70 by 16*(2*(endpoint&0x0F)+(endpoint>>7)). Thus endpoint 0 and 0x80 occupy the OUT/IN queues for endpoint zero.

Reset enqueues Rsetup with endpoint 0 at **0x9D066D8C**; its delay **0x9D066D90** supplies a2=P+0x84. Normal Rsetup callback tail-enqueues it again at **0x9D0662F8**, target V+0x38. Rdata is submitted on endpoint 0x80 by **0x9D06693C** and **0x9D0669E4**; their delays supply Rdata. Consequently the control OUT/IN queues have concrete embedded targets 0x9D066270 / 0x9D0661A8 for those submissions. Generic queue requests retain their registered generic targets. Other requests/writers are not excluded.

Enqueue clears request+0x18 (0x9D0553D4 / 0x9D0554CC), sets queued status 3 and active status 4 for an empty head, and links through next/previous fields; **0x9D055400** appends through last+0x18. These queue writes matter to callback-time mutation.

## 3. Reset cancellation and reentrancy

The recovered DINIT copy source **0x9D01A3F0**, descriptor **0x9D01A3E4**, supplies V. The observed reset virtual targets are concrete:

| Call PC | Slot | Target / arguments |
|---|---|---|
| 0x9D066C8C | +0x40 | 0x9D054710; endpoint 0 supplied in delay 0x9D066C90 |
| 0x9D066CA0 | +0x40 | 0x9D054710; endpoint 0x80 in delay 0x9D066CA4 |
| 0x9D066CBC | +0x24 | 0x9D054098; a1=0x10 in delay |
| 0x9D066CD8 | +0x20 | 0x9D054338; endpoint 0x80, a2=0, a3=0x40 in delay |
| 0x9D066D08 | +0x10 | 0x9D053DE0; a0=D in delay |
| 0x9D066D8C | +0x38 | 0x9D05529C; endpoint 0, Rsetup in delay |

Reset event 2 enters **0x9D066C74**. It cancels OUT then IN, calls child reset 0x9D066AE8, performs the virtual operations above, and submits Rsetup if its status P+0x8C is signed <3 (test 0x9D066CE0–CE8). It subsequently obtains driver state and conditionally forwards the event through P+0xDC at tail **0x9D066C6C**, guarded by P+0xD4==1 and non-null callback.

### Cancellation traversal is callback-sensitive

At **0x9D054710**:

```text
0x9D05478C  load queue head into fp
0x9D054798  load callback from fp+0x0C
0x9D0547A0  branch if callback null
0x9D0547A4  store -2 to fp+8                 [branch delay]
0x9D0547A8  jalr callback, a0=fp
0x9D0547B0  load fp from fp+0x18            [AFTER callback]
0x9D0547B4  bnel fp,zero,0x9D05479C
0x9D0547B8  load next callback from fp+0x0C [taken delay]
0x9D0547C0  clear queue head               [after traversal]
```

It does **not** unlink each request before its callback. Changes to next links or reentrant traversal can affect the outer traversal. Entry paths use D+0x74/75 interrupt-control conditions and D+0x6C busy checks, but these do not establish a universal lock against recursive cancellation from arbitrary callbacks.

Known cancellation behavior:

* **0x9D066270:** status -2 branch at 0x9D066288 goes directly to return 0x9D066388. No control handler or requeue on this branch.
* **0x9D0661A8:** status -2 branch at 0x9D0661C4 returns via 0x9D0661F8. No virtual call on this branch.
* **0x9D07B860 / 0x9D07B8FC:** under the established parent registration, report events 16/15 to 0x9D06BDA0; leaves 0x9D06BF0C / 0x9D06BE10 clear pending flags. Their counts/status updates are not a cancellation requeue.

Therefore **these four observed callbacks do not recursively cancel/requeue on -2**. This is conditional closure for their registrations, not a guarantee for arbitrary queued requests.

Normal setup completion has a different graph:

```text
0x9D055A9C unlink Rsetup
  → 0x9D066270(status=2)
    → P+0xCC default 0x9D06775C(event=13)
      → 0x9D0677B8: V+0x40 = 0x9D054710(D,0x80)
        → pending Rdata/generic callbacks(status=-2)
      → recipient/type-specific control handling
        → possibly enqueue Rdata on 0x80
    → 0x9D0662F8: tail enqueue Rsetup on endpoint 0
```

The nested cancel argument 0x80 is in delay **0x9D0677BC**. Thus synchronous cancellation inside normal setup processing is proven; recursive cancellation from the four known cancellation callbacks is not observed.

### Child reset: pruned only for the observed configuration

Initializer 0x9D0664A8/4AC installs the one flash child at **0x9D07F49C**. Its five words are **2, 0x00020001, 0, 0, 0**, so child+0x10 is null.

Child reset **0x9D066AE8** applies state/configuration predicates, then tests child+0x10 at **0x9D066B54/558** and callback-table+4 at **0x9D066B60/564**, before JALR **0x9D066B6C**; delay loads the child handle from +8. The initializer's child callback-table+0x10 call at **0x9D06651C** is likewise guarded by the null child table pointer.

These calls are skipped for this immutable flash record and the observed installed list. No writable callback table was inferred. Runtime replacement of P+0x0C/+0x10 or alternative configs has not been exhaustively excluded; do not prune globally.

## 4. Control handlers, writers and additional virtual targets

P+0xCC is a changing control transaction handler, not a fixed default. Five concrete stores in the targeted USB control region:

| Store PC | Value / condition |
|---|---|
| 0x9D066348 | Default **0x9D06775C** |
| 0x9D066F70 | Matched child's callback-table+8, when table and callback non-null; also stores child's handle into P+0xC4 |
| 0x9D066F94 | P+0xDC fallback after child-table lookup |
| 0x9D0673D8 | P+0xDC fallback |
| 0x9D0677F8 | P+0xDC fallback from default recipient processing |

The latter three yield **0x9D06BDA0** with the observed parent registration. The child-installed target has no concrete non-null value in the observed configuration: table pointer is zero. This is an explicit conditional elimination, not a guessed callback address. Global alias writes to P+0xCC/+0xDC and alternative initialization remain unresolved.

Embedded setup callback **0x9D066270** invokes P+0xCC at **0x9D0662C8, 0x9D06632C, 0x9D06639C, 0x9D0663E8**. It uses two ABIs:
* Handler != P+0xDC: a0=control handle P+0xC4, a1=event, a2=data.
* Handler == P+0xDC: a0=event, a1=data, a2=P+0xE0 context.

Equality branch 0x9D0662BC selects the latter path. Delays **0x9D0662CC / 0x9D0663A4 / 0x9D0663EC** supply data arguments; do not propagate the default handler's ABI into the parent event handler. Events include 11 (previous transfer handling), 12/14, and 13 (new setup).

Default 0x9D06775C processes event 13 only. Following its synchronous IN cancellation, routing reaches **0x9D067170**, **0x9D06751C**, **0x9D066DB0**, **0x9D066F30**, or the parent fallback according to direction/type/recipient. Direct entry alone does not prove each request case can arrive from MIDI.

Additional resolved indirect edges under V:

| Call PC | Source | Target |
|---|---|---|
| 0x9D066218 | V+0x0C | 0x9D053DBC |
| 0x9D066254 | V+0x4C | 0x9D053EF8 |
| 0x9D06693C, 0x9D0669E4, tail 0x9D0662F8 | V+0x38 | 0x9D05529C |
| 0x9D066A14 | V+0x28 | 0x9D054918 |
| 0x9D066E1C | V+0x2C | 0x9D054BE4 |
| 0x9D066E48 | V+0x34 | 0x9D053EC0 |
| 0x9D067284 | P+0xDC, event 9 | Observed 0x9D06BDA0; data pointer supplied at delay 0x9D067288 |
| tails 0x9D066F80 / 0x9D066FC8 / 0x9D067404 / 0x9D067820 | Child handler or P+0xDC as above | Conditional child target / observed 0x9D06BDA0 |

0x9D053DBC is a leaf MMIO address-setting operation. Raw **0x9D053EF8–0x9D054094** has direct branches/MMIO accesses and a local constant-data copy, with no indirect calls. Its hardware polling loop is not assigned a termination bound. Targets 0x9D054918 / 0x9D054BE4 / 0x9D053EC0 are resolved by V but their complete transitive effects were not closed in this pass.

Parent callback **0x9D06BDA0** bounds event<17, indexed jump **0x9D06BDBC**, table **0x9D06BDC4**. Events 11/12/14 return at 0x9D06BE08. Event 13 enters **0x9D06BEE8**, examines setup byte 1: 0x0B → 0x9D06BF34 → 0x9D066998(P,0); 0x0A → 0x9D06BF20 → 0x9D0668DC(P,0x8002AB52,1); otherwise 0x9D06BF04 → 0x9D066998(P,1). The helpers submit Rdata or select V+0x28; this is ordinary control processing, excluded by the embedded callbacks' -2 gates.

## 5. MIDI real-time sort: finite comparator target

The full IRQ tail through 0x9D052498 was inspected. Main real-time processing requires the observed receive-enable gate and **0x9D04D780(4)==0** at 0x9D0522B8.

| MIDI byte | IRQ call / argument delay |
|---|---|
| 0xF8 | 0x9D052460 → 0x9D05F498; 0x9D052464 supplies a1=0xF8 |
| 0xFA | 0x9D052474 → 0x9D05F498; 0x9D052478 supplies a1=0xFA |
| 0xFB | 0x9D052488 → 0x9D05F498; 0x9D05248C supplies a1=0xFB |
| 0xFC | 0x9D05244C → 0x9D05F498; 0x9D052450 supplies a1=0xFC |

0x9D05F498 sends F8 to **0x9D05F068**, FA to **0x9D05F42C**, FC to **0x9D05F400**; its FB branch performs no corresponding action.

Within 0x9D05F068, call **0x9D05F1F4 → 0x9D07EE10** supplies a0=0x80022A50, a1=25, a2=4. Comparator construction is:

```text
0x9D05F1F0  lui   a3,0x9D06
0x9D05F1F4  jal   0x9D07EE10
0x9D05F1F8  addiu a3,a3,-0x2BC8   [delay: 0x9D05D438]
```

Sort saves a3 in s3. Both **0x9D07EED8 / 0x9D07EEF8** call s3. Thus their target set is exactly **{0x9D05D438} for this caller**. Their delay instructions at 0x9D07EEDC / 0x9D07EEFC update the pivot/index argument context; neither overwrites s3. Comparator loads unsigned words and returns -1/0/1: returns at 0x9D05D468/470/478, values supplied in their delay slots. It is a leaf and not a state handler.

Ghidra reports 0x9D05F1F4 as the sort caller. Missing definitions/xrefs prevent certifying that it is the only firmware caller; another caller's a3 would need separate resolution.

FA/FC conditionally reach **0x9D07DCC8 → 0x9D07E838(M,event)**. FA additionally tests configuration 0x1F; both use the gate at 0x9D05F3C4. 0x9D07DCC8 writes event value gp-0x7BD0, loads M from 0x9D07A0C4, and tail-dispatches; delay **0x9D07DCD8** supplies event pointer gp-0x7BD4. **This is signal 13**, established by initializer store **0x9D07DA78** (not signal 12).

## 6. Hierarchical dispatcher: ownership, not 18 unrelated callbacks

**M = 0x80052E18**, supplied by flash pointer **0x9D07A0C4**.
**U = M+0x1B4 = 0x80052FCC**, the embedded menu object.

| Object | Runtime initialization |
|---|---|
| M | 0x9D01D250; first-word store **0x9D01D2FC = 0x9D023328** |
| U | Main initializer calls **0x9D0362F4** at 0x9D01D2EC with U; first-word store **0x9D036364 = 0x9D031C38**, in the return delay slot |

The DINIT zero block does not provide an initial function pointer.

Dispatcher **0x9D07E838** reads object+0. Its 18 call sites share the current object's state/superstate history. Return 3 rereads object+0 and walks the superstate; the reread occurs in taken branch-likely delay **0x9D07E888**. Return 2 selects a transition target written into object+0 and processes exit/entry/initial transitions. Return 0 handles the event. Terminal **0x9D081948** returns 1.

Internal event words: **0x9D0818C4=0** superstate query, **0x9D0818C8=1** entry, **0x9D0818CC=2** exit, **0x9D0818D0=3** initial transition.

| Call PC (prefix 0x9D07) | Invocation role |
|---|---|
| E87C | Current state, original event |
| E8F8, EAB4, EAD4, EB08, EB1C, EB34 | Exit event 2 |
| E90C, E92C, E940, E960, E97C, EA2C, EA5C, EB74 | Superstate query 0 |
| E9D8, EA84 | Entry event 1 |
| EA10 | Initial-transition event 3 |

Registers holding ancestor functions and local ancestor arrays are derived from state handlers for the **same a0 object**. They do not license combining M and U target sets at every site. The exact subset at an individual exit/entry site depends on the selected transition and ancestor chain; full per-site subsets are not closed below.

A further initialization dispatcher **0x9D0800FC** is relevant to startup: callback sites **0x9D080134, 0x9D080168, 0x9D080198, 0x9D0801C0, 0x9D0801DC** perform initial/query/entry processing on their supplied object. This is additional to the handover's 18 ordinary dispatcher sites.

### Concrete main-object graph and candidates

Initial main state **0x9D023328** calls event initialization 0x9D07D988, calls **0x9D0800FC(U,0)** at 0x9D02334C, and calls menu wrapper 0x9D036A28 at 0x9D02341C. It installs **0x9D029118** at **0x9D0234AC**, returning 2. Main root saves the supplied object in s0. Its event table is **0x9D02916C**, 16 entries for signals 4–19, jump **0x9D029164**.

The following literal first-word stores on root paths establish M's observed transition/superstate destinations. These are branch-dependent edges, not a claim that every MIDI message reaches every state:

| Store PC(s) | Target |
|---|---|
| 0x9D02995C | 0x9D081948, superstate; returns 3 |
| 0x9D029834 | 0x9D029118, self transition; return 2 in delay 0x9D02983C |
| 0x9D02F258 | 0x9D026D54; return 2 in delay 0x9D02F260 |
| 0x9D02A88C | 0x9D01EACC |
| 0x9D02B804, 02B85C, 02B608, 02B924 (all prefix 0x9D) | 0x9D01C64C |
| 0x9D02B6C4, 02B728 | 0x9D01BAA8 |
| 0x9D02B0E0 | 0x9D023AEC |
| 0x9D030580, 0317D0 | 0x9D027294 |
| 0x9D02AE00 | 0x9D026610 |
| 0x9D02F1F4 | 0x9D01E800 |

Additional concrete state-to-state edges: **0x9D023AEC → 0x9D01B61C** at store **0x9D025B58**, and **→0x9D01ABB0** at **0x9D0259D4**; **0x9D027294 → 0x9D023AEC** at **0x9D027418**. 0x9D01B61C saves object in s1 at the branch delay **0x9D01B644**; stores **0x9D01B6EC / 0x9D01B9A4** select main root. 0x9D01ABB0 decompilation shows transitions to 0x9D023AEC / main root and nested calls through the menu wrapper.

Returned-root stores recovered in targeted handler CFGs include:
* 0x9D026D54: 0x9D026D8C / 26DF0 / 26FC4 / 26FF4.
* 0x9D01EACC: 0x9D01EB7C / 1EF6C; self-state stores 1EECC / 1FD98.
* 0x9D01C64C: 0x9D01C9BC / 1CC00; self 1CA38.
* 0x9D01BAA8: 0x9D01BBB8 / 1BFFC; self 1BE4C.
* 0x9D023AEC: 0x9D0245BC / 248B0 / 25710 / 25A20.
* 0x9D027294: 0x9D027338 / 273C4 / 2754C.
* 0x9D026610: 0x9D0266BC / 26AAC.
* 0x9D01E800: 0x9D01E898 / 1E8D0.

In abbreviated lists above, omitted leading address digits match the first full address on that bullet.

**Candidate alias stores requiring a0 provenance through their paths:** 0x9D02B8D0→0x9D0203D0; 0x9D02A8FC→0x9D01EACC; 0x9D02E9B4→0x9D021B00; 0x9D02B108→0x9D027648; 0x9D02B4F0→0x9D0235EC; 0x9D02DFF0→0x9D01E800; 0x9D01B81C→0x9D023AEC. These target literals are real; attribution to M at each store is not yet established. Callees receiving an object alias can add writers beyond this local enumeration.

Stores **0x9D0303E4 / 0x9D030378 / 0x9D02ACCC** are numerical writes into timing/array data around 0x800530E4, not evidence of state callbacks. No set of 59 linear-scanner targets was assigned to the dispatcher.

### Menu graph: exact finite outbound root set

U initial state **0x9D031C38** writes **0x9D03D828** at **0x9D031C40** and returns 2. Menu root 0x9D03D828:
* Event 3 selects **0x9D03646C** at 0x9D03D978.
* Event 17 reads event+4 as unsigned selection, bounds it <50 at **0x9D03D868**, and dispatches through table **0x9D03D888**, jump **0x9D03D880**, with a NOP delay.
* Default superstate store **0x9D03D954** selects **0x9D081948** and returns 3.
* Selection stores use s1 saved from the root's object argument and return 2; common jump 0x9D03D95C has return-value delay 2.

There are **42 concrete selection destinations**, not 41. Indices 0,27,28,29,30,40,42,47 take the default path. This table is a finite proven outbound set for the root; it is not a proof of every writer reachable inside every selected handler/callee.

| Selection | Case PC | First-word store PC | Selected state |
|---|---|---|---|
| 1 | 0x9D03D970 | 0x9D03D978 | 0x9D03646C |
| 2 | 0x9D03D9A8 | 0x9D03D9B0 | 0x9D03B5D4 |
| 3 | 0x9D03D9BC | 0x9D03D9C4 | 0x9D03A700 |
| 4 | 0x9D03D9D0 | 0x9D03D9D8 | 0x9D03A42C |
| 5 | 0x9D03D9E4 | 0x9D03D9EC | 0x9D03A22C |
| 6 | 0x9D03D9F8 | 0x9D03DA00 | 0x9D039F68 |
| 7 | 0x9D03DA0C | 0x9D03DA14 | 0x9D039B7C |
| 8 | 0x9D03DA20 | 0x9D03DA28 | 0x9D0397A0 |
| 9 | 0x9D03DA34 | 0x9D03DA3C | 0x9D03AD9C |
| 10 | 0x9D03DA48 | 0x9D03DA50 | 0x9D039518 |
| 11 | 0x9D03DA5C | 0x9D03DA64 | 0x9D039290 |
| 12 | 0x9D03DA70 | 0x9D03DA78 | 0x9D039070 |
| 13 | 0x9D03DA84 | 0x9D03DA8C | 0x9D038DE8 |
| 14 | 0x9D03DA98 | 0x9D03DAA0 | 0x9D033B7C |
| 15 | 0x9D03DAAC | 0x9D03DAB4 | 0x9D0338AC |
| 16 | 0x9D03DAC0 | 0x9D03DAC8 | 0x9D038B68 |
| 17 | 0x9D03DAD4 | 0x9D03DADC | 0x9D038948 |
| 18 | 0x9D03DAE8 | 0x9D03DAF0 | 0x9D0335DC |
| 19 | 0x9D03DAFC | 0x9D03DB04 | 0x9D03330C |
| 20 | 0x9D03DB10 | 0x9D03DB18 | 0x9D035CAC |
| 21 | 0x9D03DB24 | 0x9D03DB2C | 0x9D032FEC |
| 22 | 0x9D03DB38 | 0x9D03DB40 | 0x9D032CCC |
| 23 | 0x9D03DB4C | 0x9D03DB54 | 0x9D03A9C4 |
| 24 | 0x9D03DB60 | 0x9D03DB68 | 0x9D0386D8 |
| 25 | 0x9D03DB74 | 0x9D03DB7C | 0x9D035AC4 |
| 26 | 0x9D03DB88 | 0x9D03DB90 | 0x9D03C874 |
| 31 | 0x9D03DB9C | 0x9D03DBA4 | 0x9D038434 |
| 32 | 0x9D03DBB0 | 0x9D03DBB8 | 0x9D035850 |
| 33 | 0x9D03DBC4 | 0x9D03DBCC | 0x9D0380E8 |
| 34 | 0x9D03DBD8 | 0x9D03DBE0 | 0x9D037D70 |
| 35 | 0x9D03DBEC | 0x9D03DBF4 | 0x9D037B04 |
| 36 | 0x9D03DC00 | 0x9D03DC08 | 0x9D036028 |
| 37 | 0x9D03DC14 | 0x9D03DC1C | 0x9D037798 |
| 38 | 0x9D03DC28 | 0x9D03DC30 | 0x9D0371D8 |
| 39 | 0x9D03DC3C | 0x9D03DC44 | 0x9D031ECC |
| 41 | 0x9D03DC50 | 0x9D03DC58 | 0x9D0322E4 |
| 43 | 0x9D03DC64 | 0x9D03DC6C | 0x9D03C300 |
| 44 | 0x9D03DC78 | 0x9D03DC80 | 0x9D034F88 |
| 45 | 0x9D03DC8C | 0x9D03DC94 | 0x9D0343F4 |
| 46 | 0x9D03DCA0 | 0x9D03DCA8 | 0x9D03206C |
| 48 | 0x9D03DCB4 | 0x9D03DCBC | 0x9D036B28 |
| 49 | 0x9D03D994 | 0x9D03D99C | 0x9D034068 |

Each selected handler's prefix contains a literal superstate assignment back to **0x9D03D828**, with return 3. In selection order above, store PCs are:

```text
0x9D036494 0x9D03B5FC 0x9D03A724 0x9D03A450 0x9D03A250 0x9D039F8C
0x9D039BA0 0x9D0397D8 0x9D03ADE8 0x9D03953C 0x9D0392B4 0x9D039094
0x9D038E0C 0x9D033BA4 0x9D0338D0 0x9D038B8C 0x9D03896C 0x9D033600
0x9D033330 0x9D035CD0 0x9D033010 0x9D032CF0 0x9D03A9EC 0x9D0386FC
0x9D035AE8 0x9D03C8B8 0x9D038458 0x9D035874 0x9D03810C 0x9D037D94
0x9D037B28 0x9D03604C 0x9D0377C0 0x9D037204 0x9D031EF0 0x9D032320
0x9D03C328 0x9D034FCC 0x9D034438 0x9D032090 0x9D036B50 0x9D0340AC
```

The final entry corresponds to selection 49, whose case precedes selection 2 in file order. Prefix predicates determine when the superstate write executes; the handler must not be replaced by its superstate for all events. Ghidra decompilation at 0x9D03646C, 0x9D037B04, 0x9D03C300 and 0x9D036B28 confirms event handling and root fallback. Other listed prefix edges were checked from raw literal construction/store/return instructions.

Wrapper **0x9D036A28** supplies signal **17**, initialized at **0x9D07DAA0** (gp-0x7C28). It writes selection/value at gp-0x7C24/-0x7C22 and tail-dispatches its supplied object; **0x9D036A34**, the jump delay, writes the final value. The wrapper itself does not force ownership to M.

## 7. Nested dispatch and callback cycles

### Proven object-to-object dispatch

Main root signal 15 reaches call **0x9D029944 → 0x9D07E838**. **Delay 0x9D029948 adds 0x1B4 to a0**: this dispatch belongs to U, while the M dispatcher/handler are live. It subsequently returns handled. Other concrete main→menu edges include **0x9D02341C → 0x9D036A28**, **0x9D023464 → 0x9D01AB84 → 0x9D036A28**, and the decompiled 0x9D01ABB0 menu route. No separate global callback universe should be applied to these U calls.

### Proven synchronous same-object reentry, conditionally activated

1. **M root → 0x9D06E890 → 0x9D07DB98 → 0x9D07E838(M,event 6).**

   Call **0x9D02F240** occurs after **0x9D02F234/238** tests M+0x1C nonzero. There is no intervening M state replacement before the call. 0x9D06E890 iterates 34 pot entries and invokes 0x9D07DB98. Wrapper 0x9D07DB98 loads M through flash 0x9D07A0C4 at 0x9D07DBE0/BE4, writes the event at 0x80037D14, and **tail-jumps at 0x9D07DC0C**, restoring SP in its delay. Signal 6 is initialized at **0x9D07D9D8**. The tail jump removes only the wrapper's own frame; the outer state handler/dispatcher remain live. Reentry is a real call graph edge, not evidence of unbounded recurrence.

2. **M root → 0x9D0216BC → 0x9D07DD18 → 0x9D07E838(M,event 18).**

   Ghidra root-region callers include **0x9D02E46C, 0x9D02E668, 0x9D02CE90, 0x9D02F744, 0x9D02FAEC, 0x9D0301DC, 0x9D02B158, 0x9D02F348, 0x9D030C8C, 0x9D030D24, 0x9D030E30, 0x9D030610, 0x9D030740, 0x9D031980, 0x9D0319A8**.

   0x9D0216BC compares M+0xA8 against a1, stores state fields on guarded paths and conditionally tail-jumps at **0x9D021720**. Wrapper 0x9D07DD18 loads M and jumps at **0x9D07DD20**, delay **0x9D07DD24** supplies gp-0x7BE8. Signal 18 is initialized at **0x9D07DAB4**. Call-argument and state-field predicates decide which listed callers actually dispatch; no unconditional recursion claim is made.

3. **Startup M initial handler → 0x9D07E524 → 0x9D07DAF8 → 0x9D07E838(M,event).**

   Main initial handler calls 0x9D07E524 at **0x9D0233A4** before replacing its initial state. 0x9D07E524 conditionally emits changed-button events at **0x9D07E618 / 0x9D07E698** through 0x9D07DAF8. Activation depends on pending button changes and the observed enable flag. This is a conditional startup reentry edge; the required startup flag values and repeat behavior were not proven.

Candidate: **0x9D06E910 → 0x9D07DB98** at **0x9D06E954**, for pending pot entries (40-entry loop). It clears the pending flag after dispatch. Ghidra does not provide a caller for 0x9D06E910, so reachability from the scoped MIDI graph remains open.

MIDI handler xrefs to main wrapper **0x9D07DC58** include **0x9D05D814, 05D878, 05D8A4, 05D904, 05D990, 05D9E8, 05DA3C, 05DA9C, 05DD04, 05DDB0, 05DDEC, 05DE7C, 05E340** (all prefix 0x9D). Other observed wrapper calls are **0x9D05DD60→0x9D07DC40**, **0x9D065180 / 065780→0x9D07DC14**. These load M through the same flash pointer. Event entry is proven; the current M state and branch predicates govern subsequent transitions.

The dispatcher caches state/ancestor information and uses shared event objects. Same-object nested dispatch can therefore interact with the outer operation's cached state and event contents. A complete proof of restoration/transition behavior across these cycles is still missing. No maximum nesting depth or memory clearance is inferred.

## 8. Remaining unresolved edges and precise limits

1. **USB writer exhaustiveness:** the five P+0xCC stores and concrete registration are established, but global alias writes, alternative P+0xDC registrations, driver D+0x8C replacements and other queued request+0x0C writers are not excluded. Finite control targets apply to the observed configuration; the nine request calls are not globally closed by assigning four targets everywhere.
2. **Child-list replacement:** config child is immutable and null-table, but exhaustive writes/replacements of P+0x0C/+0x10 have not been proven. A replacement child needs its callback-table+4/+8/+0x10 resolved.
3. **Cancellation mutation/reentry:** known -2 callbacks close conditionally. An additional callback could mutate request+0x18, append to the active list, or invoke cancellation while its head is still linked. Queue guards have not been proven to prevent all such cases.
4. **Control transitive effects:** V targets 0x9D054918, 0x9D054BE4 and 0x9D053EC0 are identified but their complete callees/side effects remain open. Parent event 9/other forwarded bridge events are not covered by the event 11–16 leaves/control subset above.
5. **Sort caller exhaustiveness:** the F8-reachable comparator is proven; another call to 0x9D07EE10 would need its own a3 provenance.
6. **Main-state alias candidates:** the seven candidate stores listed in section 6 need path-specific a0 provenance. Transitive callees, copied state pointers and object-alias writes prevent claiming a closed complete M target set.
7. **Menu closure:** the root has 42 finite outbound destinations and verified superstate-prefix edges, but complete selected-handler bodies and their callees have not been exhaustively audited for additional U state writers or U→M→U cycles.
8. **Per-site hierarchical target sets:** ownership is established, but exact exit/entry/initial/query subsets at all 18 sites depend on full state-transition closure; do not assign every observed state to every site.
9. **Nested dispatch predicates:** the same-object routes above are real, conditional edges. Their interaction with shared event buffers, state mutation, ancestor caching and possible repeated activation remains to be resolved. The caller of candidate 0x9D06E910 is also unresolved.
10. **Ghidra coverage:** undefined entries and incomplete xrefs constrain exhaustive claims. No additional image is specifically required for the resolved edges; remaining uncertainty here is code/data-flow coverage of the supplied payload, not evidence that these handlers are absent.

Step 1 findings end here. No build or flash clearance is implied.

