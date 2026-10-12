.text
.type completion_apply,@function
.globl completion_apply
completion_apply:
.Lbase:
 xorl %eax,%eax
 movl (%rdi),%ecx
 cmpl (%rsi),%ecx
 jne fail
 movl 4(%rdi),%ecx
 cmpl 4(%rsi),%ecx
 jne fail
 movl 12(%rdi),%ecx
 cmpl 12(%rsi),%ecx
 jne fail
 movl 16(%rdi),%ecx
 cmpl 16(%rsi),%ecx
 jne fail
 movl 8(%rsi),%ecx
 cmpl 8(%rdi),%ecx
 je success
 # rdi = &state.effective, 72 bytes into State.
 cmpl $0,84(%rdi)
 je fail
 movq -56(%rdi),%rdx
 cmpq -40(%rdi),%rdx
 jb fail
 movl %ecx,8(%rdi)
success:
 movl $1,%eax
fail:
 ret
.p2align 4
.type completion_geom,@function
.globl completion_geom
completion_geom:
 # rdi=State; r9d=observed rate; r8d=reverse; esi=loop.
 cmpl 80(%rdi),%r9d
 je geom_pass
 cmpl $0,156(%rdi)
 je geom_cancel
 movq 16(%rdi),%r11
 cmpq 32(%rdi),%r11
 jb geom_cancel
 # Check all remaining source identity fields before updating rate.
 cmpl %r8d,84(%rdi)
 jne geom_cancel
 cmpl %esi,88(%rdi)
 jne geom_cancel
 movl %r9d,80(%rdi)
geom_pass:
 jmp .Lbase+(0xf1730+0x498-0xf3c40)
geom_cancel:
 jmp .Lbase+(0xf1730+0x4a7-0xf3c40)
