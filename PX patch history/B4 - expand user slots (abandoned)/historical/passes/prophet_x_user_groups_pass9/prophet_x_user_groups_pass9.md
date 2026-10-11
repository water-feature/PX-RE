# Branch 4 — heap and interrupt-stack investigation, pass 9

2 October 2026. Static investigation only this pass; no build, patch file or flash. Standalone group expansion and eventual voice_sysex merge remain the development requirements.

## Heap path

The inspected heap-growth chain is allocator 0x9D07EB84 -> zeroing growth wrapper 0x9D08149C -> bounded sbrk 0x9D080B98. The allocator calls the wrapper at 0x9D07EC7C and 0x9D07ED54, including a retry with a different growth amount. The wrapper zeros successful positive growth using 0x9D080F4C. Allocator metadata occupies RAM around 0x80053A70..0x80053A88.

The disassembly's direct caller of the allocator is 0x9D07F044 in a formatting routine with an approximately 1 KiB stack frame. It requests output length+1 and checks null on failure. This is a direct-call finding, not a proof that there are no indirect allocator users or alternate heap configurations. The chain confirms that the default heap has bounds; it does not establish adequate available capacity for new caches.

## Stack inventory and disassembler limitation

The inventory finds 518 negative immediate SP adjustments across the linear PIC disassembly. Their sum is 33,672 bytes. The largest is 0x2060 = 8,288 bytes at 0x9D045264; the routine clears an 8 KiB local buffer at SP+0x10. Seven decoded paths restore SP from FP. Initial SP is 0x8007FFF0.

The candidate enlarged caches would end at 0x8005B50C, leaving 150,244 bytes below initial SP. Neither that distance nor the sum of all distinct frame sites is a stack bound: repeated frames/recursion, interrupt nesting, indirect calls and skipped instruction semantics remain to resolve. Do not authorize a RAM reservation from this comparison.

A critical blind spot appeared at IRQ vector target 0x9D05077C: Capstone omits raw instruction 0x415DE800, and omits companion 0x41DDE800 at 0x9D050810. Raw-word enumeration finds 22 COP0 instruction candidates with rs fields 10/14 and rt/rd fields both 29 (SP), around interrupt entry/exit paths. Their register-bank/stack semantics must be decoded with a complete target-aware decoder before using a simple SP-write inventory as proof. This report records the words and fields; it does not substitute an unverified instruction interpretation.

Vector stubs at 0x9D000200..0x9D000250 jump to multiple IRQ handlers. The first inspected handler saves CP0 state and register values, changes status, then disables interrupts before restoring state and executing eret. A complete interrupt nesting/priority analysis has not been performed. Its observed 24-byte local adjustment is not a bound on other handlers or nested callees.

## Decision and next work

No relocation location is proven safe yet. Continue by obtaining complete decoding of IRQ entry/exit instructions, identifying interrupt priority/nesting and shadow-stack behavior, then resolving call cycles/indirect targets for a stack budget. Also trace alternate heap configuration writes and allocator ownership. If that proof cannot be closed statically, a hardware stack high-water test or a deliberately bounded allocation/failure design is needed; it would be incorrect to claim the candidate gap is unused from the current evidence.

Evidence: audit_pic_stack.py and pic_stack_inventory.json preserve every discovered frame site, other decoded SP writes and raw COP0 SP candidates. This is an investigation checkpoint, not a successful RAM-safety test. Earlier emulator tests remain valid only within their stated scope.
