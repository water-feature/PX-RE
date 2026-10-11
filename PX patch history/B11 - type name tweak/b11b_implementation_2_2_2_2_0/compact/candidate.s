.set noreorder
.set noat
.text
.org 173900
entry:
lhu $v1,0x20($a0)
lhu $v0,6($a0)
bne $v0,$zero,inst2
addiu $v0,$zero,1
sh $v0,0x74($a0)
beql $v1,$v0,group1
lhu $a0,0x44($a0)
addiu $a2,$zero,0x24
normalize:
lw $v0,8($s1)
slt $a3,$zero,$v0
sll $a3,$a3,1
addiu $a3,$a3,-1
lhu $a0,0x44($s0)
jal 0x9d04d300
addu $a1,$a2,$zero
addu $s4,$v0,$zero
beq $zero,$zero,snapshot
addu $t0,$v0,$a3
.org 173972
refresh1:
nop
.org 185384
inst2:
sh $v0,0x76($a0)
beql $v1,$v0,group2
lhu $a0,0x44($a0)
beq $zero,$zero,normalize
addiu $a2,$zero,0x65
helper_tail:
sltiu $t1,$a2,1
movz $t1,$zero,$t0
j 0x9d04d4fc
addu $a2,$a2,$t1
snapshot:
lhu $s5,0xd6e($a1)
beq $zero,$zero,invoke
movn $s5,$s4,$a0
selector:
lhu $v0,6($s0)
beq $v0,$zero,refresh1
nop
.org 185444
refresh2:
nop
.org 187656
adjust:
lw $t0,0x2c($sp)
lui $t1,0x9d02
ori $t1,$t1,0xdf10
bne $t0,$t1,clamp
sll $t0,$a0,2
addu $t0,$t0,$sp
lw $t0,0x24($t0)
beq $zero,$zero,helper_tail
xor $t0,$t0,$s3
.org 188152
invoke:
sltiu $v0,$t0,17
beq $v0,$zero,selector
addu $a3,$t0,$zero
lhu $a1,0x44($s0)
jal 0x9d04dacc
addu $a0,$zero,$zero
beq $zero,$zero,selector
nop
nop
.org 191208
group2:
nop
.org 191464
group1:
nop
.org 316668
clamp:
nop
