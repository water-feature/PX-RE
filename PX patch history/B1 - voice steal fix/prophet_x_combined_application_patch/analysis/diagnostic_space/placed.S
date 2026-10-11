.intel_syntax noprefix
.section .quiet,"ax"
.global px_quiet_voice
.type px_quiet_voice,@function
# Input: rdi=audio loop; esi=nonzero individual-voice bitmask.
# Prototype: valid nonzero mask, one requester, running coordinator, no startup lock held.
# Always use handshake; avoid an unsynchronized amp-state fast path.
px_quiet_voice:
    push rbx
    push r12
    push r13
    mov rbx, rdi
    mov r12d, esi
    lea r13, [rbx+0x3648]
    mov rdi, r13
    call px_mutex_lock
    mov [rbx+0x3644], r12d
.Lwait:
    cmp DWORD PTR [rbx+0x3644], 0
    je .Ldone
    lea rdi, [rbx+0x3650]
    mov rsi, r13
    call px_cond_wait
    jmp .Lwait
.Ldone:
    mov rdi, r13
    call px_mutex_unlock
    pop r13
    pop r12
    pop rbx
.Lreturn:
    ret
.size px_quiet_voice,.-px_quiet_voice


.section .hooks,"ax"
# CALL in seven-byte NOP at 0x21399, once per note message.
# Scratch bytes unused in reachable voice path, reused by other message paths.
.global px_batch_init
.type px_batch_init,@function
px_batch_init:
    mov BYTE PTR [rbp-0x817],0
    mov DWORD PTR [rbp-0x814],0
    ret
.size px_batch_init,.-px_batch_init

# JMP at 0x21489; first scan accumulates without oscillator shutdown.
.global px_collect_hook
.type px_collect_hook,@function
px_collect_hook:
    cmp BYTE PTR [rbp-0x817],0
    jne .Lclose
    bts DWORD PTR [rbp-0x814],ebx
    jmp px_scan_next
.Lclose:
    movsxd r13,r12d
    mov ecx,ebx
    jmp px_collect_return
.size px_collect_hook,.-px_collect_hook

# JMP at 0x215b8; wait once then repeat original scan in close phase.
.global px_batch_wait_hook
.type px_batch_wait_hook,@function
px_batch_wait_hook:
    cmp BYTE PTR [rbp-0x817],0
    jne .Loriginal_wait
    mov BYTE PTR [rbp-0x817],1
    mov esi,DWORD PTR [rbp-0x814]
    test esi,esi
    je .Lrescan
    mov rdi,r15
    call px_quiet_voice
.Lrescan:
    jmp px_scan_start
.Loriginal_wait:
    mov r11d,DWORD PTR [rbp-0x810]
    jmp px_batch_wait_return
.size px_batch_wait_hook,.-px_batch_wait_hook

# JMP from 0x216bf, displace original 7-byte MOVSXD.
# Enter with original HandleMessage stack, aligned for calls.
.global px_fresh_hook
.type px_fresh_hook,@function
px_fresh_hook:
    lea rdi,[rip+px_startup_mutex]
    call px_mutex_lock
    mov rax,[r15+0x298]
    mov ecx,[rbp-0x808]
    mov BYTE PTR [rax+rcx],0
    mov BYTE PTR [rax+rcx+0x44],0
    movsxd rax,DWORD PTR [rbp-0x834]
    jmp px_fresh_return
.size px_fresh_hook,.-px_fresh_hook

# Replace existing CALL at 0x2174c. Fresh path already holds startup.
# Original rdi points at startup mutex, r14b distinguishes fresh/legato.
.global px_activation_lock_hook
.type px_activation_lock_hook,@function
px_activation_lock_hook:
    test r14b,r14b
    jne .Lheld
    jmp px_mutex_lock
.Lheld:
    ret
.size px_activation_lock_hook,.-px_activation_lock_hook

# JMP from 0x1b49e, displace original MOV + LEA (11 bytes).
# Existing coordinator acquisition at 0x1b7e5 must become five NOPs.
.global px_coordinator_hook
.type px_coordinator_hook,@function
px_coordinator_hook:
    lea rdi,[rip+px_startup_mutex]
    call px_mutex_lock
    mov esi,[rsp+0x3c]
    lea rax,[r15+0x2020]
    jmp px_coordinator_return
.size px_coordinator_hook,.-px_coordinator_hook

.section .stub,"ax"
.global px_debug_stub
.type px_debug_stub,@function
px_debug_stub:
    or eax,-1
    ret
.size px_debug_stub,.-px_debug_stub
