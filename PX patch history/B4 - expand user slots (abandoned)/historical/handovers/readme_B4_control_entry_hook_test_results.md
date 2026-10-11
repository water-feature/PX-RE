# B4 revised DINIT entry-hook test results

3 October 2026. Design: `readme_B4_control_patch_design_revised.md`. Harness: `b4_control_integration_harness.py`; command `python3 b4_control_integration_harness.py --entry-hook`. Recorded output: `b4_control_entry_hook_results.json`.

**All revised-mode assertions passed.** Legacy mode was also rerun successfully as a negative control: it reproduces the stale active root after direct DINIT. Its recorded output is `b4_control_legacy_negative_control_results.json`. There was no firmware modification or build. Stock SHA-256 is checked before and after testing: `14e9c9b9dc562b0384fc43b3c5e0eb7fea84a5792d1a19b9b3ea8276ef7646f5`.

| Test | Observed result |
|---|---|
| Helper instruction checks | Seven revised trampoline words plus unchanged 94-word guard; 101 active helper words |
| Cold startup | Unchanged startup target enters hooked original DINIT once; control readiness/pointer zero; 1,577,421 interpreted instructions |
| 4,480-byte extension | Pointer 0x80053AE8; break 0x80054CE0; upper 0x80057AD8 |
| Exhaustion | Eleven simultaneous competing 1024-byte blocks, then NULL/errno12; break 0x800579E0; live extension payload and controls intact |
| Free/reuse | Real free allows competing block reuse, without disturbing extension/control record |
| Reload retention | Real cache initializer code, with 1106 external byte reads and 64 size-query stubs; retained root/state and full 4480-byte payload |
| Coordinated reset | Clears controls and allocator state; subsequent pointer 0x80053AE8 remains unpublished |
| Preferred/minimum retry | Preferred 4608 fails against reduced valid heap; real malloc retries 4496 and succeeds at 0x80053AE8, break 0x80054C70; errno remains12 |
| Initial allocation failure | NULL; pointer/readiness remain zero |
| Actual sbrk caller boundary checks | Zero, growth zero-fill, shrink, exact cap, crossing cap and invalid upper pass; controls intact |
| Previously failing direct DINIT | **Now passes:** both controls zero after direct 0x9D081090 invocation; subsequent allocation at same address remains inactive |
| DINIT differential | All 32 final registers, flat MMIO backing, and all RAM outside the eight control bytes match unmodified stock DINIT |
| Allocator-only reset simulation | **Still hazardous:** explicitly resetting allocator/provider globals without DINIT retains active stale root and permits address reuse |

The direct-DINIT regression checks both after reset and after subsequent malloc. Thus success does not merely mean the root is eventually cleared after a later allocation. Invalidation is executed before the stock descriptor interpreter by the exact trampoline instruction sequence, readiness first then pointer; only the entry-hook stores clear the reservation during cold initialization.

The allocator-only case simulates a lifetime-reset operation by host writes to known globals; it does not identify a new actual reset route. It establishes that the entry-hook solution cannot cover resets which never enter DINIT. Such routes require separate coordinated invalidation if established.

## Limits

This remains a focused custom instruction interpreter, with serialized calls, no interrupts/DMA/cache behavior and no proof of atomic invalidation or consumer quiescence. Original DINIT MMIO writes use a flat backing map; peripheral side effects are not emulated. Serial reader 0x9D040A4C and size query 0x9D079744 are stubbed only at external I/O boundaries. No PIC/QNX activation protocol or stack-headroom claim is made.

DINIT differential execution compares final architectural state and modeled memory; it cannot prove asynchronous timing equivalence. The hook adds two stores and a trampoline transfer, and no instruction barrier or interrupt masking. Readers holding an already acquired pointer still require lifecycle coordination. Firmware flash aliases and arbitrary interior entry paths are not newly validated by this virtual-address overlay.

The actual intended voice_sysex source/binary is still absent from existing evidence. Previously recorded helper/RAM ownership and merge limits remain. No broad ownership searches were repeated. Stop at the revised design and these results.
