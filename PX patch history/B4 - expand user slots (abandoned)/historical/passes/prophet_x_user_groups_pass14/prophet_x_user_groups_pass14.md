# Branch 4 — USB completion callback paths, pass 14

2 October 2026. Stock firmware unchanged; no build or flash. Standalone user-group feature build and eventual voice_sysex integration remain required.

## Transfer callback registration recovered

The IRQ rooted at0x9D0526EC calls0x9D07ABE0, then0x9D056414. Its two unresolved indirect calls,0x9D056570 and0x9D0565CC, both load their target from transfer request+0x0C and pass the transfer request itself in a0. A local code-pointer store scanner found326 candidates across the PIC payload; the two candidates writing offset+0x0C lead to registration sites0x9D07BAA8 and0x9D07BC40.

| Registration PC | Stored callback | Parent reference |
|---|---|---|
| 0x9D07BAA8 | 0x9D07B860 | request+0x14 |
| 0x9D07BC40 | 0x9D07B8FC | request+0x14 |

The registration arithmetic selects36-byte slots. Four actual MIPS instruction-segment executions checked both slot indices0/1 for both registration paths and verified the callback and parent-reference stores. The scanner is a discovery aid: straight-line constants, data-decoding candidates and unknown aliases prevent an exhaustive writer claim.

## Parent callback and event context

Both40-byte-frame callbacks load another target from parent+0xDC. The registered parent target comes from setter0x9D066840, called at0x9D06CA8C with a1=0x9D06BDA0. Setter0x9D06686C stores that target and the following instruction stores context0 at parent+0xE0.

Importantly, callback0x9D07B860 supplies event16; callback0x9D07B8FC supplies event15. Dispatcher0x9D06BDA0 guards event<17 and uses a17-pointer table at0x9D06BDC4. Event15 points to0x9D06BE10, which clears byte0x8002AB45; event16 points to0x9D06BF0C, which clears byte0x8002AB44. Those two event handlers are leaves with no frame or further calls.

The same dispatcher has other events with virtual calls, but those cannot be included indiscriminately in these observed completion paths: the wrappers explicitly supply15/16. Other call contexts remain separately auditable. The driver vtable for those other event paths is supplied by configuration0x9D07F2FC+0x30=0x800538E0, with80 bytes copied from DINIT payload0x9D01A3F0, descriptor0x9D01A3E4. Its pointers were recovered and preserved in the evidence.

## Executed verification

Ten complete callback executions, five transfer statuses per callback, checked the emitted event, packet fields, status mapping, decrement of the pending counter, clearing of the corresponding pending flag, and restored SP. Status0/1 map to0; -3 maps to-0x62; -4 maps to-0x61; other tested status2 maps to-0x60. All passed. The dispatcher indexed load at0x9D06BDB8 was explicitly emulated because Unicorn lacks the DSP instruction. RAM transfer/parent objects were synthetic; neither hardware USB nor queue ownership was exercised.

## Conditional stack accounting

A separate conditional reachability artifact resolves the two request-callback edges to the observed callbacks, their parent-callback edges to0x9D06BDA0 and its event jump to the proven15/16 destinations. It reaches472 instruction words with zero remaining open indirect edges under those explicit assumptions. The original global reachability artifact retains its unresolved edges; no universal writer-set proof is implied.

The inventory sums480 bytes of unique frames, but that is not simultaneous stack usage: the two40-byte callback frames are alternatives. The observed deepest activation chain accounts for304+24+72+40=440 bytes. This remains conditional on the recovered registrations and one activation of the interrupt; it is not the whole-firmware stack budget or a RAM reservation proof. Mainline depth, higher-priority activation, callback aliases and remaining IRQ roots still require work.

## Next work

Continue with IRQ roots0x9D052498 and0x9D05212C, especially their callback registration and state-machine target sets. Then combine validated call paths with controller priorities and mainline stack depth before choosing RAM reservation or bounded allocation. No group limits or table addresses changed in this pass.

Evidence includes scanner and candidate index; four registration and ten completion cases; driver vtable and bounded event table; and a separate conditional reachability script/result with assumptions recorded.
