# SPDX-License-Identifier: GPL-2.0-or-later
from pathlib import Path
import sys,struct,json,hashlib
O=Path(__file__).resolve().parent;R=O.parent;sys.path.insert(0,str(R/'b15_candidate_work'))
from build_candidate_1_8 import parse,serialize,sum16,write_ranges
B=0x9d000000;regs='zero at v0 v1 a0 a1 a2 a3 t0 t1 t2 t3 t4 t5 t6 t7 s0 s1 s2 s3 s4 s5 s6 s7 t8 t9 k0 k1 gp sp fp ra'.split();reg=dict(zip(regs,range(32)))
sha=lambda b:hashlib.sha256(b).hexdigest()
def assemble(lines,start,labels=None):
 labels={} if labels is None else dict(labels);rows=[]
 for line in lines:
  line=line.split('#')[0].strip()
  if not line:continue
  if line.endswith(':'):labels[line[:-1]]=start+len(rows)*4
  else:rows.append(line)
 data=b''
 for i,line in enumerate(rows):
  pc=start+i*4;op,*a=line.replace(',',' ').split();v=lambda x:labels[x] if x in labels else int(x,0)
  if op=='nop':w=0
  elif op=='li':w=9<<26|reg[a[0]]<<16|(v(a[1])&65535)
  elif op=='lui':w=15<<26|reg[a[0]]<<16|v(a[1])
  elif op in ('sll','sllv'):
   d,t,s=a;w=reg[t]<<16|reg[d]<<11|(v(s)<<6 if op=='sll' else reg[s]<<21|4)
  elif op in ('addu','subu','or','slt','sltu','movz','movn'):
   d,s,t=a;w=reg[s]<<21|reg[t]<<16|reg[d]<<11|{'addu':33,'subu':35,'or':37,'slt':42,'sltu':43,'movz':10,'movn':11}[op]
  elif op in ('addiu','andi','sltiu'):
   d,s,t=a;w=dict(addiu=9,andi=12,sltiu=11)[op]<<26|reg[s]<<21|reg[d]<<16|(v(t)&65535)
  elif op in ('lbu','sb'):
   d,mem=a;imm,s=mem[:-1].split('(');w=dict(lbu=36,sb=40)[op]<<26|reg[s]<<21|reg[d]<<16|(v(imm)&65535)
  elif op in ('beq','bne'):
   s,t,target=a;disp=(v(target)-pc-4)//4;assert -32768<=disp<32768
   w=dict(beq=4,bne=5)[op]<<26|reg[s]<<21|reg[t]<<16|(disp&65535)
  elif op in ('j','jal'):w=dict(j=2,jal=3)[op]<<26|((v(a[0])>>2)&0x3ffffff)
  elif op=='jr':w=reg[a[0]]<<21|8
  else:raise AssertionError(line)
  data+=struct.pack('<I',w)
 return data,rows,labels
old=(R/'b15_candidate_work/pic_2.2.2.1.9_B15_LFO_fade_candidate.bin').read_bytes();assert sha(old)=='bc4b1109ccf3f45988cac165b5e8e7b41381c4f6e7cbdfb4f3d619351a7ba82f'
new=bytearray(old);writes=[];listing=[]
def put(pc,code,why,rows=()):
 off=pc-B;assert not any(max(off,x['offset'])<min(off+len(code),x['offset']+x['bytes']) for x in writes)
 writes.append(dict(offset=off,address=hex(pc),bytes=len(code),before=old[off:off+len(code)].hex(),after=code.hex(),reason=why));new[off:off+len(code)]=code
 listing.extend((pc+4*i,row) for i,row in enumerate(rows))
code,rows,_=assemble((R/'b14_sample_acceleration_investigation/decoder_layout.txt').read_text().splitlines(),B+0x7a298);assert len(code)==360
put(B+0x7a298,code,'four-ID decoder',rows)
code,rows,_=assemble(['andi t0,s1,0xfffe','li t1,4','beq t0,t1,full','li t1,18','beq t0,t1,full','nop','slt t0,s0,zero','sll t0,t0,1','j 0x9d07a4c0','nop'],B+0x7a440,{'full':B+0x7a244});put(B+0x7a440,code,'snapshot classifier',rows)
code,rows,_=assemble(['j 0x9d07a4c8','addu s2,s0,zero'],B+0x7a244);put(B+0x7a244,code,'full snapshot continuation',rows)
assert hashlib.sha256(struct.pack('<II',*struct.unpack_from('<II',old,0x7a4b8))).hexdigest()=='001495b326e8d4e2fca1be3e02652b26239e9a436d6fb8c66d7c4361c28e9e54'
code,rows,_=assemble(['j 0x9d07a440','nop'],B+0x7a4b8);put(B+0x7a4b8,code,'replay sign hook',rows)
for off in (0x1394,0x13a0):
 assert hashlib.sha256(struct.pack('<I',struct.unpack_from('<I',old,off)[0])).hexdigest()=='983caaf2fa10cbe31a126d2958e8ea3f402927d4fcfc4a2b77b6e1cef8e90952'
 put(B+off,struct.pack('<I',0x2484000a),'revision1.10')
allowed={i for x in writes for i in range(x['offset'],x['offset']+x['bytes'])}
assert len(new)==len(old) and all(a==b or i in allowed for i,(a,b) in enumerate(zip(old,new)))
# Exact B15 helper preservation.
j=json.loads((R/'b15_candidate_work/absolute_pic_integration.json').read_text())
for piece in j['pieces']:
 off=int(piece['pc'],16)-B;assert new[off:off+piece['bytes']]==old[off:off+piece['bytes']]
(O/'pic_2.2.2.1.10_B14_sample_acceleration_candidate.bin').write_bytes(new)
(O/'patch_manifest.json').write_text(json.dumps(dict(baseline_sha256=sha(old),candidate_sha256=sha(new),writes=writes,changed_bytes=sum(a!=b for a,b in zip(old,new)),B15_helpers_preserved=True),indent=2)+'\n')
# Independent decoder, not assembler rows, supplies published disassembly.
import validate_pic_emission as v
m=v.m
out=[]
for pc,row in listing:
 decoded=m.decode(new,pc);out.append(f'{pc:08x} {struct.unpack_from("<I",new,pc-B)[0]:08x} {decoded}')
 assert decoded[0] not in m.CONTROL or m.decode(new,pc+4)[0] not in m.CONTROL
(O/'disassembly.txt').write_text('\n'.join(out)+'\n')
print('BUILT',len(new),sha(new),'changed bytes',sum(a!=b for a,b in zip(old,new)))
