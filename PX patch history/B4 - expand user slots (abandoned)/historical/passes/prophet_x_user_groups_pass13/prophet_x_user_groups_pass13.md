# Branch 4 — timer controller initialization, pass 13

2 October 2026. Stock firmware unchanged; no firmware build or flash. Separate group-feature test build and later voice_sysex merge remain required.

## Configuration ownership recovered

Initialization caller 0x9D06BF44 passes flash configuration 0x9D07F2E0 to object initializer 0x9D05BA34. Its seven words are 0xF, 3, 0, 7, 28, 1, 0. The initializer copies configuration words into parent 0x800539B8 as follows:

| Parent offset | Copied value | Subsequent use |
|---|---:|---|
| +0x08 | 7 | Peripheral configuration helper argument |
| +0x0C | 3 | Peripheral dispatch selector |
| +0x10 | 0 | Configuration field |
| +0x14 | 28 | Controller bit index |
| +0x1C | 1 | Peripheral mode selector |

Caller PCs 0x9D06BF80 and 0x9D06BFA0 write 0xBF8101B0: bits 2..4 become 1, then bits 0..1 become zero. That layout is consistent with priority1/subpriority0 in the PIC32 interrupt-controller format and matches the observed IPL1 handler prologue. The byte/bit interpretation is supported by Microchip's interrupt reference manual, but the exact MCU/device register assignment remains unconfirmed. Source: https://ww1.microchip.com/downloads/en/DeviceDoc/61108B.pdf, Interrupt SFR Summary and IPC register description. This is not proof that other vectors all use IPL4.

With recovered index28, controller-start helper 0x9D05B59C writes mask0x10000000 to addresses0xBF810044 and0xBF8100C8 at PCs0x9D05B5D8/DC. The earlier computed-address uncertainty for this registration path is resolved. The initialization helper0x9D0806DC separately calculates the corresponding disable address0xBF8100C4, from the same index. Its DI/save/restore Status sequence needs to be included in interrupt analysis; it does not establish a new priority level by itself.

## Object-layout correction

The initializer clears exactly0x3C=60 bytes beginning at0x800539B8. The callback handle is parent+0x24, not a second object. The validation arithmetic at0x9D05BDB8..DDC scales the aligned offset by the inverse of15 after shifting right two bits. For aligned addresses in the nearby0..120-byte range, it accepts parent and parent+60. It does not imply44-byte objects. No second object is initialized by the recovered allocator path: allocator0x9D05BEC8 accepts selector0, operates on the parent and returns parent+0x24. Previous references to a two-entry region should therefore be read as a validator observation, not evidence of two allocated objects. The accepted one-past address is a stock validation behavior; no unrelated fix is included.

## Verification and stack implications

verify_timer_controller_init.py executes three separate MIPS instruction segments: caller plus configuration-copy prefix; caller priority writes with the parent return value supplied; and controller helper through its two stores. All assertions pass. The memset helper is substituted. Peripheral configuration helpers are outside those segments, and mapped MMIO is plain memory without hardware alias effects. An attempted full initializer emulation was not validated; the saved passing harness explicitly checks only the narrower segments and does not claim a whole initialization transaction.

For the observed callback registration, the low-priority handler's direct chain has frames304+24+24+8=360 bytes on its peripheral-disable path; the callback itself adds no frame. This is a conditional accounting of the recovered path, not a global stack bound: exhaustive callback-writer proof, repeated activation, register-bank behavior, other interrupt roots and mainline stack depth remain unresolved. RAM relocation is still unproven.

## Next work

Trace the remaining controller priority writes in initialization and recover other IRQ callback targets. Then bound mainline call cycles and delay-slot stack effects. Keep the stock group limits and proposed relocated tables unchanged until RAM ownership is defensible.

Evidence: verify_timer_controller_init.py and timer_controller_init_results.json, containing exact executed ranges, configuration, copied fields, register writes and explicit limitations.
