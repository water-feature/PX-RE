.text
.p2align 4
.globl b15_message_entry
.type b15_message_entry,@function
b15_message_entry:
.cfi_startproc
pushq %rbx
.cfi_def_cfa_offset 16
.cfi_offset %rbx,-16
subq $16,%rsp
.cfi_def_cfa_offset 32
movq %rdi,%rbx
movl %esi,0(%rsp)
movl %edx,4(%rsp)
call b15_qnx_before
testl %eax,%eax
jne 1f
movq %rbx,%rdi
movl 0(%rsp),%esi
movl 4(%rsp),%edx
call b15_original_message
movq %rbx,%rdi
movl 0(%rsp),%esi
movl 4(%rsp),%edx
call b15_qnx_after
1: addq $16,%rsp
.cfi_def_cfa_offset 16
popq %rbx
.cfi_def_cfa_offset 8
ret
.cfi_endproc
.size b15_message_entry,.-b15_message_entry
.globl b15_original_message
.type b15_original_message,@function
b15_original_message:
.cfi_startproc
pushq %rbp
.cfi_def_cfa_offset 16
.cfi_offset %rbp,-16
movq %rsp,%rbp
.cfi_def_cfa_register %rbp
pushq %r15
.cfi_offset %r15,-24
jmp b15_stock_message_continue
.cfi_endproc
.size b15_original_message,.-b15_original_message

.globl b15_noteon_thunk
.type b15_noteon_thunk,@function
b15_noteon_thunk:
.cfi_startproc
subq $40,%rsp
.cfi_def_cfa_offset 48
movq %rdi,0(%rsp)
movq %rsi,8(%rsp)
movl %r8d,16(%rsp)
movl %r9d,20(%rsp)
movl -0x848(%rbp),%eax
movl %eax,24(%rsp)
call b15_stock_noteon
movq 0(%rsp),%rax
movq 8(%rsp),%r8
cmpq %r8,0x20(%rax)
jne 1f
movq %r15,%rdi
movl 16(%rsp),%esi
movl 20(%rsp),%edx
movl 24(%rsp),%ecx
call b15_qnx_note_accepted
1: addq $40,%rsp
.cfi_def_cfa_offset 8
ret
.cfi_endproc
.size b15_noteon_thunk,.-b15_noteon_thunk

.globl b15_attempt_thunk
.type b15_attempt_thunk,@function
b15_attempt_thunk:
.cfi_startproc
subq $24,%rsp
.cfi_def_cfa_offset 32
movq %rdi,0(%rsp)
movl %esi,8(%rsp)
movl %edx,12(%rsp)
cmpl $0x5d,%edx
sete %dl
movzbl %dl,%edx
movl -0x848(%rbp),%ecx
movq %r15,%rdi
call b15_qnx_note_attempt
movq 0(%rsp),%rdi
movl 8(%rsp),%esi
movl 12(%rsp),%edx
call b15_stock_getparam
addq $24,%rsp
.cfi_def_cfa_offset 8
ret
.cfi_endproc
.size b15_attempt_thunk,.-b15_attempt_thunk

.globl b15_group_clear_thunk
.type b15_group_clear_thunk,@function
b15_group_clear_thunk:
.cfi_startproc
/* Interior detour: inherit the established outer frame, not a new return slot. */
.cfi_def_cfa %rbp,16
.cfi_offset %rbp,-16
.cfi_offset %r15,-24
.cfi_offset %r14,-32
.cfi_offset %r13,-40
.cfi_offset %r12,-48
.cfi_offset %rbx,-56
pushfq
pushq %rax
pushq %rcx
pushq %rdx
pushq %rsi
pushq %rdi
pushq %r8
pushq %r9
pushq %r10
pushq %r11
movq %r12,%rsi
subq %r15,%rsi
shrq $3,%rsi
movq %r15,%rdi
call b15_qnx_group_clear
popq %r11
popq %r10
popq %r9
popq %r8
popq %rdi
popq %rsi
popq %rdx
popq %rcx
popq %rax
popfq
movq $0,0x1fb8(%r12)
jmp b15_stock_group_continue
.cfi_endproc
.size b15_group_clear_thunk,.-b15_group_clear_thunk
.section .note.GNU-stack,"",@progbits
