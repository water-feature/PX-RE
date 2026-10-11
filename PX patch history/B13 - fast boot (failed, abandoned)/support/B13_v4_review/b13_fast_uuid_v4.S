    .text
    .p2align 4
    .globl b13_fast_uuid_v4
    .type b13_fast_uuid_v4,@function
b13_fast_uuid_v4:
    .cfi_startproc
    pushq %r12
    .cfi_def_cfa_offset 16
    .cfi_offset %r12, -16
    movq 24(%rsp), %r12          # caller's 8th integer arg: UUID output
    pushq %r13
    .cfi_def_cfa_offset 24
    .cfi_offset %r13, -24
    pushq %r14
    .cfi_def_cfa_offset 32
    .cfi_offset %r14, -32
    pushq %r15
    .cfi_def_cfa_offset 40
    .cfi_offset %r15, -40
    pushq %rbx
    .cfi_def_cfa_offset 48
    .cfi_offset %rbx, -48
    subq $0x220, %rsp
    .cfi_def_cfa_offset 592

    movq %rdi, %r13              # cache this (fallback)
    movq %rsi, %r14              # .grp path
    movq %rdx, %r15              # velocity-volume path (fallback)

    # fd = open(grp_path, O_RDONLY)
    movq %r14, %rdi
    xorl %esi, %esi
    xorl %eax, %eax
    call b13_open
    testl %eax, %eax
    js .Lfallback
    movl %eax, %ebx

    # n = read(fd, buf, 0x1ff); buf is 0x200 bytes incl NUL.
    movl %ebx, %edi
    leaq 0x20(%rsp), %rsi
    movl $0x1ff, %edx
    call b13_read
    movq %rax, 0x08(%rsp)

    movl %ebx, %edi
    call b13_close

    movq 0x08(%rsp), %rax
    testq %rax, %rax
    jle .Lfallback
    leaq 0x20(%rsp), %r8         # buffer start
    movb $0, (%r8,%rax)          # bounded terminator

    # Find end of header line. A complete line is required in the bounded read.
    movq %r8, %r10
.Lfind_header_eol:
    movzbl (%r10), %eax
    testb %al, %al
    je .Lfallback
    cmpb $0x0a, %al
    je .Lheader_eol
    cmpb $0x0d, %al
    je .Lheader_eol
    incq %r10
    jmp .Lfind_header_eol
.Lheader_eol:
    leaq 1(%r10), %rax
    movq %rax, 0x10(%rsp)        # start search for first data row
    movb $0, (%r10)              # terminate header in-place

    # This helper is scoped to the startup call, whose output is pre-zeroed
    # and whose return code is ignored. UUID-bearing files use the full parser.
    movl $0, 0x04(%rsp)       # present Mono Pitch / Mono Collapse flags
    movq %r8, %r10
.Lheader_next:
    cmpb $0x09, (%r10)
    jne .Lheader_token
    incq %r10
    jmp .Lheader_next
.Lheader_token:
    cmpb $0, (%r10)
    je .Lzero_uuid_check
    movq %r10, %rsi
.Lheader_scan:
    movzbl (%r10), %eax
    testb %al, %al
    je .Lheader_token_end
    cmpb $0x09, %al
    je .Lheader_token_end
    incq %r10
    jmp .Lheader_scan
.Lheader_token_end:
    movq %r10, %rax
    subq %rsi, %rax
    cmpq $4, %rax
    jne .Lheader_other
    cmpl $0x44495555, (%rsi)
    je .Lfallback
.Lheader_other:
    cmpq $10, %rax
    jne .Lcheck_collapse
    movabsq $0x746950206f6e6f4d, %rax # "Mono Pit"
    cmpq %rax, (%rsi)
    jne .Lheader_not_uuid
    cmpw $0x6863, 8(%rsi)          # "ch"
    jne .Lheader_not_uuid
    orl $1, 0x04(%rsp)
    jmp .Lheader_not_uuid
.Lcheck_collapse:
    cmpq $13, %rax
    jne .Lheader_not_uuid
    movabsq $0x6c6f43206f6e6f4d, %rax # "Mono Col"
    cmpq %rax, (%rsi)
    jne .Lheader_not_uuid
    cmpl $0x7370616c, 8(%rsi)      # "laps"
    jne .Lheader_not_uuid
    cmpb $0x65, 12(%rsi)          # "e"
    jne .Lheader_not_uuid
    orl $2, 0x04(%rsp)
.Lheader_not_uuid:
    cmpb $0, (%r10)
    je .Lzero_uuid_check
    incq %r10
    jmp .Lheader_next
.Lzero_uuid_check:
    # Stock maps absent fields to token index 15, not an invalid index.
    # An absent earlier field intercepts token 15 before the UUID handler.
    # Require Mono Pitch or Mono Collapse to be absent to prove UUID unreachable.
    cmpl $3, 0x04(%rsp)
    je .Lfallback
.Lzero_uuid:
    movq $0, (%r12)
    movq $0, 8(%r12)
    movb $0, 16(%r12)
    xorl %eax, %eax
    jmp .Lreturn

.Lfallback:
    # Exact call-site fallback: preserve stock behavior for malformed/unusual files.
    movq %r13, %rdi
    movq %r14, %rsi
    movq %r15, %rdx
    xorl %ecx, %ecx
    xorl %r8d, %r8d
    xorl %r9d, %r9d
    pushq %r12
    .cfi_adjust_cfa_offset 8
    pushq $0
    .cfi_adjust_cfa_offset 8
    call b13_GetGroupFileInfo
    addq $16, %rsp
    .cfi_adjust_cfa_offset -16

.Lreturn:
    addq $0x220, %rsp
    .cfi_def_cfa_offset 48
    popq %rbx
    .cfi_def_cfa_offset 40
    popq %r15
    .cfi_def_cfa_offset 32
    popq %r14
    .cfi_def_cfa_offset 24
    popq %r13
    .cfi_def_cfa_offset 16
    popq %r12
    .cfi_def_cfa_offset 8
    ret
    .cfi_endproc
    .size b13_fast_uuid_v4, .-b13_fast_uuid_v4

.section .note.GNU-stack,"",@progbits
