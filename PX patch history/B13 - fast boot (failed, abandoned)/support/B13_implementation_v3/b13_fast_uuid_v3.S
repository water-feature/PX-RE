    .text
    .p2align 4
    .globl b13_fast_uuid_v3
    .type b13_fast_uuid_v3,@function
b13_fast_uuid_v3:
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

    # Parse stock-style non-empty tokens from header; token index counts tokens,
    # not delimiter positions. Locate the exact token "UUID".
    movq %r8, %r10
    xorl %ecx, %ecx              # token index
.Lheader_next:
.Lheader_skip_tabs:
    cmpb $0x09, (%r10)
    jne .Lheader_token
    incq %r10
    jmp .Lheader_skip_tabs
.Lheader_token:
    cmpb $0, (%r10)
    je .Lfallback                # UUID header absent
    movq %r10, %rsi              # token start
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
    jne .Lheader_not_uuid
    cmpl $0x44495555, (%rsi)      # little-endian "UUID"
    je .Lhave_uuid_column
.Lheader_not_uuid:
    incl %ecx
    cmpb $0, (%r10)
    je .Lfallback
    incq %r10                    # consume tab
    jmp .Lheader_next
.Lhave_uuid_column:
    movl %ecx, 0x04(%rsp)        # UUID token index

    # Skip CR/LF left by CRLF or blank lines, matching stock's empty-line loop.
    movq 0x10(%rsp), %r10
.Lskip_line_breaks:
    movzbl (%r10), %eax
    cmpb $0x0d, %al
    je .Lskip_one_break
    cmpb $0x0a, %al
    jne .Ldata_line_start
.Lskip_one_break:
    incq %r10
    jmp .Lskip_line_breaks
.Ldata_line_start:
    testb %al, %al
    je .Lfallback
    movq %r10, %r11              # data line start

    # Require a complete first non-empty data line in the bounded read.
.Lfind_data_eol:
    movzbl (%r10), %eax
    testb %al, %al
    je .Lfallback
    cmpb $0x0a, %al
    je .Ldata_eol
    cmpb $0x0d, %al
    je .Ldata_eol
    incq %r10
    jmp .Lfind_data_eol
.Ldata_eol:
    movb $0, (%r10)

    # Select UUID-column token using the same skip-empty-token convention.
    movq %r11, %r10
    xorl %ecx, %ecx
    movl 0x04(%rsp), %edx
.Ldata_next:
.Ldata_skip_tabs:
    cmpb $0x09, (%r10)
    jne .Ldata_token
    incq %r10
    jmp .Ldata_skip_tabs
.Ldata_token:
    cmpb $0, (%r10)
    je .Lfallback
    movq %r10, %rsi              # token start
.Ldata_scan:
    movzbl (%r10), %eax
    testb %al, %al
    je .Ldata_token_end
    cmpb $0x09, %al
    je .Ldata_token_end
    incq %r10
    jmp .Ldata_scan
.Ldata_token_end:
    cmpl %edx, %ecx
    je .Lgot_uuid_token
    incl %ecx
    cmpb $0, (%r10)
    je .Lfallback
    incq %r10
    jmp .Ldata_next

.Lgot_uuid_token:
    # NUL-terminate token if it ended at a tab, then use stock GUID converter.
    movb $0, (%r10)
    movq %rsi, %rdi
    movq %r12, %rsi
    call b13_StrToGUID
    xorl %eax, %eax              # stock success code
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
    .size b13_fast_uuid_v3, .-b13_fast_uuid_v3
