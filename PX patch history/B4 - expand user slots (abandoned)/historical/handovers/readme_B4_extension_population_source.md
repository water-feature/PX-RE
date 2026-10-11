# B4 extension population source and pre-write validation

3 October 2026. Continues `readme_B4_split_addressing_design.md`; revised DINIT control baseline unchanged. Scope: existing count/size replies, count-page producer/parser, matching name-prefix indices and focused population tests. No helper placement, new negotiation protocol, journal design, firmware modification or build. No prior control/USB/startup audit was repeated.

## Decision

Use the **existing QNX0x4012 count reply**, collected once for every group/category in a stable97-group dataset, as the authoritative population source. Validate that snapshot before serial writes; populate stock and extension RAM through split addressing; make the name builder and count-page serializer consume that same snapshot rather than independently requery counts.

For raw QNX instrument count N:

```text
require integer 0 <= N <= 255
PIC count = N + 1
PIC index = -1 if N == 0, otherwise prefix
prefix += N + 1                 # also for an empty category
```

Walk groups0..96, categories0..16, in existing builder order. The prefix counts the instrument-zero placeholder in **every** category. Prefix calculation is global, never restarted at ID65. IDs0–64 retain their addresses/meanings; IDs65–96 use E. Total must not exceed65536 records.

This resolves the source and arithmetic. It does **not** establish that the unmodified QNX backend supports97 groups or can distinguish filesystem failure from a valid empty dataset. Required backend bounds/backing and explicit failure propagation remain implementation blockers, detailed below.

## Read-only evidence

Connected Ghidra segment: `ram:9D000000–9D08195F`. PIC stock SHA-256 remains `14e9c9b9dc562b0384fc43b3c5e0eb7fea84a5792d1a19b9b3ea8276ef7646f5`.

QNX stock ELF was read from its already documented container interval in memory and passed directly to `/usr/bin/objdump` through stdin; **no ELF/patched image was extracted to disk**. ELF SHA-256 checked as `7db8a8276f0bda34d22fdd2e8744b304dc7d62f80f9189836b107a4d7b178cff`. Addresses below are QNX virtual addresses, not container offsets.

Evidence artifacts: `b4_population_qnx_instructions.txt`, `b4_population_qnx_indexer_tail.txt`, `b4_population_qnx_size_file.txt`, `b4_population_pic_instructions.txt`. Ghidra disassembly supplied PIC request routines; raw words supplied exact reply fragments and producer sites.

## Count source: what the reply proves

| Site | Established behavior |
|---|---|
| PIC0x9D079978; packing0x9D079988–994 | Command0x4012, group in payload high byte/category low byte; IDs65–96 fit without encoding change |
| QNX0x22C6A–C86 | Decode category low byte/group next byte, store them in current request fields |
| QNX0x22C8D | Call `CSampleGroups::GetNumInstrumentsInFolder`,0x33C70 |
| QNX0x33C72/75 and0x33C77/7A | Stock unsigned group<=64/category<=16; invalid inputs return0, which looks like an empty folder |
| QNX0x33C8F | Read32-bit count at object+4*(17*g+c) |
| QNX0x22C92–C9C | Send count in reply0x4012 |
| QNX0x1D815/818/81B | Send helper combines opcode with **low16 bits of value** |
| PIC0x9D05177C–790 | Mask reply16 bits; store count at0x800001EC, ready1 at0x800001EE |
| PIC0x9D0799D8/DC | Return unsigned16-bit count once ready |

The reply is N real instruments, not the PIC count including instrument0. The name builder's inclusive0..N loop proves this distinction independently:0x9D042CC4 starts instrument0; increment/check0x9D042D70–7C continues through N. Instrument0 is locally formatted by0x9D079340 (zero branch0x9D079394, placeholder fields from0x9D07939C onward).

The wire result alone does not prove a populated97-group backend: stock rejects group65 as0. Existing QNX object expansion/indexer bounds must be in effect before querying new IDs. Index callback's stock name search stops at65 at0x336E4; count insertion occurs around0x33880/896. Preserve backing/scan changes already required by B4 rather than treating a returned0 as evidence that a new group was indexed.

**Validate full QNX count before wire narrowing**, at0x22C92 before ordinary sending. A32-bit count65536 is transmitted as0 and is indistinguishable on PIC from empty. PIC must also validate its received scalar0..255 before byte serialization;256 survives16-bit transport but stock byte serialization turns it into0. Negative/error/malformed counts must never become empty slots. A validation/failure return in backend code is needed; no existing terminal count-error encoding is proven here.

Only one count request may be outstanding, and the backend index must remain stable across count collection and name enumeration. Reply0x4012 carries no echoed group/category or request identity. Clearing ready at0x9D07999C and waiting is stock behavior, not proof against an old/unsolicited reply. This is an essential association/quiescence requirement; no new message protocol is specified.

## Existing page layout and loader compatibility

Count generator0x9D042A8C collects N through0x9D079978 at0x9D042B14 (group in delayB18). It writes a marker at scratch0x80010DAC, then byte counts at0x80010DAD. Category loop is17 at0x9D042B04; stock group loop65 at0x9D042B08. Store0x9D042B28 is in the category-loop delay. **Stock performs no scalar-range check before that sb.**

Existing count page is4KiB `[0x5FD000,0x5FE000)`:

- Legacy unmarked layout:41*17 raw count bytes, beginning at0x5FD000. Remaining stock rows default count1/index-1.
- Stock marked layout: byte0=0xFF, then65*17 raw count bytes. Logical used length1106.
- Proposed compatible97 layout: same0xFF marker and unchanged first65 groups, append32*17 raw bytes. Logical used length1650. No wider count field or relocated page.

For marked data, `(g,c)` byte address is `0x5FD001+17*g+c`. ID65/category0 is0x5FD452; ID96/category16 is0x5FD671. Last exclusive address0x5FD672 remains inside the existing page.

Stock loader0x9D040ED8 treats0xFF as the existing extended-stock marker. First-category branch0x9D040F3C takes0x9D04102C, consumes the following count, and delay0x9D041044 sets last group64. Ordinary bytes are incremented by1 at0x9D040F8C; count/index stores at0x9D040F90/FA8 use a running prefix incremented at0x9D040FAC. The marked first slot uses equivalent0x9D041034/1038 and0x9D040F50–68 logic. Empty slots get index-1, but still advance prefix by1.

**The marker does not discriminate65 from97.** Existing page tail is neither a trusted length nor evidence that extension names were generated. Preserve stock loading of41/65 groups. On cold restart, reset or unqualified reload, initialize extension defaults and keep it unavailable; do not silently change marker handling to read97 bytesets.

For this design, qualified extension population comes from a current live checked snapshot and a successful matching97-group name construction/verification. No new persistent header is introduced. Consequently expanded readiness is reconstructed by that live workflow after restart; it cannot be restored merely by seeing a marked page. If immediate reboot restoration without reconstruction is required, a separately defined persistent validity/extent mechanism is needed. That decision remains open; it is not guessed from trailing bytes.

Appending later groups preserves the names/index prefix for IDs0–64 for an unchanged stock subset. Reverting capacity must not rewrite stored group IDs or erase extra source folders. Already existing page contents may still be malformed/overflowing; compatibility means recognizing their layout, not treating every byte sequence as valid.

## Recommended population/build integration

Use the current tables themselves as the count/index snapshot while all cache-dependent users are gated. The stock rows and E together hold1649 entries; no additional full snapshot allocation or scratch-owner search is needed. Clear local readiness before replacing rows. Allocation ownership survives failure/reload.

1. Collect group0..96/category0..16 through checked existing count requests. Reject unknown/missing/malformed replies. Store N+1 and compute prefix through private split writers. Partial RAM writes are permitted only while gated/inactive.
2. Validate every response and final sum before serial erase/program. Require checked arithmetic, total<=65536, and the same immutable QNX index for later name fetches. A partially collected snapshot is not usable.
3. Emit name records using **snapshot N=count-1**. Fetch0..N under existing name request mechanism. Do not obtain a second independent count at each category. The snapshot's prefix must equal emitted record ordinal at every nonempty category.
4. After successful matching name construction/verification, serialize the same RAM snapshot into the existing count-page scratch: marker0xFF, rawN bytes in group/category order, deterministic remaining page fill. Since the name builder reuses0x80010DAC scratch, regenerate this page from RAM; do not expect the earlier scratch counts to survive name emission.
5. Commit count page only for the successfully constructed dataset. Both names and counts must be usable before publishing cache readiness; size population must separately succeed. Preserve current RAM snapshot after commit rather than running the old loader tail that resets extension defaults.

This is logical ordering and integration scope, not an atomic-write or crash-recovery claim. Serial I/O failure after destructive writing requires the previously identified recovery work; no journaling is designed here. Before-write count/overflow failure needs no serial rollback: restore stock RAM from unchanged valid stock metadata, reset extension defaults, and keep readiness inactive. If old metadata is itself invalid, keep consumers gated instead of claiming coherent fallback.

### Exact change anchors

| PIC site | Required change |
|---|---|
|0x9D042B08| Candidate count65/97 according to already admitted backend/backing; not merely E!=NULL |
|0x9D042B1C, before original category increment/store sequence| Validate full returned PIC count0..255 **before** sb at0x9D042B28; consume checked-request status |
|0x9D042B38, before erase call0x9D042B3C| Final preflight of all counts/prefix demand. No erase/program on failure. Split collection from persistent commit |
|0x9D042B3C/B40;0x9D042B50–5C| Existing count-page erase/program phase; delayB40 supplies page address. Move/invoke this commit only after successful name construction; preserve16 page-program calls |
|0x9D042CB4, with group load0x9D042CB0 and category delay0x9D042CB8| Replace live count query with private snapshot count-1. Public getter returns1 while gated and is unsuitable here |
|0x9D042CBC/CC0| Current negative-count skip stores result in delay. A missing/invalid candidate is build failure, not a category to skip; preserve delay semantics when changing it |
|0x9D042D9C| Candidate group limit65/97; category end remains17 at0x9D042D88 |
|0x9D042D64–6C;0x9D042DA8–C8;0x9D042DFC–E18| Defensive capacity stop and actual name erase/program paths. All must be preceded by successful global preflight; silent capacity stop becomes an error if reached unexpectedly |
|0x9D01B904 /B90C /B914| Existing import flow is count-page generation, name builder, count reload. Route through collect/preflight -> names -> count commit -> preserve qualified RAM snapshot; do not reload/reset E on success |
|0x9D02453C /4544 /454C| Same generation/build/reload order in second recovered rebuild flow; same change required |
|0x9D079228 ->0x9D040ED8| Startup stock parser remains compatible41/65. A separate current live qualification/reconstruction is required before extension readiness; earliest QNX-ready automatic trigger remains to be specified without repeating startup tracing |
|Private count/index writer from split design| Write validated N+1 and global prefix for65..96; skip final stock-loader reset tail when preserving a successful candidate. Do not infer indices from E-relative byte offsets |

No blanket NOP of final reload calls is authorized: skip/replacement applies only when the coordinator has already populated and verified all corresponding RAM rows. Failure paths need an explicit stock reload or continued gating.

## Size-query completion and failure detection

Size units are **rounded-up decimal megabytes**, not bytes: QNX0x22DCF–DF2 computes `(bytes+999999)/1000000` using unsigned arithmetic, then sends low16 via0x4037 at0x22DF8 and high16 via0x4038 at0x22E12. Validate byte arithmetic/conversion before narrowing if introducing a checked backend result.

PIC0x9D079744 uses result0x80000454, phase0x8000044E, shared resend flag0x800001F0 and timer0x800001F4. It clears phase/resend/result initially. Low handler0x9D051A10–30 inserts the low half and sets phase1. High handler0x9D051A3C–60 inserts the high half; phase1 branches to0x9D051CD8, which also writes0xFF into the search tuple and sets phase2 at0x9D051CF4. This tuple write is stock completion behavior, **not a size-error sentinel**. Unexpected high half instead sets resend flag through0x9D051A6C. The0x403C dispatch path also reaches this shared resend flag when its alternate search path does not apply.

Success gate is phase==2 at0x9D0797A4. Return at0x9D0797EC/F0 clears phase and loads size; caller cannot inspect a retained completion flag afterward. Missing/partial replies and resend conditions loop; timeouts0x9D07980C–824 restart rather than return failure. Count timeout0x9D0799F4–A04 likewise retries forever. No finite retry maximum is present in these recovered routines.

Required checked-request change sites, without new message IDs:

- Count initial/retry setup0x9D07999C–9AC and0x9D0799F4–A04, successful scalar return0x9D0799D8–DC: finite attempt/deadline policy, status return, scalar range validation.
- Size setup0x9D079778–794, resend reset0x9D0797C8–D4, timeout reset0x9D07980C–824, success0x9D0797EC/F0: finite policy counting **both** resend and timeout attempts, return an explicit validity status separate from size0. Numeric budget remains a policy decision; do not infer wall-time units from immediate200/2000.
- Size initializer0x9D079A38/A40 and import query0x9D01B8D4/B8DC: consume status before storing or continuing, using existing split writer contracts. Existing callers ignore failure because original routine has no terminal failure result.

**Backend failure remains undetectable from successful scalar replies alone.** QNX0x15320 returns cached values without a success tag; its part-function0x151C0 initializes accumulated size0 at0x1524D. Group-info file failure falls back to filesystem walking. The return from `nftw` at0x152A4 and0x152C4 is ignored, permitting0 or a partial positive size after an unsuccessful traversal. Callback0x14E20 ignores nonzero traversal-type values, and group-info conversion at0x1502D uses `atol` without an established checked numeric result. The direct file path also does not consume stat's return at0x14F11 before using its output.

Therefore do not treat size0 as error, or as proof of a verified empty folder. A complete low/high pair proves delivery of a scalar, not successful enumeration. QNX must propagate a validated size-operation outcome at these backend sites and consume it at0x22DCA/DCF before sending ordinary successful halves. Existing error/resend reporting may be usable, but a concrete terminal-error policy and backend error classification have not been proven. This is failure semantics for current requests, not a new capacity negotiation protocol. Until resolved, full LOCAL_VALID cannot be justified by size-store completion.

## Tests

Run `python3 b4_extension_population_model.py`; results in `b4_extension_population_results.json`. Imports the existing split/integration interpreter. New optional transport hooks and a default-enabled size-query stub switch allow execution of the **real stock request and reply fragments**, without changing prior default tests.

| Dataset / test | Result |
|---|---|
|97 groups empty|1649 placeholder records,1650 count bytes; all entries count1/index-1 |
|Populated fixture at factory,ID64,65,96; includes N255|1915 records; ID65/category0 prefix1109, ID96/category0 prefix1895; actual stock parser and private extension writes match global enumeration |
|Exact name capacity|65536 records admitted; last actual record address<=0xFFFFC0 |
|One record over / saturated97 groups|Rejected before serial operations |
|Negative,256,65535,65536,missing/noninteger counts; missing group/category|Rejected by full-source/dataset validation, no simulated serial writes |
|Real count generator with proposed checks atB1C/B38|Malformed256 and both overflow fixtures reach **zero erase/program calls**; valid fixtures generate expected marker/count prefix and16 program calls after one erase |
|Metadata compatibility|Actual stock parser matches legacy41 defaults/indices; marked65 prefix of97 candidate is byte-compatible; unqualified97 suffix rejected |
|Real count request/reply|0,4,255,256,65535 returned unchanged16 bits;65536 aliases0 through modeled stock wire narrowing, demonstrating necessity of QNX pre-narrowing validation |
|Real size request/reply|0,1,65536,0x12345678 reconstructed exactly; two-half completion required |
|Missing count or size; low-only, high-only, duplicated-low size|No terminal return before test instruction limit; repeated sends observed |
|Size zero ambiguity|Successful-empty and backend-failure scalar0 have identical ordinary wire encoding; no PIC-only discriminator |

The generator checks atB1C/B38 are **test-only semantic hooks** at proposed integration seams; they are not encoded/placed firmware helpers. Real count-generator instructions execute with the candidate loop bound overlaid in memory. UI/transport/serial boundaries are stubbed. Prefix/name matching is independently tested against inclusive instrument enumeration; full name-request hardware, QNX filesystem/indexer execution, erase/program hardware and crash recovery are not emulated. Test timer progress is synthetic; resend counts are observations of this model, not hardware retry timing. Snapshot stability and delayed-reply association are conditional assumptions, not measured guarantees.

## Remaining decisions before helper placement

1. Implement QNX97-group backing/indexing and full-width count validation; stock0 replies for invalid/new groups cannot certify empty folders.
2. Checked count/size request terminal-status and bounded retry/deadline policy, plus QNX backend size success/error propagation. Size validity is not resolved by the current wire scalar.
3. Stable dataset ownership across counts and names and serialized reply association using existing application lifecycle. No new negotiation protocol is specified.
4. Automatic cold/reconnect reconstruction trigger versus explicit reindex before expansion. The proposed unchanged metadata format deliberately carries no97-group validity marker.
5. Explicit successful-build status, count/name commit ordering and post-build snapshot retention at both existing rebuild call chains. Post-write I/O failure/recovery remains outside this pre-write population model.

Stop here. Population source and prefix arithmetic are concrete and tested; the unresolved backend validity/status decisions must not be disguised as validated expansion or solved by helper placement.
