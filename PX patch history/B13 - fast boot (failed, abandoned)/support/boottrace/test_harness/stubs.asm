; Linux test stubs standing in for PLT/original targets. Each checks stack alignment at entry,
; records its inputs, then clobbers every caller-saved register and xmm0-7.
bits 64
default rel
org 0x10200000

RET_RAX equ 0x1122334455667788
RET_RDX equ 0x0102030405060708
BAD     equ 0xBAD0BAD0BAD0BAD0

%macro ENTRYCHK 0
    mov r11, rsp
    and r11d, 15
    cmp r11d, 8
    je %%ok
    inc qword [rel misalign]
%%ok:
%endmacro

%macro CLOBBER_ALL 0              ; volatile regs except rax/rdx (set by caller of macro)
    mov rcx, BAD
    mov rsi, rcx
    mov rdi, rcx
    mov r8, rcx
    mov r9, rcx
    mov r10, rcx
    mov r11, rcx
    movq xmm1, rcx
    movq xmm2, rcx
    movq xmm3, rcx
    movq xmm4, rcx
    movq xmm5, rcx
    movq xmm6, rcx
    movq xmm7, rcx
%endmacro

; target stub: record inputs (rdi,rsi,rdx,rcx,r8,r9,rax, xmm0-7), return RET_RAX/RET_RDX/xmm0=RET pattern
%macro TSTUB 1
align 16
stub_%1:
    ENTRYCHK
    lea r11, [rel rec_%1]
    inc qword [r11]
    mov [r11+8],  rdi
    mov [r11+16], rsi
    mov [r11+24], rdx
    mov [r11+32], rcx
    mov [r11+40], r8
    mov [r11+48], r9
    mov [r11+56], rax
    movups [r11+64],  xmm0
    movups [r11+80],  xmm1
    movups [r11+96],  xmm2
    movups [r11+112], xmm3
    movups [r11+128], xmm4
    movups [r11+144], xmm5
    movups [r11+160], xmm6
    movups [r11+176], xmm7
    CLOBBER_ALL
    mov rax, 0x7777777777777777
    movq xmm0, rax
    mov rax, RET_RAX
    mov rdx, RET_RDX
    ret
%endmacro

TSTUB procmgr
TSTUB comopen
TSTUB comrts
TSTUB ctor
TSTUB index
TSTUB cacheinfo
TSTUB preload
TSTUB newarr
TSTUB workers
TSTUB vt0          ; [rax]
TSTUB vt8          ; [rax+8]
TSTUB vt10         ; [rax+0x10]

align 16
stub_clock:
    ENTRYCHK
    mov rax, [rel clk_n]
    inc rax
    mov [rel clk_n], rax
    lea rcx, [rax+5]
    mov [rsi], rcx                 ; tv_sec  = 5 + n
    imul rcx, rax, 1000
    add rcx, 123
    mov [rsi+8], rcx               ; tv_nsec = n*1000 + 123
    mov rdx, BAD
    CLOBBER_ALL
    movq xmm0, rcx
    xor eax, eax
    ret

align 16
stub_errno:
    ENTRYCHK
    CLOBBER_ALL
    mov rdx, BAD
    lea rax, [rel errno_var]
    ret

%macro SYSSTUB 4                   ; name, linux nr, errno-on-fail, flag rewrite for open
align 16
stub_%1:
    ENTRYCHK
    mov [rel last_%1_rsi], rsi
    mov [rel last_%1_rdx], rdx
    mov eax, %2
%if %4
    mov esi, 0x241                 ; Linux O_WRONLY|O_CREAT|O_TRUNC (QNX 0x101 recorded above)
    mov edx, 0x1b6
%endif
    syscall
    test rax, rax
    jns %%ok
    neg eax
    mov [rel errno_var], eax
    mov eax, -1
%%ok:
    mov [rel sys_ret], rax
    CLOBBER_ALL
    mov rdx, BAD
    mov rax, [rel sys_ret]
    ret
%endmacro
SYSSTUB remove, 87, 0, 0
SYSSTUB open,   2,  0, 1
SYSSTUB write,  1,  0, 0
SYSSTUB close,  3,  0, 0

align 16
misalign:  dq 0
sys_ret:   dq 0
clk_n:     dq 0
errno_var: dd 0
           dd 0
last_remove_rsi: dq 0
last_remove_rdx: dq 0
last_open_rsi: dq 0
last_open_rdx: dq 0
last_write_rsi: dq 0
last_write_rdx: dq 0
last_close_rsi: dq 0
last_close_rdx: dq 0
%macro REC 1
align 16
rec_%1: times 24 dq 0
%endmacro
REC procmgr
REC comopen
REC comrts
REC ctor
REC index
REC cacheinfo
REC preload
REC newarr
REC workers
REC vt0
REC vt8
REC vt10

align 8
    dq 0xDEADBEEFCAFEF00D
%macro L 1
    dq %1
%endmacro
    L stub_procmgr
    L stub_comopen
    L stub_comrts
    L stub_ctor
    L stub_index
    L stub_cacheinfo
    L stub_preload
    L stub_newarr
    L stub_workers
    L stub_vt0
    L stub_vt8
    L stub_vt10
    L stub_clock
    L stub_errno
    L stub_remove
    L stub_open
    L stub_write
    L stub_close
    L misalign
    L clk_n
    L errno_var
    L rec_procmgr
    L rec_comopen
    L rec_comrts
    L rec_ctor
    L rec_index
    L rec_cacheinfo
    L rec_preload
    L rec_newarr
    L rec_workers
    L rec_vt0
    L rec_vt8
    L rec_vt10
    L last_open_rsi
    L last_open_rdx
