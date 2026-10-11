#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Real emitted MIPS component tests; synthetic in-memory overlay only."""
from pathlib import Path
import json,struct,os
import validate_pic_operations as p
O=Path(__file__).resolve().parent;R=O.parent;m=p.m;S=p.v.S
meta=json.loads((O/'pic_absolute_assembly.json').read_text());L={k:int(v,16) for k,v in meta['labels'].items()}
raw=(R/'b14_stable_frame_packaging_work/pic_2.2.2.1.7.bin').read_bytes();img=bytearray(raw);code=(O/'pic_absolute_unplaced.bin').read_bytes();img[0x2a0:0x2a0+len(code)]=code
originalL=L.copy()
placed=os.environ.get('B15_PLACED')=='1'
if placed:
 integration=json.loads((O/'absolute_pic_integration.json').read_text());L={k:int(v,16) for k,v in integration['labels'].items()};img=bytearray((O/'pic_B15_absolute_INCOMPLETE.bin').read_bytes())
STOP=0x9d088000
class CPU(p.CPU):
 def __init__(self):super().__init__(img);self.work=[];self.maxima=[3,4,6,8];self.setter_calls=[]
 def external(self,pc):
  answer=0;sp=self.g('sp');ra=self.g('ra')
  if pc==0x9d04dad4:
   self.s('ra',self.read(sp+44,4));self.s('sp',sp+48);return self.external(0x9d04dacc)
  if pc==0x9d0816e0:answer=max(0,min(self.g('a2'),m.signed(self.g('a0'))+m.signed(self.g('a1'))))
  elif pc==0x9d0792c0:answer=self.maxima[2*self.g('a0')+self.g('a1')]
  elif pc==0x9d031b70:answer=0
  elif pc==0x9d04dacc:
   origin,bank,pid,value=[self.g(r) for r in ('a0','a1','a2','a3')]
   if pid in (0x1c,0x5d,0x13,0x54):value=min(value,self.maxima[2*bank+(pid>=0x41)])
   self.setter_calls.append((bank,pid,value));self.write(0x8000046c+2*(bank*0x6b7+pid),value,2)
   self.s('a0',((bank*0x800+pid)<<16)|value);self.run(L['b15_transport'],{ra});answer=value
  elif pc in (0x9d07c370,0x9d040420,0x9d0744d4,0x9d046e54,0x9d04cd1c,0x9d07c2b4):
   self.work.append(pc);entry=pc-8;w1=struct.unpack_from('<I',raw,entry-m.BASE)[0];w2=struct.unpack_from('<I',raw,entry-m.BASE+4)[0]
   n=-(w1&65535 if w1&32768==0 else (w1&65535)-65536);ra=self.read(sp+(w2&65535),4);self.s('sp',sp+n);sp+=n;self.s('ra',ra);answer=123
   assert self.read(sp+16,4)==0x11223344 and self.read(sp+20,4)==0x55667788
  else:return p.v.CPU.external(self,pc)
  for i in list(range(2,16))+[24,25]:self.r[i]=0xbad00000+i
  for off in range(0,16,4):self.write(sp+off,0xdecafbad,4)
  self.s('v0',answer);self.s('ra',ra);return True

def main():
 cases=[];c=CPU()
 def call(name,*args,stop=STOP):
  for n,x in zip(('a0','a1','a2','a3'),args):c.s(n,x)
  c.s('ra',stop);status_before=c.status;saved={r:c.g(r) for r in ('s0','s1','s2','s3','s4','s5','s6','s7','gp','fp','sp')};c.run(L[name],{stop},maxsteps=100000)
  for n,x in saved.items():assert c.g(n)==x,(name,n,hex(c.g(n)),hex(x))
  assert c.g('ra')==stop and c.status==status_before
  return c.g('v0')
 def status(pair,epoch,n):
  call('b15_pic_receive',0x4058,epoch&65535);call('b15_pic_receive',0x4059,epoch>>16);return call('b15_pic_receive',0x404a,pair<<7|n)
 call('b15_pic_init');assert c.read(S,64)==0
 for bank in (0,1):
  for pid in (0x12,0x53):c.write(0x8000046c+2*(bank*0x6b7+pid),1,2)
 for pair in range(4):assert status(pair,0,pair+2)
 # Actual shadow seeds transient cursor, but no reverse stored setting write.
 for bank in (0,1):
  for pid in (0x1c,0x5d):assert c.read(0x8000046c+2*(bank*0x6b7+pid),2)==0
 call('b15_pic_service');assert len(c.redraws)==4;cases.append('status-only framing, independent cursors; redraw without parameter stores')
 c.write(c.g('sp')+16,16,4);call('b15_encoder',0,2,0x1c,1)
 assert c.setter_calls[-2:]==[(0,0x1c,3),(1,0x1c,5)],c.setter_calls
 # Feedback from earlier positive edits cannot reset a committed cursor.
 assert not status(0,0,1);assert c.read(S+5,1)==3
 for d in [-1,1]*250:
  c.write(c.g('sp')+16,16,4);call('b15_encoder',0,0,0x1c,d&0xffffffff)
 assert c.read(0x800004a4,2)==3
 c.write(c.g('sp')+16,16,4);call('b15_encoder',0,0,0x1c,0xffffffff)
 cases.append('A+B dynamic3/6 limits, immediate stores;500 rapid reversals ignore delayed base status')
 # On retains cursor, next movement starts at retained actual/intended sample.
 call('b15_transport',0x001c0000);c.write(0x800004a4,0,2);assert c.read(S+5,1)==2
 c.write(c.g('sp')+16,16,4);call('b15_encoder',0,0,0x1c,1);assert c.read(0x800004a4,2)==3
 cases.append('On sends zero but retains cursor; next detent avoids hidden-zero jump')
 c.sent=[];call('b15_transport',0x00140041);epoch=c.read(S,4);assert epoch>1 and c.read(S+4,1)==0 and c.read(S+5,1)==0
 assert [x>>16 for x in c.sent]==[0x404b,0x4053,0x14],c.sent
 assert not status(0,0,16);assert status(0,epoch,2)
 assert c.read(S+4,1)==2 and c.read(S+5,1)==2
 # Exhaustion cannot alias an old token.
 c.write(S,0xffffffff,4);call('b15_invalidate',0);assert c.read(S+9,1)==1;assert not status(0,0,16)
 cases.append('lifecycle token before ordinary command; stale full32 epoch and exhausted generation rejected')
 call('b15_pic_init');root=0x80052e18;c.write(root+6,1,2);c.s('s0',root);c.s('s1',64);c.sent=[]
 call('b15_capture_prepare',2);assert [x>>16 for x in c.sent]==[0x4048,0x4048]
 for bank in (0,1):c.write(0x8000046c+2*(bank*0x6b7+0x55),67,2)
 c.sent=[];call('b15_capture_commit',0,2,0x54,0);assert [x>>16 for x in c.sent]==[0x4049,0x4049] and all(x&127==67 for x in c.sent)
 cases.append('capture prepare A+B before panic and commit final stored keys; o32 preservation')
 for name,bank in [('b15_replay',0),('b15_replay',1),('b15_replay',2),('b15_reset',0),('b15_load',0),('b15_import',0),('b15_edit_apply',0),('b15_defaults',0)]:
  call('b15_pic_init');c.sent=[];c.work=[];c.write(c.g('sp')+16,0x11223344,4);c.write(c.g('sp')+20,0x55667788,4)
  assert call(name,bank,22,33,44)==123 and len(c.work)==1
  assert not c.read(S+44,4)
  cmds=[x>>16 for x in c.sent]
  if name in ('b15_replay','b15_reset'):assert 0x404f in cmds and cmds[-1]==0x4050
  else:assert cmds[-1]==0x4057
 cases.append('raw/replay/reset wrappers preserve return,register/stack args; bulk masks and no waiting phase')
 # Verify likely-branch trampolines execute the copied slot only when taken.
 for name,entry in [('compare',0x9d04feb4),('restore',0x9d04ffc4)]:
  w=struct.unpack_from('<I',raw,entry-m.BASE+4)[0];im=w&65535;target=entry+8+(im if im<32768 else im-65536)*4
  for bank in (0,1):
   c.s('a0',bank);c.s('ra',STOP);c.run(L['stock_'+name],{entry+12,target});assert c.trace[-1]
 cases.append('stock compare/restore BNE-likely trampolines preserve branch/annul destinations')
 # Whole immediate-store wrapper, with interrupts enabled or already disabled.
 for irq in (0,1):
  c.status=irq;call('b15_setter',0,0,0x1c,2);assert c.status==irq and c.read(0x800004a4,2)==2
 c.status=0;c.sent=[];c.write(c.g('sp')+16,0x11223344,4);c.write(c.g('sp')+20,0x55667788,4)
 call('b15_cold_defaults');assert not c.sent and c.read(S,64)==0 and c.status==0;c.status=1
 cases.append('SampleVel setter atomic store+send restores IE both ways; cold defaults initializes state without transport')
 # Reduced ISR save set must cover every register written by the leaf receiver.
 receive_rows=meta['rows'][(originalL['b15_pic_receive']-m.BASE-0x2a0)//4:(originalL['b15_pic_service']-m.BASE-0x2a0)//4]
 writes={r[1] for r in receive_rows if r[0] not in ('sb','sh','sw','j','jr','beq','bne','nop')}
 assert writes <= {'v0','t0','t1','t2','t3','t9'} and not any(r[0] in ('jal','jalr') for r in receive_rows)
 cases.append('reduced ISR save set covers all emitted receiver writes; leaf has no callee clobbers')
 # Execute actual baseline serialization loops immediately after an edit, before
 # any display feedback. This is stock code, not a serializer contract.
 for bank in (0,1):
  for pid,n in ((0x1c,2+bank),(0x5d,3+bank)):
   call('b15_setter',0,bank,pid,n)
 c.s('s1',0x80060000);c.run(0x9d046c40,{0x9d046c88},maxsteps=50000)
 for bank in (0,1):
  for pid in (0x1c,0x5d):assert c.read(0x80060000+bank*0x800+pid,1)==c.read(0x8000046c+2*(bank*0x6b7+pid),2)
 before_params={bank:c.read(0x8000046c+2*(bank*0x6b7+0x1c),2) for bank in (0,1)}
 for pair in range(4):status(pair,c.read(S+16*pair,4),1)
 for bank,n in before_params.items():assert c.read(0x8000046c+2*(bank*0x6b7+0x1c),2)==n
 old_epoch=c.read(S,4);c.write(c.g('sp')+16,0x11223344,4);c.write(c.g('sp')+20,0x55667788,4)
 call('b15_load',0,22,33,44);assert not status(0,old_epoch,16)
 cases.append('actual stock A/B serialization loops save immediate P with feedback pending; display cannot rewrite P and old context is rejected after load')
 # Pending/unavailable is a display sentinel, not the hidden stored request.
 call('b15_pic_init');c.write(0x80000490,1,2);c.write(0x800004a4,3,2)
 assert call('b15_effective_get',0,0x1c)==65535
 buf=0x80061000;c.write(buf,0,4);assert call('b15_format',0x1c,65535,buf)==buf and c.read(buf,3)==0x2d2d
 c.write(0x80000490,0,2);assert call('b15_effective_get',0,0x1c)==3
 c.write(buf,0x203a6c65,4);c.write(buf+4,0,1);assert call('b15_format',0x5d,65535,buf)==buf and c.read(buf+4,3)==0x2d2d and c.read(buf,4)==0x203a6c65
 # Guard ordinary formatter routes, including FFFF on unrelated IDs.
 for pid,n in ((0x1c,2),(0x5d,0),(0x20,65535)):
  c.s('a0',pid);c.s('a1',n);c.s('a2',buf);c.s('ra',STOP);sp=c.g('sp')
  c.run(L['b15_format'],{0x9d05f7fc});assert c.g('sp')==sp-48 and c.read(sp-4,4)==STOP
  c.s('sp',sp)
 cases.append('actual unknown uses display-only FFFF/--, disabled reveals P; ordinary formatter trampoline unchanged')
 # Every emitted control delay slot is noncontrol; reject bad branch displacement.
 controls=0
 pcs=[int(pc,16) for pc,row in integration['pc_rows']] if placed else range(m.BASE+0x2a0,m.BASE+0x2a0+len(code),4)
 for pc in pcs:
  row=m.decode(img,pc)
  if row[0] in m.CONTROL:
   controls+=1;assert m.decode(img,pc+4)[0] not in m.CONTROL,(hex(pc),row)
 report={'status':'EMITTED_COMPONENT_PASS_NOT_RELEASE','cases':cases,'control_delay_slots_checked':controls,'bytes':len(code),'limits':('Fitted/scattered emitted components; stock setter/worker contracts and modeled feedback. Not a full paired or physical IRQ test.' if placed else 'Synthetic overlay exceeds cave; stock setter/worker contracts and modeled feedback. Not a fitted payload or physical IRQ test.')}
 (O/('absolute_pic_placed_execution.json' if placed else 'absolute_pic_execution.json')).write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
if __name__=='__main__':main()
