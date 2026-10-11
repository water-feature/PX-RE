; Prophet X boot-trace helper for exact .15 ELF (sha256 dd9efbcd...a2fa)
; Assemble: nasm -f bin -DCODE_BASE=0x1016d0 trace.asm
; All calls/jumps are rel32 so size is independent of CODE_BASE.
bits 64
default rel
org CODE_BASE

TS            equ 0x2b21c0        ; 20 x u64 timestamps, in the +0x100 of RW bss
N_MARKERS     equ 20

PLT_CLOCK     equ 0x7510          ; clock_gettime@plt
PLT_REMOVE    equ 0x71f0          ; remove@plt
PLT_OPEN      equ 0x75a0          ; open@plt
PLT_WRITE     equ 0x7240          ; write@plt
PLT_CLOSE     equ 0x7810          ; close@plt
PLT_ERRNO     equ 0x77e0          ; __get_errno_ptr@plt

T_PROCMGR     equ 0x79c0          ; procmgr_ability@plt
T_COMOPEN     equ 0x4a090         ; COMPort_Open()
T_COMRTS      equ 0x4a0d0         ; COMPort_SetRTS(bool)
T_CTOR        equ 0x15f90         ; CMessageAudioLoop::CMessageAudioLoop()
T_INDEX       equ 0x33db0         ; CSampleGroups::IndexSampleGroupFiles(int,int)
T_CACHEINFO   equ 0x34b90         ; CGroupFileInfoCache::GetGroupFileInfoCache()
T_PRELOAD     equ 0x356b0         ; CSampleGroup::CacheSampleGroups(...)
T_NEWARR      equ 0x7930          ; operator new[]@plt
T_WORKERS     equ 0x18710         ; CMessageAudioLoop::StartAudioProcessThreads()

%macro STAMP 1
    mov r11d, %1
    call stamp
%endmacro

%macro PROLOGUE 0
    push rbp
    mov rbp, rsp
%endmacro

; ---------------------------------------------------------------------------
; stamp: r11d = marker id. Preserves every register except flags and r11.
; Entered with rsp = 8 mod 16 (called from a 16-aligned site).
; ---------------------------------------------------------------------------
align 16, db 0xcc
stamp:
    PROLOGUE
    push rax
    push rcx
    push rdx
    push rsi
    push rdi
    push r8
    push r9
    push r10
    push r11                       ; [rbp-72] = id
    sub rsp, 152                   ; 72 + 152 = 224 = 14*16 -> rsp 16-aligned
    movups [rsp+16],  xmm0
    movups [rsp+32],  xmm1
    movups [rsp+48],  xmm2
    movups [rsp+64],  xmm3
    movups [rsp+80],  xmm4
    movups [rsp+96],  xmm5
    movups [rsp+112], xmm6
    movups [rsp+128], xmm7
    mov edi, 2                     ; same clock id the application passes
    mov rsi, rsp                   ; struct timespec {tv_sec, tv_nsec} 64-bit each
    xor eax, eax
    call PLT_CLOCK
    test eax, eax
    jnz .out
    mov rax, [rsp]
    imul rax, rax, 1000000000
    add rax, [rsp+8]
    mov r11d, [rbp-72]
    db 0x48, 0x8d, 0x0d            ; lea rcx, [rip+disp32]  (TS is a bare constant, so encode by hand)
    dd TS - ($ + 4)
    mov [rcx+r11*8], rax
.out:
    movups xmm0, [rsp+16]
    movups xmm1, [rsp+32]
    movups xmm2, [rsp+48]
    movups xmm3, [rsp+64]
    movups xmm4, [rsp+80]
    movups xmm5, [rsp+96]
    movups xmm6, [rsp+112]
    movups xmm7, [rsp+128]
    add rsp, 152
    pop r11
    pop r10
    pop r9
    pop r8
    pop rdi
    pop rsi
    pop rdx
    pop rcx
    pop rax
    pop rbp
stamp_epi:
    ret
stamp_end:

; ---------------------------------------------------------------------------
; flush: marker 19, then write /hd/px_boot_trace.bin once. Preserves all regs.
; Same open pattern the application already uses at 0x150f3..0x15107:
; remove(path); open(path, 0x101, 0x1b6).
; ---------------------------------------------------------------------------
align 16, db 0xcc
flush:
    PROLOGUE
    push rax
    push rcx
    push rdx
    push rsi
    push rdi
    push r8
    push r9
    push r10
    push r11
    sub rsp, 152
    movups [rsp],     xmm0
    movups [rsp+16],  xmm1
    movups [rsp+32],  xmm2
    movups [rsp+48],  xmm3
    movups [rsp+64],  xmm4
    movups [rsp+80],  xmm5
    movups [rsp+96],  xmm6
    movups [rsp+112], xmm7         ; xmm save area is [rsp .. rsp+127]
    STAMP 19                       ; LOOP_ENTER
    call PLT_ERRNO
    mov eax, [rax]
    mov [rsp+128], eax             ; saved errno
    lea rdi, [path]
    call PLT_REMOVE
    lea rdi, [path]
    mov esi, 0x101                 ; O_WRONLY|O_CREAT, as used at 0x150ff
    mov edx, 0x1b6                 ; mode 0666, as used at 0x150fa
    xor eax, eax                   ; variadic call
    call PLT_OPEN
    mov [rsp+132], eax             ; fd
    test eax, eax
    js .nofile
    mov edi, eax
    lea rsi, [hdr]
    mov edx, 64
    call PLT_WRITE
    mov edi, [rsp+132]
    db 0x48, 0x8d, 0x35            ; lea rsi, [rip+disp32]
    dd TS - ($ + 4)
    mov edx, N_MARKERS*8
    call PLT_WRITE
    mov edi, [rsp+132]
    call PLT_CLOSE
.nofile:
    call PLT_ERRNO
    mov ecx, [rsp+128]
    mov [rax], ecx                 ; restore errno
    movups xmm0, [rsp]
    movups xmm1, [rsp+16]
    movups xmm2, [rsp+32]
    movups xmm3, [rsp+48]
    movups xmm4, [rsp+64]
    movups xmm5, [rsp+80]
    movups xmm6, [rsp+96]
    movups xmm7, [rsp+112]
    add rsp, 152
    pop r11
    pop r10
    pop r9
    pop r8
    pop rdi
    pop rsi
    pop rdx
    pop rcx
    pop rax
    pop rbp
flush_epi:
    ret
flush_end:

; ---------------------------------------------------------------------------
; Wrappers. Entered with rsp = 8 mod 16, exactly as the original callee would
; be. PROLOGUE re-aligns to 16 for the inner calls.
; Tail wrappers stamp then jump to the original target; the original returns
; straight to the original call site.
; ---------------------------------------------------------------------------
%macro TAILWRAP 3                  ; name, id, target
align 16, db 0xcc
%1:
    PROLOGUE
    STAMP %2
    pop rbp
%1_epi:
    jmp near %3
%1_end:
%endmacro

TAILWRAP w_main,       0, T_PROCMGR     ; MAIN_ENTRY
TAILWRAP w_serial_beg, 1, T_COMOPEN     ; SERIAL_BEGIN
TAILWRAP w_cache_beg,  6, T_CACHEINFO   ; CACHE_SETUP_BEGIN
TAILWRAP w_select_end, 9, T_NEWARR      ; SELECT_END (just before operator new[])

%macro WBEGIN 1
align 16, db 0xcc
%1:
    PROLOGUE
%endmacro

%macro WEND 1
    pop rbp
%1_epi:
    ret
%1_end:
%endmacro

WBEGIN w_serial_end                ; SERIAL_END (after COMPort_SetRTS returns)
    call T_COMRTS
    STAMP 2
WEND w_serial_end

WBEGIN w_ctor                      ; CTOR_BEGIN / CTOR_END
    STAMP 3
    call T_CTOR
    STAMP 10
WEND w_ctor

WBEGIN w_index                     ; INDEX_BEGIN / INDEX_END
    STAMP 4
    call T_INDEX
    STAMP 5
WEND w_index

WBEGIN w_preload                   ; PRELOAD_BEGIN / PRELOAD_END
    STAMP 7
    call T_PRELOAD
    STAMP 8
WEND w_preload

WBEGIN w_fpga_open                 ; FPGA_OPEN_BEGIN / END  (replaces mov rdi,r15 ; call [rax])
    STAMP 11
    mov rdi, r15
    call qword [rax]
    STAMP 12
WEND w_fpga_open

WBEGIN w_sched                     ; SCHED_START_BEGIN / END (replaces mov rdi,r13 ; call [rax+8])
    STAMP 13
    mov rdi, r13
    call qword [rax+8]
    STAMP 14
WEND w_sched

WBEGIN w_workers                   ; WORKERS_BEGIN / END
    STAMP 15
    call T_WORKERS
    STAMP 16
WEND w_workers

WBEGIN w_stream                    ; STREAM_BEGIN / END (replaces mov rdi,r15 ; call [rax+0x10])
    STAMP 17
    mov rdi, r15
    call qword [rax+0x10]
    STAMP 18
WEND w_stream

; ---------------------------------------------------------------------------
; Constants (read-only, in the code segment)
; ---------------------------------------------------------------------------
align 16, db 0xcc
path:
    db "/hd/px_boot_trace.bin", 0
align 16, db 0
hdr:
    db "PXBTRACE"                  ; magic
    dd 1                           ; schema version
    dd N_MARKERS                   ; marker count
%include "sha.inc"                 ; 32 raw bytes: baseline application SHA-256
    db "PXTRACE-1.1"               ; build identity, 16 bytes zero padded
    times 5 db 0
hdr_end:
%if (hdr_end - hdr) != 64
%error header must be 64 bytes
%endif

code_end:

; ---------------------------------------------------------------------------
; Label table for the build script (NOT copied into the ELF).
; ---------------------------------------------------------------------------
align 8, db 0
    dq 0xDEADBEEFCAFEF00D
%macro LBL 1
    dq %1, %1_epi, %1_end
%endmacro
    LBL stamp
    LBL flush
    LBL w_main
    LBL w_serial_beg
    LBL w_serial_end
    LBL w_ctor
    LBL w_index
    LBL w_cache_beg
    LBL w_preload
    LBL w_select_end
    LBL w_fpga_open
    LBL w_sched
    LBL w_workers
    LBL w_stream
    dq code_end
