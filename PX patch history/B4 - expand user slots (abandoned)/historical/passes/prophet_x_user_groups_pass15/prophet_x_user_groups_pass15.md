# Branch 4 — USB event registration and controller indices, pass 15

2 October 2026. Stock firmware unchanged. No build or flash; separate user-group test build and eventual voice_sysex merge remain required.

## Registered event callback verified

The IRQ rooted at0x9D052498 reaches0x9D055A9C. Four indirect event calls at0x9D055B30/4C/74/8C load the driver's callback field+0x8C. The other nine previously recorded indirect calls load transfer-request callback+0x0C, matching the request representation traced in pass14. This classifies their sources; it does not establish an exhaustive set of callback writers.

Setter0x9D066840 installs parent callback0x9D06BDA0 at parent+0xDC and context0 at+0xE0. It then invokes driver-vtable slot+8 with parent reference and bridge callback0x9D066BA8. The initialized vtable0x800538E0 has slot+8=0x9D07AD3C. That leaf setter stores the parent reference at driver+0x88 and bridge callback at driver+0x8C. Actual MIPS execution of this registration chain on synthetic initialized objects verified all four stores. This connects the IRQ callback source to an observed registration path.

The bridge has32-byte frame and event<9 guard, dispatching through nine pointers at0x9D066BEC. Events3 and4 respectively clear/set bit7 in the parent byte and can tail-forward the same event to the registered parent callback. Event6 returns without forwarding. Three complete instruction executions checked these events and restored SP; all passed. DSP indexed loads were explicitly emulated. These tests are not USB hardware transactions.

## Reset event remains separate

Event2 enters0x9D066C74 and calls several driver-vtable functions. Under the recovered parent vtable, the call targets are:

| Call PC | Vtable slot | Target |
|---|---|---|
| 0x9D066C8C | +0x40 | 0x9D054710 |
| 0x9D066CA0 | +0x40 | 0x9D054710 |
| 0x9D066CBC | +0x24 | 0x9D054098 |
| 0x9D066CD8 | +0x20 | 0x9D054338 |
| 0x9D066D08 | +0x10 | 0x9D053DE0 |
| 0x9D066D8C | +0x38 | 0x9D05529C |

It also calls0x9D066AE8, which has a40-byte frame and can dispatch a child-class callback through a configuration record. The observed configuration has one child record at0x9D07F49C with a null callback-table pointer at+0x10. This narrows the stock setup, but mutable configuration and other contexts still require ownership checks. The reset path was not executed in this pass and has no final stack figure. Pass14's conditional440-byte completion accounting does not apply to it.

## Controller indices and priority writes recovered

Driver initializer0x9D07A720 consumes configuration0x9D07F2A8 and initializes driver0x8003A27C. It copies controller indices132 and133 into driver+0x64/+0x68 and mode1 into+0x60. Actual execution of this simple initializer verified those fields.

Caller0x9D06BF44 subsequently writes controller word0xBF810350 at0x9D06BFD4 and0x9D06BFF4, setting bits2..4 and bits10..12 to4. These writes are consistent with both observed USB IPL4 prologues using the interrupt-controller bit layout discussed in pass13. Exact device register-map confirmation is still outstanding; no global nesting bound is inferred.

The two IRQ wrappers compute their flag-clear addresses from the recovered indices. Isolated actual instruction-segment executions confirmed0x9D07ABC8 writes mask0x10 and0x9D07AC4C writes mask0x20, both to0xBF810084. Priority writes were also executed as an isolated segment and verified as word0x1010 from zero-initialized mapped memory. MMIO is plain memory in these fixtures, not hardware alias semantics.

## Status and next work

Callback registrations and controller indices are now recovered for the observed timer and two USB paths. Remaining work: audit reset-path callees and conditional child dispatch, classify the0x9D05212C state-machine callback targets, and bound mainline stack depth and activation cycles. RAM relocation remains unproven; no firmware patch follows merely from these controller findings.

Evidence includes registration/event checks, controller initialization/write checks and six conditional reset virtual-call targets. Each result records fixture scope and limitations. No stock group limit or cache address changed.
