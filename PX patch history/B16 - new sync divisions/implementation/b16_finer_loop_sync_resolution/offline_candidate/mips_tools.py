"""Small explicit MIPS32 decoder for the scoped B16 sites; no firmware writes."""
import struct
R='zero at v0 v1 a0 a1 a2 a3 t0 t1 t2 t3 t4 t5 t6 t7 s0 s1 s2 s3 s4 s5 s6 s7 t8 t9 k0 k1 gp sp fp ra'.split()
def signed(n):return n if n<32768 else n-65536
def decode(w,p):
 op=w>>26;rs=(w>>21)&31;rt=(w>>16)&31;rd=(w>>11)&31;sh=(w>>6)&31;fn=w&63;imm=w&65535;s=signed(imm)
 if not w:return 'nop'
 if op in (2,3):return ('j' if op==2 else 'jal')+f' 0x{((p+4)&0xf0000000)|((w&0x3ffffff)<<2):08x}'
 if op in (4,5):return f'{"beq" if op==4 else "bne"} {R[rs]},{R[rt]},0x{p+4+4*s:08x}'
 if op in (6,7):return f'{"blez" if op==6 else "bgtz"} {R[rs]},0x{p+4+4*s:08x}'
 if op in (8,9,10,11,12,13,14):return f'{ {8:"addi",9:"addiu",10:"slti",11:"sltiu",12:"andi",13:"ori",14:"xori"}[op]} {R[rt]},{R[rs]},{s if op<12 else hex(imm)}'
 if op==15:return f'lui {R[rt]},0x{imm:04x}'
 if op in (32,33,35,36,37,40,41,43):return f'{ {32:"lb",33:"lh",35:"lw",36:"lbu",37:"lhu",40:"sb",41:"sh",43:"sw"}[op]} {R[rt]},{s:#x}({R[rs]})'
 if op==0:
  if fn in (0,2,3):return f'{ {0:"sll",2:"srl",3:"sra"}[fn]} {R[rd]},{R[rt]},{sh}'
  if fn in (8,9):return f'{"jr" if fn==8 else "jalr"} {R[rs]}'
  if fn in (32,33,34,35,36,37,38,39,42,43):return f'{ {32:"add",33:"addu",34:"sub",35:"subu",36:"and",37:"or",38:"xor",39:"nor",42:"slt",43:"sltu"}[fn]} {R[rd]},{R[rs]},{R[rt]}'
 return f'.word 0x{w:08x}'
def listing(b,lo,hi,base=0x9d000000):return '\n'.join(f'{a:08x}: {struct.unpack_from("<I",b,a-base)[0]:08x} {decode(struct.unpack_from("<I",b,a-base)[0],a)}' for a in range(lo,hi,4))
if __name__=='__main__':
 import sys,pathlib
 b=pathlib.Path(sys.argv[1]).read_bytes()
 for span in sys.argv[2:]:
  a,z=map(lambda x:int(x,16),span.split(':'));print(listing(b,a,z))
