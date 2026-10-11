.text
.globl original_read
.type original_read,@function
original_read:
.cfi_startproc
pushq %r15
.cfi_adjust_cfa_offset 8
.cfi_offset %r15,-16
pushq %r14
.cfi_adjust_cfa_offset 8
.cfi_offset %r14,-24
pushq %r13
.cfi_adjust_cfa_offset 8
.cfi_offset %r13,-32
pushq %r12
.cfi_adjust_cfa_offset 8
.cfi_offset %r12,-40
jmp read_resume
.cfi_endproc
.size original_read,.-original_read
.globl original_update
.type original_update,@function
original_update:
.cfi_startproc
cmpl $4096,%esi
jmp update_resume
.cfi_endproc
.size original_update,.-original_update
.globl fade_hook
.type fade_hook,@function
fade_hook:
.cfi_startproc
subq $72,%rsp
.cfi_adjust_cfa_offset 72
movq 80(%rsp),%rax
movq %rax,0(%rsp)
movq 88(%rsp),%rax
movq %rax,8(%rsp)
movq 96(%rsp),%rax
movq %rax,16(%rsp)
movq 104(%rsp),%rax
movq %rax,24(%rsp)
movq 112(%rsp),%rax
movq %rax,32(%rsp)
movq %rbx,40(%rsp)
movq 72(%rsp),%rax
subq $5,%rax
/* Return addresses are runtime addresses: subtract the runtime image base. */
leaq image_anchor(%rip),%r10
subq $0x1012c0,%r10
subq %r10,%rax
movq %rax,48(%rsp)
call entry_fade
addq $72,%rsp
.cfi_adjust_cfa_offset -72
ret
.cfi_endproc
.size fade_hook,.-fade_hook
.globl reverse_read_hook
.type reverse_read_hook,@function
reverse_read_hook:
.cfi_startproc
pushq %rax
.cfi_adjust_cfa_offset 8
movq 0x1a8(%rbx),%rax
testb $8,0x500(%rax)
je 2f
cmpl $0,0x40(%rsp)
je 2f
cmpq 0xb8(%rbx),%r15
jne 2f
movl 0x90(%rbx),%eax
addl %r12d,%eax
cmpl %r11d,%eax
jge 2f
cmpl 0x28(%rsp),%eax
jle 2f
subl %r8d,%edx
2: popq %rax
.cfi_adjust_cfa_offset -8
jmp local_read
.cfi_endproc
.size reverse_read_hook,.-reverse_read_hook
.globl close_hook
.type close_hook,@function
close_hook:
.cfi_startproc
pushq %rax
.cfi_adjust_cfa_offset 8
movq 0x1a8(%rdi),%rax
testq %rax,%rax
je 1f
movl $0,0x500(%rax)
1: popq %rax
.cfi_adjust_cfa_offset -8
cmpq $0,0x88(%rdi)
jmp close_resume
.cfi_endproc
.size close_hook,.-close_hook
.globl open_hook
.type open_hook,@function
open_hook:
.cfi_startproc
.cfi_def_cfa_offset 176
.cfi_offset %r15,-16
.cfi_offset %r14,-24
.cfi_offset %r13,-32
.cfi_offset %r12,-40
.cfi_offset %rbp,-48
.cfi_offset %rbx,-56
pushq %rax
.cfi_adjust_cfa_offset 8
movq 0x1a8(%r15),%rax
movl $0,0x500(%rax)
popq %rax
.cfi_adjust_cfa_offset -8
movb $0,8(%r15)
jmp open_resume
.cfi_endproc
.size open_hook,.-open_hook
