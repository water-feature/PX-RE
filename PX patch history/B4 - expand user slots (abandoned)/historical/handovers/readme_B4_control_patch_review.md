# B4 control patch: independent instruction and integration review

3 October 2026. Scope: review `readme_B4_control_patch_design.md` and execute its proposed instructions alongside stock allocator code. No firmware file was changed, serialized, compiled or built. No ownership search or startup/USB audit was repeated.

## Result

The 103 helper words and six replacement-site words pass independent bitfield/target checks against the supplied stock image. The focused integration tests pass for cold initialization, a 4,480-byte allocation, exhaustion, free/reuse, cache reload retention, coordinated reset, and allocator minimum-growth retry. Allocator operations do not write the eight reserved control bytes. This supports the instruction design, **not approval to merge or flash**.

A concrete conditional lifecycle failure remains: invoking original DINIT directly bypasses root invalidation. The harness demonstrates an active stale root surviving allocator reset and its address being allocated again. The defensive sbrk guard cannot prevent this. No real bypass trigger is asserted.

## Stock and instruction evidence

Stock input: `stock_pic_2.2.2.0.0.bin`, SHA-256 `14e9c9b9dc562b0384fc43b3c5e0eb7fea84a5792d1a19b9b3ea8276ef7646f5`. Hash verified before and after execution. Connected Ghidra stock segment: `ram:9D000000–9D08195F`; raw instruction bytes are read from that payload base. Tests assert all six stock replacement words before creating a **memory-only instruction overlay**.

Reviewed extents: wrapper `[0x9D001240,0x9D001264)`, guard `[0x9D001280,0x9D0013F8)`. Every documented opcode, register field, immediate, branch displacement and jump target is checked by separately decoding its numeric word against its stated operands. No encoding discrepancy was found.

- Startup target construction at `0x9D0010D4/D8` produces `0x9D001240`; actual `jalr` at `0x9D0010DC` and NOP at `0x9D0010E0` return to `0x9D0010E4`.
- Wrapper `jal` at `0x9D001244` encodes `0x9D081090`; its delay is NOP. The stock DINIT descriptor interpreter saves its return in v1, uses t0–t4, neither writes t7 nor calls another function. Saving the outer RA in t7 therefore works for this exact routine. The wrapper restores RA at `0x9D001258`; `jr` and NOP delay at `0x9D00125C/1260` return without changing SP.
- Entry `j` at `0x9D080B98` targets `0x9D001280`; replacing the original RA-store delay with NOP is necessary because the helper owns its prologue. Original body is not executed through this entry.
- Guard keeps the original 32-byte frame: RA at SP+28, s0 at SP+24, increment at SP+16 across real lazy initialization. All guard transfer delays are NOP except SP restoration at `0x9D0013F4`. Branch targets, error convergence and epilogue targets check out. Every invoked routine preserves s0–s7/fp/GP/SP sentinels.
- Lazy initializer constant `0x9D07FB40` and provider constant `0x9D081868` become 0x3FF8; their existing addition/store delays remain stock. Actual initialization reaches upper `0x80057AD8`, rather than merely assuming it from a stub.

## Actual sbrk caller contract

Exact direct J/JAL scan of stock words recovers only `0x9D0814AC`, in wrapper `0x9D08149C`, consistent with Ghidra. No literal target word or addiu/ori immediate 0x0B98 was recovered. This closes recovered direct callers; it does not prove absence of arbitrary computed calls or interior entries.

Ghidra disassembly and execution confirm:

| Address | Instruction/assumption |
|---|---|
| `0x9D0814AC/B0` | `jal sbrk`; **delay `move s1,a0` saves increment before callee execution** |
| `0x9D0814B4/B8` | Branch on saved signed increment; delay saves returned old break into s0 |
| `0x9D0814BC/C0/C4` | Compare old break against -1; delay prepares memset destination |
| `0x9D0814CC/D0` | Call real memset `0x9D080F4C`; delay puts saved increment into a2 |
| `0x9D0814D4–E8` | Return saved old break; restore RA/s1/s0 and SP in return delay |

Thus this caller does not rely on preserved a0/v1/t0–t6. It uses saved s1 for growth size and saved s0 for result. Negative and zero increments skip memset; failure skips memset. Exact-cap growth clears only bytes below the control record.

Malloc `0x9D07EB84` calls that wrapper at `0x9D07EC7C`, with preferred size in fp/s8 and a0 set in delay `0x9D07EC80`. Failure comparison at `0x9D07EC88` sets minimum size from s5 into a0 in **its delay** `0x9D07EC8C`. Retry at `0x9D07ED54` saves -1 on the stack in delay `0x9D07ED58`; it reloads that sentinel at `0x9D07ED5C`, then sets fp/s8 to minimum size in branch delay `0x9D07ED64`. Successful paths clear t0 at `0x9D07ECBC`; none assumes sbrk's former t-register clobber set. These paths execute in the integration tests.

Free `0x9D0817C0` updates block metadata and malloc cursor, without shrinking sbrk or invalidating the retained extension. Actual free/reuse is exercised.

## Reproducible integration harness

Artifacts: `b4_control_integration_harness.py` and `b4_control_integration_results.json`. Run `python3 b4_control_integration_harness.py`. This is an isolated, focused MIPS instruction interpreter, not a firmware build or full CPU emulator. It reads immutable stock bytes, fetches proposed words from a separate overlay, implements executed instructions and branch/delay/branch-likely semantics, and fails on unsupported instructions or unmapped accesses. Cached and uncached RAM aliases share physical backing. Control-byte writes are logged and checked, including writes through aliases.

The wrapper executes the real DINIT interpreter and descriptor data. Malloc, sbrk caller, guarded sbrk, lazy initializer, provider, memset and free execute their instructions; none is replaced by a mathematical allocator stub.

| Scenario | Evidence/result |
|---|---|
| Cold startup through actual call site | DINIT executed once; allocator state reset; only wrapper stores `0x9D001250/1254` clear controls |
| Permanent extension allocation | `malloc(4480)` returns `0x80053AE8`; preferred growth 4608; break `0x80054CE0`; upper `0x80057AD8`; controls initially zero |
| Exhaustion with extension live | Repeated 1024-byte allocations reach NULL; errno12; extension payload and published pointer/state intact; no allocator control writes |
| Free/reuse | Real free of competing blocks permits another allocation; live extension and controls retained |
| Cache reload | Real count initializer `0x9D079220` and size initializer `0x9D079A08` run; stock count/index updates checked; pointer/state and all 4480 payload bytes retained |
| Coordinated reset | Actual startup call routes through wrapper, zeroes controls and allocator state; fresh allocation may reuse old address but remains inactive until explicit publication |
| Minimum retry | Initialize real heap first, then set valid upper to base+4496. Preferred 4608 fails; actual malloc retries 4496 and succeeds. errno12 remains after success, as errno need not clear |
| First allocation failure | Valid upper base+4488: both growth attempts fail; malloc returns NULL, both control words remain zero |
| Real caller boundaries | Zero query, positive zero-fill, shrink, exact-cap growth, cap+1 failure, below-lower shrink and invalid old full upper all pass; controls intact |
| Uncoordinated direct DINIT | **Failure demonstrated:** active root survives while allocator globals reset; next malloc returns same address, exposing stale ownership |

Reduced-capacity tests set bounds **after** lazy initialization. Setting them before initialization would let the real initializer replace them with default provider bounds and would not test retry/failure. The harness does not confuse that setup issue with a firmware defect.

Publication of pointer/state and coordinated consumer quiescence are explicit test-host actions, not implemented activation code. Reload tests show stock reload retention; they do not establish future readiness invalidation/republication behavior.

## Remaining limitations and blockers

1. The interpreter is purpose-built and is not independently validated CPU silicon or an established emulator. Encoding checks, Ghidra instructions, arithmetic assertions and sentinel checks corroborate execution but cannot remove that limitation.
2. DINIT MMIO destinations use a flat register backing with no peripheral side effects. Cache tests stub serial-byte reader `0x9D040A4C` and external size query `0x9D079744`; they execute cache initializer code, not serial hardware or PIC/QNX transport. No protocol fallback coherence is claimed.
3. No interrupts, DMA, concurrent allocator entry, hardware timing, cache behavior, fault injection or stack bound is tested. The wrapper's t7 contract assumes existing interrupt register preservation. Coordinated reset is serialized by the test, not proven for every real reset route.
4. No new ownership closure is claimed for control RAM/helper space, computed sbrk interior entry, or reset writers. Direct DINIT and allocator-only reset routes require coordinated control invalidation before consumers resume; the guard alone does not provide it.
5. Actual intended voice_sysex source/binary remains unavailable in existing evidence; merge compatibility remains unresolved. No historical comparison was repeated.

No helper encoding, delay-slot or recovered-caller contract defect was found. The demonstrated reset-bypass failure and these limitations remain blockers beyond this focused review. Stop here; no firmware patch, build or flashing recommendation follows.
