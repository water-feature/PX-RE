import struct,sys
from pathlib import Path
p=Path('audit/B13_on_1.2/baseline_pic.bin').read_bytes();r=['zero','at','v0','v1','a0','a1','a2','a3','t0','t1','t2','t3','t4','t5','t6','t7','s0','s1','s2','s3','s4','s5','s6','s7','t8','t9','k0','k1','gp','sp','fp','ra']
def dec(x,a):
 op=x>>26;rs=r[x>>21&31];rt=r[x>>16&31];rd=r[x>>11&31];im=x&65535;si=im if im<32768 else im-65536
 if x==0:return 'nop'
 if op in (2,3):return ('j','jal')[op-2]+' '+hex((a+4)&0xf0000000|(x&0x3ffffff)*4)
 if op in (4,5):return ('beq','bne')[op-4]+f' {rs},{rt},{hex(a+4+si*4)}'
 if op==1:return f'regimm {rs},{rt},{hex(a+4+si*4)}'
 if op in (6,7):return ('blez','bgtz')[op-6]+f' {rs},{hex(a+4+si*4)}'
 if op==15:return f'lui {rt},{hex(im)}'
 if op in (8,9,10,11,12,13,14):return {8:'addi',9:'addiu',10:'slti',11:'sltiu',12:'andi',13:'ori',14:'xori'}[op]+f' {rt},{rs},{hex(im)}'
 if op in (32,33,35,36,37,40,41,43):return {32:'lb',33:'lh',35:'lw',36:'lbu',37:'lhu',40:'sb',41:'sh',43:'sw'}[op]+f' {rt},{si}({rs})'
 if op==0:
  fn=x&63
  if fn in (8,9):return ('jr' if fn==8 else 'jalr')+' '+rs
  if fn in (0,2,3):return {0:'sll',2:'srl',3:'sra'}[fn]+f' {rd},{rt},{x>>6&31}'
  if fn in (33,35,36,37,38,42,43):return {33:'addu',35:'subu',36:'and',37:'or',38:'xor',42:'slt',43:'sltu'}[fn]+f' {rd},{rs},{rt}'
 return hex(x)
for off in range(int(sys.argv[1],16),int(sys.argv[2],16),4):
 x=struct.unpack_from('<I',p,off)[0];a=0x9d000000+off;print(hex(a),dec(x,a))
