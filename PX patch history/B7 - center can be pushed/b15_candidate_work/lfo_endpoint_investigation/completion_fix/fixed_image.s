.section __TEXT,__text,regular,pure_instructions
.p2align 4
_firmware:
.incbin "fixed_qnx.elf",0,189152
jmp _fixture_load
.space 11,0x90
.incbin "fixed_qnx.elf",189168,34864
jmp _fixture_filter
.space 11,0x90
.incbin "fixed_qnx.elf",224048,36112
jmp _fixture_read
.space 11,0x90
.incbin "fixed_qnx.elf",260176,8096
jmp _fixture_publish
.space 11,0x90
.incbin "fixed_qnx.elf",268288,718848
.globl _b5_image
_b5_image:
.incbin "fixed_qnx.elf",987136,49152
