# B4: stall callers and startup reentry

3 October 2026. Focused continuation of section 8, step 1 and `readme_B4_reentry_results.md`. **Step 1 remains open.** This report narrows the two identified issues; it establishes neither a stack bound nor an observed firmware failure.

The connected Ghidra session reports `ram: 9d000000 - 9d08195f`, suitable for the existing stock PIC payload. Ghidra decompilation and cross-references were checked against raw little-endian instructions from the already extracted `stock_pic_2.2.2.0.0.bin`. Several entries remain undefined in Ghidra, including 0x9D06775C, 0x9D023328 and 0x9D0800FC; their instruction sequences were read directly. No extraction, database mutation, firmware modification, stack budgeting, RAM reservation, building or flashing occurred.

Names carried forward: P=0x800536BC, D=0x8003A27C, V=0x800538E0, setup request R=P+0x84=0x80053740, data request=P+0x60=0x8005371C, M=0x80052E18, U=M+0x1B4=0x80052FCC. Default USB handler is **0x9D06775C**.

## Stall call inventory and delay-slot correction

V+0x28 resolves to **0x9D054918**, from the existing initialized table whose flash source word is **0x9D01A418**. Ghidra reports that data reference, rather than the indirect callers. There are two recovered call instructions that can select this slot:

| Call instruction | Target provenance | Arguments and predicate |
|---|---|---|
| **0x9D066A14** | `lw v0,0x28(v0)` at 0x9D066A10, following P+0xE8 | D, endpoint **0x80**, supplied by call delay 0x9D066A18. Helper 0x9D066998 takes this branch only when argument a1==1, its object-pointer validity test passes, and P+0xD8!=0. |
| **0x9D066E1C** | 0x9D066E90 loads P+0xE8; jump 0x9D066E98 executes **`lw v0,0x28(v0)` in delay 0x9D066E9C**, then reaches the shared call | D, setup.byte[4]. Endpoint handler 0x9D066DB0 requires setup.byte[1]==3 and setup.word[2]==0. |

The second call is also used for CLEAR_FEATURE: the alternative load **0x9D066E18 selects V+0x2C**, not stall. Ghidra's shared-call prototype drops the second argument from its pseudocode; raw **0x9D066DC8** loads a1 from setup+4 and the stall branch preserves it. Neither a linear look-forward scan nor the pseudocode prototype alone gives the complete call inventory.

The targeted raw slot-load inventory found ten non-sp `lw ...,0x28(...)` instructions. Besides the two above, they are 0x9D052AC8 (flag manipulation), 0x9D0698D4/9A5C/9C70 (numeric arithmetic), 0x9D06D3C8/D3D4/E534 (fp-relative local values), and 0x9D07A760 (configuration field copied to another object). Their local uses do not call the loaded value. The only literal 0x9D054918 word is the table source at 0x9D01A418; no direct J/JAL to that address was recovered. **This closes the recovered immediate-slot callers, not arbitrary computed aliases, externally installed pointers, or executable RAM.**

### All recovered callers of the stall/ACK helper

Ghidra xrefs and exact raw J/JAL encodings agree on these ten references to 0x9D066998. Arguments include their delay slots.

| Reference | Meaning | Can reach V+0x28? |
|---|---|---|
| 0x9D066E34 | ACK after endpoint SET_FEATURE/CLEAR_FEATURE; a1=0 at 0x9D066E28 | No; the SET_FEATURE branch has already used the separate shared stall call. |
| **0x9D066EA8** | Endpoint request byte[1]==12 (SYNC_FRAME); **taken branch-likely delay 0x9D066DE4 sets a1=1** | Yes. This is reachable, not an orphan epilogue. |
| **0x9D066FD8** | Interface/child matcher 0x9D066EB0 returns null | Yes, a1=1. |
| 0x9D067290 | End of SET_CONFIGURATION processing | No, ACK argument 0. |
| **0x9D0672C8** | Shared device OUT request response | Yes for unsupported CLEAR_FEATURE values and unsupported SET_FEATURE values/state; no for its ACK branches. |
| **0x9D067318** | Other unsupported device OUT standard requests | Yes, a1=1. |
| **0x9D0675CC** | Device IN request/descriptor rejection | Yes, a1=1. |
| **0x9D06796C** | Default-handler rejection | Yes, a1=1 at 0x9D06795C. |
| **0x9D06BF04** | Registered parent event 13, setup request byte[1] neither 0x0A nor 0x0B | Yes; jump delay 0x9D06BF08 sets a1=1. |
| 0x9D06BF3C | Parent event 13, setup request byte[1]==0x0B | No; jump delay 0x9D06BF40 supplies 0. |

At 0x9D0672C8 the precise stall branches are: request 1 with wValue!=1; request 3 unless wValue==1 or (wValue==2 and `(P.word[0]&0xE)==2`). SET_ADDRESS is ACK. SET_CONFIGURATION also has ACK paths; its event-9 parent notification does not stall in the observed registration.

At 0x9D0675CC rejection covers unsupported request bytes, unsupported descriptor types, absent descriptor pointers, out-of-range configuration/other-speed indices, and failed string lookup. Successful responses use 0x9D0668DC and the embedded data request.

The endpoint standard path is selected by default handler 0x9D06775C at **0x9D06791C**, after recipient=2 and request-type bits `setup.byte[0]&0x60==0`. Its endpoint-zero case reaches this handler directly; nonzero endpoints first undergo descriptor/state checks at 0x9D067874–8FC. Rejection there reaches 0x9D06796C instead.

## Is the setup request linked when these calls execute?

**For the recovered normal setup-delivery path and observed callback registration: no.** The conclusion depends on ordering, rather than assuming that status -3 cannot requeue.

1. The driver extracts a new setup packet in 0x9D055A9C's path. It loads R.next at **0x9D056084**, sets R.status=2 at 0x9D056090 and R.length=8 at 0x9D056098, then replaces the endpoint OUT list head with R.next at **0x9D0560A0**. That store is the delay slot of the callback-presence branch and executes before the callback **0x9D0560A4**. Thus R is no longer a member of the head-reachable list, even if stale next/prev fields remain inside R.
2. Embedded setup callback **0x9D066270** routes status 2 to 0x9D066300. It can notify the preceding transaction with event 11, installs default handler **0x9D06775C** at 0x9D066348, sets P+0xC0=1, and invokes event **13** through 0x9D066354/358 and the shared callback code at 0x9D0662B8. All the recovered stall cases above are reached inside this handler interval.
3. Default handler accepts only event 13 (**0x9D06775C–76C**). It first cancels IN endpoint 0x80 through V+0x40 at **0x9D0677B8**, with argument supplied in delay **0x9D0677BC**. Cancellation status -2 returns immediately from both embedded request callbacks; this is not the stall status -3 path.
4. Only after the transaction callback returns does R reach requeue: **0x9D0662D0–2FC**, V+0x38 with endpoint 0 and a2=P+0x84. ACK paths enqueue P+0x60 instead, e.g. **0x9D0669E4**, delay **0x9D0669E8**. They do not put R back on the OUT list before a stall.
5. Ordinary completion also removes its head before the callback (previously established **0x9D055C8C**). Its events 12/14 do not enter default-handler stall processing. In the observed parent registration they are leaves as well.

The registered parent **0x9D06BDA0** uses its bounded 17-entry table at 0x9D06BDC4. **Only event 13 selects 0x9D06BEE8**, its stall/ACK handling. Events 11,12,14 select leaf 0x9D06BE08; event 9 selects 0x9D06BEC8, which only updates a flag; events 15/16 select flag-clearing leaves. Reset/control bridge notifications therefore do not supply another known stall entry while R waits linked for a new packet. The previously recovered stock child record has no child callback table, so its fallback is this parent, under that configuration assumption.

At the separate endpoint SET_FEATURE stall, setup.byte[4]&0xF==0 selects the driver's special endpoint-zero case: it visits both control queues irrespective of direction. For nonzero endpoint numbers it visits the selected endpoint/direction, and the embedded setup request is registered on endpoint zero. Even the endpoint-zero case runs inside the same unlinked setup callback interval.

### What remains hazardous and what is actually established

The low-level stall routine **0x9D054918 remains unsafe against a callback that mutates the list it is walking**: callbacks at 0x9D0549F8/0x9D054A38/0x9D054B54 receive status -3, and next is read afterwards at 0x9D054A00/0x9D054A40/0x9D054B5C. Heads are cleared only later. Embedded R callback explicitly returns for -2, but not -3; with nonzero length and P+0xC0==0 it can take **0x9D06635C → 0x9D0662D4 → requeue**. Enqueue accepts signed status<3 and does not reject solely because the queue has the stall bit. A still-linked R could therefore mutate its own links.

**No recovered normal stall caller supplies that still-linked R situation. No observed failure is claimed.** The remaining USB edge is an interleaving or alternative pointer/registration path that invokes stall while R has been requeued, or requeues it during an outer stall traversal. The local ordering proof assumes the observed registration, intact queue ownership, and no untraced interrupt/external callback that defeats that interval. It is not a global exclusion of every possible RAM alias or interrupt nesting. These are the exact limits of the closure, rather than a reason to reinterpret the conditional hazard as demonstrated corruption.

## Startup reentry: exact predicate and consequence

The recovered startup sequence calls 0x9D01D250 at **0x9D053164**, which initializes U and stores initializer **0x9D023328** into M.word[0] at **0x9D01D2FC**. Outer startup calls **0x9D0800FC(M,0)** at **0x9D0531B4**. Its first action calls the current object handler at **0x9D080134**, preserving the null a1; it does not change M to a guarded state first.

Inside 0x9D023328:

* **0x9D023340 → 0x9D07D988** initializes event buffers, not the scanner snapshots/button records.
* **0x9D02334C → 0x9D0800FC(U,0)** initializes the menu before scanning.
* **0x9D0233A4 → 0x9D07E524** scans buttons while M still names 0x9D023328. Preceding 0x9D07C114(2) and 0x9D07C564→0x9D07C368(2) operate parameter/audio data; their recovered bodies do not prime the button snapshots.
* The preset setter that can suppress a button event is later, at **0x9D0233F4**. Main-root selection is later still: **0x9D0234AC stores 0x9D029118**.

Let bank b=0..8, bit k=0..7, mask[k] from 0x9D081348, id from 0x9D081350+8*b+k, old=halfword[0x80010988+2*b], new=the sampled low byte, and B=0x80010774 (stride 10). The edge-code-2 synchronous dispatch predicate is:

```text
(old XOR new) & new & mask[k] != 0
id < 53
B.halfword[10*id+4] == 0
M.word[0] == 0x9D023328       // to reenter the initializer
```

The scanner does **not** require gp-0x7F50!=0 on this branch. That enable test belongs only to edge code 1. The first-pass condition is sampled logical 1 on an accepted bit if old and the suppression field retain their startup zeros. The DINIT zero descriptors **0x9D019F90** (0x800000A0, length 2) and **0x9D019F9C** (0x80010708, length 0x292) cover the enable field, records and snapshots. Runtime enable is set only at **0x9D05326C**, after the outer initialization and a further scanner call at 0x9D053214. Zero enable therefore does not exclude this reentry.

The mapping and masks are literal: masks are `08 04 02 01 80 40 20 10`; bank selectors at **0x9D081398** are `12 13 14 02 03 04 01 0A 0B`. 0xFF mapping entries are ignored by id<53. No physical button identity or electrical polarity is inferred.

Ordering matters:

* **0x9D07E5A8** stores the entire bank snapshot before any callback in that bank.
* **0x9D07E680/684** test record+4; **0x9D07E688** clears record+0 in the branch delay.
* **0x9D07E698 → 0x9D07DAF8(id,2)** dispatches; **0x9D07E6B4** clears record+6 and branch delay **0x9D07E6C0** sets record+4=1 **after the callback returns**.
* Wrapper tail **0x9D07DB3C → 0x9D07E838** dispatches M synchronously. The dispatcher calls the current handler without a startup/reentrancy test. Initializer 0x9D023328 has no incoming-signal discrimination.

Thus the predicate is sufficient for **synchronous initializer reentry**, assuming the established startup state is still current. Updating the snapshot prevents a stable repeat of the same bit in the next scan; it does not prevent this first reentry, nor prime later banks before the callback. No recursion-depth bound follows from the nine-bank loop because changing samples, other writers and menu reinitialization must be accounted for first.

### Reinitializing the already initialized menu is not a harmless event

A nested initializer again calls **0x9D0800FC(U,0)**. That function directly calls U.word[0] with a1==0 at 0x9D080134. Initialized menu leaf **0x9D03646C** reads event halfword at **0x9D03647C** (`lhu v0,0(a1)`); menu root **0x9D03D828** does so at **0x9D03D83C**. Other selected menu states' event-read prefixes were established in the preceding report. There is no null-event conversion in 0x9D0800FC before its first call.

**Proven conditional consequence:** if the button predicate causes reentry after outer U initialization, a current initialized U handler can dereference the null event pointer. The resulting hardware exception/recovery behavior is not established here. This is distinct from claiming that a particular button gesture has reproduced the path.

## Remaining evidence needed within step 1

1. **Startup hardware condition:** the code proves the logical predicate, but the static image does not tell us the first nine sampled GPIO low bytes. Reader 0x9D07757C selects the bank using the halfword table at 0x9D081540, then reads **0xBF860420 at 0x9D077640** and masks it to 8 bits. No inversion is present. To decide whether real startup reaches the predicate, the missing evidence is a trace of those samples plus snapshots/suppression fields at the first 0x9D0233A4 scan (or a faithful hardware/input model). A new firmware image is not required for the code path; idle polarity or an actual startup occurrence cannot be supplied by guessing.
2. **USB global exclusion:** normal recovered control-handler ordering excludes linked R at each recovered stall call. Alternative callback registrations/computed aliases and interrupt nesting that can invalidate that interval remain outside this local proof. A counterexample would specifically need stall entry while R is head-reachable, or a callback requeue during an outer traversal—not merely the fact that R is normally queued between setup packets.
3. **Step 1 status:** no global reentry/indirect-target closure or stack bound is asserted. These findings do not authorize RAM placement or a firmware build. Stop at this report.
