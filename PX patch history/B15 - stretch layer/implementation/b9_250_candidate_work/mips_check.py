"""Bounded instruction interpreter. Decodes real little-endian MIPS words only.
No symbolic patch overlays. External program-application/I/O callees use contracts.
"""
from pathlib import Path
import struct
BASE=0x9d000000;REGS='zero at v0 v1 a0 a1 a2 a3 t0 t1 t2 t3 t4 t5 t6 t7 s0 s1 s2 s3 s4 s5 s6 s7 t8 t9 k0 k1 gp sp fp ra'.split();R=dict(zip(REGS,range(32)))
GP=0x80007ff0;STATE=0x80052e18;WRAPPER=0x9d0234cc;APPLY=0x9d022eb4;GLOBAL=0x9d04d780
PANEL={0x9d02a3d0,0x9d02a808,0x9d02aabc,0x9d02bcc8,0x9d02dcf0,0x9d02e0c0}
signed=lambda v:v if v<0x80000000 else v-0x100000000
CONTROL={'j','jal','jr','beq','bne','beql','bnel','blez','bltz','bgez','bgtz'}
def decode(image,pc):
 w=struct.unpack_from('<I',image,pc-BASE)[0]
 op,rs,rt,rd,sa,fn=w>>26,(w>>21)&31,(w>>16)&31,(w>>11)&31,(w>>6)&31,w&63
 imm=w&65535;si=imm if imm<32768 else imm-65536;s,t,d=REGS[rs],REGS[rt],REGS[rd]
 if w==0:return ('nop',)
 if op==0:
  if fn==8:return ('jr',s)
  if fn==0:return ('sll',d,t,sa)
  if fn==2:return ('srl',d,t,sa)
  name={10:'movz',11:'movn',33:'addu',35:'subu',36:'and',37:'or',38:'xor',42:'slt',43:'sltu'}.get(fn)
  if name:return (name,d,s,t)
 if op in (2,3):return ('j' if op==2 else 'jal',((pc+4)&0xf0000000)|((w&0x3ffffff)<<2))
 if op in (4,5,20,21):return ({4:'beq',5:'bne',20:'beql',21:'bnel'}[op],s,t,pc+4+si*4)
 if op in (6,7):return ('blez' if op==6 else 'bgtz',s,pc+4+si*4)
 if op==1 and rt in (0,1):return ('bltz' if rt==0 else 'bgez',s,pc+4+si*4)
 if op==15:return ('lui',t,imm)
 if op in (9,10,11,12,13,14):return ({9:'addiu',10:'slti',11:'sltiu',12:'andi',13:'ori',14:'xori'}[op],t,s,imm if op>=12 else si)
 if op in (32,33,35,36,37,40,41,43):return ({32:'lb',33:'lh',35:'lw',36:'lbu',37:'lhu',40:'sb',41:'sh',43:'sw'}[op],t,si,s)
 if op==31 and fn==10 and sa==0:return ('lwx',d,t,s)
 raise AssertionError(f'unhandled {pc:08x} {w:08x}')

class CPU:
 def __init__(self,image,gate=1):
  self.image=image;self.r=[(0x12340000+i*0x101)&0xffffffff for i in range(32)];self.r[0]=0
  self.r[R['gp']]=GP;self.r[R['sp']]=0x80070000;self.mem={};self.calls=[];self.trace=[];self.gate=gate;self.inject=None;self.writes=[]
  for off in range(-0x200,0x80):self.mem[self.g('sp')+off]=0xa5
  self.write(GP-0x7c84,-1,4);self.write(GP-0x7c80,-1,4)
  for slot in (0,1):self.write(STATE+0x4a+2*slot,0,2);self.write(STATE+0x4e+2*slot,0,2)
 def g(self,n):return self.r[R[n]]
 def s(self,n,v):
  if n!='zero':self.r[R[n]]=v&0xffffffff
 def read(self,a,n):
  if BASE<=a and a+n<=BASE+len(self.image):return int.from_bytes(self.image[a-BASE:a-BASE+n],'little')
  return sum(self.mem.get((a+i)&0xffffffff,0)<<(8*i) for i in range(n))
 def write(self,a,v,n):
  a&=0xffffffff
  for i in range(n):self.mem[(a+i)&0xffffffff]=(v>>(8*i))&255
  self.writes.append((a,v&((1<<(8*n))-1),n))
 def simple(self,row):
  op,*a=row;g,s=self.g,self.s
  if op=='nop':return
  if op=='lui':s(a[0],a[1]<<16)
  elif op in ('addiu','slti','sltiu','andi','ori','xori'):
   x,y=g(a[1]),a[2]
   v={'addiu':lambda:x+y,'slti':lambda:int(signed(x)<y),'sltiu':lambda:int(x<(y&0xffffffff)),'andi':lambda:x&y,'ori':lambda:x|y,'xori':lambda:x^y}[op]()
   s(a[0],v)
  elif op in ('sll','srl'):s(a[0],g(a[1])<<a[2] if op=='sll' else g(a[1])>>a[2])
  elif op in ('addu','subu','and','or','xor','slt','sltu'):
   x,y=g(a[1]),g(a[2]);v={'addu':lambda:x+y,'subu':lambda:x-y,'and':lambda:x&y,'or':lambda:x|y,'xor':lambda:x^y,'slt':lambda:int(signed(x)<signed(y)),'sltu':lambda:int(x<y)}[op]();s(a[0],v)
  elif op in ('movn','movz'):
   if (g(a[2])!=0)==(op=='movn'):s(a[0],g(a[1]))
  elif op=='lwx':s(a[0],self.read((g(a[1])+g(a[2]))&0xffffffff,4))
  elif op in ('lb','lh','lw','lbu','lhu'):
   n={'lb':1,'lh':2,'lw':4,'lbu':1,'lhu':2}[op];v=self.read((g(a[2])+a[1])&0xffffffff,n)
   if op in ('lb','lh') and v>>(8*n-1):v-=1<<(8*n)
   s(a[0],v)
  elif op in ('sb','sh','sw'):self.write(g(a[2])+a[1],g(a[0]),{'sb':1,'sh':2,'sw':4}[op])
  else:raise AssertionError(row)
 def fetch_simple(self,pc):
  if self.inject:self.inject(self,pc)
  row=decode(self.image,pc);assert row[0] not in CONTROL,(hex(pc),row)
  self.trace.append((pc,row));self.simple(row)
 def external(self,pc):
  if pc not in (APPLY,GLOBAL):return False
  ra=self.g('ra');sp=self.g('sp')
  if pc==GLOBAL:assert self.g('a0')==17;answer=self.gate
  else:
   state,bank,program,force=[self.g(x) for x in ('a0','a1','a2','a3')];mode=self.read(sp+16,4);inram=self.read(sp+20,4)
   assert state==STATE and mode in (0,1,2) and inram==0
   self.calls.append((bank,program,force,mode,inram))
   if force or self.gate:
    for slot in ([0,1] if mode==2 else [mode]):self.write(state+0x4a+2*slot,bank,2);self.write(state+0x4e+2*slot,program,2)
   answer=0
  # Adversarial legitimate o32 clobbers and outgoing argument home-area writes.
  for i in list(range(2,16))+[24,25]:self.r[i]=0xbad00000+i
  for off in range(0,16,4):self.write(sp+off,0xdecafbad,4)
  self.s('v0',answer);self.s('ra',ra);return True
 def run(self,pc,stops,maxsteps=3000):
  for _ in range(maxsteps):
   if pc in stops:return pc
   if self.inject:self.inject(self,pc)
   if self.external(pc):pc=self.g('ra');continue
   row=decode(self.image,pc);op=row[0];self.trace.append((pc,row))
   if op in CONTROL:
    annul=False
    if op in ('beq','bne','beql','bnel'):
     take=(self.g(row[1])==self.g(row[2]))==(op in ('beq','beql'));target=row[3] if take else pc+8;annul=not take and op.endswith('l')
    elif op in ('blez','bgtz','bltz','bgez'):
     x=signed(self.g(row[1]));take={'blez':x<=0,'bgtz':x>0,'bltz':x<0,'bgez':x>=0}[op];target=row[2] if take else pc+8
    else:
     target=self.g(row[1]) if op=='jr' else row[1]
     if op=='jal':self.s('ra',pc+8)
    if not annul:self.fetch_simple(pc+4)
    pc=target
   else:self.simple(row);pc+=4
  raise AssertionError(('instruction limit',hex(pc)))
 def count(self,slot=0):return signed(self.read(GP-0x7c84+slot*4,4))
 def pending(self,slot=0):return tuple(self.read(GP+off+slot*4,4) for off in (-0x7ca4,-0x7c7c,-0x7c74,-0x7c9c))
 def applied(self,slot=0):return self.read(STATE+0x4a+slot*2,2),self.read(STATE+0x4e+slot*2,2)
 def call(self,site,bank,prog,mode=2,force=None):
  delay=struct.unpack_from('<I',self.image,site-BASE+4)[0]
  if force is None:force=1 if delay==0x24070001 else 0
  self.s('a0',STATE);self.s('a1',bank);self.s('a2',prog);self.s('a3',force);self.s('s2',mode);self.s('v0',1)
  self.write(self.g('sp')+16,mode,4)
  before=self.r.copy();guard=self.read(self.g('sp')+32,16)
  self.run(site,{site+8})
  for name in [*REGS[16:24],'gp','sp','fp']:assert self.g(name)==before[R[name]],(name,hex(site))
  assert self.g('ra')==site+8 and self.read(self.g('sp')+32,16)==guard
 def tick(self,eligible=True):
  save=self.r.copy();inj=self.inject;self.inject=None;self.s('sp',self.g('sp')-0x160);self.s('s6',int(eligible))
  stop=self.run(0x9d051228,{0x9d051290,0x9d051170})
  assert stop==(0x9d051290 if eligible else 0x9d051170)
  self.r=save;self.inject=inj
 def expire(self):
  save=self.r.copy();sp=self.g('sp')
  for name,value in [('s3',GP-0x7c84),('s1',0xffffffff),('s2',GP-0x7c74),('s6',GP-0x7ca4),('s7',GP-0x7c7c),('fp',GP-0x7c9c)]:self.s(name,value)
  self.write(sp+0x60,STATE,4)
  self.run(0x9d053314,{0x9d053344})
  self.r=save
