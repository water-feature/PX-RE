# B4 storage alternatives: 32 additional group rows

Prepared 3 October 2026. Assessment based on the existing B4 handovers; no new Ghidra audit, firmware modification, RAM reservation, patch or build was performed.

## Recommendation and status

Pursue **split tables for internal IDs 65–96, backed by one permanent 4,480-byte allocation from the existing bounded heap**. Keep both stock tables at their current addresses. Activate expanded capacity only after successful allocation and initialization, with a coherent stock-capacity fallback on failure.

This is a recommended design direction, **not clearance to implement or build**. Heap capacity, allocator concurrency, allocation lifetime and persistent pointer ownership remain unproven. Step 1's unresolved findings remain unchanged; this assessment does not repeat or resolve the startup/USB audit and does not assume spare stack space.

If expanded capacity must always be available, consider a fixed reservation inside the existing heap instead. That gives deterministic extension ownership but requires evidence that the reduced stock heap is sufficient.

## Existing storage and extension layout

Source: [readme_B4.md](readme_B4.md), sections 5–6.

| Storage | Existing extent | Ownership / constraint |
|---|---|---|
| PIC count/index cache | `[0x80037E90, 0x8003A118)` | 65 × 17 × 8 = 8,840 bytes |
| PIC size cache | `[0x8003A118, 0x8003A21C)` | 65 × 4 = 260 bytes; immediately follows count/index cache |
| Default heap | `[0x80053AE0, 0x80057AE0)` | 16,384 bytes; bounded sbrk at 0x9D080B98 |

Adjacent startup objects and copied data are owned. Extending the count/index cache in place would overwrite the size cache; growing the combined storage would reach other owned data. Cached/uncached aliases must be considered when establishing physical ownership.

Let E be the extension base, aligned suitably for four-byte fields:

```text
[E + 0x0000, E + 0x1100)   32 × 17 count/index entries, 8 bytes each
[E + 0x1100, E + 0x1180)   32 size entries, 4 bytes each
```

The payload is **4,352 + 128 = 4,480 bytes (0x1180)**. Allocator metadata, alignment padding and any separately stored pointer are additional costs.

## Alternatives

### 1. One permanent heap allocation — preferred direction

**Ownership:** the allocator owns the block; the group-cache subsystem retains it for its lifetime. Stock tables remain untouched. Do not allocate or free it per query or per selected group.

**Addressing changes:** route IDs 0–64 to stock bases and IDs 65–96 to E. Store E in separately proven persistent storage. Publish expanded availability only after the whole extension has been initialized. Reinitialization must reuse the retained allocation or follow a proven release/reallocation lifecycle; it must not leak blocks or expose partially initialized rows.

**Remaining evidence:**

- Allocator alignment, metadata overhead, failure return and free semantics.
- Competing allocations, their sizes and lifetimes, including indirect users and alternate heap configurations.
- Whether allocation/free can occur in interrupt contexts and how concurrent use is protected. The existing MIDI-reachable sort finding makes this a specific investigation target; comparator resolution alone does not establish allocator safety.
- A startup/lifecycle point at which allocation and publication are safe.
- Ownership and initialization of the persistent extension pointer.
- Whether retaining the block causes later stock allocations to fail; successful initial allocation alone is insufficient evidence.
- Coherent allocation-failure behavior across group selection, import, index rebuilding and communication with QNX. A PIC-only fallback must not leave the two processors disagreeing about active capacity.

**Tradeoff:** preserves allocator boundaries and allows an explicit failure path, but expansion availability depends on allocatable capacity and fragmentation. The remaining 11,904 bytes before overhead are arithmetic, not proven spare capacity.

### 2. Fixed reservation inside the existing heap — deterministic alternative

**Ownership:** explicitly transfer 0x1180 bytes from allocator ownership to group-cache ownership. A hypothetical reservation is `[0x80056960, 0x80057AE0)`, leaving `[0x80053AE0, 0x80056960)` for an 11,904-byte stock heap. **This is a calculated candidate, not an approved placement.**

**Addressing changes:** use the same split addressing with a fixed E rather than a persistent pointer. Reduce every applicable allocator upper bound before the first allocation. Initialize the reserved block separately; do not assume the existing DINIT descriptors cover it.

**Remaining evidence:**

- Every heap configuration, boundary initializer and later boundary writer, including the break/upper/lower words around 0x80053A64/68/6C.
- The earliest allocation and confirmation that reservation takes effect before it.
- Alternate or indirect allocators and direct users of the reservation, including uncached aliases.
- Evidence that relevant stock workloads tolerate an 11,904-byte heap and its allocation-failure behavior.
- The extension initialization and publication lifecycle.

**Tradeoff:** removes extension-allocation uncertainty and pointer-storage requirements, but reduces stock heap capacity unconditionally. It does not require placing new storage above the existing heap or claiming additional stack headroom.

### 3. Reuse an existing buffer — conditional candidate only

**Ownership:** requires a documented transfer from the buffer's current owner, or proof that its lifetime never overlaps group-cache use. The B4 handovers identify no suitable reusable 4,480-byte buffer.

**Addressing changes:** the same split addressing, plus explicit acquisition/release or reconstruction rules if storage is shared. These caches are persistent; a temporarily idle buffer is not enough unless retained data can be reconstructed before every consumer safely.

**Remaining evidence:** a specific contiguous buffer of sufficient size and alignment, all readers/writers and aliases, asynchronous access, lifetime overlap, and contents needed after reuse.

**Tradeoff:** could avoid heap pressure, but has no established placement or ownership proof. Do not select a buffer from an absence of references alone.

## Split addressing and known consumers

Preserve internal IDs and preset meanings. Browsing-order conversion is a separate mapping operation.

```text
count/index(g,c):
    g <= 64: 0x80037E90 + 8*(17*g + c)
    otherwise: E + 8*(17*(g-65) + c)

size(g):
    g <= 64: 0x8003A118 + 4*g
    otherwise: E + 0x1100 + 4*(g-65)
```

Validate group/category ranges before computing addresses: g must be 0–96 and c must be 0–16. Extension access must additionally require an initialized, available extension. Existing sentinels or special group values must be handled according to their callers' semantics, not blindly treated as indices.

Shared getter edits alone are insufficient. Known PIC consumers from readme_B4.md include:

| Consumer | Address / required change |
|---|---|
| Getter and availability | 0x9D0792E0, 0x9D079300: route group addressing and validate expanded access |
| Runtime initialization | 0x9D040ED8; base construction 0x9D040EEC/EF0, stores 0x9D040F40/F44 and 0x9D041038, bounds 0x9D040FC8/FD0: stop assuming all rows form one contiguous array |
| Direct name-display index access | 0x9D041184/188/190: route the direct row access |
| Size initialization | 0x9D079A08; count at 0x9D079A30: extend queries and route writes |
| Import size write / renderer size read | Around 0x9D01B8EC / 0x9D034288: route direct size accesses |
| Count rebuild | 0x9D042A8C, limits around 0x9D042B04/B08: expand traversal and preserve coherent persistence |
| Name builder | 0x9D042B80, bound 0x9D042D9C: expand traversal with coherent capacity handling |

This is the known consumer set, not a claim that every alias or direct access has been recovered. Initialization should preserve established default count/index meanings; zeroing the allocation alone does not reproduce the documented count=1/index=-1 defaults.

## Options not preferred

- **In-place growth:** conflicts with the stock size cache and adjacent owned data.
- **Full-table relocation to 0x80058000:** the candidate 13,580-byte region has no established reservation or stack clearance. Emulator fixtures do not prove ownership.
- **Full-table heap allocation:** 13,580 bytes leaves only 2,804 bytes of the default heap before allocator overhead and other users; it also replaces rather than preserves stock table placement.
- **Stack-local extension:** persistent tables require a lifetime beyond a local frame, and stack headroom remains unproven.

## Next-step decision and blockers

The immediate decision is whether allocation failure may leave the synth at stock capacity. If yes, investigate the permanent-allocation design first. If capacity must be guaranteed, investigate a fixed reservation within the existing heap and prove the reduced heap sufficient. Neither choice currently has enough evidence for implementation.

The next focused evidence work should establish allocator ownership, concurrency and competing demand; persistent pointer ownership if allocation is chosen; the extension initialization/publication lifecycle; and complete split-addressing coverage. It does not require repeating the startup/USB audit or selecting an address above the heap.

Independent feature blockers remain:

- **Name-region overflow and rollback:** the existing serial name region holds 65,536 shared records. The handover documents an initializer/builder inconsistency and out-of-region reads. More RAM does not fix this.
- **QNX expansion:** its count/pointer object, accessors, size cache and lifecycle bounds must be expanded coherently with PIC capacity. The 4,480-byte calculation applies to the PIC extension only.
- **Limits, mappings and lifecycle coverage:** selection, sanitization, imports, rebuilds and persistent metadata must agree on active capacity and preserve existing IDs.

Stop at this design assessment. No placement is reserved, no firmware is modified, and no build or flashing recommendation follows.
