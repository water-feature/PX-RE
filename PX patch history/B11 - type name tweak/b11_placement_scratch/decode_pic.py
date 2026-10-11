import struct,sys
from pathlib import Path
b=(Path(__file__).resolve().parent.parent/'b10_ordinary_entry_design_1_12/candidate_1_15/reextracted_pic.bin').read_bytes()
r='zero at v0 v1 a0 a1 a2 a3 t0 t1 t2 t3 t4 t5 t6 t7 s0 s1 s2 s3 s4 s5 s6 s7 t8 t9 k0 k1 gp sp fp ra'.split()
def dec(pc,w):
 op=w>>26;s=(w>>21)&31;t=(w>>16)&31;d=(w>>11)&31;n=(w>>6)&31;f=w&63;u=w&65535;i=u if u<32768 else u-65536
 if w==0:return 'nop'
 if op==0:
  if f in (0,2,3):return f'{ {0:"sll",2:"srl",3:"sra"}[f]} {r[d]},{r[t]},{n}'
  if f in (8,9):return ('jr '+r[s]) if f==8 else f'jalr {r[d]},{r[s]}'
  if f in (10,11,32,33,34,35,36,37,38,39,42,43):return f'{ {10:"movz",11:"movn",32:"add",33:"addu",34:"sub",35:"subu",36:"and",37:"or",38:"xor",39:"nor",42:"slt",43:"sltu"}[f]} {r[d]},{r[s]},{r[t]}'
 if op in (2,3):return f'{"j" if op==2 else "jal"} {((pc+4)&0xf0000000)|((w&0x3ffffff)<<2):08x}'
 if op in (4,5,6,7,20,21,22,23):return f'{ {4:"beq",5:"bne",6:"blez",7:"bgtz",20:"beql",21:"bnel",22:"blezl",23:"bgtzl"}[op]} {r[s]},{r[t]},{pc+4+4*i:08x}'
 if op==1:return f'REGIMM({t}) {r[s]},{pc+4+4*i:08x}'
 if op in (8,9,10,11,12,13,14):return f'{ {8:"addi",9:"addiu",10:"slti",11:"sltiu",12:"andi",13:"ori",14:"xori"}[op]} {r[t]},{r[s]},{i if op<12 else hex(u)}'
 if op==15:return f'lui {r[t]},{u:04x}'
 if op in (32,33,35,36,37,40,41,43):return f'{ {32:"lb",33:"lh",35:"lw",36:"lbu",37:"lhu",40:"sb",41:"sh",43:"sw"}[op]} {r[t]},{i:#x}({r[s]})'
 if op==31 and f==10:return f'lwx {r[d]},{r[t]}({r[s]})'
 return 'UNKNOWN'
def dump(start,end):
 for pc in range(start,end,4):
  w=struct.unpack_from('<I',b,pc-0x9d000000)[0];print(f'{pc:08x} {w:08x} {dec(pc,w)}')
if __name__=='__main__':
 for x in sys.argv[1:]:
  a,z=x.split(':');dump(int(a,16),int(z,16))
