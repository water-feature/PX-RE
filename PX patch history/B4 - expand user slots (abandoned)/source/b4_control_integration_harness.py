"""Read-only firmware interpreter with a proposed-instruction overlay in memory.

No patched image is emitted. Implements only instructions reached by these
focused tests, with strict unsupported-instruction and memory checks.
"""
from pathlib import Path
import hashlib, re, struct, json, collections, os

SOURCE=Path(__file__).resolve().parent
ROOT=Path(os.environ.get('B4_PRIVATE_INPUTS', '.')).resolve()
ROM=(ROOT/'stock_pic_2.2.2.0.0.bin').read_bytes()
SHA='14e9c9b9dc562b0384fc43b3c5e0eb7fea84a5792d1a19b9b3ea8276ef7646f5'
assert hashlib.sha256(ROM).hexdigest()==SHA
import sys
REVISED='--entry-hook' in sys.argv
TEXT=(SOURCE.parent/'historical/handovers/readme_B4_control_patch_design.md').read_text()
LINES=re.findall(r'^(9D[0-9A-F]{6}) ([0-9A-F]{8}) (.+)$',TEXT,re.M)
LABELS={k:int(v,16) for k,v in re.findall(r'^(validate|alias_ok|shrink|commit|range_error|enomem|einval|error|done)\s+(0x[0-9A-Fa-f]+)$',TEXT,re.M)}
REG='zero at v0 v1 a0 a1 a2 a3 t0 t1 t2 t3 t4 t5 t6 t7 s0 s1 s2 s3 s4 s5 s6 s7 t8 t9 k0 k1 gp sp fp ra'.split()
RI={v:i for i,v in enumerate(REG)}
def v(s):return LABELS[s] if s in LABELS else int(s,0)
def review_encoding(pc,w,txt):
 op,*a=txt.split();s=w>>21&31;t=w>>16&31;d=w>>11&31;im=w&65535;si=im if im<32768 else im-65536
 if op=='nop':assert w==0
 elif op in ('addu','and','xor','sltu'):
  assert w>>26==0 and (w&63)=={'addu':33,'and':36,'xor':38,'sltu':43}[op]
  assert (d,s,t)==tuple(RI[x] for x in a) and w>>6&31==0
 elif op=='lui':assert w>>26==15 and s==0 and t==RI[a[0]] and im==v(a[1])
 elif op in ('addiu','ori'):
  assert w>>26=={'addiu':9,'ori':13}[op] and (t,s)==(RI[a[0]],RI[a[1]]) and im==(v(a[2])&65535)
 elif op in ('lw','sw'):
  assert w>>26=={'lw':35,'sw':43}[op] and (t,s)==(RI[a[0]],RI[a[2]]) and si==v(a[1])
 elif op in ('beq','bne','blez'):
  assert w>>26=={'beq':4,'bne':5,'blez':6}[op]
  assert s==RI[a[0]] and t==(0 if op=='blez' else RI[a[1]])
  assert pc+4+4*si==v(a[-1])
 elif op in ('j','jal'):
  assert w>>26=={'j':2,'jal':3}[op] and ((pc+4)&0xf0000000)|((w&0x3ffffff)<<2)==v(a[0])
 elif op=='jr':assert w>>26==0 and w&63==8 and s==RI[a[0]] and w&0x1fffff==8
 else:raise AssertionError(txt)
OVERLAY={}
for pc,w,txt in LINES:
 pc,w=int(pc,16),int(w,16);review_encoding(pc,w,txt);OVERLAY[pc]=w
assert len(OVERLAY)==103
PATCHES={0x9d0010d4:(0x3c089d08,0x3c089d00),0x9d0010d8:(0x25081090,0x25081240),0x9d07fb40:(0x24844000,0x24843ff8),0x9d081868:(0x24634000,0x24633ff8),0x9d080b98:(0x27bdffe0,0x0b4004a0),0x9d080b9c:(0xafbf001c,0)}
for pc,(old,new) in PATCHES.items():
 assert struct.unpack_from('<I',ROM,pc-0x9d000000)[0]==old
 OVERLAY[pc]=new

if REVISED:
 # Remove the superseded cold-call wrapper and cold target changes.
 for pc in range(0x9d001240,0x9d001264,4):OVERLAY.pop(pc)
 for pc in (0x9d0010d4,0x9d0010d8):OVERLAY.pop(pc)
 ENTRY_LINES=[
 (0x9d001240,0x3c088005,'lui t0 0x8005'),
 (0x9d001244,0xad007adc,'sw zero 0x7adc t0'),
 (0x9d001248,0xad007ad8,'sw zero 0x7ad8 t0'),
 (0x9d00124c,0x03e01821,'addu v1 ra zero'),
 (0x9d001250,0x3c089d00,'lui t0 0x9d00'),
 (0x9d001254,0x0b420426,'j 0x9d081098'),
 (0x9d001258,0,'nop')]
 for pc,w,txt in ENTRY_LINES:review_encoding(pc,w,txt);OVERLAY[pc]=w
 for pc,old,new in [(0x9d081090,0x03e01821,0x0b400490),(0x9d081094,0x3c089d00,0)]:
  assert struct.unpack_from('<I',ROM,pc-0x9d000000)[0]==old
  OVERLAY[pc]=new

MASK=0xffffffff;BASE=0x80053ae0;CAP=0x80057ad8;STOP=0x9ffff000
def signed(v):return v if v<0x80000000 else v-0x100000000
class Machine:
 def __init__(self,patched=True):
  self.r=[0]*32;self.r[28]=0x80007ff0;self.r[29]=0x8007fff0
  self.ram=bytearray([0xa5])*0x80000;self.patched=patched;self.pc=0
  self.control_writes=[];self.entries=collections.Counter();self.steps=0;self.mmio={};self.serial_reads=0;self.size_queries=0;self.external_hooks={};self.stub_size_queries=True
 def phys(self,a):
  if a>>29 not in (4,5):raise RuntimeError(f'unsupported segment {a:08x} at {self.pc:08x}')
  return a&0x1fffffff
 def read(self,a,n):
  p=self.phys(a)
  if p+n<=len(self.ram):return int.from_bytes(self.ram[p:p+n],'little')
  if 0x1f800000<=p and p+n<=0x1f900000:return sum(self.mmio.get(p+i,0)<<(8*i) for i in range(n))
  if 0x1d000000<=p and p+n<=0x1d000000+len(ROM):return int.from_bytes(ROM[p-0x1d000000:p-0x1d000000+n],'little')
  raise RuntimeError(f'unmapped read {a:08x} at {self.pc:08x}')
 def write(self,a,n,x):
  p=self.phys(a)
  if 0x1f800000<=p and p+n<=0x1f900000:
   for i in range(n):self.mmio[p+i]=(x>>(8*i))&255
   return
  if p+n>len(self.ram):raise RuntimeError(f'unmapped write {a:08x} at {self.pc:08x}')
  if p<0x57ae0 and p+n>0x57ad8:self.control_writes.append((self.pc,a,n,x))
  self.ram[p:p+n]=(x&((1<<(n*8))-1)).to_bytes(n,'little')
 def word(self,pc):
  return OVERLAY[pc] if self.patched and pc in OVERLAY else self.read(pc,4)
 def execute(self,pc,w):
  self.pc=pc;self.steps+=1;self.entries[pc]+=1
  o=w>>26;s=w>>21&31;t=w>>16&31;d=w>>11&31;f=w&63;sa=w>>6&31;im=w&65535;si=im if im<32768 else im-65536
  R=self.r;dest=None;annul=False
  def put(i,x):
   if i:R[i]=x&MASK
  if w==0:pass
  elif o==0:
   if f in (0,2,3):put(d,R[t]<<sa if f==0 else R[t]>>sa if f==2 else signed(R[t])>>sa)
   elif f in (32,33,34,35,36,37,38,39,42,43):
    put(d,{32:lambda:R[s]+R[t],33:lambda:R[s]+R[t],34:lambda:R[s]-R[t],35:lambda:R[s]-R[t],36:lambda:R[s]&R[t],37:lambda:R[s]|R[t],38:lambda:R[s]^R[t],39:lambda:~(R[s]|R[t]),42:lambda:int(signed(R[s])<signed(R[t])),43:lambda:int(R[s]<R[t])}[f]())
   elif f in (10,11):
    if (R[t]==0 if f==10 else R[t]!=0):put(d,R[s])
   elif f in (8,9):
    dest=R[s]
    if f==9:put(d,pc+8)
   else:raise RuntimeError(f'unsupported SPECIAL {w:08x} at {pc:08x}')
  elif o in (2,3):
   dest=((pc+4)&0xf0000000)|((w&0x3ffffff)<<2)
   if o==3:put(31,pc+8)
  elif o in (4,5,6,7,20,21,22,23):
   take={4:lambda:R[s]==R[t],5:lambda:R[s]!=R[t],6:lambda:signed(R[s])<=0,7:lambda:signed(R[s])>0,20:lambda:R[s]==R[t],21:lambda:R[s]!=R[t],22:lambda:signed(R[s])<=0,23:lambda:signed(R[s])>0}[o]()
   dest=pc+4+si*4 if take else pc+8;annul=o>=20 and not take
  elif o==1:
   if t not in (0,1,2,3):raise RuntimeError(f'unsupported REGIMM {w:08x}')
   take=signed(R[s])<0 if t in (0,2) else signed(R[s])>=0
   dest=pc+4+si*4 if take else pc+8;annul=t in (2,3) and not take
  elif o in (8,9,10,11,12,13,14,15):
   put(t,{8:lambda:R[s]+si,9:lambda:R[s]+si,10:lambda:int(signed(R[s])<si),11:lambda:int(R[s]<(si&MASK)),12:lambda:R[s]&im,13:lambda:R[s]|im,14:lambda:R[s]^im,15:lambda:im<<16}[o]())
  elif o in (32,33,35,36,37,40,41,43):
   a=(R[s]+si)&MASK;n={32:1,33:2,35:4,36:1,37:2,40:1,41:2,43:4}[o]
   if a%n:raise RuntimeError(f'unaligned access {a:08x} at {pc:08x}')
   if o in (40,41,43):self.write(a,n,R[t])
   else:
    x=self.read(a,n)
    if o in (32,33) and x>>(8*n-1):x-=1<<(8*n)
    put(t,x)
  elif o==31 and f in (0,4):
   if f==0:put(t,(R[s]>>sa)&((1<<(d+1))-1))
   else:
    assert d>=sa;bits=((1<<(d-sa+1))-1)<<sa;put(t,(R[t]&~bits)|((R[s]<<sa)&bits))
  else:raise RuntimeError(f'unsupported opcode {w:08x} at {pc:08x}')
  R[0]=0;return dest,annul
 def invoke(self,pc,a0=0,stop=STOP,max_steps=3000000,check=True,seed=True):
  self.r[4]=a0&MASK;self.r[31]=stop
  if seed:
   for i in range(16,24):self.r[i]=0x12340000+i
   self.r[30]=0x1234001e
  preserved=[self.r[i] for i in [16,17,18,19,20,21,22,23,28,29,30]]
  begin=self.steps
  while pc!=stop:
   if pc in self.external_hooks:
    self.external_hooks[pc](self);pc=self.r[31];continue
   # External storage/QNX boundaries only; cache initializer instructions run.
   if pc==0x9d040a4c:
    self.serial_reads+=1;self.r[2]=255 if self.r[4]==0x5fd000 else 0;pc=self.r[31];continue
   if pc==0x9d079744 and self.stub_size_queries:
    self.size_queries+=1;self.r[2]=self.r[5]*4096;pc=self.r[31];continue
   if self.steps-begin>max_steps:raise RuntimeError(f'instruction limit at {pc:08x}')
   dest,annul=self.execute(pc,self.word(pc))
   if dest is None:pc+=4
   else:
    if not annul:
     delay_dest,_=self.execute(pc+4,self.word(pc+4))
     if delay_dest is not None:raise RuntimeError('control transfer in delay slot')
    pc=dest
  if check:assert preserved==[self.r[i] for i in [16,17,18,19,20,21,22,23,28,29,30]],'callee-saved clobber'
  return self.r[2]
 def ctrl(self):return [self.read(CAP,4),self.read(CAP+4,4)]
 def publish(self,p,state=1):
  self.write(CAP,4,p);self.write(CAP+4,4,state)

def review_callers():
 xs=[];literals=[];construct=[]
 for off in range(0,len(ROM),4):
  pc=0x9d000000+off;w=struct.unpack_from('<I',ROM,off)[0]
  if w>>26 in (2,3) and ((pc+4)&0xf0000000)|((w&0x3ffffff)<<2)==0x9d080b98:xs.append(pc)
  if w==0x9d080b98:literals.append(pc)
  if w>>26 in (9,13) and w&65535==0x0b98:construct.append(pc)
 assert xs==[0x9d0814ac] and not literals and not construct
 return xs

def suite():
 out={'design':'DINIT entry hook' if REVISED else 'cold call wrapper','reviewed_helper_words':101 if REVISED else len(LINES),'sbrk_direct_callers':[hex(x) for x in review_callers()]}
 m=Machine();m.invoke(0x9d0010d4,stop=0x9d0010e4)
 assert m.ctrl()==[0,0] and m.read(0x80053a64,4)==0 and m.read(0x80053a80,4)==0
 assert m.entries[0x9d081090]==1
 assert [pc for pc,_,_,_ in m.control_writes]==([0x9d001244,0x9d001248] if REVISED else [0x9d001250,0x9d001254])
 out['cold_steps']=m.steps
 p=m.invoke(0x9d07eb84,4480);assert p==BASE+8
 assert m.read(0x80053a64,4)==BASE+4608 and m.read(0x80053a68,4)==CAP
 assert m.ctrl()==[0,0]
 m.publish(p);control=m.ctrl();writes=len(m.control_writes)
 # Fill and mark the allocated payload; allocator operations must preserve it.
 for i in range(4480):m.write(p+i,1,(i*13)&255)
 payload=bytes(m.ram[m.phys(p):m.phys(p)+4480])
 out['extension']={'pointer':hex(p),'break':hex(m.read(0x80053a64,4)),'upper':hex(m.read(0x80053a68,4))}
 allocated=[]
 for _ in range(100):
  q=m.invoke(0x9d07eb84,1024)
  if q==0:break
  allocated.append(q)
 else:raise AssertionError('no exhaustion')
 assert m.ctrl()==control and len(m.control_writes)==writes
 assert bytes(m.ram[m.phys(p):m.phys(p)+4480])==payload
 assert m.invoke(0x9d07eb84,1024)==0
 out['exhaustion']={'live_1024_blocks':len(allocated),'break':hex(m.read(0x80053a64,4)),'errno':m.read(0x80053ad8,4)}
 for q in allocated:m.invoke(0x9d0817c0,q)
 q=m.invoke(0x9d07eb84,1024);assert q!=0;m.invoke(0x9d0817c0,q)
 assert m.ctrl()==control and len(m.control_writes)==writes
 # Real count-loader and size-initializer instructions, mocked external I/O.
 m.invoke(0x9d079220);m.invoke(0x9d079a08);assert m.ctrl()==control
 assert len(m.control_writes)==writes
 assert bytes(m.ram[m.phys(p):m.phys(p)+4480])==payload
 assert m.read(0x80037e90,4)==1 and m.read(0x80037e94,4)==0xffffffff
 out['reload']={'serial_reads':m.serial_reads,'size_queries':m.size_queries,'pointer_state_payload_retained':True}
 # coordinated reset: consumers quiesced by harness, run real DINIT wrapper
 m.invoke(0x9d0010d4,stop=0x9d0010e4)
 assert m.ctrl()==[0,0] and m.read(0x80053a64,4)==0 and m.read(0x80053a80,4)==0
 p2=m.invoke(0x9d07eb84,4480);assert p2==p and m.ctrl()==[0,0]
 out['coordinated_reset']={'fresh_pointer':hex(p2),'old_allocation_invalidated':True}
 # real preferred-failure -> minimum retry path using reduced valid upper
 r=Machine();r.invoke(0x9d081090 if REVISED else 0x9d001240);r.invoke(0x9d08149c,0)
 r.write(0x80053a6c,4,BASE);r.write(0x80053a68,4,BASE+4496)
 q=r.invoke(0x9d07eb84,4480);assert q==BASE+8 and r.read(0x80053a64,4)==BASE+4496
 assert r.read(0x80053ad8,4)==12 and r.ctrl()==[0,0]
 out['real_minimum_retry']={'pointer':hex(q),'break':hex(r.read(0x80053a64,4)),'errno_after_success':12}
 # first extension allocation failure: stock capacity represented by zero root
 f=Machine();f.invoke(0x9d081090 if REVISED else 0x9d001240);f.invoke(0x9d08149c,0)
 f.write(0x80053a6c,4,BASE);f.write(0x80053a68,4,BASE+4488)
 assert f.invoke(0x9d07eb84,4480)==0 and f.ctrl()==[0,0]
 out['initial_failure']='NULL, root remains zero, errno12'
 # Exercise the real sole caller's positive zeroing and nonpositive paths.
 c=Machine();c.invoke(0x9d081090 if REVISED else 0x9d001240)
 assert c.invoke(0x9d08149c,0)==BASE
 assert c.invoke(0x9d08149c,8)==BASE
 assert c.read(BASE,8)==0 and c.read(BASE+8,1)==0xa5
 assert c.invoke(0x9d08149c,-8)==BASE+8
 assert c.invoke(0x9d08149c,-1)==MASK and c.read(0x80053ad8,4)==22
 before=len(c.control_writes)
 assert c.invoke(0x9d08149c,CAP-BASE)==BASE
 assert c.read(CAP-4,4)==0 and c.ctrl()==[0,0]
 assert c.invoke(0x9d08149c,1)==MASK and c.read(0x80053ad8,4)==12
 assert c.invoke(0x9d08149c,-(CAP-BASE))==CAP
 c.write(0x80053a68,4,CAP+8)
 assert c.invoke(0x9d08149c,0)==MASK and c.read(0x80053ad8,4)==22
 assert c.ctrl()==[0,0] and len(c.control_writes)==before
 out['actual_caller_boundaries']='zero, grow/zero-fill, shrink, exact cap, overflow and invalid upper passed'
 # Previously failing direct entry, retain legacy mode as a negative control.
 u=Machine();u.invoke(0x9d081090 if REVISED else 0x9d001240);up=u.invoke(0x9d07eb84,4480);u.publish(up)
 u.invoke(0x9d081090)
 assert u.read(0x80053a64,4)==0
 assert u.ctrl()==([0,0] if REVISED else [up,1])
 uq=u.invoke(0x9d07eb84,4480);assert uq==up
 assert u.ctrl()==([0,0] if REVISED else [up,1])
 out['direct_DINIT']='PASS: reset root inactive, reused allocation unpublished' if REVISED else 'negative control: stale active root survives reset'
 if REVISED:
  # Differential stock DINIT: all final registers and RAM except reserved bytes.
  stock=Machine(patched=False);hook=Machine()
  stock.publish(0x80053ae8);hook.publish(0x80053ae8)
  stock.invoke(0x9d081090);hook.invoke(0x9d081090)
  assert stock.r==hook.r and stock.mmio==hook.mmio
  assert stock.ram[:0x57ad8]==hook.ram[:0x57ad8]
  assert stock.ram[0x57ae0:]==hook.ram[0x57ae0:]
  assert hook.ctrl()==[0,0] and stock.ctrl()==[0x80053ae8,1]
  out['DINIT_differential']='all 32 registers, MMIO and RAM outside controls equal to stock'
  # Simulated allocator-only lifetime reset does not enter hooked DINIT.
  z=Machine();z.invoke(0x9d081090);zp=z.invoke(0x9d07eb84,4480);z.publish(zp)
  for addr in range(0x80053a4c,0x80053a90,4):z.write(addr,4,0)
  assert z.ctrl()==[zp,1]
  assert z.invoke(0x9d07eb84,4480)==zp and z.ctrl()==[zp,1]
  out['allocator_only_reset']='separate handling required: simulated globals reset leaves stale root active'
 assert hashlib.sha256((ROOT/'stock_pic_2.2.2.0.0.bin').read_bytes()).hexdigest()==SHA
 return out

if __name__=='__main__':print(json.dumps(suite(),indent=2))
