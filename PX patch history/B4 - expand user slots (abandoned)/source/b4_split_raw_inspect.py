"""Targeted read-only stock instruction listing; unknown words remain explicit."""
import struct, os
from pathlib import Path
R='zero at v0 v1 a0 a1 a2 a3 t0 t1 t2 t3 t4 t5 t6 t7 t8 t9 k0 k1 gp sp fp ra'.split()
R='zero at v0 v1 a0 a1 a2 a3 t0 t1 t2 t3 t4 t5 t6 t7 s0 s1 s2 s3 s4 s5 s6 s7 t8 t9 k0 k1 gp sp fp ra'.split()
B=(Path(os.environ.get('B4_PRIVATE_INPUTS', '.'))/'stock_pic_2.2.2.0.0.bin').read_bytes()
def word(a):return struct.unpack_from('<I',B,a-0x9d000000)[0]
def dec(p,w):
 o=w>>26;s=w>>21&31;t=w>>16&31;d=w>>11&31;sa=w>>6&31;f=w&63;im=w&65535;si=im if im<32768 else im-65536
 if not w:return 'nop'
 if o in (2,3):return f'{["j","jal"][o-2]} {((p+4)&0xf0000000)|((w&0x3ffffff)<<2):08x}'
 if o in (4,5,6,7,20,21):return f'{ {4:"beq",5:"bne",6:"blez",7:"bgtz",20:"beql",21:"bnel"}[o]} {R[s]} {R[t]} {p+4+si*4:08x}'
 if o==1:return f'REGIMM{t} {R[s]} {p+4+si*4:08x}'
 if o==15:return f'lui {R[t]} {im:#x}'
 if o in (8,9,10,11,12,13,14):return f'{ {8:"addi",9:"addiu",10:"slti",11:"sltiu",12:"andi",13:"ori",14:"xori"}[o]} {R[t]} {R[s]} {si if o<12 else im:#x}'
 if o in (32,33,35,36,37,40,41,43):return f'{ {32:"lb",33:"lh",35:"lw",36:"lbu",37:"lhu",40:"sb",41:"sh",43:"sw"}[o]} {R[t]} {si:#x}({R[s]})'
 if o==0:
  if f in (0,2,3):return f'{ {0:"sll",2:"srl",3:"sra"}[f]} {R[d]} {R[t]} {sa}'
  if f in (8,9):return f'{"jr" if f==8 else "jalr"} {R[s]}'
  if f in (33,35,36,37,38,42,43,10,11):return f'{ {33:"addu",35:"subu",36:"and",37:"or",38:"xor",42:"slt",43:"sltu",10:"movz",11:"movn"}[f]} {R[d]} {R[s]} {R[t]}'
 return f'UNKNOWN {w:08x}'
def listing(a,b):return '\n'.join(f'{p:08X} {word(p):08X} {dec(p,word(p))}' for p in range(a,b,4))
if __name__=='__main__':
 import sys
 if len(sys.argv)>1:print(listing(int(sys.argv[1],16),int(sys.argv[2],16)))
 else:
  for off in range(0,len(B)-4,4):
   w=struct.unpack_from('<I',B,off)[0];o=w>>26;s=w>>21&31;t=w>>16&31
   if o in (9,35,43) and w&65535 in (0x7e90,0xa118):print(listing(max(0x9d000000,0x9d000000+off-8),0x9d000000+off+12))
