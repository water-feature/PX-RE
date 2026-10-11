# B4: persistent extension-pointer and readiness storage

3 October 2026. Focused continuation of `readme_B4_heap_feasibility.md`. Scope: existing cache-owner storage, initialization/reload writers and aliases, followed by requirements for dedicated static control storage. No allocator audit expansion, PIC/QNX protocol design, firmware/database modification or build.

## Result

**No genuinely unused persistent pointer/readiness field was established in the recovered cache-owner structures.** Several plausible candidates are positively disqualified by writers, including the apparent padding at the ends of 64-byte name-cache records. This is a scoped result, not a claim that every byte of PIC RAM has been classified.

Do not repurpose these fields. A dedicated control record with explicit ownership and initialization is the preferred next design direction. It needs a memory reservation contract; no absolute address is approved by this report.

## Method and program

Connected Ghidra segment remains `ram: 9d000000 - 9d08195f`. Used decompilation/xrefs plus targeted raw instruction reads from the already extracted stock PIC payload. In particular, examined the cache initialization at 0x9D079220, name-buffer accessors 0x9D079264/280, loaders 0x9D041048/0x9D041E8C, request/retry functions 0x9D079340/534/640/744, size initialization 0x9D079A08 and relevant reply-writer instruction ranges near 0x9D051xxx.

Derived addressing and loop writes were checked rather than relying on field xrefs. Literal/base-reference searches only guided these reads. They are not proof against arbitrary computed aliases. Cached/uncached addresses refer to the same physical bytes: evidence of a writer to either alias is enough to reject reuse.

## Recovered ownership map

The group tables are standalone globals, not a recovered heap-owned cache object with a spare header. Nearby name/search structures are related consumers and scratch state, rather than a proven persistent group-extension owner.

| Region / field | Owner and decisive evidence | Reuse result |
|---|---|---|
| `[0x80037D30,0x80037D3C)` | Three-word search/result tuple. 0x9D079640 clears all three words on retry at 0x9D0796CC/D0/D4. Reply handlers also fill/reset them. | All 12 bytes owned and rewritten. |
| `[0x80037D3C,0x80037E3C)` | Four 64-byte selected-instrument/name records, indexed by `(part*2+slot)*0x40`. Serial loader 0x9D041048 populates their fields and trailing bytes. | No spare record tail. |
| `[0x80037E3C,0x80037E7C)` | Shared 64-byte name/display record. Direct loader 0x9D041E8C populates it, and 0x9D079340 clears/reformats its name fields during requests. | No spare record tail; transient state cannot own a persistent root. |
| `[0x80037E7C,0x80037E8D)` | 16-byte name-response buffer plus terminator. 0x9D079534 clears it initially and on retries; 0x9D0419BC consumes it. | Owned scratch buffer, not persistent storage. |
| `[0x80037E8D,0x80037E90)` | Three intervening bytes before count/index table. No unused-field contract established. | Insufficient for even an ordinary four-byte pointer; cannot provide pointer plus readiness. |
| `[0x80037E90,0x8003A118)` | 65×17 count/index rows. 0x9D040ED8 reloads counts/indices and writes defaults to remaining stock rows. | Existing group semantics must be preserved. |
| `[0x8003A118,0x8003A21C)` | 65 four-byte size entries. 0x9D079A08 resets group 0 to zero and writes groups1–64 from queries. | Not spare storage, including factory entry 0. |

The cold-start DINIT zero descriptor **0x9D01A3B4** contains base **0x80037D30**, length **0x24EC**, type word zero, covering `[0x80037D30,0x8003A21C)`. Zero initialization establishes startup values, not permission to reuse any field within the region.

## Apparent record padding is positively written

Accessor **0x9D079264** returns:

```text
0x80037D3C + 0x40*(2*part+slot)
```

Accessor **0x9D079280** returns the same record plus **0x16**, the second name field. These are aliases into one record, not separate objects with independently free space.

Recovered record layout:

```text
+0x00 … +0x15   first 22-byte field
+0x16 … +0x2B   second 22-byte field
+0x2C, +0x2D    metadata bytes
+0x2E … +0x3F   18 bytes copied from the serial name record
```

**Selected record loader 0x9D041048:**

- First/second fields are copied from serial offsets +0 and +0x16; metadata comes from +0x2C/+0x2D.
- **0x9D041278–284** computes the selected RAM record and adds +0x2E.
- **0x9D041288–290** computes the serial end at record+0x40.
- **0x9D041298** reads each serial byte; **0x9D0412A0** stores to the RAM tail.
- Branch **0x9D0412A4** loops until the serial cursor reaches +0x40; **delay 0x9D0412A8 increments the destination**. All 18 tail bytes are written, including any proposed aligned pointer/flag fields there.

**Shared record loader 0x9D041E8C:**

- **0x9D041F88** selects tail destination **0x80037E6A** (shared base+0x2E).
- **0x9D041F8C–94** sets the serial end at +0x40.
- **0x9D041FA4** writes each byte; branch **0x9D041FA8** and delay **0x9D041FAC** advance through `[0x80037E6A,0x80037E7C)`.

The logical meaning of every tail byte need not be known to reject reuse: loading normal records overwrites the entire candidate area. A locally absent direct xref to a particular word would have missed these computed byte writes.

## Initialization, reload and reply writers

**0x9D079220** calls count/index initialization at **0x9D079228**, then invalidates six name-buffer fields:

```text
0x9D079240 -> 0x80037E51
0x9D079244 -> 0x80037E67
0x9D079248 -> 0x80037D51
0x9D07924C -> 0x80037DA7
0x9D079250 -> 0x80037DD1
0x9D079254 -> 0x80037E27
```

These are name-field terminator/invalidation positions reached through base+offset arithmetic. They are not persistent readiness bits that can be reassigned.

**0x9D079534:** raw initial clear at **0x9D079590–5A0** writes four words at response-buffer offsets 0/4/8/12 and a byte at +16. Retry clear at **0x9D0795E8–600** repeats this; the final byte clear is the call delay at **0x9D079600**. A pointer hidden in this buffer would be lost on a normal request/retry. The caller 0x9D0419BC also sets its terminator and consumes the returned 16-byte name.

**Search tuple replies:** **0x9D0519C0/D0** store returned fields at 0x80037D30/+4; **0x9D051D4C** writes +8. Reset/sentinel paths **0x9D051CE0/E8/EC** fill all three words with 0xFF, and **0x9D051D68/70/74** clear them. These positive writers exclude using the tuple as a long-lived root even when it is temporarily zero.

**Size cache:** 0x9D079A08 resets **0x8003A118** to zero, then iterates through groups1–64 and writes their four-byte size slots. The factory zero value is part of initialization semantics, not evidence that its slot may become a pointer. Existing import/render consumers retain table ownership.

**GP-relative request state:** the recovered name/search/size routines use completion counters and transient result state, including halfwords around **0x80000444–44E** and size result **0x80000454**. For example, 0x9D079744 clears its completion halfword at GP-0x7BA2 and size-result word at GP-0x7B9C on initial request and retries, then returns that word when completion reaches 2. They cannot supply persistent readiness/pointer storage. No surrounding padding was cleared for reuse.

These are cache/request writers, not a re-audit of startup reentry or USB reset handling. No global warm-reset coverage is asserted: positively overwritten candidates already fail the persistence requirement, without needing to trace unrelated reset paths.

## Alias and ownership limits

The useful aliases recovered here include part/slot-indexed record pointers, pointers to the second name field, moving byte cursors for the serial tail, and the shared response buffer used by request and reply code. They demonstrate why direct-field xrefs are insufficient.

Corresponding uncached aliases, e.g. 0xA0037D3C and 0xA0037E3C, do not create separate storage. No candidate was approved based on absence of an uncached reference. The three-byte interval before the count table is too small regardless of alias coverage. State-machine/USB objects and runtime allocator fields were not searched for unrelated spare words; they are outside this cache-owner task.

## What dedicated static control storage would require

Reserve an explicit, four-byte-aligned **eight-byte control record**:

```text
+0   extension pointer (uint32)
+4   readiness/lifecycle state (uint32)
```

Eight bytes gives straightforward aligned access and avoids packing state into a live table field. This is control storage only; the 4,480-byte extension remains a heap allocation.

Required ownership work, before any firmware change:

1. **Choose storage by an explicit memory contract.** Existing static objects/tables cannot be enlarged into their neighbours. A gap above the heap requires the unproven stack clearance and is unsuitable for the current direction.
2. **One possible source is a deliberate eight-byte transfer from the existing bounded heap.** For example, the calculated tail interval `[0x80057AD8,0x80057AE0)` would leave 16,376 heap bytes. This is a reservation proposal, not a finding of unused bytes or an approved address. It would require every heap provider/bound configuration to exclude that interval before any allocation. Checking those contracts would be a separate authorized task; no allocator audit was broadened here.
3. **Cold initialization must explicitly set pointer=NULL and state=inactive before readers or allocation.** Either give the record a correct zero-initialization descriptor with verified DINIT layout/space, or initialize it explicitly at a proven early lifecycle point. Do not extend an unrelated descriptor into owned neighbours.
4. **Define reload/reset ownership.** Cache reloads must retain the pointer rather than erase it or allocate again. Any path that resets the allocator/RAM lifetime must also reset the root; paths that invalidate contents must clear readiness without losing ownership of the allocation. This requires a focused lifecycle contract for the new record, not repurposing stock reset flags.
5. **Account for physical aliases and publication.** Use one documented root address/alias, aligned word accesses, and a publication order in which readiness is never visible before valid pointer/data. No PIC/QNX protocol is designed here.
6. **Preserve merge ownership.** Dedicated storage and initialization changes must be checked against the other firmware branch's ownership; the existing handover's preliminary code-overlap checks do not certify a new control reservation.

No existing cache-owner field is cleared for use. The next concrete step is to authorize and verify a dedicated eight-byte static-control reservation contract, or provide additional owner-layout evidence that establishes a different unused field. Stop here; no firmware changes or build.
