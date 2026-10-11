# B4 — QNX 97-group expansion design

## Decision and scope

Recommend expanding the existing `CSampleGroups` allocation to a single owned 97×17 count/head object with appended validity and lifetime metadata. Relocate size-cache ownership into a dedicated process-lifetime reservation; do not extend the stock cache into adjacent storage. Preserve group IDs and existing wire messages. Checked results must gate successful count/size replies and subsequent publication.

This is a design, not an applied patch or build. It reuses `readme_B4_extension_population_source.md`, `readme_B4_checked_operations_design.md` and the accepted split-addressing/population results. No PIC audit, capacity negotiation or flashing was performed. Addresses below are QNX ELF virtual addresses, not PIC addresses. Stock ELF was read directly from the documented update slice in memory; instruction evidence is in `b4_qnx97_*.txt`. Source-level layouts and synchronization below are proposed requirements, not recovered source definitions.

## Stock evidence and preserved identity

The stock allocation is 0x33D0: counts at +0, 65×17 uint32 entries ending +0x1144; four padding bytes; heads at +0x1148, 65×17 uint64 entries ending +0x33D0. Index nodes are 0x408 bytes, with next at +0x400. Use the existing new/delete family, not an unverified malloc/free substitution.

`gpGroupNames` at 0x2A0160 already has the required names. ID0=f00; IDs1–8=u00–u07; IDs9–40=p00–p31; IDs41–64=u08–u31; IDs65–96=u32–u63. ID97=u64 exists in the larger name table but is outside the proposed supported range. Do not renumber or derive names from a new arithmetic convention.

The stock size cache starts at 0x2A4A20 and occupies 65×8=0x208 bytes. The traversal accumulator starts immediately at 0x2A4C28. An in-place 97-entry extension would overwrite owned storage.

## Exact new count/head owner layout

All offsets are relative to the existing `CSampleGroups` owner. `i=17*g+c`, with unsigned group 0…96 and category 0…16 validated before arithmetic.

| Offset range, half-open | Field | Ownership/initialization |
|---|---|---|
| 0x0000–0x19C4 | uint32 counts[97][17] | Object, zero at construction |
| 0x19C4–0x19C8 | padding | Zero |
| 0x19C8–0x4D50 | node* heads[97][17] | Object, null at construction |
| 0x4D50–0x53C1 | uint8 count_state[97][17] | Object, INVALID at construction |
| 0x53C1–0x53C8 | padding | Zero |
| 0x53C8–0x53D0 | uint64 index_epoch | Object, zero; advance on mutation |
| 0x53D0–0x53D4 | uint32 writer_gate | Atomic, zero |
| 0x53D4–0x53D8 | uint32 reader_pins | Atomic, zero |
| 0x53D8–0x53DC | uint32 last_index_status | Explicit outcome, zero=not initialized |
| 0x53DC–0x53E0 | uint32 lifecycle | CONSTRUCTING=0, READY=1, CLOSING=2 |

Total allocation 0x53E0 (21,472 bytes), 8,208 bytes more than stock. Arrays alone end at 0x4D50. Metadata is owned appended storage, not a presumed unused field. States: INVALID=0, BUILDING=1, VALID_PRESENT=2, VALID_ABSENT=3. VALID_PRESENT includes a successfully enumerated zero; ABSENT means an intentionally optional path was conclusively absent. Count values are meaningful only in a valid state. Enforce count ≤255 before admitting another node or wire narrowing.

Checked accessor contracts: `bool CountChecked(owner,g,c,uint32*out)` and `bool FolderChecked(owner,g,c,index,node**out)`, with separate outcome and numeric/pointer result. Failure leaves the output untouched. Index is zero-based; require index<count before walking. Empty valid cell yields count success/zero; a folder lookup has no element and returns false/null through a separately defined unavailable result. Never interpret null or zero alone as backend success. Legacy numeric accessors may remain as compatibility wrappers only where callers do not publish a successful backend result; all publication and node-use callers must consume checked status.

## Allocation, constructor and instruction sites

| Stock site | Required change |
|---|---|
| 0x16181 `mov edi,0x33D0`; call new at 0x16186 | Allocate 0x53E0. Mandatory owner construction failure must not leave a null owner installed or continue startup as though indexed. |
| 0x16191 calls ctor 0x33390; owner installed at 0x1619B | Replace/redirect constructor with exact-layout initialization. Publish the initialized owner only after construction; do not publish count validity merely because construction completed. |
| 0x161A3 index call | Consume explicit checked index outcome; failed initial indexing leaves affected cells INVALID and no successful count replies. Startup policy may retain a usable process with unavailable library backend, provided all consumers honor status. |
| Ctor 0x33390 outer end +0x2288 | Arrays-only end becomes +0x3388; head store 0x333AF displacement +0x1148 becomes +0x19C8. A complete replacement must also initialize appended fields; immediate edits alone are insufficient. |
| Folder accessor 0x33C10: group compare 0x33C10 | Maximum group 0x40→0x60; category check stays 0x10. Replace with checked contract/lease support. |
| Folder address 0x33C2A / load 0x33C32 | Stock scaled constant +0x228 and final +8 give +0x1148. New scaled constant +0x338 and final +8 give +0x19C8. |
| Count accessor 0x33C70, group compare 0x33C72 | Maximum 0x40→0x60; count load 0x33C8F still uses owner+4*i. Add state check. |
| Callback group check 0x336E4 | Upper exclusive bound 65→97; reject unsupported names before indexing. |
| Node allocation 0x33701 / call 0x3370A; count update 0x33880/0x33896 | Checked node allocation, full-width count limit and failure propagation before publishing/appending another node. |
| Index 0x33DB0, alias setup 0x33DC9 and 0x33DDE | `gpNumOfGroupFiles` at 0x2A9030 still points to counts; `gpGroupFileIndex` at 0x2A9028 must point to owner+0x19C8. Serialize callback ownership for the complete walk. |
| Index group check 0x33DF1; full end 0x33E9E | 0x40→0x60 and 0x41→0x61. Validate explicit sentinels before release at 0x33DEC. |
| Index walks 0x33E3B/0x33E84 into 0x339B0 | Propagate traversal/conversion/allocation failures. A zero walker return does not alone establish every optional cell's validity. |
| Post-index size calls 0x33E4A/0x33E99 | Checked size outcome; never convert failure into a valid zero. Count validity and size validity remain separate. |
| MakeNewUserFolders 0x2DFE0: name begin 0x2E017, end 0x2E01E | Keep start +0x148 (ID41); change end +0x208→+0x308 (ID97 exclusive). Check opendir/mkdir outcomes at 0x2E059/0x2E06B/0x2E0A3. Main call is 0x7E31. |

`operator new` at 0x7410 is throwing. A null test after 0x16186/0x3370A is not an allocation-failure implementation. Preserve mandatory-owner construction failure semantics, or implement an explicit exception-aware startup continuation. Node failures require a helper which catches allocation failure, reports FAILED, and releases partial nodes with matching operator delete at 0x7920. That helper needs correct QNX C++ exception ABI/unwind information. Existing caller catch behavior cannot be assumed to provide checked recovery. Count-owner allocation is mandatory even for IDs0–64; do not claim it can fall back to stock by merely changing a flag.

## Release, rebuild and borrowed-pointer lifetime

Preserve the explicit public sentinels `ALL_GROUPS=-1` and `ALL_CATEGORIES=-1`. ALL_GROUPS releases all 97×17 cells, ignoring category as the stock broad-all path does. A valid group with category -1 releases all 17 categories. Otherwise validate g0…96,c0…16. Invalid group97, other negative values and category17 must fail without mutation, not silently become release-all.

Stock 0x33CB1/0x33CB4 routes *any* unsigned group>64 into broad release; 0x33CBA/0x33CBD does likewise for categories. Replace these predicates with explicit sentinel handling. Head load/store sites 0x33CFB/0x33D30 become +0x19C8; node next remains +0x400; deletion remains 0x33D17. Broad loop end at 0x33D6C becomes 97. Destructor 0x33DA0/0x33DA7 still invokes all/all, after quiescence.

**Explicit correction:** stock advances the outer group at 0x33D4A without resetting the category cursor after 0x33D45. A correct replacement resets category to the selected category start for each group. This is a release-loop behavioral correction needed to actually release all owned nodes, not an immediate-only expansion disguised as unchanged behavior.

Before any scoped release/rebuild: validate arguments, acquire exclusive writer ownership, invalidate selected count states and corresponding HD size states, advance epoch, then free old nodes. Mark the count scope BUILDING. Append nodes only into this unavailable scope. On any failure, free every partial node in the scope, clear counts/heads and leave INVALID. On complete validated traversal, publish the scope's count states together. Unaffected cells retain their prior published results. Rebuild does not provide rollback of old nodes: it provides coherent unavailability on failure. No consumer may observe partially indexed counts as successful empty/populated cells.

Proposed ownership gate is nonrecursive and nonblocking: reader checks writer, atomically pins, rechecks writer and lifecycle, and backs out if unavailable; writer CASes gate and refuses mutation if pins remain. All accesses use correctly ordered atomics. A node-use lease lasts through the final dereference, not just the accessor. Writer callbacks use internal already-owned accessors. Updates release reader leases before invoking release/reindex, avoiding self-deadlock. Destructor marks CLOSING, rejects new readers, joins/drains users, then deletes; merely checking a counter once is not a proven destruction barrier. Exact containing-owner teardown/join integration remains a blocker.

### Direct readers and worker changes

Direct head accesses at 0x3518C, 0x351CC, 0x35410 and 0x3552D all change +0x1148→+0x19C8 and require count state plus a lifetime lease. Parser group end 0x35216 becomes 97. Update bounds at 0x3535C and all-group end at 0x35650 become max96/end97. Update release/reindex calls 0x35457, 0x354F3 and 0x35623 must consume outcome before further dereference/publication. Validate explicit update sentinels before stock out-of-range broad paths. Dictionary calls at 0x354D2/0x355EF must not continue after backend failure. Existing removals cannot be rolled back merely by returning false; transactional dictionary publication would require owned staging or an established dictionary transaction API. Treat that integration as unresolved rather than promising prior dictionary retention.

`CacheSampleGroups` at 0x356B0 passes entry rdi as node owner in worker argument+8 and entry rsi in argument+0x10 as dictionary, as demonstrated by parser loads at 0x35183 and 0x352B0. Do not infer an extra implicit `this` from the mangled class name. Proposed worker record is 32 bytes: +0 legacy worker ID/completion, +4 explicit result, +8 owner, +0x10 dictionary, +0x18 captured epoch. SUCCESS=1/FAILED=2 at +4; legacy done=-1 remains separate. Allocation arithmetic at 0x35706…0x3570E changes 24*n→32*n; record strides at 0x35784/0x357D4/0x357E2 change 0x18→0x20. Initialize outcome before pthread_create at 0x35788; failed creation must set FAILED and DONE rather than leave the coordinator waiting indefinitely. Worker normal completion 0x3521F and error 0x352E6 both publish outcome before DONE with release ordering. ThreadCtl's -1 must not masquerade as success. Coordinator waits at 0x357CB/0x357E0 must acquire-read completion and inspect result before declaring success or freeing arguments. Epoch mismatch is failure. Pin/release all node walks, and establish actual thread termination/join before freeing argument storage. Those changes need machine-level worker validation; the current semantic model does not execute threads.

Accessor caller inventory from stock references: 0x16386, 0x221EF, 0x222A7, 0x22E97 call folder accessor; 0x22C8D calls count accessor. Every folder caller must retain the lease through use and respect unavailable results. Count dispatch at 0x22C8D must branch on checked success before the existing successful count reply. These sites are integration requirements; their complete publication/cleanup rewrites are not certified by a displacement search.

## Exact process-owned size record

Reserve an aligned, zero-initialized 0x718-byte `B4SizeOwner`, separately from existing tables:

| Offset | Field |
|---|---|
| 0x000–0x610 | uint64 bytes[2][97] (HD=0, USB=1) |
| 0x610–0x6D2 | uint8 state[2][97], same validity states |
| 0x6D2–0x6D8 | padding |
| 0x6D8–0x6E8 | uint64 volume_epoch[2] |
| 0x6E8 / 0x6EC | uint32 writer_gate / reader_pins |
| 0x6F0 / 0x6F4 | uint32 root_ready_mask / closing |
| 0x6F8 | uint64 walk_bytes |
| 0x700 / 0x704 / 0x708 / 0x70C | uint32 walk_error / volume / group / active |
| 0x710–0x718 | uint64 captured_walk_epoch |

Process startup owns initialization; all cache states INVALID, root_ready=0. Mutation/reconnection invalidates affected volume/cells and advances epoch; stale completion cannot publish. Count scope release/rebuild invalidates HD sizes before freeing/indexing. HD supports valid cache hits unless force refresh; USB continues fresh enumeration for each request as stock, despite retaining a last-result record. State ownership does not authorize a new USB caching policy.

Serialize use of the traversal workspace. Checked internal callbacks access the active workspace without recursively taking its lock; externally overlapping requests fail BUSY. If count and size ownership are both required, use one consistent order (count then size), never call back into count acquisition while holding size ownership. Existing shared accumulator references must either be redirected into this owned workspace in checked replacements or be unreachable from all checked paths. Retaining an unguarded legacy walker beside the checked walker would remain a data race.

| Exact stock sites | Size changes |
|---|---|
| 0x7BC0–0x7BDE initial cache sentinel loop | Initialize the new record early, without extending its old endpoint into 0x2A4C28. Preserve unrelated startup work. |
| 0x15320 front end; cache load 0x15324…0x15332 | Validate volume/group first; use state+bytes, not all-ones as the sole validity marker. Force must bypass HD cache. |
| 0x151C0 backend; stores 0x15278/0x1527F | Commit only after complete checked enumeration/conversion and current epoch; failures invalidate state. |
| Workspace 0x1524D/0x1525A/0x1526D/0x152C9/0x152E7; callback adds 0x14E61/0x14E80 | Redirect to owned checked workspace; checked addition, nftw/stat/file parsing outcomes and traversal status. |
| Size dispatch call 0x22DCA | Checked result before either successful size half, using accepted 0x4037/0x4038 contract. |
| Copy/update 0x15A80; old invalidation 0x15BB1/0x15BC2 | Invalidate before the first filesystem mutation, not only at the late old store. Direct backend call 0x15BCA must consume checked status. |
| Delete 0x15D60; old cache store 0x15E22/0x15E2C | Invalidate before deletion; replace unconditional zero with verified complete-empty success only. |
| GroupInfo writers 0x152E2 and 0x15BE5 into 0x15050 | Never write successful GroupInfo on partial/backend failure; filesystem write errors propagate too. |

Checked size returns bytes separately from success. Validate uint64 accumulation and accepted decimal-MB conversion `(bytes/1000000)+(bytes%1000000!=0)` ≤UINT32_MAX before sending either wire half. Successful zero is allowed. Full-width counts 0…255 are checked before successful 0x4012 narrowing. Backend failure follows accepted error behavior, not a fabricated zero. Existing checked request/retry design is unchanged.

## Intentionally absent folders

Proposed explicit policy: HD user groups (IDs1–8 and41–96) may be valid empty on ENOENT only after `/hd` is positively established as the intended available filesystem root. Required HD factory/preset groups are not automatically valid empty on missing paths. Sparse USB group folders may be valid empty only after `/fs/usb0/px` is positively established as available. Missing/unmounted source root, EACCES, EIO, malformed GroupInfo/ZIP/conversion and failed traversal are failures. Do not infer mount availability from an empty walk or turn all stat errors into absence. A missing category beneath a validated optional user-group scope may be a valid empty cell under the same explicit policy; a required scope needs its own documented provisioning rule.

The new root_ready_mask is owned state, initially false, cleared on root loss/reconnection and set only by checked mount/root identity evidence. Its exact existing mount-event producer is not yet identified in accepted results; this is a blocker to implementing the policy, not a claim that ENOENT already proves optional emptiness. Checked mkdir of new user folders cannot certify absence after provisioning errors. Readers need not create folders to return a validated optional empty result.

Full indexing must positively account for each selected cell: successful enumeration, or checked allowed absence. Initialize INVALID/BUILDING, not valid zero by default. Unknown names outside the supported domain do not create groups; malformed entries within an admitted scope invalidate the scope. After full-walk success, explicitly validate absent optional roots/cells where the walker could have skipped them. Count and size outcomes remain independent: a valid count scope with failed size refresh does not authorize a successful size or overall population-ready result.

## Code/data placement requirements

Stock ELF program headers are recorded in `b4_qnx97_elf_layout.txt`. RX PT_LOAD is [0,0x9D480). RW PT_LOAD starts VA0x29E2B8, file offset0x9E2B8, filesz0x61D8, memsz0x13BF8, ending VA0x2B1EB0. `.bss` is [0x2A44A0,0x2B1EB0).

Concrete proposed data reservation: append `B4SizeOwner` at VA0x2B1EB0 through 0x2B25C8, increasing RW p_memsz to 0x14310 and `.bss` size to 0xE128, without moving or overwriting existing data. This is a newly created reservation, not an existing free cave. Verify loader mapping, linker/runtime heap-end symbols and end-of-image consumers before adoption; extend those definitions if they seed heap allocation. All new PC-relative references/relocations must target this reservation correctly.

Helper code needs a declared executable placement for checked ctor/index/release/accessors, failure-aware node allocator, checked size backend/callbacks and updated thread coordination. No stock padding has been established as an owned code cave. RX extension can begin at VA0x9D480 only with explicit segment/file-layout ownership and updates; the file gap to RW file offset0x9E2B8 is only 0xE38 bytes and is not a certified sufficient or unused helper area. If helpers exceed owned RX extension space, relayout the ELF or introduce a new mapped segment with correct offset/VA congruence, permissions and headers. Eight existing program headers end at file0x200, immediately where `.interp` begins: do not insert a ninth header over it. Address assignment/size of helpers remains unresolved until implementation is sized; no arbitrary PCs are asserted.

Preserve x86-64 SysV argument/return contracts, callee-saved registers and 16-byte call alignment. Entry detours require whole-instruction overwrite windows and displaced RIP-relative instruction relocation. Checked-output APIs use explicit bool/status plus out parameter, not an invented PIC-style v1 register. Exception-aware helpers require compatible LSDA/personality/eh_frame coverage and any necessary relocations. Existing callers expecting a pointer/count must be adapted explicitly, rather than silently changing return conventions.

## Focused tests and limits

`python3 b4_qnx97_model.py` passes 35 assertions; exact results are in `b4_qnx97_model_results.json`. Cases include groups64/65/96 at categories0/16, group97/category17 rejection, exact array boundaries, mandatory allocation failure, partial indexing cleanup/unavailability, preservation of unaffected cells, valid zero, count256 rejection, explicit release sentinels and category-cursor reset, reader-pinned rebuild refusal, closing-state refusal, optional user absence, required-factory/mount/permission failure, sparse USB emptiness, HD force bypass, fresh USB behavior, rebuild invalidation, backend failure and stale/reconnection epoch rejection.

These are semantic/layout model checks, not execution of QNX malloc/new, ELF helpers, filesystem walks, worker synchronization or exception unwinding. The model proves neither leak freedom of an actual implementation nor QNX memory capacity. Bytearray backing validates computed offsets; it does not establish executable patch bytes. Reused accepted checked-operation models cover backend conversion/reply behavior; they were not replaced by a new protocol.

## Remaining blockers / next implementation evidence

1. Exact available helper-code placement, ELF growth/end-symbol/loader handling and exception-unwind integration. No proven code cave or completed encodings are supplied here.
2. Concrete catch/cleanup implementation for node allocation and a deliberate mandatory-owner failure continuation, if continuing startup is desired. Additional object demand is 8,208 bytes plus nodes/worker records; simultaneous QNX heap capacity has not been measured.
3. Checked mount/root identity and reconnect event sites to own root_ready/volume epochs; confirm optional-category policy against actual provisioning expectations.
4. Complete folder-consumer leases, containing-owner destruction/thread joins and checked dictionary publication. Direct raw readers are enumerated, but current stock dictionary removals have no demonstrated rollback transaction.
5. Checked filesystem/ZIP/GroupInfo/walker implementation and error propagation, including full-scope validation on traversal success. Accepted findings identify ignored failures; they do not make stock backends checked automatically.
6. Execute eventual QNX helper/worker/allocator code in an isolated machine harness, including real partial-node failure and unwind cleanup. The current tests cannot certify binary thread safety.

Proceed with the expanded owned object and appended size owner only after these integration choices are resolved. This handover authorizes no firmware modification or build and introduces no negotiation machinery.
