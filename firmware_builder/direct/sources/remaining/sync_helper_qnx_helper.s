# B16 ELF virtual addresses are resolved by build.py; no stack changes.
.text
.globl b16_helper
b16_helper:
 movl 0x18(%r12), %eax
 subl $16, %eax
 cmpl $1, %eax
 jbe .Lnew
 cvtsi2ssl 0x18(%r12), %xmm1
 jmp resume_old
.Lnew:
 addl $1, %eax
 negl %eax
 cvtsi2ssl %eax, %xmm1
 mulss %xmm2, %xmm0
 addss %xmm1, %xmm0
 ucomiss %xmm7, %xmm0
 jae resume_positive
 movss .Lminusone(%rip), %xmm1
 ucomiss %xmm1, %xmm0
 jb .Llower
 addss .Lone(%rip), %xmm0
 movss .Lhalf(%rip), %xmm1
 jmp .Laffine
.Llower:
 addss .Ltwo(%rip), %xmm0
 movss .Lquarter(%rip), %xmm1
.Laffine:
 maxss %xmm7, %xmm0
 mulss runtime_s0(%rip), %xmm1
 mulss %xmm1, %xmm0
 addss %xmm1, %xmm0
 movq 0x20c0(%r15), %rdi
 movl -0x258(%rbp), %esi
 jmp resume_duration
.globl b16_code_end
b16_code_end:
.p2align 2
.Lminusone: .long 0xbf800000
.Lone: .long 0x3f800000
.Ltwo: .long 0x40000000
.Lhalf: .long 0x3f000000
.Lquarter: .long 0x3e800000
