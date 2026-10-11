# Branch 4 — NRPN encoding and receive dispatch, pass 6

2 October 2026. Clean firmware; no BIN emitted, built or flashed. Standalone group-expansion baseline remains clean 2.2.2.0.0; eventual merge remains voice_sysex.

## Verified result

The inspected PIC NRPN sender and controller receive-dispatch paths preserve group values 65, 96, 128 and 132. There is no seven-bit group-value ceiling in these paths. This is not yet proof of the queued-message consumer or complete MIDI receive transaction.

Sender 0x9D05E9EC emits controller sequences 99/98 for the parameter number, then 6/38 for the value. It splits each into upper and lower seven-bit pieces. Global-setting getter 0x9D04D780 is called for send mode and output configuration. The emulator mocks these settings as NRPN enabled, ring-buffer output. Real sender instructions write the 12 bytes to RAM 0x80012A10 and update the ring pointer.

Controller-dispatch entry 0x9D05DCB8 handles NRPN select LSB 98 at 0x9D05DE8C, MSB 99 at 0x9D05DE28, data-entry MSB 6 at 0x9D05DDC0 and LSB 38 at 0x9D05DD90. Selected parameter number is assembled in the GP-relative halfword at GP-0x7EC6. Data value is assembled from GP-0x7ECC/0x7ECE and dispatched to 0x9D07DC58 as message type 0xFD, channel, selected parameter and full value. Selector bounds are parameter-number bounds (<0x1062), not a sample-group ID bound. Parameters 0x22/0x63 and part-B 0x822/0x863 pass that gate.

Message constructor 0x9D07DC58 stores the selected parameter and value as halfwords in the record at RAM 0x80037D04, then jumps to queue routine 0x9D07E838. Its eventual consumer must still be traced for NRPN-to-internal-parameter mapping, relative increment/decrement sentinels, validation and actual state updates. Controller 96/97 paths emit special values 0xFFFF/0xFFF3; these must not be interpreted as ordinary group IDs.

## Execution evidence

verify_nrpn.py executes the actual complete sender and the actual controller-dispatch slice under Unicorn. It tests parameters 0x22,0x63,0x822,0x863 and values 0,64,65,96,127,128,132,255: 32 cases. Every emitted byte sequence matches the parameter/value split, and feeding its four controller pairs through the dispatch slice reconstructs the original parameter and value at the queue-message call.

Mocks: configuration getter; capture before message construction/queue delivery. The receive test starts after input-byte acquisition and does not run UART/USB/running-status parsing, channel assignment or queue consumer. No hardware I/O is exercised. These scope limits are explicit in the harness and result description.

## Parameter-reference coverage remains open

Pass 5's 555 generic getter and 351 setter direct-edge candidates are not all group operations. Inspection around 0x9D04DE80 confirms comparisons with 0x63/0x66 select sample-oscillator parameter families, rather than group-ID limits; its group/category changes still index the runtime table at 0x9D0792E0. Numeric matches alone must not become patches.

The current turn establishes NRPN encoding/dispatch only. It does not claim that all 165 parameter-literal candidates have been classified. Next is following message 0xFD through the consumer and mapping tables, including relative controls, then classifying the remaining group-parameter callers. PIC RAM reservation and complete QNX lifecycle coverage remain unresolved before a standalone build.
