#!/usr/bin/env python3
"""Execute installed wrapper and actual inherited/stock SampleVel store path."""
import os,json,struct
os.environ['B15_PLACED']='1'
import validate_pic_absolute as v
O=v.O;m=v.m
class CPU(v.CPU):
 def __init__(self):super().__init__();self.calls=[];self.write(0x80006ffe,1,2)
 def external(self,pc):
  if pc in (0x9d04dacc,0x9d04dad4,0x9d075c1c):return False
  if pc in (0x9d04e970,0x9d031b70):
   self.calls.append((hex(pc),[self.g(r) for r in ('a0','a1','a2','a3')],self.status));self.s('v0',0);return True
  return super().external(pc)
def main():
 c=CPU();cases=[]
 for origin in (0,1):
  for bank in (0,1,2):
   for pid in (0x1c,0x5d):
    for value in (0,1,2,16):
     c.s('a0',origin);c.s('a1',bank);c.s('a2',pid);c.s('a3',value);c.s('ra',v.STOP)
     saved={n:c.g(n) for n in ('s0','s1','s2','s3','s4','s5','s6','s7','fp','sp','gp')};irq=c.status
     c.run(0x9d04dacc,{v.STOP},maxsteps=100000)
     assert all(c.g(n)==x for n,x in saved.items()) and c.status==irq
     targets=(0,1) if bank==2 else (bank,)
     maximum=c.maxima[2*(0 if bank==2 else bank)+(pid==0x5d)]
     for target in targets:assert c.read(0x8000046c+2*(target*0x6b7+pid),2)==min(value,maximum),(bank,pid,value,target)
     assert c.sent and c.sent[-1]&65535==min(value,maximum)
     cases.append((origin,bank,pid,value))
 report={'status':'STOCK_SETTER_PASS','cases':len(cases),'modeled_callees':c.calls,'limits':'Actual1.7 inherited store/clamp/send path with audio-ready6ffe=1; selected UI bank and physical send are contracts; MIDI output disabled6fe6=0.'}
 (O/'absolute_stock_setter_results.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:report[k] for k in ('status','cases','limits')},indent=2))
if __name__=='__main__':main()
