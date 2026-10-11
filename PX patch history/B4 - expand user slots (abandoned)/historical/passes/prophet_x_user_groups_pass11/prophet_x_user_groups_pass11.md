# Branch 4 — bounded interrupt jump tables, pass 11

2 October 2026. Static analysis of unchanged firmware; no build or flash. Continues pass10's unresolved-edge inventory. Standalone group-expansion and eventual voice_sysex integration remain required.

## Five computed jumps resolved

Manual instruction tracing found explicit index bounds and table bases for five prior open edges. Every pointer in these finite tables was decoded and asserted to be an aligned address inside the PIC payload.

| Jump PC | Pointer table | Guarded entries |
|---|---|---:|
| 0x9D077B18 | 0x9D077B20 | 5 |
| 0x9D06E9E0 | 0x9D06E9E8 | 40 |
| 0x9D05B8F0 | 0x9D05B8F8 | 9 |
| 0x9D056F34 | 0x9D056F3C | 5 |
| 0x9D056F74 | 0x9D056F7C | 5 |

The bounds come from sltiu comparisons and traced branch conditions, followed by four-byte index scaling, LUI/ADDIU base construction and lwx/JR. These are finite dispatch tables, not arbitrary function pointers. Table targets and their guard sizes are preserved in resolved_irq_jump_tables.json. The 40-entry table path has its input bound propagated through the routine's earlier branch and later test; the nearby branch alone should not be read without that context.

Adding those targets to the direct-control-flow closure leaves zero open indirect edges for handler0x9D050BF4, previously two. Its reachable inventory grows from1157 to1429 words. Handler0x9D051DB0 goes from two open edges to one, at the callback call0x9D05BE6C. Handler0x9D05212C goes from22 to20 open edges. The other previously closed handlers remain closed within the analyzer's scope.

Zero open indirect edges is not a stack bound or proof that this analyzer handles every instruction/control mode. Delay-slot effects, repeated activation/cycles, register-bank semantics and controller ownership remain independent checks.

## Runtime callback ownership traced further

The low-IPL handler0x9D051DB0 calls0x9D05BEC0, which tail-jumps to0x9D05BD98. That routine validates an object against a two-entry region rooted at RAM0x800539B8, checks state and, on its callback path, loads the target from object+0x34 and the callback argument from object+0x38. The callback target is tested for null before JALR at0x9D05BE6C.

This identifies where the callback target comes from. It does not yet identify all writers or the possible non-null values. Clearing at0x9D05BE94 is one observed writer; registration/copy/alias paths still require tracing. Treating this as an unrestricted jump or assuming it is always null would both be premature.

## Controller write discovery

A constructed-address scan finds20 store candidates into0xBF810000..0xBF810FFF,11 with locally recoverable literal values. The scan propagates simple LUI/ADDIU/ORI/ANDI/MOVE values and resets at calls/jumps or undecodable words. It is a discovery aid, not a complete MMIO write inventory. Data words can decode as instructions; propagation can miss aliases, tables, read-modify-write and longer control-flow dependencies.

Register ownership and priority/vector configuration are still unresolved. No device-specific IPC/IEC/IFS assignment is claimed from an address alone. Therefore pass10's observed handler IPL1/IPL4 prologues still do not establish a global two-level nesting limit.

## Status and next work

RAM reservation is still unproven. Next: recover callback registration writers and target sets; map controller writes using the actual device/register ownership evidence; check call cycles and delay-slot effects for mainline and interrupt roots. Then assemble a defensible stack budget or choose bounded allocation with explicit failure behavior. No new firmware build is justified solely by the reduced open-edge count.

Evidence includes resolved table targets, updated reachability script/results, MMIO discovery script/results. The updated reachability analyzer remains deliberately conservative and records its limitations in every root result. No hardware experiment or emulator transaction was performed in this pass.
