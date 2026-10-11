# Branch 4 — timer callback registration, pass 12

2 October 2026. Unmodified stock firmware. No build or flash; separate group-feature build and later voice_sysex integration remain the intended deliverables.

## Callback writer recovered and checked

The unresolved low-priority interrupt call at 0x9D05BE6C reads its target at parent-object+0x34 and argument at parent+0x38. Registration routine 0x9D05C4E4 receives a handle pointing to parent+0x24. At 0x9D05C540 it loads the fifth argument from the caller's stack; 0x9D05C544 stores it at handle+0x10, which is parent+0x34. The next stores write the callback argument at handle+0x14 (parent+0x38).

The direct call at 0x9D075644 supplies target 0x9D074F0C via a LUI/ADDIU pair at 0x9D07562C/630 and stack store at 634. It passes timer state 0x80053810 as the callback argument. Actual MIPS execution of the valid registration prefix through 0x9D05C54C confirmed both destination fields.

Target 0x9D074F0C is an eleven-instruction leaf: it compares the incoming counter with the previous counter unsigned, increments a wrap counter when the incoming value is lower, saves the incoming value and sets a pending byte. There are no calls or stack allocations. Five actual MIPS executions checked increasing, equal and wrapping values, including 0xFFFFFFFF to zero; all passed, with unchanged SP.

An aligned raw-word scan finds three direct jump/call candidates to the registration routine: the observed caller and two tail wrappers at 0x9D05C764/76C. Neither wrapper has direct or aligned literal-pointer references in this scan. This does not exclude constructed function pointers, copies or other aliases. Consequently the callback target is established for the observed registration path, not proven exhaustive for every possible writer. The global reachability result deliberately retains this edge as open pending that proof.

## Controller alias writes recovered

Routine 0x9D05B59C constructs controller addresses from the parent object's word at offset 0x14. Let n be that word, q=n>>5, and m=1 shifted left by n using MIPS variable-shift behavior. It writes m to 0xBF810044+16*q and 0xBF8100C8+16*q at PCs 0x9D05B5D8/DC. The routine is called from the registration path at 0x9D05C5EC. Thus the pass11 literal-address candidate scan was incomplete in a concrete, demonstrated way. These writes require parent-object initialization tracing to recover the actual n values. No device-specific register names or global interrupt nesting limit are inferred here.

## Remaining work

Recover initialization of the two parent objects and their controller index/priority fields, trace remaining callback aliases and mainline activation cycles, and include delay-slot effects in stack analysis. RAM relocation remains unproven. The candidate cache must not be treated as safely reserved based only on the free address gap or this leaf callback.

Evidence: verify_timer_callback.py and timer_callback_results.json. Emulator scope is the registration prefix and callback leaf; MMIO setup and whole interrupt transactions were not executed.
