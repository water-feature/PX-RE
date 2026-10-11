#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Run operation words, including their displaced stock prologue words.
Worker bodies/IRQ delivery are explicit contracts; no complete caller closure claim.
"""
from pathlib import Path
import struct,json
import validate_pic_emission as v
O=Path(__file__).resolve().parent;R=O.parent
m=v.m;prior=m.decode

def decode(b,pc):
 w=struct.unpack_from('<I',b,pc-m.BASE)[0]
 if w>>26==0 and w&63==9:return ('jalr',m.REGS[w>>21&31])
 if w&0xffe0ffff==0x40006000:return ('mfc0_status',m.REGS[w>>16&31])
 if w&0xffe0ffff==0x40004800:return ('mfc0_count',m.REGS[w>>16&31])
 return prior(b,pc)
m.decode=decode
m.CONTROL.add('jalr')
class CPU(v.CPU):
 def __init__(self,img):
  super().__init__(img);self.count=0;self.clock_step=100000000;self.reply=True;self.workers=[];self.q=False
 def simple(self,row):
  if row[0]=='mfc0_status':self.s(row[1],self.status);return
  if row[0]=='mfc0_count':self.s(row[1],self.count);self.count=(self.count+self.clock_step)&0xffffffff;return
  super().simple(row)
 def run(self,pc,stops,maxsteps=3000):
  for _ in range(maxsteps):
   if pc in stops:return pc
   if self.inject:self.inject(self,pc)
   if self.external(pc):pc=self.g('ra');continue
   row=decode(self.image,pc);op=row[0];self.trace.append((pc,row))
   if op in m.CONTROL:
    annul=False
    if op in ('beq','bne','beql','bnel'):
     take=(self.g(row[1])==self.g(row[2]))==(op in ('beq','beql'));target=row[3] if take else pc+8;annul=not take and op.endswith('l')
    elif op in ('blez','bgtz','bltz','bgez'):
     x=m.signed(self.g(row[1]));take={'blez':x<=0,'bgtz':x>0,'bltz':x<0,'bgez':x>=0}[op];target=row[2] if take else pc+8
    else:
     target=self.g(row[1]) if op in ('jr','jalr') else row[1]
     if op in ('jal','jalr'):self.s('ra',pc+8)
    if not annul:self.fetch_simple(pc+4)
    pc=target
   else:self.simple(row);pc+=4
  raise AssertionError(('instruction limit',hex(pc)))
 def external(self,pc):
  if pc==0x9d075c1c and self.g('a0')>>16==0x4052:self.q=True
  if pc==0x9d07c114:return super().external(0x9d075c1c)
  frames={0x9d022ebc:('load',None),0x9d046b64:('save',40),0x9d046de0:('bank_export',48),
          0x9d046e54:('edit_apply',24),0x9d04cd1c:('defaults',None)}
  if pc in frames:
   name,n=frames[pc];self.workers.append(name)
   assert self.read(v.S+54,1)==4
   sp=self.g('sp')
   args=[self.g(r) for r in ('a0','a1','a2','a3')]
   # The actual two stock prologue words ran. Read their frame/RA offset directly.
   entry=pc-8;w1=self.read(entry,4);w2=self.read(entry+4,4)
   assert w1>>26==9 and w1>>21&31==29 and w1>>16&31==29
   frame=-(w1&65535 if w1&32768==0 else (w1&65535)-65536)
   assert w2>>26==43 and w2>>16&31==31
   assert args==[11,22,33,44]
   assert self.read(sp+frame+16,4)==0x11223344 and self.read(sp+frame+20,4)==0x55667788
   ra=self.read(sp+(w2&65535),4);self.s('sp',sp+frame);self.s('ra',ra)
   # o32 home area and volatile clobbers, then stock return contract.
   for i in list(range(2,16))+[24,25]:self.r[i]=0xbad00000+i
   for off in range(0,16,4):self.write(sp+frame+off,0xdecafbad,4)
   self.s('v0',123);return True
  return super().external(pc)

def main():
 a=json.loads((O/'pic_operations_assembly.json').read_text());labels={k:int(x,16) for k,x in a['labels'].items()}
 b=bytearray((R/'b14_stable_frame_packaging_work/pic_2.2.2.1.7.bin').read_bytes())
 helpers=(O/'pic_helpers_unplaced.bin').read_bytes();ops=(O/'pic_operations_unplaced.bin').read_bytes()
 b[0x2a0:0x2a0+len(helpers)]=helpers
 b.extend(b'\xff'*(0x90000+len(ops)-len(b)));b[0x90000:]=ops
 stop=0x9d088000;cases=[]
 def cpu():
  c=CPU(b);c.s('ra',stop);c.run(labels['b15_pic_init'],{stop});return c
 def run(c,name,*args,stops=None,maxsteps=20000000):
  for r,x in zip(('a0','a1','a2','a3'),args):c.s(r,x)
  c.s('ra',stop);saved={r:c.g(r) for r in ('s0','s1','s2','s3','s4','s5','s6','s7','gp','fp','sp')}
  c.run(labels[name],stops or {stop},maxsteps=maxsteps)
  if stops is None:
   for r,x in saved.items():assert c.g(r)==x,(name,r)
   assert c.g('ra')==stop
  return c.g('v0')
 def irq(c,pc):
  if not(c.q and c.reply):return
  c.q=False;data=c.sent[-1]&65535;tag=data>>9
  # Deliver all snapshot messages and the ordered barrier through real receive words.
  saved=c.r.copy();inj=c.inject;c.inject=None
  for p in range(4):
   epoch=c.read(v.S+12*p+6,1)
   run(c,'b15_pic_receive',0x4051,epoch<<9|p<<7|7|0x40)
  run(c,'b15_pic_receive',0x4052,tag<<9|15)
  c.r=saved;c.inject=inj
 for name in ('b15_whole_load','b15_whole_save','b15_whole_bank_export','b15_whole_edit_apply','b15_whole_defaults'):
  c=cpu();c.inject=irq;c.write(c.g('sp')+16,0x11223344,4);c.write(c.g('sp')+20,0x55667788,4)
  if name=='b15_whole_save':c.write(v.S,1,2) # requires a drain, rather than fast path
  assert run(c,name,11,22,33,44)==123 and len(c.workers)==1
  assert c.read(v.S+54,1)==0
  assert c.read(0x8000046c+2*0x1c,2)==7
 cases.append('five whole workers run only after applied query snapshot; ABI/fifth/sixth args retained')
 for name in ('b15_whole_load','b15_whole_save','b15_whole_bank_export','b15_whole_edit_apply','b15_whole_defaults'):
  c=cpu();c.reply=False;c.write(v.S,1,2)
  assert run(c,name,11,22,33,44)==0xffffffff and not c.workers
  assert c.read(v.S+54,1)==3 and c.read(v.S+56,4)==1
 cases.append('five whole workers suppressed on Count deadline failure before any stock body')
 c=cpu();c.inject=irq;c.write(v.S+54,3,1)
 assert run(c,'b15_operation_begin',1)==1 and c.read(v.S+54,1)==4
 assert run(c,'b15_operation_begin',1)==2
 run(c,'b15_operation_end',2);assert c.read(v.S+54,1)==4
 run(c,'b15_operation_end',1);assert c.read(v.S+54,1)==0
 cases.append('ERROR query recovery; nested token cannot release root lock')
 for status in (0,2,3,5):
  c=cpu();c.status=status
  assert not run(c,'b15_operation_begin',1) and c.status==status and not c.sent
 cases.append('interrupt-disabled/exception contexts refused without waiting')
 # Both import branches must take the common parser epilogue on failure.
 for name in ('b15_import_store_guard','b15_import_edit_guard'):
  c=cpu();c.reply=False;before=c.r.copy()
  run(c,name,stops={0x9d0783d8})
  assert c.g('sp')==before[m.R['sp']] and not c.workers
  assert not any(x[0] in (0x9d0744cc,0x9d046b5c,0x9d041e10,0x9d07dc88) for x in c.trace)
 cases.append('both import guards reach parser epilogue on timeout; import/save/load/success ACK not reached')
 # Context helpers affect precisely A/B/both; stale feedback cannot write a new epoch.
 for bank,pairs in ((0,(0,1)),(1,(2,3)),(2,(0,1,2,3))):
  c=cpu();c.write(v.S+54,4,1)
  for p in range(4):c.write(v.S+12*p+4,9,1)
  assert run(c,'b15_bulk_begin',bank)==1
  packets=c.sent.copy();assert len(packets)==len(pairs)
  for p,word in zip(pairs,packets):
   assert word>>16==0x404f and word&65535==0x200|(1<<p)
  for p in range(4):
   assert c.read(v.S+12*p+6,1)==int(p in pairs)
   assert c.read(v.S+12*p+4,1)==(0 if p in pairs else 9)
  assert c.read(v.S+60,4)==1
  run(c,'b15_bulk_end',bank)
  assert len(c.sent)==2*len(pairs) and all(w>>16==0x4050 for w in c.sent[len(pairs):])
  assert c.read(v.S+60,4)==0
  for p in pairs:assert not run(c,'b15_pic_receive',0x4051,p<<7|16)
 cases.append('bulk A/B/both masks, epochs, actual invalidation, BEGIN/END packets and stale mirror rejection')
 # Import success resumes at original JAL continuation, with the original frame.
 for name,pc in (('b15_import_store_guard',0x9d07823c),('b15_import_edit_guard',0x9d0783a8)):
  c=cpu();c.inject=irq;before=c.r.copy()
  run(c,name,stops={pc+8})
  assert c.g('sp')==before[m.R['sp']] and c.g('ra')==pc+8
  assert c.read(v.S+54,1)==4 and c.read(v.S+10,2)==1
  run(c,'b15_import_exit',stops={0x9d0783e0})
  assert c.read(v.S+54,1)==0 and c.read(v.S+10,2)==0
 cases.append('import success uses original continuation/RA; exact parser exit releases owning token')
 # READY coverage churn cannot bypass the finite poll budget.
 c=cpu();c.clock_step=0
 def churn(c,pc):
  irq(c,pc)
  if pc==labels['op_wait'] and c.g('s2')>4:c.s('s2',4)
  if pc==labels['b15_pic_fence_finish']:c.write(v.S+7,1,1)
 c.inject=churn
 assert not run(c,'b15_operation_begin',1) and c.read(v.S+56,4)==2
 cases.append('READY/dirty churn also reaches finite failure; no budget-bypassing finish loop')
 c=cpu();c.count=0xfffffff0;c.reply=False
 assert not run(c,'b15_operation_begin',1) and c.read(v.S+56,4)==1
 cases.append('Count deadline crosses32-bit wrap correctly')
 # A dead Count still terminates by finite poll ceiling, including READY churn.
 c=cpu();c.clock_step=0;c.reply=False
 def trim(c,pc):
  if len(c.trace)>10000:c.trace.clear()
 c.inject=trim
 assert not run(c,'b15_operation_begin',1) and c.read(v.S+56,4)==2
 cases.append('stopped Count terminates by independent 65536-poll ceiling')
 for off in range(0,len(ops),4):
  pc=0x9d090000+off;row=decode(b,pc)
  if row[0] in m.CONTROL:assert decode(b,pc+4)[0] not in m.CONTROL
 report={'status':'OPERATION_COMPONENT_PASS_NOT_RELEASE','cases':cases,'emitted_operation_bytes':len(ops),
  'combined_emitted_bytes':len(ops)+len(helpers),'complete_caller_closure':False,'complete_PIC_size_established':False,
  'synthetic_image_written':False,'limitations':'Stock worker bodies and IRQ delivery are contracts. Ancestor callers, pre-store freeze, bulk/reset installation routing, terminal UI and placement remain unresolved.'}
 (O/'pic_operation_execution.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
if __name__=='__main__':main()
