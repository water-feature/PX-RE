"""Proposal only: text words and in-memory execution, no firmware/package emission."""
from pathlib import Path
import runpy,struct,json,hashlib
D=Path(__file__).resolve().parent;B=D.parent;BASE=0x9d000000
p=runpy.run_path(str(B/'safety_review/tight_editor_probe.py'));C=p['CPU']
old=(B.parent/'b11b_implementation_2_2_2_2_0/pic_2.2.2.2.0_B11b.bin').read_bytes();current=(B/'in_place_candidate/pic_2.2.2.2.1_B16_in_place.bin').read_bytes()
assert hashlib.sha256(current).hexdigest()=='b7d59c09d57e2b9c18146e51b517404a8deba5cfcc5291d8a17f88904fe53e59'
assert current[0x3ad9c:0x3b5b0]==old[0x3ad9c:0x3b5b0]
reg=p['REG'];W={};S={}
def emit(a,w,s):W[BASE+a]=w;S[BASE+a]=s
def r(a,fn,d,s,t):emit(a,reg[s]<<21|reg[t]<<16|reg[d]<<11|fn,f'{ {33:"addu",43:"sltu",10:"movz"}[fn]} {d},{s},{t}')
def imm(a,op,t,s,n):emit(a,op<<26|reg[s]<<21|reg[t]<<16|n&65535,f'{ {9:"addiu",14:"xori",37:"lhu"}[op]} {t},{n:#x}({s})' if op==37 else f'{ {9:"addiu",14:"xori"}[op]} {t},{s},{n:#x}')
def jump(a,op,t):emit(a,op<<26|((BASE+t)>>2&0x3ffffff),f'{"jal" if op==3 else "j"} {BASE+t:#x}')
def branch(a,op,s,t,d):emit(a,op<<26|reg[s]<<21|reg[t]<<16|((d-a-4)//4&65535),f'{"beq" if op==4 else "bne"} {s},{t},{BASE+d:#x}')
def mul(a,d,s,t):emit(a,28<<26|reg[s]<<21|reg[t]<<16|reg[d]<<11|2,f'mul {d},{s},{t}')
jump(0x3b0a0,3,0x31b70);emit(0x3b0a4,0,'nop');r(0x3b0a8,33,'a0','v0','zero');jump(0x3b0ac,3,0x4d300);imm(0x3b0b0,37,'a1','s0',0xb4);imm(0x3b0b4,37,'v1','s0',0xb4)
imm(0x3b0b8,14,'t0','v1',0x1d);imm(0x3b0bc,14,'t1','v1',0x5e);r(0x3b0c0,10,'t0','zero','t1');branch(0x3b0c4,4,'t0','zero',0x3b55c);imm(0x3b0c8,9,'a2','zero',32)
imm(0x3b0cc,14,'t0','v1',11);r(0x3b0d0,43,'t0','zero','t0');r(0x3b0d4,33,'a0','v0','t0');imm(0x3b0d8,9,'t1','zero',12);mul(0x3b0dc,'v1','v1','t1');r(0x3b0e0,33,'v1','s1','v1');imm(0x3b0e4,37,'a2','v1',0);r(0x3b0e8,33,'a2','a2','t0');emit(0x3b0ec,reg['a2']<<16|reg['a2']<<11|1<<6,'sll a2,a2,1');imm(0x3b0f0,9,'t1','zero',246);mul(0x3b0f4,'a0','a0','t1');emit(0x3b0f8,reg['a0']<<21|reg['a2']<<16|27,'divu a0,a2');emit(0x3b0fc,reg['a2']<<21|7<<6|52,'teq a2,zero,7');emit(0x3b100,reg['s5']<<11|18,'mflo s5')
emit(0x3b55c,11<<26|reg['v0']<<21|reg['t0']<<16|16,'sltiu t0,v0,16');branch(0x3b560,5,'t0','zero',0x3b574);imm(0x3b564,9,'a0','v0',1);imm(0x3b568,9,'t0','v0',-15);imm(0x3b56c,9,'a0','zero',1);emit(0x3b570,reg['t0']<<21|reg['a2']<<16|reg['a2']<<11|4,'sllv a2,a2,t0');jump(0x3b574,2,0x3b0f0);emit(0x3b578,0,'nop')
assert len(W)==33
(D/'proposed_words.tsv').write_text(''.join(f'{a:08x}\t{W[a]:08x}\t{S[a]}\n' for a in sorted(W)))
class CPU(C):
 def plain(self,w):
  op=w>>26;s=w>>21&31;t=w>>16&31;d=w>>11&31;fn=w&63
  if op==28 and fn==2:self.reg[d]=(self.reg[s]*self.reg[t])&0xffffffff;self.reg[0]=0
  elif op==0 and fn==4:self.reg[d]=(self.reg[t]<<(self.reg[s]&31))&0xffffffff
  elif op==0 and fn==27:assert self.reg[t];self.lo,self.hi=divmod(self.reg[s],self.reg[t])
  elif op==0 and fn==18:self.reg[d]=self.lo
  elif op==0 and fn==52:assert self.reg[s]!=self.reg[t]
  else:super().plain(w)
 def run(self,pc,stop):
  for _ in range(120):
   if pc==stop:return
   if pc==BASE+0x31b70:self.reg[2]=self.layer;pc=self.reg[31];continue
   if pc==BASE+0x4d300:
    assert self.reg[4]==self.layer and self.reg[5]==self.ident
    self.reg[2]=self.raw;self.reg[3]=0xabcdef01;pc=self.reg[31];continue
   w=self.word(pc);op=w>>26;s=w>>21&31;t=w>>16&31;u=w&65535;k=u if u<32768 else u-65536;target=None
   if op in (2,3):
    target=((pc+4)&0xf0000000)|((w&0x3ffffff)<<2)
    if op==3:self.reg[31]=pc+8
   elif op in (4,5):target=pc+4+k*4 if ((self.reg[s]==self.reg[t])==(op==4)) else pc+8
   if target is None:self.plain(w);pc+=4
   else:self.plain(self.word(pc+4));pc=target
  raise AssertionError('limit')
def run(image,overlay,ident,raw,layer):
 c=CPU(image,overlay);c.reg=[0x12340000+i for i in range(32)];c.reg[0]=0;c.reg[16]=0x80060000;c.reg[17]=BASE+0x47498;c.reg[3]=ident;c.reg[28]=0x80007ff0;c.ident=ident;c.raw=raw;c.layer=layer;c.write(c.reg[16]+0xb4,2,ident);c.run(BASE+0x3b0a0,BASE+0x3b104);return c
cases=0;rows=[]
for ident in range(0x6b6):
 maximum=struct.unpack_from('<H',old,0x47498+12*ident)[0]
 if maximum==0 and ident==11:continue
 vals=range(18) if ident in (29,94) else sorted({0,1,min(maximum,15),maximum//2,maximum})
 for layer in (0,1):
  for raw in vals:
   z=run(current,W,ident,raw,layer)
   if ident in (29,94) and raw>=16:assert z.reg[21]==(3 if raw==16 else 1)
   else:
    a=run(old,None,ident,raw,layer);assert (z.reg[21],z.lo,z.hi)==(a.reg[21],a.lo,a.hi),(ident,raw,z.reg[21],a.reg[21]);assert z.reg[16:21]==a.reg[16:21] and z.reg[22:24]==a.reg[22:24] and z.reg[28:31]==a.reg[28:31]
   cases+=1
for raw in (1,0,16,17):rows.append({'raw':raw,'baseline_halfwidth':run(old,None,29,raw,0).reg[21] if raw<16 else None,'current_halfwidth':run(current,None,29,raw,0).reg[21],'proposed_halfwidth':run(current,W,29,raw,0).reg[21]})
# Targeted incoming references; proposed occupied ranges only.
ranges=[(BASE+0x3b0a0,BASE+0x3b104),(BASE+0x3b55c,BASE+0x3b57c)];inside=lambda a:any(lo<=a<hi for lo,hi in ranges);refs=[];ptrs=[]
for off in range(0,len(current)-3,4):
 w=struct.unpack_from('<I',current,off)[0];op=w>>26;pc=BASE+off;target=None
 if op in (2,3):target=((pc+4)&0xf0000000)|((w&0x3ffffff)<<2)
 elif op in (1,4,5,6,7,20,21,22,23):
  k=w&65535;k=k if k<32768 else k-65536;target=pc+4+k*4
 if target is not None and inside(target):refs.append([hex(pc),hex(target)])
for off in range(len(current)-3):
 v=struct.unpack_from('<I',current,off)[0]
 if inside(v):ptrs.append([hex(BASE+off),hex(v)])
print('refs',refs,'pointers',ptrs)
result={'status':'PASS: scoped proposal model only','cases':cases,'representative_halfwidth_pixels':rows,'proposed_instruction_bytes':132,'first_range_bytes':100,'second_range_bytes':32,'existing_two_blocks_capacity_bytes':184,'existing_second_block_tail_unchanged_bytes':52,'incoming_direct_candidates':refs,'incoming_literal_candidates':ptrs,'firmware_files_written':False,'package_generated':False,'limits':['Not an independent PIC emulator','Getter I/O boundary mocked, actual downstream drawing not emulated','No hardware validation of correction','Proposed instruction assembly requires separate independent check']}
(D/'proposal_results.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
