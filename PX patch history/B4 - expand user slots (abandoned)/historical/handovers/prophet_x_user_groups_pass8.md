# Branch 4 — relocated count initialization, pass 8

2 October 2026. Emulator-only relocation experiment; no firmware emitted or flashed. Standalone test build remains based on clean firmware, with later voice_sysex integration required.

## New reference and validated mechanics

PIC name-display path around 0x9D041178 directly constructs the count/index cache base at 0x9D041184/0x9D041188, reads its second word at 0x9D041190, and computes a serial name-record address. This is another reference to relocate alongside the separate reader 0x9D041E8C, count getter and availability getter. Changing only shared accessor functions would miss it.

An emulator-only candidate relocation to 0x80058000 with 97 rows passes five initializer fixtures: legacy count page with instrument counts 0 and 1; extended marker layout with counts 0,1,255. The test updates initializer base constructions/direct stores, extended read-through bound, default-row bound and table end. The 97-row count/index table is 13,192 bytes (0x3388). No on-disk firmware bytes are changed.

Legacy records still read 41 groups and initialize remaining groups to count1/index-1. Extended records read 97 groups. Every entry is asserted; guards immediately before/after the new table survive, and a marker at the old base remains untouched. Relocated count and group-availability getters return expected values for groups 0,40,41,64,65,96, including empty default rows.

Unicorn lacks DSP indexed-word loads. The harness supplies the exact unsigned word-read semantics for the getter's return-delay-slot load (intercepted together with jr) and the availability loop's lwx. Serial count-byte reads are mocked. All remaining instructions in the inspected routines execute from stock bytes with the emulator-only address/bound changes. These are targeted mechanics tests, not device transactions.

## Explicit ownership gap

The candidate address is still unapproved. Passing initialization and boundary guards does not prove runtime RAM ownership, worst-case stack depth or interrupt nesting. No claim that the gap is free follows from these tests.

Two alternatives require further design: a documented static reservation with a proven stack budget, or heap-owned additional rows with allocation failure handled coherently. Allocating the complete 13,580-byte count/index plus size caches from the stock 16 KiB heap would leave only 2,804 bytes before allocator overhead and other users; it cannot be assumed viable. Allocating only the extra 32 rows and size entries requires 4,480 bytes before overhead, but introduces split-table addressing and allocation/fallback logic. Neither alternative is selected or implemented yet.

The existing in-place growth remains invalid because it overwrites the adjacent size cache and other initialized data. Startup initialization for any relocated region must also be explicit; merely changing lookup bases cannot establish ownership.

## Next work

Complete the constructed-address reference inventory, including direct count/index reads and size-cache writes; trace heap users and stack/interrupt ownership before choosing a reservation strategy. Then check full index lifecycle and remaining parameter callers. Generic candidates, indirect calls and complete MIDI transactions remain open. Current voice_sysex byte disjointness does not certify future new code or RAM reservations.

Evidence: verify_relocated_initialization.py and relocated_initialization_results.json. Five fixtures and both getter paths pass. No firmware build.
