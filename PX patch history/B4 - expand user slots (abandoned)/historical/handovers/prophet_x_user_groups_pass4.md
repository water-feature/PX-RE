# Branch 4 — import bounds, overflow and voice_sysex compatibility, pass 4

2 October 2026, Australia/Brisbane. Continues pass 3; clean 2.2.2.0.0 is the standalone group-expansion baseline. No firmware built, modified on disk or flashed. Higher limits were tested only as arguments to actual stock functions in emulator memory.

## Build policy recorded from the user

Keep group expansion in a separate test build containing only this feature. Use a distinct external filename and corresponding internal/screen revision; select an unused revision when building, after refreshing the authoritative handover. Eventual integration target is voice_sysex. Preserve old internal group IDs and document code, RAM, persistent-record and container ownership for the merge. Do not combine features prematurely. Do not create ambiguously named duplicate firmware packages.

## New independent import limit

The import event handler has cursor bounds separate from group parameter descriptors. Calls to saturating helper 0x9D0816E0 set max cursor 0x3F in delay-slot instructions at 0x9D01B7C4 and 0x9D01B9B8. Positive and negative input paths both need changing for 96 destinations (64 users plus 32 purchased), whose zero-based cursor max is 95. The selected cursor becomes display ID cursor+1 before inverse mapping to internal IDs.

The same handler maintains a four-row viewport: if selected cursor is below its top, the top follows; if above top+3, top becomes selected-3. Renderer 0x9D0341EC..0x9D0342D8 draws four rows using viewport top+i+1. Its display-ID byte mask accommodates 96; this observation does not prove every global initialization or navigation path.

Actual helper instructions were executed for every cursor and +/-1 movement for maxima 63 and 95. All boundary cases passed. No patch to the event handler was emitted.

## Name overflow is an index-consistency problem

Pass 3 established the name builder stops at 65,536 records. This pass executes actual stock initializer 0x9D040ED8 with an extended count-page marker and mocked 255-instrument counts. It creates count 256 for every category and a monotonically increasing record index across all 1105 category entries, without capping indexes at the name region's capacity.

The first out-of-region entry is entry 256 = internal group 15, category 1: index 65,536. The last stock entry has index 282,624. This is a deliberately saturated fixture, not a claim about typical installed libraries or a reproduced hardware failure.

Actual name-reader instructions at 0x9D041E8C, supplied that cache entry and instrument 1, call the serial byte reader with 0x1000040. The capture stops before device I/O. Thus count initialization and name traversal do not enforce the same capacity. Expansion must handle this coherently, for example preflighting aggregate record demand and retaining the prior coherent cache on overflow. Simply increasing the builder loop, or silently truncating names, is insufficient. Exact acceptance/error behavior and rollback design remain to implement and test.

## RAM investigation

Actual sbrk routine 0x9D080B98 enforces configured heap upper bound at RAM 0x80053A68 and lower bound at 0x80053A6C. With default-range fixture base 0x80053AE0, upper 0x80057AE0 and current break 0x80057AD0, an allocation of 16 reaches the end; a further byte returns -1 and leaves the break at the end. This closes one direct growth path into the proposed cache location 0x80058000.

This is not a proof that the location is free. The allocator initialization can use nonzero configured range values, physical/cached/uncached aliases exist, and stack starts at 0x8007FFF0 without an inspected guard against descending into the candidate interval. Indirect calls, interrupt nesting, dynamic stack use and worst-case high-water remain unresolved. The candidate must not be presented as an approved relocation. Static address absence and the default heap bound cannot supply the missing stack proof.

## Comparison with the actual integration target

Retrieved voice_sysex_2.2.2.0.3.zip and checked the contained BIN against its manifest hash:

- Clean baseline SHA-256: a4b304b3bb48ca933ae63c99c0098698c497ebfc7c38ab2a823b5e0df4919fa9.
- voice_sysex BIN SHA-256: bbc3c2ad26bef7310fc15cac8edee22a1792d8ced3788f7080acccc047304857.
- Equal container lengths: 3,099,064 bytes. There are 2893 differing bytes overall.
- PIC payload differences occur in offsets 0x1200..0x121F, 0x258B4, 0x295B0..0x295B3 and 0x51BC4. Reserve the SysEx trampoline and its entry edits. Revisions and container checksums are shared merge responsibilities.
- PIC startup descriptor bytes 0x1480..0x1A84B are identical to clean firmware. This comparison shows no startup-descriptor relocation by this build; it does not prove all dynamic RAM uses absent.
- Seventeen inspected group instruction sites, including parameter maxima, selector helpers, runtime initialization limits/base, name-builder bounds and import bounds/cache references, are byte-disjoint from these PIC changes.
- QNX bytes at VA 0x33390 (512 bytes), accessors 0x33C10/0x33C70 (96 bytes each) and name table 0x2A0160 (1064 bytes) are identical to clean firmware. The group-size cache is BSS and has no file bytes to compare; allocation, references and runtime ownership need a separate audit.

The exact changed-byte intervals are saved in import_compatibility_results.json as inclusive container ranges. This is a preliminary overlap audit, not certification of a future combined binary. Once an actual group patch exists, compare full change sets including new code caves, expanded objects, unwind metadata, RAM reservations, initialization changes, checksums and version fields. Re-run voice and SysEx behavioral checks against the merged image.

## Evidence and remaining work

verify_import_and_compatibility.py passes hashes, exact-byte disjointness, QNX inspected-region comparison, all cursor boundary cases, heap boundary rejection, count initialization and actual name-reader address capture. External serial reads are mocked; no complete import transaction, hardware flash or device protocol acceptance was tested.

Next: obtain a defensible RAM reservation/stack bound or choose another allocation strategy; trace the remaining import/global initialization and NRPN limits; design coherent name-capacity validation and failure behavior; enumerate relocation references on both processors and produce the standalone patch plan. The user has authorized continued development and intends a separate test build. Unresolved ownership is a technical gap to close, not a request for another permission checkpoint.
