# Branch 4 — NRPN consumer, mapping and relative controls, pass 7

2 October 2026. Clean official 2.2.2.0.0; hypothetical larger descriptor maxima exist only in emulator memory. No firmware built or flashed. Separate group-expansion test build and eventual voice_sysex integration requirements remain unchanged.

## Result

The inspected queued NRPN consumer correctly routes both group parameters for both parts. Absolute values 65,96,132 reach the central setter unchanged. Relative increment/decrement uses the same parameter descriptor maximum, with no separate group64 ceiling found in this path. This is evidence for one traced path, not whole-firmware coverage.

## Consumer path and mapping

In the main PIC event handler, message type 0xFD is recognized at 0x9D02CE08..0x9D02CE10. Parameter numbers below 0x800 route through 0x9D02DE0C for part A; numbers 0x800..0xFFF route through 0x9D02E47C for part B after subtracting 0x800.

Mapping helper 0x9D05ED94 reads a halfword table at 0x9D0727C0. Inspection and execution confirm NRPN numbers 0x22 and 0x63 map to internal parameters 0x22 and 0x63. No alternate parameter number mapping is needed for these groups. Part B's 0x822 and 0x863 become those same internal parameters with part argument 1.

Absolute receive path calls central setter 0x9D04DACC with arguments (source=1, part, internal parameter, full received value). Actual group max validation and table-dependent side effects are in that setter, previously inspected in pass 2; this turn captures immediately before entering it.

## Relative controls

Receive value 0xFFFF selects increment; 0xFFF3 selects decrement. Part A routes to 0x9D030084 and 0x9D02F410 respectively; part B uses counterpart branches beginning around 0x9D02FC94/0x9D02F6C8.

The consumer loads the internal parameter's maximum from its 12-byte descriptor at 0x9D047498 and passes it as the fifth argument to relative helper 0x9D04FA6C. This helper reads the current halfword from the correct part's parameter storage, adds +/-1 through saturating helper 0x9D0816E0, and tail-calls the central setter. Parameter 0x182 has a special floor; the two group parameters do not take that exception.

Thus relative group edits can reach ID96 or ID132 with hypothetical max96/max132, and stop at that max. If current state is already above the configured max, this path clamps back to the max; test fixtures include that condition rather than assuming every current value is valid.

## Actual instruction evidence

verify_nrpn_consumer.py executes from consumer branch 0x9D02CE14, through the real dispatch, real mapping table, relative branches and relative helper, capturing at entry to 0x9D04DACC.

300 cases pass: descriptor maxima 64,96,132; both parameters; both parts; current values 0,64,65,96,132; incoming values 65,96,132,0xFFFF,0xFFF3. Absolute cases preserve the received value at the setter boundary. Relative cases match saturation of current+/-1 to 0..max. No external mapping or arithmetic is mocked; only the capture before setter execution terminates the case. Descriptor changes are in emulator memory only.

Combined with pass 6, the inspected chain now covers sender byte construction, controller-value assembly, message argument shape, queued-message consumer dispatch, part selection, mapping and relative calculation. The tests are segmented; no actual queue scheduler, UART/USB parser, simultaneous-controller ordering, complete state update or audio selection transaction is executed. Existing setter limiter tests provide separate evidence, not a substitute for a future integrated transaction test.

## Remaining coverage

Generic PIC setter/getter candidates still need classification by caller and input parameter provenance. Other MIDI controller and alternate UI paths remain outside this claim. Index release semantics, cache relocation, name-capacity consistency and stack/RAM reservation from earlier passes still block a defensible standalone build. Next priority is closing the group-table reference inventory and initialization/relocation ownership, then expanding regression coverage around full index lifecycle.
