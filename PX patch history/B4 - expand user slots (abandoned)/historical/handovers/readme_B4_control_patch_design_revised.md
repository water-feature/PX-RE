# B4 revised control design: intercept original DINIT entry

3 October 2026. Supersedes the cold-call wrapper portion of `readme_B4_control_patch_design.md`. The guarded sbrk and shortened provider/default bounds remain exactly as previously specified. This is a design and memory-only harness overlay; no firmware file is modified or built.

## Change and coverage

Intercept **original DINIT entry 0x9D081090**, rather than redirecting only cold startup. Every transfer entering that address, including an indirect call, now invalidates the B4 record before executing the original descriptor interpreter. The cold startup target construction `0x9D0010D4/D8` remains stock (`3C089D08`, `25081090`), with stock jalr and delay at `0x9D0010DC/E0`.

This protects entry at 0x9D081090. An arbitrary transfer into the interior at 0x9D081098 or later bypasses it; no new closure of interior entries or allocator-only resets is claimed.

## Exact revised sites

| Address | Required stock word | Proposed word | Instruction |
|---|---|---|---|
| 0x9D081090 | 03E01821 | 0B400490 | j 0x9D001240 |
| 0x9D081094 | 3C089D00 | 00000000 | NOP in jump delay |

Displaced stock instructions are `addu v1,ra,zero` and `lui t0,0x9D00`. Execute them in the trampoline below, then jump directly to **0x9D081098**, where unchanged stock `25081480` (`addiu t0,t0,0x1480`) resumes the descriptor interpreter. Never call or jump back to the redirected entry from the trampoline: doing so would recurse.

Use `[0x9D001240,0x9D00125C)`, seven instructions/28 bytes, wholly inside the already reviewed wrapper candidate extent. It does not overlap guarded sbrk beginning 0x9D001280 or the documented voice_sysex helper extent. This reuses existing placement evidence; it does not repeat ownership searches or resolve absent current branch inputs. The obsolete nine-word wrapper is not part of the revised design; unused remaining bytes are left stock.

```text
9D001240 3C088005 lui t0 0x8005
9D001244 AD007ADC sw zero 0x7adc t0
9D001248 AD007AD8 sw zero 0x7ad8 t0
9D00124C 03E01821 addu v1 ra zero
9D001250 3C089D00 lui t0 0x9d00
9D001254 0B420426 j 0x9d081098
9D001258 00000000 nop
```

Readiness is cleared first at 0x80057ADC, then pointer at 0x80057AD8. Both stores precede any original DINIT descriptor writes, including allocator reset. No invalidation store is put in a transfer delay slot. This improves entry sequencing; it is not an atomic eight-byte transaction or a concurrency protocol. Consumers must be quiesced for lifetime reset, and no stale pointer already held in a register becomes safe simply by clearing the record.

Keep the four previous allocator changes: 0x9D07FB40 `24843FF8`, 0x9D081868 `24633FF8`, 0x9D080B98 `0B4004A0`, 0x9D080B9C `00000000`, plus the unchanged 94-word guard. There are six stock replacement sites in the revised design, two DINIT-entry sites and four allocator sites. Do not combine the obsolete cold target edits or obsolete wrapper with this trampoline.

## Actual register/return contract

The entry hook uses j, not jal: RA remains the caller's return address. The trampoline does not create a stack frame and does not use t7. It temporarily uses t0, which original DINIT overwrites immediately; t0 is restored to exactly its displaced stock value before continuation. It copies RA to v1 exactly as the original entry did. No a-register, saved register, GP, SP, fp or other temporary register is touched by the hook.

At 0x9D081098 the register state therefore matches stock DINIT at that same point. Original descriptor parsing, v1-based return, delays and side effects execute unchanged; the only additional architectural memory effect is clearing the two B4 controls. Existing DINIT register preservation assumptions are preserved rather than adding a t7 convention. Interrupt/MMIO behavior remains subject to existing hardware conventions; the harness does not prove asynchronous behavior.

Raw stock bytes establish both displaced words and the continuation word. The connected Ghidra request returned “No function found” for this address in the current session, so no fresh named-function decompilation is claimed; raw instructions and differential execution supply this review's evidence.

## Integration results

Run `python3 b4_control_integration_harness.py --entry-hook`. Results: `b4_control_entry_hook_results.json`. Legacy mode remains available as the prior negative control. The harness independently checks new helper numeric encodings and jump targets, asserts original replacement-site bytes, and executes real stock DINIT/malloc/free/lazy initialization/provider/memset alongside the overlay guard. No patched binary is emitted.

The previously failing direct-DINIT case now requires both control words to become zero, allocator state to reset, and a fresh allocation reusing the same address to remain unpublished/inactive. Cold startup still executes original entry through the unchanged jalr call. Existing exhaustion, reload retention, free/reuse, minimum retry, first-allocation failure and caller-boundary tests remain enabled.

Additional differential test executes unmodified stock DINIT and entry-hook DINIT from identical RAM/register inputs. It compares all 32 final registers, modeled MMIO and every RAM byte outside `[0x00057AD8,0x00057AE0)`. Those must match exactly. Hooked controls must be zero; stock controls remain their published values. This checks actual DINIT behavior, including preservation of t7, rather than only callee-saved sentinels.

See the accompanying revised test report for recorded outcomes and limitations.

## Allocator-only resets still require separate handling

Yes. A reset that clears/reconstructs malloc metadata or heap lifetime **without entering 0x9D081090** does not execute this hook. The sbrk bounds guard validates addresses; it cannot distinguish a stale allocation from a new allocation at the same valid address.

The harness explicitly simulates clearing the known allocator/provider globals `[0x80053A4C,0x80053A90)` while a root is active. The active control record survives and the allocator returns the same address. This is a demonstrable consequence of an allocator-only reset, not evidence of an additional real stock reset caller. No new exact stock site is inferred or patched.

Any established full allocator-lifetime reset must quiesce consumers, clear readiness then pointer before resetting allocation state, and leave the extension inactive until fresh allocation/initialization completes. Cache reload that preserves allocation ownership must retain the pointer and must not invoke lifetime reset. Lazy initialization is not an unconditional root-clear hook: indiscriminately clearing there would conflate initial heap setup with coordinated lifetime reset and hide stale ownership.

Remaining blockers are allocator-only/interior reset-route closure, consumer synchronization, physical/helper ownership limits already recorded, and current voice_sysex merge inputs. No allocation protocol, firmware build or flashing recommendation follows.
