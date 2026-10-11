# Branch 4 — interrupt decoding and reachable-edge inventory, pass 10

2 October 2026. Static analysis; no firmware patched, built or flashed. Separate group-expansion build and eventual voice_sysex merge remain the requirements.

## Decoding gap closed for the 11 inspected handlers

Raw words 0x415DE800 and 0x41DDE800 decode as RDPGPR sp,sp and WRPGPR sp,sp respectively. The MIPS-authored instruction manual specifies COP0 rs fields 10/14, rt/rd fields and the zero low11 bits. RDPGPR copies a register from the previous shadow set to the current set; WRPGPR transfers the current register into the previous set. These handlers therefore carry the interrupted SP into their active register bank and restore it on exit. A shadow register bank does not by itself provide separate stack memory.

Sources consulted: MIPS32 Volume II-A revision5.01, MIPS-authored manual (instruction encoding entries, accessed via StudyLib mirror) (instruction entries RDPGPR/WRPGPR); [Microchip Interrupts reference manual DS61108B](https://ww1.microchip.com/downloads/en/DeviceDoc/61108B.pdf), sections8.7 and8.9; [Microchip shadow-register overview](https://developerhelp.microchip.com/xwiki/bin/view/products/mcu-mpu/32bit-mcu/PIC32/mx-arch-cpu-overview/m4k-isa-overview/shadow-register/). The reference manuals describe architecture behavior; they do not establish the PX's exact installed PIC model or controller configuration.

The supplemental decoder recognizes the two instruction classes and retains Capstone for other words. All 11 inspected handler intervals now have zero undecoded words. This is a scoped completeness claim for these intervals, not the whole PIC image.

## Handler entry/exit inventory

The jump stubs at 0x9D000200..0x9D000250 identify these handlers. Each inspected interval begins with the same SP bank transfer and ends with its reverse transfer, restored Status and eret.

| Handler entry | Local frame | Entry IPL literal | Direct calls in body |
|---|---:|---:|---:|
| 0x9D05077C | 24 | 4 | 0 |
| 0x9D05081C | 328 | 4 | 1 |
| 0x9D050F30 | 352 | 4 | 5 |
| 0x9D050B54 | 24 | 4 | 0 |
| 0x9D050BF4 | 304 | 4 | 2 |
| 0x9D051DB0 | 304 | 1 | 1 |
| 0x9D052004 | 24 | 4 | 0 |
| 0x9D05212C | 312 | 4 | 1 |
| 0x9D0520A4 | 24 | 4 | 0 |
| 0x9D052498 | 304 | 4 | 1 |
| 0x9D0526EC | 304 | 4 | 1 |

Each prologue clears Status bits1..15 then ORs 0x1000 or0x0400 (IPL bits15..10); IE bit0 is preserved. Each interval has two explicit Status writes: prologue and restore. This does not exclude Status changes in callees.

Microchip describes higher-priority interrupts preempting lower-priority ones, with subpriority not causing same-priority preemption. An IPL1 handler interrupted by IPL4 is plausible from these literals. A two-level global nesting bound is **not established**: all active sources/vector assignments, controller programming and callee priority changes must be checked first.

## Reachability discovery

trace_irq_reachability.py follows candidate MIPS32 direct branches, direct calls and tail jumps, stopping at returns/eret and recording unresolved register jumps/calls. It records delay slots as reachable but does not inventory their effects. It does not compute stack depth or activation multiplicity.

| Handler | Candidate reachable words | Open indirect edges | Unique negative-SP bytes |
|---|---:|---:|---:|
| 05077C | 40 | 0 | 24 |
| 05081C | 1107 | 0 | 368 |
| 050F30 | 1944 | 0 | 520 |
| 050B54 | 40 | 0 | 24 |
| 050BF4 | 1157 | 2 | 464 |
| 051DB0 | 268 | 2 | 360 |
| 052004 | 40 | 0 | 24 |
| 05212C | 3880 | 22 | 2688 |
| 0520A4 | 34 | 0 | 24 |
| 052498 | 1005 | 13 | 440 |
| 0526EC | 373 | 2 | 400 |

Addresses in this table share prefix0x9D. Open edges include computed jumps at0x9D077B18/0x9D06E9E0, an indirect call at0x9D05BE6C, dispatch/formatting edges in the05212C closure, and callbacks around0x9D055E7C/0x9D056020/0x9D0565CC. The exact PCs are in JSON. Some edges may be jump tables with recoverable targets rather than unrestricted calls; resolve their data provenance before claiming completion.

Unique negative-SP bytes are discovery totals, not simultaneous frame usage or valid worst-case bounds. Cycles, repeated activation, indirect targets, branch delay effects and actual vector ownership remain open. No RAM location is certified.

## Next concrete work

Resolve the identified computed-jump tables and callback targets, inspect controller priority/vector configuration, and detect cycles in reachable function calls. Apply the same analysis to mainline roots and include delay-slot SP/status effects. Only then combine mainline and nested-interrupt stack budgets with heap/static reservations. If unresolved dynamic callbacks prevent a defensible static bound, use a hardware high-water experiment or a bounded allocation design; do not replace the missing proof with the apparent 150 KiB gap.

Evidence contains the supplemental decoder, completed scoped disassembly, raw handler inventory, reachability script and exact open-edge inventory. Earlier group relocation tests remain emulator-only mechanics checks. No standalone firmware build yet.
