# SPDX-License-Identifier: GPL-2.0-or-later
"""Execute actual B9 PIC instructions and compare to exact B6 baseline.
Only external application/global-getter/I/O functions are summarized.
"""
from pathlib import Path
import sys,json,struct,itertools,hashlib
ROOT=Path(__file__).resolve().parent.parent;OUT=Path(__file__).resolve().parent
sys.path.insert(0,str(OUT));from mips_check import *
old=(ROOT/'b6_candidate_work/pic_2.2.2.0.9.bin').read_bytes();new=(OUT/'pic_2.2.2.1.1.bin').read_bytes()
assert hashlib.sha256(old).hexdigest()=='80723ffbd381e1e6cf401f09cff99591d43a07d91d00d57570fe2dea5265e2f3'
callers=[]
for i in range(0,len(old)-3,4):
 w=struct.unpack_from('<I',old,i)[0]
 if w>>26 in (2,3) and ((w&0x3ffffff)<<2|0x90000000)==WRAPPER:callers.append(BASE+i)
assert len(callers)==16 and {c+8 for c in callers if c+8 in PANEL}==PANEL
# Every emitted word decoded independently and all delay slots checked.
listing=[]
for pc in [0x9d023550,*range(0x9d000d84,0x9d000de8,4)]:
 row=decode(new,pc);listing.append(f'{pc:08x} {struct.unpack_from("<I",new,pc-BASE)[0]:08x} {row}')
 if row[0] in CONTROL:
  assert decode(new,pc+4)[0] not in CONTROL
  if row[0]=='beq':assert 0x9d000d84<=row[3]<0x9d000de8
  if row[0]=='j':assert row[1] in (0x9d000d84,0x9d023558,0x9d02355c)
assert decode(new,0x9d023554)==('addiu','v0','zero',500)
assert decode(old,0x9d023550)==('addu','s0','s3','s0')==decode(new,0x9d000d84)
assert decode(new,0x9d000d88)==('lw','t1',0x44,'sp')
(OUT/'emitted_helper_disassembly.txt').write_text('\n'.join(listing)+'\n')

# Conservative caller continuation liveness: explore both branch paths until
# an ABI call barrier or function return, checking scratch reads before writes.
def rw(row):
 op,*a=row
 if op in ('nop','j'):return set(),set()
 if op=='lui':return set(),{a[0]}
 if op in ('addiu','slti','sltiu','andi','ori','xori','sll','srl'):return {a[1]},{a[0]}
 if op in ('addu','subu','and','or','xor','slt','sltu','lwx'):return {a[1],a[2]},{a[0]}
 if op in ('movn','movz'):return {a[0],a[1],a[2]},set() # conditional write is not a definite kill
 if op in ('lb','lh','lw','lbu','lhu'):return {a[2]},{a[0]}
 if op in ('sb','sh','sw'):return {a[0],a[2]},set()
 if op in ('beq','bne','beql','bnel'):return {a[0],a[1]},set()
 if op in ('blez','bgtz','bltz','bgez','jr'):return {a[0]},set()
 if op=='jal':return set(),{'ra'}
 raise AssertionError(row)
def audit(start):
 todo=[(start,frozenset(('t0','t1','t2')))];seen=set();barriers=[]
 while todo:
  pc,dirty=todo.pop()
  if not dirty or (pc,dirty) in seen:continue
  seen.add((pc,dirty));assert len(seen)<10000
  row=decode(old,pc);reads,writes=rw(row);assert not (reads&dirty),(hex(start),hex(pc),row,dirty)
  remain=set(dirty)-writes;op=row[0]
  if op in CONTROL:
   slot=decode(old,pc+4);r,w=rw(slot);assert not(r&remain),(hex(start),hex(pc+4),slot,remain)
   after=frozenset(remain-w)
   if op in ('jal','jr'):barriers.append(hex(pc));continue
   if op=='j':todo.append((row[1],after))
   elif op in ('beq','bne','beql','bnel'):
    todo.append((row[3],after));todo.append((pc+8,frozenset(remain) if op.endswith('l') else after))
   else:todo.append((row[2],after));todo.append((pc+8,after))
  else:todo.append((pc+4,frozenset(remain)))
 return {'return_address':hex(start),'checked_states':len(seen),'barriers':sorted(set(barriers)),'scratch_read_before_write':False}
liveness=[audit(c+8) for c in callers]

# Actual JAL/delay -> whole wrapper -> helper/epilogue for every direct caller.
cases=0;nonpanel=0;helper_exits=set()
for site,mode,count,gate,key in itertools.product(callers,(0,1,2),(-1,0,1,37,500),(0,1),((0,0),(1,7),(11,127),(0x10001,0x1007f))):
 a,b=CPU(old,gate),CPU(new,gate);slot=int(mode==1)
 for m in (a,b):m.write(GP-0x7c84+slot*4,count,4);m.write(GP-0x7c84+(1-slot)*4,81,4)
 a.call(site,*key,mode);b.call(site,*key,mode)
 active=gate or hashlib.sha256(struct.pack('<I',struct.unpack_from('<I',old,site-BASE+4)[0])).hexdigest()=='c649fcc60d70c4248e94d320e3603d8b89e77ab47051795f9cbc4e7c5a005576'
 panel=site+8 in PANEL
 expected=count if panel and active and count>0 else a.count(slot)
 assert b.count(slot)==expected and b.count(1-slot)==a.count(1-slot)
 assert a.pending(0)==b.pending(0) and a.pending(1)==b.pending(1)
 assert a.applied(0)==b.applied(0) and a.applied(1)==b.applied(1) and a.calls==b.calls
 for i,n in enumerate(REGS):
  if n not in ('t0','t1','t2'):assert a.r[i]==b.r[i],(hex(site),n)
 allow=set(range(GP-0x7c84+slot*4,GP-0x7c84+slot*4+4)) if panel and active and count>0 else set()
 assert all(a.mem.get(x,0)==b.mem.get(x,0) or x in allow for x in set(a.mem)|set(b.mem))
 for pc,row in b.trace:
  if 0x9d000d84<=pc<0x9d000de8 and row[0]=='j':helper_exits.add(row[1])
 if not panel:assert a.mem==b.mem;nonpanel+=1
 cases+=1
assert helper_exits=={0x9d023558,0x9d02355c}

# Real panel handler preludes including status/clamp/equality/argument setup.
handler_cases=0
entries=[(0x9d02a398,0x9d02a3c8,'program',3),(0x9d02a7d0,0x9d02a800,'bank',3),(0x9d02aa74,0x9d02aab4,'program',-1),(0x9d02bc80,0x9d02bcc0,'program',1),(0x9d02dcb8,0x9d02dce8,'program',3),(0x9d02e08c,0x9d02e0b8,'bank',3)]
for entry,site,kind,delta in entries:
 m=CPU(new);m.write(STATE+0x46,2,2);m.write(STATE+0x48,5,2);m.write(GP-0x7c84,123,4)
 event=0x80065000;m.write(event+5,1,1);m.write(event+8,delta,4)
 m.s('a0',STATE);m.s('a1',event);m.s('s0',STATE);m.s('s1',event)
 if entry==0x9d02e08c:m.s('a0',2) # predecessor has already loaded selected bank
 m.run(entry,{site+8})
 target=(2,5+delta) if kind=='program' else (2+delta,5)
 assert m.pending(0)==(*target,0,2) and m.count()==123 and not m.calls
 handler_cases+=1

# Exact ISR counter-service instructions, including gate and zero saturation.
tick_cases=0
for c0,c1,eligible in itertools.product((-1,0,1,2,500),(-1,0,1,2,500),(False,True)):
 m=CPU(new);m.write(GP-0x7c84,c0,4);m.write(GP-0x7c80,c1,4);regs=m.r.copy();m.tick(eligible)
 assert m.r==regs
 assert [m.count(0),m.count(1)]==[c-1 if eligible and c>0 else c for c in (c0,c1)]
 tick_cases+=1
# Actual expiry instructions and actual applied getters, all routing/equality cases.
expiry_cases=0
for mode,key,match_bank,match_prog in itertools.product((0,1,2),((0,0),(11,127)),(False,True),(False,True)):
 slot=int(mode==1);a,b=CPU(old),CPU(new)
 for m in (a,b):
  m.write(GP-0x7c84+4*slot,0,4)
  for off,v in zip((-0x7ca4,-0x7c7c,-0x7c74,-0x7c9c),(*key,1,mode)):m.write(GP+off+4*slot,v,4)
  m.write(STATE+0x4a+2*slot,key[0] if match_bank else (key[0]+1)%12,2)
  m.write(STATE+0x4e+2*slot,key[1] if match_prog else (key[1]+1)%128,2)
  m.expire()
 assert a.mem==b.mem and a.calls==b.calls
 assert len(b.calls)==int(not(match_bank and match_prog)) and b.count(slot)==-1
 expiry_cases+=1
# Counter becomes zero after positive snapshot; interrupt executed at actual PCs.
interrupt_cases=0
for pc in [0x9d02351c,0x9d023550,*range(0x9d000d84,0x9d000de8,4)]:
 m=CPU(new);m.write(GP-0x7c84,1,4);fired=[]
 def inject(cpu,where):
  if where==pc and not fired:fired.append(where);cpu.tick()
 m.inject=inject;m.call(0x9d02a3c8,7,120);m.inject=None
 # Some compare tails are not reached for this caller; record only reached PCs.
 if not fired:continue
 assert m.count()==0 and m.pending()==(7,120,0,2) and not m.calls
 m.expire();assert m.applied(0)==(7,120)==m.applied(1) and m.count()==-1
 interrupt_cases+=1
for site in callers:
 for mode in (0,1,2):
  a,b=CPU(old),CPU(new);slot=int(mode==1)
  for cpu in (a,b):
   cpu.write(GP-0x7c84+4*slot,1,4);fired=[]
   def inject(c,where):
    if where==0x9d023550 and not fired:fired.append(where);c.tick()
   cpu.inject=inject;cpu.call(site,3,97,mode);cpu.inject=None
  if site+8 not in PANEL:assert a.mem==b.mem and a.calls==b.calls and b.count(slot)==500
  else:assert b.count(slot)==0
  interrupt_cases+=1

scenarios={}
def drain(m,n=500):
 for _ in range(n):m.tick()
 m.expire()
for order in ('input_first','expiry_first'):
 for reverse in (False,True):
  m=CPU(new);m.call(0x9d02a3c8,0,1);m.call(0x9d02bcc0,0,2)
  for _ in range(500):m.tick()
  final=1 if reverse else 3
  if order=='input_first':m.call(0x9d02a3c8,0,final);m.expire()
  else:m.expire();m.call(0x9d02a3c8,0,final)
  assert m.applied(0)==(0,final)==m.applied(1) and m.count()==500
  assert len(m.calls)==(2 if order=='input_first' else 3)
  scenarios[order+('_reversal' if reverse else '')]=m.calls
m=CPU(new);m.call(0x9d02a3c8,0,1);m.call(0x9d02bcc0,0,2);m.call(0x9d02aab4,0,1);drain(m)
assert len(m.calls)==1 and m.count()==-1;scenarios['pending_reversal_suppressed']=m.calls
m=CPU(new);m.call(0x9d02a3c8,0,1);m.call(0x9d02a800,1,1);drain(m)
assert m.applied(0)==(1,1)==m.applied(1);scenarios['bank_change']=m.calls
for order in ('input_first','expiry_first'):
 m=CPU(new)
 for t in range(2001):
  if t:m.tick()
  if order=='expiry_first':m.expire()
  if t%50==0:m.call(0x9d02a3c8,0,(t//50+1)%128)
  if order=='input_first':m.expire()
 drain(m)
 assert m.applied(0)==(0,41)==m.applied(1) and m.count()==-1
 assert len(m.calls)==(5 if order=='input_first' else 9)
 scenarios['sustained_'+order]={'application_count':len(m.calls),'final':m.applied(0)}
# Latest force/mode/bank/program overwrite including mixed source routing.
m=CPU(new);m.call(0x9d02a3c8,1,1);m.call(0x9d02d5b8,2,2,1);m.call(0x9d026fe4,3,3,2);m.call(0x9d02a800,4,3,2)
assert m.pending(0)==(4,3,0,2) and m.pending(1)==(2,2,1,1);drain(m)
assert m.count(0)==m.count(1)==-1;scenarios['mixed_source_slot_order']=m.calls

# Inherited B6/B7 actual-byte regression, no symbolic BLOCKS/OVERLAY execution.
sys.path.insert(0,str(ROOT));import b7_combined_instruction_model as inherited
class Center(inherited.Machine):
 def __init__(self,image,*args,**kw):self.image=image;super().__init__(*args,**kw)
 def instruction(self,pc):
  prior=inherited.IMAGE
  try:inherited.IMAGE=self.image;return inherited.decode(pc)
  finally:inherited.IMAGE=prior
center_cases=0
for osc,mode,loops,flag,gate,req in itertools.product((0,1),(0,1,2),((0,0),(1,0),(0,1),(1,1)),(0,1),(0,1),(0,250,650,999,65535)):
 args=([(200,600,450,loops[0]),(700,900,800,loops[1])],osc,flag,gate)
 a,b=Center(old,*args,design=False),Center(new,*args,design=False)
 for cpu in (a,b):cpu.set('gp',GP);cpu.edit(mode,15+osc*0x41,req)
 assert a.m==b.m and a.events==b.events and a.r==b.r
 center_cases+=1
result={'status':'PASS','all_direct_callers':list(map(hex,callers)),'panel_returns':sorted(map(hex,PANEL)),'caller_wrapper_matrix_cases':cases,'nonpanel_equivalence_cases':nonpanel,'real_panel_handler_cases':handler_cases,'real_counter_service_cases':tick_cases,'real_expiry_cases':expiry_cases,'interrupt_to_zero_cases':interrupt_cases,'inherited_B6_actual_instruction_regressions':center_cases,'both_helper_exits':sorted(map(hex,helper_exits)),'caller_scratch_liveness':liveness,'scenarios':scenarios,'instruction_source':'candidate payload bytes only; independent raw decoder; no symbolic overlays','ABI':'callee-saved/SP/GP/FP/RA, caller canary, o32 home-area clobbers and global-getter volatile clobbers checked','limits':['Program application/global-getter external contracts summarize their effects; preset I/O/audio and complete hardware interrupts are not emulated.','Counter-service instructions and expiry/getter instructions execute exactly; IRQ register save/restore is an explicit contract.','Inherited B6 tests compare actual Center/endpoint code with original engine/UI/MIDI call summaries.']}
(OUT/'b9_instruction_validation.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k not in ('caller_scratch_liveness','scenarios')},indent=2))
