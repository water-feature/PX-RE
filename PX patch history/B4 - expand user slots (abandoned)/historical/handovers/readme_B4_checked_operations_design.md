# B4 checked count and size operations

The historical file references listed here are not included in this public bundle: `b4_checked_operations_instructions.txt`, `b4_checked_operations_model.py`, `b4_checked_operations_results.json`, `b4_checked_size_callers.txt`.

3 October 2026. Baseline: [extension population source](readme_B4_extension_population_source.md), accepted split addressing, and revised DINIT control design. This is a design and isolated harness test, not a firmware patch or build. No capacity negotiation, helper placement, ownership/allocator audit or startup/USB tracing was performed.

## Recommended contracts

Replace the existing PIC count and size request bodies with checked equivalents. Preserve the successful wire formats and use the existing `0x403C` error opcode when QNX cannot produce a validated result. No new capacity message or success sentinel is introduced.

| Operation | Input | Successful PIC return | Failed PIC return |
|---|---|---|---|
| Count, entry `0x9D079978` | `a0=group`, `a1=category`; physical limits 0–96 and 0–16, further restricted by admitted backend capacity | `v0=N`, `v1=1`, N 0–255 | `v0=0`, `v1=0` |
| Size, entry `0x9D079744` | `a0=volume` 0/1, `a1=group` 0–96, further restricted by admitted backend capacity | `v0=rounded-up decimal MB`, `v1=1` | `v0=0`, `v1=0` |
| Size initializer, entry `0x9D079A08` | Existing gated cache population | `v0=1`, `v1=1` only after all required queries and stores succeed | `v0=0`, `v1=0`; cache remains gated/inactive |

Numeric zero is a valid successful result. Every caller must test `v1` **before** overwriting it or interpreting `v0`. Invalid input fails before packing/sending. Allowing a physical ID here does not certify QNX backing or activate the extension.

Both request designs retain their original 32-byte frame and saved-register slots. Count saves/restores `ra,s1,s0`; size saves/restores `ra,s2,s1,s0`. GP and callee-saved registers retain their contracts. `v1` becomes an explicit output. The retry counter occupies existing saved registers, not additional RAM or stack: count `s1`, size `s2`. All generated branches/calls have explicit delay slots; request call slots are `nop`, return slots restore SP by 32. The detailed tested encodings are in instruction artifact (`b4_checked_operations_instructions.txt`). Its `0x9F...` PCs are **synthetic test labels**, not approved firmware addresses.

## Retry policy

Choose **three sends total: initial send plus at most two retries**, independently for each checked operation. Both timeout and resend/error events consume the same budget. This provides two opportunities to recover an incomplete delivery while preventing indefinitely repeated sends. It is a policy choice, not a measured optimum or reliability guarantee.

Retain the original timer reload immediates: count **200**, size **2000**, at `0x800001F4`. No milliseconds, timer frequency or total elapsed duration is asserted. Missing replies terminate only if the existing timer continues to progress and the send call returns; three sends is a retry bound, not a proven wall-clock bound with stalled interrupts or a blocked transport.

For each attempt:

1. Reject exhausted budget; otherwise decrement once, immediately before preparing/sending.
2. Clear completion, numeric result and shared error/resend flag. Reload the original timer constant. Size phase starts at 0.
3. Send the original packed command. Poll error/resend first, completion second, timer expiration third. An error must win over an already marked successful result.
4. On error or timeout, restart through the budget check. Size discards both halves and requires a new low-then-high pair; a low half alone is never success. Out-of-order high halves use the existing resend behavior.
5. On count completion, reject N>255 immediately; do not serialize it or retry a known malformed scalar. On size completion, phase must equal 2. Return `v1=1` with the scalar.
6. On terminal failure return `(v0,v1)=(0,0)`. On either exit clear completion, resend and timer state. These shared fields require exclusive request ownership.

Successful numeric values remain available in their result fields until the next attempt clears them; callers use the returned scalar/status. Readiness is separate from all these request fields.

## QNX checked backend design

Use new checked interfaces with a Boolean outcome and an output scalar, rather than encoding backend error as zero:

```c
bool GetNumInstrumentsChecked(owner, group, category, uint32_t *out);
bool GetFolderContentsSizeChecked(volume, group, forceRefresh, uint64_t *outBytes);
bool BytesToWireMBChecked(uint64_t bytes, uint32_t *outMB);
```

Initialize outputs to zero, but expose them only on success. These are proposed interfaces, not recovered symbols or assigned helper addresses. Use the original backend's filters, ordering, volumes and cache semantics; add status propagation rather than replacing its definition of an instrument or folder size.

### Count/index validity and enumeration failures

The cached count read at QNX `0x33C8F` does not establish enumeration success. Bounds at `0x33C72/75` and `0x33C77/7A` currently return zero for unsupported input. The checked read must instead require supported backing, valid group/category, and a **completed valid index generation for that cell**. An empty successfully indexed cell may return zero. An unindexed, partially indexed or failed cell may not.

Targeted new evidence establishes that this count index uses **custom `DSI_FTW`, not the size routine's nftw**:

| Exact QNX site | Existing behavior and required change |
|---|---|
| `0x33DEC` | Releases the old index before rebuilding. Invalidate affected checked-index validity before this call; do not retain a validity tag over released or partially rebuilt data. |
| `0x33E3B`, `0x33E84` | Calls custom walker `0x339B0` for scoped/full indexing. Checked walker must return status; publish affected cell/generation validity only after complete success. |
| `0x339E0/E5/E8` | `opendir` failure branches directly toward return without a checked outcome. Propagate failure. Missing/unreadable requested folders do not automatically certify an empty group. |
| `0x33A08`, `0x33A20`, `0x33B22` | Directory-control operations; preserve/restore directory mode, but check platform-defined error returns and propagate failures. Exact QNX success/error conventions require its headers/documentation; no numeric convention is guessed here. |
| `0x33A28`, `0x33B03` | `readdir` null currently ends traversal. Checked walker clears/tests the platform error state around each read to distinguish end-of-directory from error. |
| `0x33BD9`, `0x33BEB` | Callback result is ignored. Checked callback must propagate path/record/conversion/allocation errors; walker must stop and unwind on failure. |
| `0x33BFD` | Recursive walk result ignored. Propagate it and invalidate the affected scope, rather than publishing a positive partial count. |
| `0x33B2A` | Close directory on both success and failure; conservatively propagate close failure. |
| `0x33880`, `0x33896` | Count increment/store. Validate full-width increment and the 255-per-cell limit before insertion is accepted; overflow invalidates the candidate index. Clean up candidate nodes on failure. |
| `0x33E4A`, `0x33E99` | Post-index size refreshes currently return scalars. Route through checked size refresh; a failed refresh cannot publish a valid size-cache entry. Count validity and size validity remain distinct. |
| `0x22C8D–0x22C9C` | Replace ordinary count read with checked read; verify full-width `0 <= N <= 255` **before** SendMessageToPIC narrows to 16 bits. Send `0x4012,N` only on success; otherwise send one `0x403C,0`. |

The walker deliberately uses an `open` probe at `0x33BBE`, with failure leading to recursion; that failure alone cannot simply become an enumeration error without preserving the existing directory classification. The checked variant must distinguish directory classification from actual access/I/O failure. Existing `.tmp` cleanup and file-selection behavior must also be retained. Such platform/filesystem details are implementation evidence still required, not exercised by the Python enumeration model.

Validity must be **explicitly owned by the QNX index/cache implementation**, initialized invalid on construction, invalidated on release/rebuild/mutation/reconnection as appropriate, and published after successful completion. Do not place it in an alleged unused object field. Add declared validity metadata to the intended expanded QNX owner/source, or reserve separately owned storage with documented lifetime if implementing a binary patch. That QNX storage layout is not established here. A scoped rebuild may retain validity only for untouched cells; a full failed rebuild cannot certify zero-filled cells. A failed rebuild must not leave the active table tagged as a valid old snapshot after `ReleaseSampleGroupFilesIndex` has destroyed it.

### Size enumeration, parsing and conversion

| Exact QNX site | Required checked behavior |
|---|---|
| `0x15320` cache front end; `0x151C0` computation body | Return a cached value only with valid provenance for the current dataset/volume. Failed or partial calculations leave cache invalid, including zero. Preserve force-refresh semantics. |
| `0x15264` -> `0x14E90` | GroupInfo read becomes a three-outcome operation: valid scalar, metadata absent (may enumerate), or failure. Only genuine absence may choose the existing walk fallback; permission/read/parse errors cannot become zero or silent successful fallback. |
| `0x14F11` | Existing stat result ignored, and pathname is the folder while descriptor is GroupInfo. Obtain/check metadata for the actual opened file, preferably fstat; validate length and allocation arithmetic before reading. Do not use an unchecked stat buffer. |
| `0x14F2E`, `0x14F38` | Handle interrupted/short reads until complete or fail; bound every line copy, terminate buffers safely, check required metadata field and close outcome. No positive partial file parse becomes success. |
| `0x1502D–0x1503C` | Replace unchecked atol/success publication with checked unsigned decimal conversion. Accept digits and surrounding ordinary whitespace; reject signs, empty fields, trailing junk and uint64 overflow. Reject duplicate authoritative size fields to avoid ambiguous metadata. |
| `0x152A4`, `0x152C4` | Consume nftw return and callback error state. Nonzero traversal outcome or callback failure invalidates the entire result, not just the failed subtree. |
| `0x14E20/22` | Preserve ordinary ignored traversal types, but explicitly fail for QNX traversal error types such as FTW_DNR/FTW_NS. Obtain constants from the QNX headers; do not infer their values from nonzero alone. |
| `0x14E5C/61`, `0x14E7B/80` | Reject negative file lengths and uint64 accumulation overflow; checked ZIP result required before addition. |
| ZIP helper `0x14D00`: `0x14D61`, `0x14D71`, `0x14D8A`, `0x14DAD`, `0x14DD9–E1` | Existing system/open/stat/read/sscanf path can yield zero on failure; checks are missing. Checked helper must verify command completion, fresh output, actual file metadata, full read and all expected numeric conversions with range checks. Existing test only for sscanf result -1 is insufficient. Close/free/temporary-file cleanup on every exit. Preserve valid ZIP total zero. |
| `0x22DCA–0x22E12` | Consume checked backend status and validate final wire-MB conversion **before either** successful half is sent. On failure send one `0x403C,0`, and no `0x4037/0x4038` scalar halves. |

Avoid the overflowing `bytes+999999` expression:

```text
q = bytes / 1000000
if bytes % 1000000 != 0: q += 1
require q <= UINT32_MAX
wireMB = uint32(q)
```

For uint64 input, this quotient increment cannot overflow uint64. `UINT32_MAX*1000000` bytes is admissible; one byte more is rejected. Validate once, then send low and high 16-bit halves of that same computed scalar. A transport failure after one sent half remains possible; the bounded PIC partial-reply policy handles failure to complete. Sending successful halves is not a proof of hardware delivery.

### Existing error dispatch requires a change

PIC `0x9D0514F0–0x9D05150C` handles `0x403C`. If search-ready `0x80000446` equals 1, branch `0x9D0514FC` takes `0x9D051D38` and skips the shared resend store at `0x9D051504`. Merely consuming `0x800001F0` in the new requests would therefore miss some errors.

Replace the first two instructions at `0x9D0514F0/F4` with a jump/nop to a helper that **unconditionally sets the shared resend/error flag**, then replays those two instructions and rejoins `0x9D0514F8`:

```asm
addiu v1,zero,1
sh    v1,-0x7E00(gp)       # 0x800001F0
lhu   v1,-0x7BAA(gp)       # replay original search-ready load
addiu v0,zero,1            # replay original
j     0x9D0514F8
nop
```

Original search-specific handling remains in place, including its branch and delay slot. Only v0/v1, already clobbered by this path, are used; no frame or control-record storage is introduced. The harness tests this helper with stale search-ready=1 and verifies the flag before rejoining. It does **not** execute the full alternate search handler or prove compatibility for concurrent legacy operations. Shared flag semantics require serialized requests and review of any intended legacy use of the newly unconditional flag before integration.

## Population and import status consumption

The accepted snapshot, prefix arithmetic, count page layout, name preflight and stock/extension split addresses remain unchanged. Add the following checks to those designs:

| PIC seam | Required status consumption and failure behavior |
|---|---|
| Count generator return `0x9D042B1C`, query `0x9D042B14` | Check `v1` before any store/category increment; then validate N<=255 before byte store `0x9D042B28` (a delay-slot store). On failure abort collection, perform zero erase/program calls, leave readiness unpublished. No failed slot becomes count1. |
| Count preflight `0x9D042B38` | Admit commit only after **all** required count statuses succeeded and validated total<=65536. Checked addition/prefix logic remains as accepted. |
| Name builder query `0x9D042CB4`, return `0x9D042CBC/CC0` | Use the accepted private snapshot instead of a second live count request. Return scalar/status from snapshot access and check status before the existing signed branch/delay-slot store. Failed snapshot access aborts, rather than silently skipping a category. |
| Size initializer call `0x9D079A38`, first result use `0x9D079A40` | Check `v1` before converting v0 into writer input. Return failure immediately if query or private split writer fails; return success only after the entire selected group range. Group0 retains its accepted local stock-size initialization. |
| Import query `0x9D01B8D4`, return `0x9D01B8DC` | The split import helper must **first** branch on query v1, before the address resolver uses v1 as scratch. Failure goes to the previously identified import-abort continuation `0x9D01B6B0`, with no size store or success command. Success resolves destination, stores even a valid zero and continues at `0x9D01B8F8` with original command setup. |
| Rebuild chains `0x9D01B904/B90C/B914` and `0x9D02453C/4544/454C` | Consume collector, name-builder and size-population status at each stage. Any failure prevents subsequent commit/readiness publication. Successful qualified snapshot retention remains as accepted. |

On reload/population failure keep E allocated, LOCAL_VALID/EXPANDED_ACTIVE clear and consumers gated while restoring a verified stock dataset. Release gating only after stock reconstruction succeeds. If restoration is unverified or any failure occurred after destructive serial writes, remain gated and report failure; this design does not claim rollback or invent journaling. It also does not activate QNX/PIC capacity merely from a valid scalar reply.

### Additional actual size callers cannot be left unchanged

A targeted scan for direct jal to the two request entries found exactly two count sites above and **six size sites**, including four beyond the prior two anchors. Raw successor instructions are captured in size caller evidence (`b4_checked_size_callers.txt`). This establishes direct-call coverage; indirect calls are not exhaustively proven absent.

| Size call -> status-check seam | Successful continuation; failure requirement |
|---|---|
| `0x9D023F34` -> `0x9D023F3C` | Only after status success replay `sltu v1,zero,v0` and subsequent presence-byte/sum logic. Failure must abort the candidate scan, preserving its prior published result; it cannot set “absent” or add zero to the total. |
| `0x9D024258` -> `0x9D024260` | Check status before v1 is overwritten by `lw v1,0xE8(fp)` and its branch-likely range logic. Only success may accumulate at `0x9D024284/288` and `0x9D024290`. Failure invalidates the candidate total and cancels the dependent operation. |
| `0x9D0246E8` -> `0x9D0246F0` | Check status before numeric-zero branch. Success resumes the existing `bne v0,zero,0x9D0248BC` with nop slot; valid zero may clear the candidate halfword at `0x9D0246F8`. Failure cannot classify a group as empty or continue to subsequent action. |
| `0x9D026600` -> `0x9D026608` | Check status before original jump `0x9D0242B4` and its **delay-slot store** `sw v0,0xF8(s0)`. Only success may execute that store. Failure must preserve the published total and abort the operation. |

For each of these seams, use `beq v1,zero,<operation_failure>; nop` before replaying any original instruction, and preserve original branch-likely/delay-slot behavior on success. **Safe complete failure/unwind continuations for these four larger operations are not established by the accepted evidence.** Do not substitute an arbitrary common PC or jump into an epilogue with unmatched frame/register state. They are explicit remaining integration blockers. Candidate scratch updates earlier in a scan must not be published after a failure. The current harness exercises the initializer and import continuation, not full execution of these four operations.

## Focused tests and evidence

Run:

```sh
python3 b4_checked_operations_model.py
```

Artifacts: model/harness (`b4_checked_operations_model.py`), results (`b4_checked_operations_results.json`), MIPS encodings (`b4_checked_operations_instructions.txt`). Uses the existing integer-MIPS interpreter and accepted split writers. Request implementations execute newly encoded test instructions; successful low/high/count receive fragments execute **stock PIC instructions**. Frames/register contracts are checked by the existing interpreter. Transport delivery is scripted and timer progress is synthetic per instruction, with no inferred hardware timing.

| Test | Result |
|---|---|
| Count/size valid zero and positive result | Success=true, scalar preserved, one send |
| Backend error and explicit repeated resend, either request | Success=false, scalar0, exactly three sends |
| Missing count or both size halves | Terminal failure after exactly three sends |
| Low-only, high-only, repeated-low size replies | Terminal failure after exactly three sends; no partial result exposed |
| Timeout then error then completion | Success on third send for count and size |
| Partial old size then complete new size | Success on second send; returned `0x12345678`, not previous low half `0xBEEF` |
| Full32 size | Reconstructed `0x12345678` |
| Count reply256 | Immediate failure, one send |
| Invalid group/category/volume input | No sends; explicit failure |
| Stale alternate search-ready=1 during error | Proposed error prefix sets request error flag; no false success |
| QNX count0/255; negative/256/65535/65536/malformed; failed index | Only valid0/255 produce successful count replies; failures produce error, never wire-narrowed successful zero |
| QNX enumeration with zero/positive/partial failure | Complete empty succeeds; partial positive then failure discarded |
| QNX uint64 accumulation overflow, bad decimal conversion and MB overflow | Failure before any successful reply half; valid zero and exact maximum wire-MB pass |
| Actual encoded checked size initializer | Failure leaves failed slot untouched and returns failure; successful zero is stored. Control record unchanged and still gated |
| Actual encoded split import helper | Failure reaches `0x9D01B6B0` with slot untouched; successful zero stored and original success continuation reached |
| Real count generator with proposed semantic status check at B1C | Failure at ID65/category0: **zero serial operations**; successful zero fixture: original erase plus16 page programs |

QNX checks and enumeration are **semantic models**, not execution of rebuilt QNX routines or a real filesystem. QNX raw evidence adds only the immediately relevant index walker/owner and ZIP conversion paths: `b4_checked_qnx_index_build.txt`, `b4_checked_qnx_index_owner.txt`, `b4_checked_qnx_zip.txt`. Earlier size/dispatch evidence was reused. Count-generator status admission is a semantic hook at the accepted seam, not a placed firmware helper. Name construction and larger scan unwind paths are not newly emulated. Control words remain intact in the checked-request and tested caller cases; no control design change is required.

## Remaining blockers and limits

1. Supply/implement declared QNX checked-index and size-cache validity ownership, expanded backing, and the platform-correct checked walker/file/ZIP operations. Cached scalars alone remain insufficient evidence of backend success. Determine how intentionally absent optional group folders are represented: this conservative design treats requested missing folders as failure unless the backend explicitly certifies an intentionally empty cell.
2. Resolve the four additional size callers' operation-specific failure/unwind and scratch-publication paths. The two original caller changes alone are insufficient.
3. Preserve the accepted stable dataset and exclusive-request requirements. Existing replies have **no transaction identity**: late count replies or mixed size halves across attempts/operations cannot be excluded merely by clearing fields. The bounded retry design does not solve reply association. Establish transport ordering/quiescence using the existing lifecycle before trusting completion or starting a different operation after exhaustion. No new negotiation or transaction protocol is designed here.
4. Request field clearing currently follows original-style stores. IRQ interleaving and full `0x403C` alternate-search effects have not been executed; the test receives fragments at scripted transport boundaries. Integration must justify initialization/send boundaries under existing serialized ownership without reopening unrelated interrupt audits.
5. Assign real nonoverlapping helper code and reviewed relocations later; synthetic encodings do not establish placement. Confirm actual intended PIC/QNX/voice_sysex source or binary merge compatibility when supplied. No historical merge check was repeated.
6. Successful status is a prerequisite for readiness, not proof of atomic metadata commits, name-request reliability or post-write recovery. Those accepted limits remain.

Stop here. The checked API, three-send policy, zero handling and tested population/import guards are concrete. Remaining QNX implementation details, additional caller unwinds and reply association must stay visible before this design is treated as firmware-ready.
