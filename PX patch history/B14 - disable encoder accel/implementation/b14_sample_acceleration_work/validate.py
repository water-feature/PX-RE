# SPDX-License-Identifier: GPL-2.0-or-later
from pathlib import Path
import sys,json,itertools,struct
O=Path(__file__).resolve().parent;R=O.parent
sys.path.insert(0,str(R/'b15_candidate_work'));import validate_pic_emission as v
sys.path.insert(0,str(R/'b14_sample_acceleration_investigation'));from check_layout import ref
m=v.m;image=(O/'pic_2.2.2.1.10_B14_sample_acceleration_candidate.bin').read_bytes();old=(R/'b15_candidate_work/pic_2.2.2.1.9_B15_LFO_fade_candidate.bin').read_bytes();stop=0x9d088000;n=0
# Real emitted decoder, independent baseline reference. Preserve live scanner registers.
for enc,q,t,w,d,lastsame in itertools.product(range(21),range(16),(0,228,229,233,234,237,238,243,244,249,250,255),(0,1,2,3,255),(0,1),(True,False)):
 c=v.CPU(image);base=0x80010bf0+12*enc;last=q if lastsame else (q+1)%16
 for off,value in ((0,q>>2),(1,q&3),(2,w),(4,d),(5,t),(6,last)):c.write(base+off,value,1)
 c.s('a0',enc);c.s('ra',stop);before={r:c.g(r) for r in ['t2','t3','t4','t5','t6','t7','t8','gp','sp','ra',*m.REGS[16:24]]}
 c.run(0x9d07a298,{stop});actual=(m.signed(c.g('v0')),*(c.read(base+x,1) for x in (2,4,5,6)))
 assert actual==ref(enc,q,t,w,d,last),(enc,q,t,w,d,last,actual)
 assert all(c.g(r)==x for r,x in before.items());n+=1
class Service(v.CPU):
 def __init__(self,im,arrival):super().__init__(im);self.events=[];self.arrival=arrival
 def external(self,pc):
  if pc!=0x9d07db44:return False
  enc=self.g('a0');self.events.append((enc,m.signed(self.g('a1'))));assert self.status==self.original_status
  if len(self.events)==1:self.write(0x80010bf0+enc*12+8,self.arrival,4)
  ra=self.g('ra');sp=self.g('sp')
  for r in [*m.REGS[2:16],'t8','t9']:self.s(r,0xbad00000)
  for off in range(0,16,4):self.write(sp+off,0xdecafbad,4)
  self.s('ra',ra);return True
services=0
for enc,count,arrival,status in itertools.product(range(21),(-999,-10,-1,0,1,10,999),(-3,0,4),(0,1,0x10400001)):
 c=Service(image,arrival);c.original_status=c.status=status;base=0x80010bf0+12*enc;c.write(base+8,count,4);c.s('a0',enc);c.s('ra',stop)
 before={r:c.g(r) for r in ['sp','gp',*m.REGS[16:24]]}
 c.run(0x9d07a208,{stop},maxsteps=15000)
 expected=[] if count==0 else [(enc,count)] if enc in (4,5,18,19) else [(enc,1 if count>0 else -1)]*abs(count)
 assert c.events==expected and m.signed(c.read(base+8,4))==(arrival if count else 0)
 assert c.status==status and all(c.g(r)==x for r,x in before.items());services+=1
# Actual main signal5 table -> B15 guarded encoder -> original clamp wrapper -> setter entry.
# Getter executes as its documented storage lookup; setters/notifications not run.
class Numeric(v.CPU):
 def external(self,pc):
  if pc!=0x9d04d300:return False
  result=self.read(0x8000046c+2*(self.g('a0')*0x6b7+self.g('a1')),2);self.s('v0',result);return True
numeric=0
for enc,inst,selector,delta in itertools.product((5,18,19),(0,1),(0,1,2),(-999,-40,-1,1,40,999)):
 outputs=[]
 for im in (old,image):
  c=Numeric(im);state=0x80052e18;event=0x80037cf8
  c.write(state+6,inst,2);c.write(state+0x44,selector,2);c.write(event+4,enc,1);c.write(event+8,delta,4)
  pid={5:15,18:7,19:9}[enc]+inst*0x41
  for bank in (0,1):c.write(0x8000046c+2*(bank*0x6b7+pid),100,2)
  for reg,val in [('a0',state),('a1',event),('s0',state),('s1',event)]:c.s(reg,val)
  c.run(0x9d0292e4,{0x9d04dacc});outputs.append(tuple(c.g(r) for r in ('a0','a1','a2','a3')))
 assert outputs[0]==outputs[1]==(0,selector,pid,max(0,min(999,100+delta))),outputs;numeric+=1
# Size's mode-specific numeric paths, before stock notifications.
for entry,pid,maximum in ((0x9d02a06c,0x1d,15),(0x9d02da9c,0xb,999),(0x9d02e388,0xd,999),(0x9d02d390,0x5e,15),(0x9d02dc90,0x4c,999),(0x9d02e3b0,0x4e,999)):
 for selector,delta in itertools.product((0,1,2),(-999,-1,1,999)):
  outputs=[]
  for im in (old,image):
   c=Numeric(im);state=0x80052e18;event=0x80037cf8;c.write(state+0x44,selector,2);c.write(event+8,delta,4)
   for bank in(0,1):c.write(0x8000046c+2*(bank*0x6b7+pid),5,2)
   c.s('a0',0);c.s('s0',state);c.s('s1',event);c.run(entry,{0x9d04dacc});outputs.append(tuple(c.g(r) for r in('a0','a1','a2','a3')))
  assert outputs[0]==outputs[1]==(0,selector,pid,max(0,min(maximum,5+delta))),outputs;numeric+=1
report=dict(status='PASS_EMITTED_TARGETED_HOST_CHECKS',decoder_cases=n,service_cases=services,numeric_handler_cases=numeric,hardware='NOT VERIFIED',limits='Decoder/service real words; event callback mocked with adversarial ABI clobbers and ISR-arrival storage. Numeric routes stop at setter entry; getter storage lookup modeled. Existing B15/hardware limits inherited.')
(O/'validation_results.json').write_text(json.dumps(report,indent=2)+'\n');print(report)
