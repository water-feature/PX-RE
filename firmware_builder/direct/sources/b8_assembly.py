# SPDX-License-Identifier: GPL-2.0-or-later
"""Pure assembly source emitter extracted from reviewed B8 source."""
JUMPS = [('prepare', 226004, {'size': 7, 'sha256': 'c64495f9ceed5b96c965b8444405f3fa843a01fd10846a72498d35ec32deab55'}, 226011, 144), ('gate', 261165, {'size': 6, 'sha256': '0123a39e28cb9c884592372bdfb8ba10d1c00e83e5d6f6fb942094a6ad55b64c'}, 261171, 176), ('reset', 248054, {'size': 6, 'sha256': '8050aa90b16beae254509d9741ff0580be72f0c95adf59fe9478b7a5f83b5fea'}, 248060, 24), ('note', 222271, {'size': 9, 'sha256': '8a987a7b556f1599b2ce4332be797b0540ae8c5115bfb69bd5d6eb0a654a609e'}, 222280, 64), ('return', 226461, {'size': 5, 'sha256': '603ee83db6782f4c499fe945f3c08012e2ee658261921f1427f98af9558a1a44'}, 226466, 144)]
CALLS = [('open', 251026, 271968, 3)]
REGS = ['rax', 'rcx', 'rdx', 'rsi', 'rdi', 'r8', 'r9', 'r10', 'r11', 'rbx', 'rbp', 'r12', 'r13', 'r14', 'r15']

def assembly():
    out = ['.text']
    for name, cfa, event, call in [(n, c, {'note': 4, 'return': 5}.get(n, i), False) for i, (n, _, _, _, c) in enumerate(JUMPS)] + [('open', 8, 3, True)]:
        label = 'b8_wrap_open' if call else 'b8_hook_' + name
        extra = 16 if name in ['gate', 'note'] else 8 if cfa % 16 == 8 else 0
        inherited = {} if call else {'r12': -16, 'rbp': -24} if name == 'reset' else {'rbx': -56, 'rbp': -48, 'r12': -40, 'r13': -32, 'r14': -24, 'r15': -16}
        out += ['.p2align 4', f'.globl {label}', f'.hidden {label}', f'.type {label},@function', label + ':', '.cfi_startproc', f'.cfi_def_cfa %rsp,{cfa}', '.cfi_offset %rip,-8']
        out += [f'.cfi_offset %{r},{o}' for r, o in inherited.items()]
        if extra:
            out += [f'leaq -{extra}(%rsp),%rsp', f'.cfi_adjust_cfa_offset {extra}']
        out += ['pushfq', '.cfi_adjust_cfa_offset 8']
        for i, r in enumerate(REGS):
            out += [f'pushq %{r}', '.cfi_adjust_cfa_offset 8']
            if r not in inherited:
                out += [f'.cfi_offset %{r},-{cfa + extra + 16 + 8 * i}']
        out += ['subq $256,%rsp', '.cfi_adjust_cfa_offset 256']
        out += [f'movdqu %xmm{i},{i * 16}(%rsp)' for i in range(16)]

        def dispatch(e):
            return ['movq %rsp,%rdi', f'movl ${e},%esi', f'leaq {384 + extra}(%rsp),%rdx', 'call b8_dispatch']
        if name != 'note':
            out += dispatch(event)
        if call or name == 'note':
            out += [f'movdqu {i * 16}(%rsp),%xmm{i}' for i in range(16)]
            out += [f'movq {376 - 8 * (i + 1)}(%rsp),%{r}' for i, r in enumerate(REGS)]
            out += ['pushq 376(%rsp)', '.cfi_adjust_cfa_offset 8', 'popfq', '.cfi_adjust_cfa_offset -8']
            if call:
                out += ['pushq 408(%rsp)', '.cfi_adjust_cfa_offset 8', 'pushq 408(%rsp)', '.cfi_adjust_cfa_offset 8', 'call b8_original_open', 'leaq 16(%rsp),%rsp', '.cfi_adjust_cfa_offset -16']
            else:
                out += ['movq 0x18(%rbp),%rdi', 'call b8_original_resampler_reset']
            out += [f'movq %{r},{376 - 8 * (i + 1)}(%rsp)' for i, r in enumerate(REGS[:9])]
            out += ['pushfq', '.cfi_adjust_cfa_offset 8', 'popq %r11', '.cfi_adjust_cfa_offset -8', 'movq %r11,376(%rsp)']
            out += [f'movdqu %xmm{i},{i * 16}(%rsp)' for i in range(16)]
            out += dispatch(event | 128 if call else event)
        out += [f'movdqu {i * 16}(%rsp),%xmm{i}' for i in range(16)]
        out += ['leaq 256(%rsp),%rsp', '.cfi_adjust_cfa_offset -256']
        for r in reversed(REGS):
            out += [f'popq %{r}']
            if r not in inherited:
                out += [f'.cfi_restore %{r}']
            out += ['.cfi_adjust_cfa_offset -8']
        out += ['popfq', '.cfi_adjust_cfa_offset -8']
        if extra:
            out += [f'leaq {extra}(%rsp),%rsp', f'.cfi_adjust_cfa_offset -{extra}']
        if call:
            out += ['retq']
        elif name == 'prepare':
            out += ['movq 0x30(%r15),%rdi', 'movaps %xmm1,%xmm0', 'jmp b8_continue_prepare']
        elif name == 'gate':
            out += ['movl %eax,0x94(%rdi)', 'jmp *-16(%rsp)']
        elif name == 'reset':
            out += ['xorl %ebp,%ebp', 'pushq %rbx', '.cfi_adjust_cfa_offset 8', '.cfi_offset %rbx,-32', 'movq %rdi,%rbx', 'jmp b8_continue_reset']
        elif name == 'note':
            out += ['movq 0x30(%rbp),%rdi', 'movq (%rdi),%rax', 'jmp *-16(%rsp)']
        else:
            out += ['movq 0x48(%rsp),%rcx', 'jmp b8_continue_return']
        out += ['.cfi_endproc', f'.size {label},.-{label}']
    return '\n'.join(out) + '\n'
