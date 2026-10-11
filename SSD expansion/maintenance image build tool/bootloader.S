.code16
.section .text
.global _start
_start:
    cli
    xor %ax,%ax
    mov %ax,%ds
    mov %ax,%es
    mov %ax,%ss
    mov $0x7c00,%sp
    sti
    mov %dl,drive
    # Load padded IFS in 32 KiB chunks, BIOS buffer at 0x10000.
    mov $715,%bp
load_loop:
    movw $64,dap+2
    mov $dap,%si
    mov drive,%dl
    mov $0x42,%ah
    int $0x13
    jc disk_error
    push %bp
    mov $move_table,%si
    mov $0x4000,%cx
    mov $0x8700,%ax
    int $0x15
    pop %bp
    jc move_error
    addl $64,dap+8
    addw $0x8000,move_table+26
    adcb $0,move_table+28
    adcb $0,move_table+31
    dec %bp
    jnz load_loop
    # Reload the BIOS prefix and startup into conventional memory.
    movl $1,dap+8
    movw $0x1000,dap+6
    mov $6,%bp
low_loop:
    movw $64,dap+2
    mov $dap,%si
    mov drive,%dl
    mov $0x42,%ah
    int $0x13
    jc disk_error
    addl $64,dap+8
    addw $0x800,dap+6
    dec %bp
    jnz low_loop
    ljmp $0x1000,$0
disk_error:
    mov $'D',%al
    jmp error
move_error:
    mov $'M',%al
error:
    mov $0xe,%ah
    xor %bx,%bx
    int $0x10
halt:
    hlt
    jmp halt
.align 4
drive: .byte 0
.align 4
dap:
    .byte 16,0
    .word 64,0,0x1000
    .quad 1
.align 8
move_table:
    .quad 0,0
    # Source: base 0x10000, 64KiB data segment.
    .word 0xffff,0
    .byte 1,0x93,0,0
    # Destination: starts at 20MiB, incremented each chunk.
    .word 0xffff,0
    .byte 0x40,0x93,0,1
    .quad 0,0
.org 510
.word 0xaa55
