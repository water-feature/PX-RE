# SPDX-License-Identifier: GPL-2.0-or-later
"""Pure assembly source emitter extracted from reviewed B5 source."""
JUMPS = [('forward', 263613, {'size': 11, 'sha256': 'e29a896de7c775fd1cdde012acce7fbbe28e2bca4ea23530ecac1a85e36eb194'}, 263624, 176), ('reverse', 263284, {'size': 11, 'sha256': 'e29a896de7c775fd1cdde012acce7fbbe28e2bca4ea23530ecac1a85e36eb194'}, 263295, 176), ('geometry', 261097, {'size': 9, 'sha256': 'f70bb3145cf1165ad717bcb1734d71dfa68108939486cfafb44095d0ca67dbd1'}, 261106, 176), ('prepare', 226021, {'size': 6, 'sha256': '8363b53dbf73b2fd335ea443b3ca98f8ab9c434349c91623f00c749275b9ecfb'}, 226027, 144), ('note_on', 222280, {'size': 7, 'sha256': '0ae783f1fbea99e134aa4bdbf3f1422dce3c6be80cd27d065beba76d735ce542'}, 222287, 64), ('reset', 248048, {'size': 6, 'sha256': 'd9483df69699427b7878676dfa5f99c39a3cc09362d3d12c8190c2ffe81eb72f'}, 248054, 8), ('return', 226454, {'size': 7, 'sha256': 'e42328b759e3f0e03f14bc73242ae8277379bfd7a79dc9a2cd1af195ff687511'}, 226461, 144), ('eof', 262240, {'size': 7, 'sha256': '083d481d167567303eb1b342a5b0f715280710ac77d53a5aaec8849fea711d77'}, 262247, 176)]
CALLS = [('read', 248961, 260160, 8), ('load', 226147, 189152, 9), ('filter', 226374, 224032, 10), ('publish', 249193, 268272, 11)]
BINDINGS = {'b5_ram_vtable': 2745576, 'b5_stack_guard_got': 2752424, 'b5_geometry_default': 265280, 'b5_continue_forward': 263624, 'b5_continue_reverse': 263295, 'b5_continue_geometry': 261106, 'b5_continue_prepare': 226027, 'b5_continue_note_on': 222287, 'b5_continue_reset': 248054, 'b5_continue_return': 226461, 'b5_continue_eof': 262247, 'b5_original_read': 260160, 'b5_original_load': 189152, 'b5_original_filter': 224032, 'b5_original_publish': 268272}
REGS = ['rax', 'rcx', 'rdx', 'rsi', 'rdi', 'r8', 'r9', 'r10', 'r11', 'rbx', 'rbp', 'r12', 'r13', 'r14', 'r15']
INHERITED = {'rbx': -56, 'rbp': -48, 'r12': -40, 'r13': -32, 'r14': -24, 'r15': -16}

def assembly():
    out = ['.text']
    for name, cfa, event, call in [(n, c, i, False) for i, (n, _, _, _, c) in enumerate(JUMPS)] + [(n, 8, e, True) for n, _, _, e in CALLS]:
        label = 'b5_wrap_' + name if call else 'b5_hook_' + name
        dummy = call or name == 'reset'
        extra = 8 if dummy else 0
        out += ['.p2align 4', f'.globl {label}', f'.hidden {label}', f'.type {label},@function', label + ':', '.cfi_startproc', f'.cfi_def_cfa %rsp,{cfa}', '.cfi_offset %rip,-8']
        if not dummy:
            out += [f'.cfi_offset %{r},{o}' for r, o in INHERITED.items()]
        if dummy:
            out += ['pushq $0', '.cfi_adjust_cfa_offset 8']
        out += ['pushfq', '.cfi_adjust_cfa_offset 8']
        for i, r in enumerate(REGS):
            out += [f'pushq %{r}', '.cfi_adjust_cfa_offset 8']
            if dummy or r not in INHERITED:
                out += [f'.cfi_offset %{r},-{cfa + extra + 16 + 8 * i}']
        out += ['subq $256,%rsp', '.cfi_adjust_cfa_offset 256']
        out += [f'movdqu %xmm{i},{i * 16}(%rsp)' for i in range(16)]

        def dispatch(e):
            return ['movq %rsp,%rdi', f'movl ${e},%esi', f'leaq {384 + extra}(%rsp),%rdx', 'call b5_dispatch']
        out += dispatch(event)
        if call:
            out += [f'movdqu {i * 16}(%rsp),%xmm{i}' for i in range(16)]
            out += [f'movq {376 - 8 * (i + 1)}(%rsp),%{r}' for i, r in enumerate(REGS)]
            out += ['pushq 376(%rsp)', '.cfi_adjust_cfa_offset 8', 'popfq', '.cfi_adjust_cfa_offset -8', f'call b5_original_{name}']
            if name == 'read':
                out += ['.globl b5_read_original_return', '.hidden b5_read_original_return', 'b5_read_original_return:']
            out += [f'movq %{r},{376 - 8 * (i + 1)}(%rsp)' for i, r in enumerate(REGS[:9])]
            out += ['pushfq', '.cfi_adjust_cfa_offset 8', 'popq %r11', '.cfi_adjust_cfa_offset -8', 'movq %r11,376(%rsp)']
            out += [f'movdqu %xmm{i},{i * 16}(%rsp)' for i in range(16)]
            out += dispatch(event | 128)
        out += [f'movdqu {i * 16}(%rsp),%xmm{i}' for i in range(16)]
        out += ['leaq 256(%rsp),%rsp', '.cfi_adjust_cfa_offset -256']
        for r in reversed(REGS):
            out += [f'popq %{r}']
            if dummy or r not in INHERITED:
                out += [f'.cfi_restore %{r}']
            out += ['.cfi_adjust_cfa_offset -8']
        out += ['popfq', '.cfi_adjust_cfa_offset -8']
        if dummy:
            out += ['leaq 8(%rsp),%rsp', '.cfi_adjust_cfa_offset -8']
        if call:
            out += ['retq']
        else:
            if name in ('forward', 'reverse'):
                out += ['cmpb $0,0x20(%rsp)', 'movzbl 0x3c(%rsp),%r11d']
            elif name == 'geometry':
                out += ['cmpl $-1,%edx', 'je b5_geometry_default']
            elif name == 'prepare':
                out += ['movq (%rdi),%rax', 'call *0x68(%rax)']
            elif name == 'note_on':
                out += ['movq 0x30(%rbp),%rdi', 'movq (%rdi),%rax']
            elif name == 'return':
                out += ['movq b5_stack_guard_got(%rip),%rbx']
            elif name == 'eof':
                out += ['movq (%rsp),%rax', 'testq %rax,%rax']
            elif name == 'reset':
                out += ['pushq %r12', '.cfi_adjust_cfa_offset 8', '.cfi_offset %r12,-16', 'xorl %r12d,%r12d', 'pushq %rbp', '.cfi_adjust_cfa_offset 8', '.cfi_offset %rbp,-24']
            out += [f'jmp b5_continue_{name}']
        out += ['.cfi_endproc', f'.size {label},.-{label}']
    return '\n'.join(out) + '\n'
