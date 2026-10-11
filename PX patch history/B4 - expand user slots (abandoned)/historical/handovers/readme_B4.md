# Prophet X — Branch 4: user sample-group expansion

Prepared 2 October 2026, Australia/Brisbane. Focused handover for Codex with Ghidra. Cross-checked against master `prophet_x_re_handoff_2026-10-01.md`, version 33, and branch reports 1–15. Includes clearly marked preliminary findings from the interrupted next pass.

## 1. Objective and current authorization

Develop a separate test firmware expanding the user sample-group capacity, with **64 user groups** as the working target: factory + 32 purchased + 64 user = **97 total groups, internal IDs 0–96**. Preserve all existing internal IDs and preset meanings.

The standalone build must start from clean 2.2.2.0.0 and contain only this feature. Eventually merge it into `voice_sysex`; preserve that feature's code and ownership. At build time choose an unused external filename and matching internal/screen revision. No branch-4 firmware has been built, patched on disk or flashed.

**Current task is step 1 only:** resolve the USB reset-path callbacks and remaining state-machine/indirect-call targets. The user stopped manual tracing and moved to Ghidra. Do not proceed to mainline stack budgeting, RAM reservation, group patches, a firmware build or a flash recommendation in this task.

The proposed RAM location remains unproven. Findings below are a starting map, not whole-firmware coverage or clearance to build. Use Ghidra to resolve named gaps rather than repeating extraction, broad number searches or already completed tests.

## 2. Inputs and address conventions

| Input | Identity / layout |
|---|---|
| Clean container | `PxUpdate_V2.2.2.0.0.bin`, 3,099,064 bytes |
| Container SHA-256 | `a4b304b3bb48ca933ae63c99c0098698c497ebfc7c38ab2a823b5e0df4919fa9` |
| QNX ELF | Container slice `[0xD, 0xF0DA5)`; x86-64; addresses below are ELF virtual addresses |
| QNX ELF SHA-256 | `7db8a8276f0bda34d22fdd2e8744b304dc7d62f80f9189836b107a4d7b178cff` |
| PIC payload | Container slice `[0x273055, 0x2F49B5)`; 530,784 bytes (`0x81960`) |
| PIC SHA-256 | `14e9c9b9dc562b0384fc43b3c5e0eb7fea84a5792d1a19b9b3ea8276ef7646f5` |
| PIC import | Raw binary, 32-bit little-endian MIPS with appropriate DSP instruction support; base `0x9D000000` |
| PIC supplied range | `0x9D000000..0x9D08195F`, inclusive |

PIC flash offsets = virtual address minus `0x9D000000`. Never confuse these with container offsets or external serial-flash offsets. RAM is addressed through cached/uncached aliases; physical ownership must account for aliases.

If Ghidra has no program open, report that immediately. Do not spend time searching for an import capability that the MCP does not expose. If the loaded program is a modified firmware, identify it and report the difference before using it as the clean baseline. No need to re-extract an already available verified PIC payload.

## 3. Group map and established representation

Stock actively supports **32 user groups**, not the older eight-user limit. The existing names table describes more folders than the active index supports.

| Internal ID | Folder | Meaning |
|---|---|---|
| 0 | `f00` | Factory |
| 1–8 | `u00`–`u07` | First eight user groups |
| 9–40 | `p00`–`p31` | Purchased groups |
| 41–64 | `u08`–`u31` | Remaining active user groups |
| 65–132 | `u32`–`u99` | Names exist, but outside stock active bounds |

Working expansion appends IDs 65–96 (`u32`–`u63`). Proposed display order: factory 0, users 1–64, purchased 65–96. This preserves internal IDs while changing browsing order; it requires new mapping logic.

PIC group parameters are `0x22` and `0x63`; instruments `0x23/0x64`, categories `0x24/0x65`. Runtime parameter base `0x8000046C`, halfwords, `0x6B7` slots per part, part B offset `0xD6E`.

Inspected preset, SysEx and NRPN paths represent ID96 and even ID132. SysEx carries full raw bytes via seven-bit packing. NRPN splits parameter/value across two seven-bit controllers. **Do not resurrect the early hypothetical seven-bit group-ID ceiling.** This is encoding evidence, not proof that all consumers support those IDs.

## 4. QNX dependencies already identified

| Address / object | Finding |
|---|---|
| `gpGroupNames`, `0x2A0160` | 133 eight-byte pointers, size `0x428`; all names decoded |
| Allocation `0x16181`; constructor `0x33390` | Stock object size `0x33D0`; 65×17 four-byte counts, padded pointer-array offset `0x1148`; 65×17 eight-byte pointers |
| Accessors `0x33C10`, `0x33C70` | Reject group >64 and category >16; row index group×17+category |
| Index callback around `0x336E4` | Searches only 65 names |
| `MakeNewUserFolders`, `0x2DFE0` | Creates IDs41–64 only |
| `gGroupSizeCache`, `0x2A4A20` | 65×8 bytes (`0x208`); unchecked index in `GetFolderContentsSize`, `0x15320` |
| Startup `0x7BC0` | Size-cache endpoint `0x2A4C28`; relocation must change initializer endpoint |
| Import validator `0x15350`, endpoint at `0x1542A` | Searches 65 names via displacement `0x208`; hypothetical 97-name endpoint `0x308` tested |
| Release `0x33CA0`, comparison `0x33CB1` | Group >64 enters broad-release/sentinel path at `0x33D6C`, rather than simple rejection |
| Post-index refresh `0x33E9E` | Loop ends at group count65 |
| Size-cache update/delete | References around `0x15BC2` and `0x15E22` |

Object expansion must move the pointer-array offset and update every consumer together. The release routine's observed category cursor is not reset across its outer group loop; do not silently fix unrelated stock behavior as part of group expansion.

QNX dispatcher sample-switch path `0x220E8..0x222C3` carries low-byte group values. PIC count request `0x9D079978` sends message `0x4012` with group high byte/category low byte; QNX `0x22C6A` decodes it. Size request `0x9D079744` uses `0x4037`, group low14 bits and volume bit15; QNX `0x22DAE` decodes it. Backing table sizes remain the limiting dependencies.

## 5. PIC group limits, caches and persistent metadata

| Address / path | Finding |
|---|---|
| Descriptor table `0x9D047498`, 12-byte entries | Group maximum halfwords at `0x9D047630` and `0x9D04793C`, stock64 |
| Individual limiter `0x9D04D4FC`; setter `0x9D04DACC` | Clamps above-max edits; setter also uses group/category table |
| Bulk sanitizer `0x9D04D6D4` | Above-max values reset to default0; must change together with edit limit |
| Selector maps `0x9D080E2C`, `0x9D080E60` | Stock permutation for IDs0–64; tested larger IDs collapse to64 |
| Labels `0x9D063F60` | 132 labels, indexed by internal ID−1; presence does not establish active support |
| Import bounds `0x9D01B7C4`, `0x9D01B9B8` | Independent cursor max63; target cursor max95; cursor+1 passed through inverse mapping |
| Count/index cache `0x80037E90..0x8003A118` | 65×17×8 =8840 bytes, exclusive end |
| Getter `0x9D0792E0`; availability `0x9D079300` | Direct row indexing; no getter range gate |
| Size cache `0x8003A118..0x8003A21C` | 65×4=260 bytes; first extra count row overwrites it |
| Size initialization `0x9D079A08` | Queries groups1–64; loads loop count65 at `0x9D079A30` |
| Import size write / renderer read | Around `0x9D01B8EC` / `0x9D034288` |
| Runtime initialization `0x9D040ED8` | Count page at external serial address `0x5FD000`; legacy reads41 groups; marker `0xFF` selects extended read through64 at `0x9D041044`; remaining rows default count1/index−1 |
| Initialization bounds/base | Base construction `0x9D040EEC/EF0`; direct stores `0x9D040F40/F44/0x9D041038`; total bound65 at `0x9D040FC8`, end offset `0x2288` at `0x9D040FD0` |
| Count rebuild `0x9D042A8C` | Marker plus65×17 byte counts; writes existing4KiB count page; limits around `0x9D042B04/B08` |
| Extra direct name-display access | Base construction `0x9D041184/188`, index load `0x9D041190`; shared getter edits alone are insufficient |

Address correction against the stock disassembly: group-size initialization starts at `0x9D079A08`; `0x9D079A30` loads count65. Earlier references to `0x9D0799A0` as this initializer were inaccurate; that address is inside the count-request function.

Name builder `0x9D042B80` writes 64-byte records in external serial region `[0xC00000,0x1000000)`: **65,536 records shared across every group/category**, including one instrument-zero placeholder per category. Loop bound at `0x9D042D9C`, capacity stop at `0x9D042D64`. For97 groups, empty categories alone use1649 records. Count-page size fits97 groups (1650 bytes including marker), but name-region capacity does not automatically grow with the SSD.

Verified overflow inconsistency: initializer can construct record indices beyond65535 while the builder silently stops at capacity. A saturated stock fixture's first out-of-region entry is group15/category1, index65536. Reader `0x9D041E8C` with instrument1 requests serial address `0x1000040`. Expansion needs coherent demand validation and failure/rollback behavior; no solution has been implemented.

## 6. RAM candidate and boundaries — not approved

Startup SP `0x8007FFF0`, GP `0x80007FF0`. DINIT begins `0x9D001480`, 93 descriptors, ends `0x9D01A84C`. Zero descriptor `0x9D01A3B4` covers `0x80037D30..0x8003A21C`. Adjacent startup objects and copied data are owned; in-place growth is invalid.

Default heap `[0x80053AE0,0x80057AE0)`, size16KiB. Bounded `sbrk` `0x9D080B98` uses break/upper/lower words around `0x80053A64/68/6C`; boundary rejection tested. Alternate configuration and indirect users remain to audit.

Candidate contiguous cache base `0x80058000`:97×17×8 count/index bytes plus97×4 size bytes =13,580 (`0x350C`), end `0x8005B50C`. Relocated initialization/getter tests pass in emulator memory only. This does not reserve the RAM or prove safe stack clearance.

Alternative extra32 rows plus size entries needs4480 bytes before allocator overhead, with split addressing and coherent allocation failure handling. Allocating all13,580 bytes from the stock heap leaves2804 bytes before overhead/other users. Neither strategy selected.

Do not use the sum of distinct function frames or the apparent free address gap as a stack bound. An earlier report described the allocator caller at `0x9D07F044` as formatting; preliminary inspection instead identifies surrounding `0x9D07EE10` as a sort routine with comparator argument. Recheck function ownership before relying on that earlier label.

## 7. Interrupt and callback work already completed

Capstone's linear disassembly omitted22 SP-related COP0 instructions. Raw words `0x415DE800` / `0x41DDE800` were decoded as RDPGPR/WRPGPR for SP: previous-register-bank SP handling. Ghidra must decode those and DSP instructions correctly; omitted words cannot be treated as NOPs.

| IRQ root | Observed frame / IPL | Current target status |
|---|---|---|
| `0x9D05077C` | 24 /4 | No open indirect edge in prior direct CFG scope |
| `0x9D05081C` | 328 /4 | Same |
| `0x9D050F30` | 352 /4 | Same |
| `0x9D050B54` | 24 /4 | Same |
| `0x9D050BF4` | 304 /4 | Bounded tables resolved; no open edge in that scope |
| `0x9D051DB0` | 304 /1 | Timer callback `0x9D05BE6C`: observed registration recovered, writer exhaustiveness open |
| `0x9D052004` | 24 /4 | No open edge in prior scope |
| `0x9D05212C` | 312 /4 | MIDI path reaches sort and hierarchical state dispatch; target-set audit open |
| `0x9D0520A4` | 24 /4 | No open edge in prior scope |
| `0x9D052498` | 304 /4 | USB event/control/completion path; reset analysis open |
| `0x9D0526EC` | 304 /4 | USB completion targets conditionally recovered |

“No open edge” is a scoped analyzer result, not a stack/nesting proof. Controller ownership, delay slots and repeat activation remain independent. Prior CFG scripts stop at unresolved indirect targets and record delay slots without full effects.

Five finite jump tables recovered: jump/table/count `0x9D077B18/0x9D077B20/5`, `0x9D06E9E0/0x9D06E9E8/40`, `0x9D05B8F0/0x9D05B8F8/9`, `0x9D056F34/0x9D056F3C/5`, `0x9D056F74/0x9D056F7C/5`.

### Timer registration

IRQ `0x9D051DB0` → `0x9D05BEC0` → `0x9D05BD98`, JALR `0x9D05BE6C` reads parent+`0x34`, argument+`0x38`.

Parent `0x800539B8`, initialized60 bytes; handle parent+`0x24`. Setter `0x9D05C4E4`, stores at `0x9D05C544/54C`, writes target/argument through handle+`0x10/14`. Caller `0x9D075644` supplies leaf `0x9D074F0C` and timer state `0x80053810`; leaf compares counter, updates wrap count and pending byte, no frame/calls. Registration prefix and five leaf cases passed.

Configuration `0x9D07F2E0` passed by `0x9D06BF60`: controller index28, peripheral selector3. Caller writes `0xBF8101B0` at `0x9D06BF80/BFA0`, low priority field1/subpriority0, consistent with IPL1. Start helper `0x9D05B59C` writes mask`0x10000000` to `0xBF810044` and `0xBF8100C8`. Verified instruction segments, mapped MMIO only.

Correction: the handle is not a second object. Aligned validator arithmetic also accepts parent+60; this is not evidence of two allocated44-byte objects. Observed timer chain accounting360 bytes is conditional, not global.

### USB driver initialization and bridge registration

Driver `0x8003A27C`; initializer `0x9D07A720`, config `0x9D07F2A8`. Controller indices132/133 at driver+`0x64/68`; driver+`0x60`=1. Caller writes `0xBF810350` at `0x9D06BFD4/BFF4`, fields4/4; tested zero fixture ends`0x1010`. IRQ wrappers clear masks`0x10/20` at `0xBF810084`, stores `0x9D07ABC8/AC4C`.

Parent `0x800536BC`. Config `0x9D07F2FC`+`0x30` supplies driver vtable `0x800538E0`; DINIT descriptor `0x9D01A3E4`, copy source `0x9D01A3F0`,80 bytes.

Setter `0x9D066840` stores parent callback `0x9D06BDA0` at+`0xDC`, context0 at+`0xE0`; vtable+8=`0x9D07AD3C` receives parent and bridge `0x9D066BA8`, stores them at driver+`0x88/8C`. Full registration chain tested on synthetic enabled objects.

Bridge `0x9D066BA8` guards event<9, table `0x9D066BEC`, computed jump `0x9D066BE4`. Events3/4 update parent bit7 and can tail-forward; event6 returns. Three cases passed with explicit DSP indexed-load emulation. Event2 reset enters `0x9D066C74` and remains open.

### Generic transfer completion — established scope

Request callback+`0x0C`, parent+`0x14`. Stores `0x9D07BAA8` / `0x9D07BC40` install `0x9D07B860` / `0x9D07B8FC` in36-byte request slots. Four registration cases and ten completion cases passed.

Callbacks emit only events16/15 to parent `0x9D06BDA0`; dispatcher guards<17, table `0x9D06BDC4`, jump `0x9D06BDBC`. Event15=`0x9D06BE10` clears `0x8002AB45`; event16=`0x9D06BF0C` clears `0x8002AB44`; both leaves.

IRQ `0x9D0526EC` → `0x9D07ABE0` → `0x9D056414`: request calls `0x9D056570/65CC`. Conditional closure using those registrations had zero open edges. Conditional single-chain accounting440 bytes applies only to the tested completion registrations. Other request types/writers and reset calls are excluded.

## 8. Step 1: exact remaining Ghidra tasks

### A. USB reset and control callbacks

IRQ `0x9D052498` → `0x9D07AB60` → `0x9D055A9C`.

Event-field indirect calls: `0x9D055B30`, `0x9D055B4C`, `0x9D055B74`, `0x9D055B8C`, reading driver+`0x8C` → observed bridge `0x9D066BA8`.

Request-field indirect calls: `0x9D056020`, `0x9D055E7C`, `0x9D055F14`, `0x9D055F60`, `0x9D0560A4`, `0x9D055C90`, `0x9D0562A4`, `0x9D0562F4`, `0x9D0562C8`.

Reset bridge virtual targets under recovered vtable:

| Call PC | Slot | Target |
|---|---|---|
| `0x9D066C8C`, `0x9D066CA0` | +`0x40` | `0x9D054710` |
| `0x9D066CBC` | +`0x24` | `0x9D054098` |
| `0x9D066CD8` | +`0x20` | `0x9D054338` |
| `0x9D066D08` | +`0x10` | `0x9D053DE0` |
| `0x9D066D8C` | +`0x38` | `0x9D05529C` |

Direct reset helper `0x9D066AE8` walks child records, callback at `0x9D066B6C`. Observed configuration has one20-byte child record `0x9D07F49C`, callback-table pointer+`0x10`=0. Confirm initialization and all writes before pruning that call. Do not assume the same for every configuration.

**Preliminary discoveries made immediately before stopping; not yet independently verified or added to master:**

- Parent initializer `0x9D0663F8` stores callbacks `0x9D066270` at parent+`0x90` (`0x9D06646C`) and `0x9D0661A8` at+`0x6C` (`0x9D066478`). These alias request+`0x0C` for embedded requests at parent+`0x84` and parent+`0x60`; parent references at+`0x98/74`. These are two additional control-transfer callbacks, beyond the generic pair. Verify queue ownership and reachable call sites.
- `0x9D054710` synchronously invokes queued request callbacks at `0x9D0547A8` while cancelling requests with status−2. Trace its list loop and whether callbacks enqueue new requests or reenter cancellation.
- `0x9D0661A8` uses vtable slots+`0x0C/4C` at `0x9D066218/6254` depending on parent flags.
- `0x9D066270` can call parent+`0xCC` at `0x9D0662C8/632C/639C/63E8`; stores default handler `0x9D06675C` at+`0xCC` (`0x9D066348`), and tail-dispatches vtable+`0x38` at `0x9D0662F8`. Trace all writers of+`0xCC`, not only this default.

Deliverable: callback-source/target table with registration and ownership evidence, reset cancellation/reentrancy graph, explicit unresolved edges and conditions. Do not infer a global stack bound.

### B. MIDI-reachable sort and hierarchical state dispatch

IRQ `0x9D05212C` has additional MIDI real-time branches after its main body; inspect through `0x9D052498`, not just its first call. Prior closure reached260 direct calls and20 indirect sites.

**Preliminary, not yet emulator-tested:**

- Two indirect sort calls `0x9D07EED8` / `0x9D07EEF8` use saved comparator a3 in s3. Call `0x9D05F1F4` supplies comparator `0x9D05D438` in the delay slot `0x9D05F1F8`, with25 four-byte elements. Comparator is unsigned comparison, not a state handler. Verify caller set and resolve these separately.
- Hierarchical dispatcher `0x9D07E838` takes object pointer a0 and event a1, loads first-word state function and invokes it. Other18 indirect sites: `0x9D07E87C`, `EAB4`, `E9D8`, `EA10`, `EA2C`, `EA84`, `EA5C`, `E92C`, `E940`, `EB1C`, `EB08`, `E960`, `EAD4`, `EB34`, `EB74`, `E97C`, `E8F8`, `E90C` (all with prefix `0x9D07`). Track state/superstate transitions and nested dispatch; don't treat each site as an unrelated callback.
- Wrappers such as `0x9D07DC58` load object pointer from flash `0x9D07A0C4` → RAM `0x80052E18`, then tail-call dispatcher. Object is zero-initialized by DINIT descriptor `0x9D01A348`,732 bytes; no initial state pointer can be inferred from its zero descriptor's following file bytes.
- Initializer `0x9D01D250` stores `0x9D023328` into this object's first word at `0x9D01D2FC`.
- State handler `0x9D029118` can recursively dispatch subobject at main+`0x1B4`, call `0x9D029944` (delay slot adjusts a0). Trace subobject initializer `0x9D0362F4`, transition handlers and superstates; frequently stored `0x9D03D828` is one observed menu state, not the entire set.
- Linear code-pointer scanner found326 candidates;281 first-word stores with59 distinct targets. This is **not exhaustive**: missed constant propagation, aliases, tables and code/data ownership remain. Use Ghidra xrefs/data flow to establish actual state-object writers, rather than blindly assigning all59 targets to every indirect call.

Deliverable: object/state ownership map, finite target sets where proven, state/superstate graph and nested-dispatch or callback cycles. Explicitly flag any edge whose target set cannot be established. Stop after step1 findings.

## 9. Validation already done — do not repeat unnecessarily

Reports1–15 and uniquely named `prophet_x_user_groups_passN_evidence.zip` contain scripts/results. Original local filenames, if supplied separately, are:

- `verify_group_layout.py`, `verify_group_encoding.py`: name map, stock bytes, limiter/sanitizer and SysEx encoding.
- `verify_pic_metadata.py`: selectors, labels, metadata capacity/collision.
- `verify_import_and_compatibility.py`: cursor bounds, heap boundary, overflow read capture, preliminary voice_sysex overlap.
- `verify_qnx_import_bound.py` (22 cases), `verify_qnx_release_bound.py`.
- `verify_nrpn.py` (32 cases), `verify_nrpn_consumer.py` (300 cases).
- `verify_relocated_initialization.py`: five relocated initializer fixtures; hypothetical bounds/bases in emulator memory only.
- `audit_pic_interrupts.py`, `trace_irq_reachability_resolved.py`, `resolved_irq_jump_tables.json`: scoped IRQ inventory/finite table targets.
- `verify_timer_callback.py`, `verify_timer_controller_init.py`.
- `verify_usb_completion_callbacks.py`, `trace_usb_irq_conditional.py`.
- `verify_usb_event_registration.py`, `verify_usb_controller_init.py`, `usb_reset_virtual_targets.json`.

These tests are segmented and use documented mocks, synthetic RAM, DSP instruction hooks or plain mapped MMIO. They do not constitute complete synth transactions. Ghidra decompilation also needs verification against raw instructions and delay slots.

## 10. Compatibility and future work, outside current task

Compared `voice_sysex_2.2.2.0.3.bin`, SHA-256 `bbc3c2ad26bef7310fc15cac8edee22a1792d8ced3788f7080acccc047304857`, against stock:2893 differing container bytes. PIC differences at payload offsets `0x1200..0x121F`, `0x258B4`, `0x295B0..0x295B3`, `0x51BC4`. DINIT unchanged;17 inspected group sites disjoint. QNX constructor/accessor/name-table byte regions inspected were unchanged. This is preliminary overlap evidence, not certification of a future merge.

The current master includes later branch3 corrections: normal PIC firmware receiver is `0x9D0442A4`; `0x9D0448AC` is FPGA receiver; `0x9D045264` is user-content transfer. Do not conflate these when identifying the large stack frame. Internal post-reset installation remains a separate branch3 issue. Do not work on it during this branch4 task.

After step1, separately authorized future stages would combine mainline and interrupt stack evidence or choose bounded allocation, finalize all cache/layout/reference changes, implement coherent name-capacity handling, finish remaining UI/import/lifecycle coverage, and produce/test the standalone firmware. No absence-of-reference argument, extra label, successful emulator fixture or apparent address gap proves the change ready.
