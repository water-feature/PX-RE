.text
.globl _run_mapper
_run_mapper:
 pushq %rbp
 pushq %rbx
 pushq %r12
 pushq %r13
 pushq %r14
 pushq %r15
 subq $8,%rsp
 movq %rdx,%r12
 movl %esi,0x18(%r12)
 leaq 0x258(%rcx),%rbp
 movq %rcx,%rbx
 movq %r8,%r15
 pxor %xmm1,%xmm1
 pxor %xmm7,%xmm7
 movss Lfifteen(%rip),%xmm2
 callq *%rdi
 addq $8,%rsp
 popq %r15
 popq %r14
 popq %r13
 popq %r12
 popq %rbx
 popq %rbp
 retq
.p2align 2
Lfifteen: .long 0x41700000
