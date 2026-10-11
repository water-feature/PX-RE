"""Execute fitted lifecycle roots without whole-lifecycle-body substitutions.
Peripheral and listed stock dependency contracts are explicit in each result.
"""
import os,json,struct,hashlib,io
from contextlib import redirect_stdout
os.environ['B15_PLACED']='1'
import validate_pic_absolute as v
with redirect_stdout(io.StringIO()):
 import validate_absolute_formatter as f
O=v.O;BASE=v.m.BASE;S=v.S;STOP=v.STOP
old_decode=v.p.decode
def decode(b,pc):
 w=struct.unpack_from('<I',b,pc-BASE)[0];names=v.m.REGS
 if w>>26==31 and w&63==0:return ('ext',names[(w>>16)&31],names[(w>>21)&31],(w>>6)&31,((w>>11)&31)+1)
 if w>>26==28 and w&63==2:return ('mul',names[(w>>11)&31],names[(w>>21)&31],names[(w>>16)&31])
 if w>>26==17:
  rs=(w>>21)&31;rt=(w>>16)&31;fs=(w>>11)&31;fd=(w>>6)&31
  if rs in (0,4):return ('mfc1' if rs==0 else 'mtc1',names[rt],fs)
  if rs==20 and w&63==32:return ('cvt_s_w',fd,fs)
 if w&0xffe007ff==0x7c000420:return ('seh',names[(w>>11)&31],names[(w>>16)&31])
 return old_decode(b,pc)
v.p.decode=decode
v.m.decode=decode
roots={'replay':0x9d07c368,'load':0x9d040418,'import':0x9d0744cc,'edit_apply':0x9d046e4c,
 'defaults':0x9d04cd14,'reset':0x9d07c2ac,'compare':0x9d04feb4,'restore':0x9d04ffc4,
 'load_bypass':0x9d02e238,'startup':0x9d052d0c}
class CPU(f.CPU):
 def __init__(self,fitted=True):
  super().__init__();self.image=bytearray(v.img if fitted else v.raw);self.models=[];self.stream=0;self.delays=[];self.stale=[];self.injected=set();self.root=None;self.fpr={};self.ready_reads=0
  self.write(0x80006ffe,1,2)
 def simple(self,row):
  if row[0]=='seh':
   x=self.g(row[2])&65535;self.s(row[1],x if x<32768 else x-65536);return
  if row[0]=='ext':self.s(row[1],(self.g(row[2])>>row[3])&((1<<row[4])-1));return
  if row[0]=='mul':self.s(row[1],self.g(row[2])*self.g(row[3]));return
  if row[0]=='mtc1':self.fpr[row[2]]=self.g(row[1]);return
  if row[0]=='mfc1':self.s(row[1],self.fpr.get(row[2],0));return
  if row[0]=='cvt_s_w':self.fpr[row[1]]=struct.unpack('<I',struct.pack('<f',v.m.signed(self.fpr.get(row[2],0))))[0];return
  super().simple(row)
 def read(self,addr,n):
  if addr==self.g('gp')-31660 and any(a>>16==0x4020 for a in self.sent):
   self.models.append('0794d0 group-info completion flag (modeled IRQ response)');return 1
  if addr==self.g('gp')-31652 and any(a>>16==0x4039 for a in self.sent):
   self.models.append('0795b8/07960c query completion flag (modeled IRQ response)');return 1
  if addr in (0xbf821410,0xbf821420):
   if addr==0xbf821410:return 1
   # Deterministic flash stream: byte values, all valid <=16 for SampleVel.
   result=self.stream%17;self.stream+=1;return result
  return super().read(addr,n)
 def external(self,pc):
  # No substitutions at any lifecycle root or its +8 displaced-prologue resume.
  if pc==0x9d075c24:
   self.models.append('075c24 physical transport');a=self.g('a0');self.sent.append(a)
   sp=self.g('sp');self.s('ra',self.read(sp+20,4));self.s('sp',sp+24);return True
  if pc==0x9d081194:
   self.models.append('081194 delay/time');self.delays.append(self.g('a0'));return True
  if pc==0x9d040230:
   self.models.append('040230 flash seek/CS');self.stream=0;return True
  if pc==0x9d078878:
   self.models.append('078878 SysEx input (seven bytes)');ptr=self.g('a0');n=self.g('a1')
   for i in range(n):self.write(ptr+i,(self.stream+i)%17,1)
   self.stream+=n;return True
  contracts={0x9d04e970:'04e970 metadata/audio reconciliation',
             0x9d07636c:'07636c hardware gain programming',
             0x9d07f4b0:'07f4b0 hardware float gain programming'}
  if pc in contracts:
   self.models.append(contracts[pc]);self.s('v0',0);return True
  return False

def call(c,pc,args=(),stops=None):
 for r,x in zip(('a0','a1','a2','a3'),args):c.s(r,x)
 c.s('ra',STOP);sp=c.g('sp');saved={r:c.g(r) for r in ('s0','s1','s2','s3','s4','s5','s6','s7','fp','gp')}
 c.run(pc,stops or {STOP},maxsteps=500000)
 if stops is None:
  assert c.g('sp')==sp,('sp',hex(c.g('sp')),hex(sp))
  assert all(c.g(r)==x for r,x in saved.items()),('callee saved',[(r,hex(x),hex(c.g(r))) for r,x in saved.items() if c.g(r)!=x])
 return c.g('v0')
def seed(c):
 for bank in (0,1):
  for pid in range(0x6b7):
   for addr,value in ((0x8000046c,3),(0x80033318,5),(0x80034df4,7)):
    c.write(addr+2*(bank*0x6b7+pid),value,2)
 for p in range(4):c.write(S+16*p,10+p,4);c.write(S+16*p+4,2,1)
 c.write(c.g('sp')+16,0,4);c.write(c.g('sp')+20,0,4)
def params(c):
 return bytes(c.read(0x8000046c+i,1) for i in range(2*0x6b7*2))
PRIVATE=set(range(0x4048,0x4051))|set(range(0x4053,0x405a))
def feedback(c,old):
 before=params(c);saved=c.r.copy();inj=c.inject;c.inject=None;answers=[]
 try:
  for pair,epoch in enumerate(old):
   for cmd,data in ((0x4058,epoch&65535),(0x4059,epoch>>16),(0x404a,pair<<7|16)):
    for r,x in zip(('a0','a1','ra'),(cmd,data,STOP)):c.s(r,x)
    c.run(v.L['b15_pic_receive'],{STOP},maxsteps=200)
   answers.append(c.g('v0'))
 finally:c.r=saved;c.inject=inj
 assert params(c)==before,'feedback wrote live preset'
 return answers

def main():
 cases=[];hook_checks={};integration=json.loads((O/'absolute_pic_integration.json').read_text())
 for name,entry in roots.items():
  if name in ('load_bypass','startup'):continue
  label=v.L['stock_'+name];start=v.L['b15_'+name]
  next_starts=[int(x['pc'],16) for x in integration['pieces'] if int(x['pc'],16)>start]
  end=min(next_starts)
  targets=[]
  for pc in range(label,end,4):
   row=v.m.decode(v.img,pc)
   if row[0]=='j':targets.append(row[1])
  assert targets and all(not entry<=target<entry+8 for target in targets),(name,targets)
  hook_checks[name]={'overwritten':[hex(entry),hex(entry+8)],'stock_resume_targets':[hex(x) for x in targets]}
 hook_checks['load_bypass']={'call':'0x9d02e238','target':'0x9d041e10','resume':'0x9d02e240','overwritten_bytes':0}
 hook_checks['startup']={'call':'0x9d052d0c','target':hex(v.L['b15_cold_defaults']),'resume':'0x9d052d14','overwritten_bytes':4}
 assert 0x9d052d14>=0x9d052d0c+4
 trials=[]
 for name in ('replay','compare','restore'):
  for bank in (0,1,2):trials.append((name,(bank,0,0,0),1))
 for args in ((0,0,0,0),(4,1,1,0),(8,2,2,2),(0,0,0,1)):trials.append(('load',args,1))
 for name in ('import','edit_apply','defaults','reset','load_bypass','startup'):trials.append((name,(0,0,0,0),1))
 trials.extend((name,(0,0,0,0),0) for name in ('replay','load','import','edit_apply','defaults','reset','compare','restore','startup'))
 for name,args,irq in trials:
  stop={0x9d052d14} if name=='startup' else {0x9d02e240} if name=='load_bypass' else None
  baseline=CPU(False);seed(baseline);baseline.status=irq
  fitted=CPU(True);seed(fitted);fitted.status=irq
  old=[fitted.read(S+16*p,4) for p in range(4)]
  feedback(fitted,old) # deliver old feedback before entry; this may update old display only
  anchors={roots[name]+8,0x9d0404e8,0x9d074530,0x9d074564,0x9d04cdc4,0x9d04cdd8,
           0x9d04feec,0x9d04ff30,0x9d04fffc,0x9d050040,0x9d04cd1c,0x9d07c370}
  injections=[]
  def inject(c,pc):
   if pc in anchors and pc not in c.injected:
    c.injected.add(pc);answers=feedback(c,old);injections.append({'at':hex(pc),'accepted':answers})
  fitted.inject=inject
  row={'root':name,'entry':hex(roots[name]),'args':list(args),'initial_IE':irq,'models':[]}
  try:
   rb=call(baseline,roots[name],args,stops=stop)
   rf=call(fitted,roots[name],args,stops=stop)
   assert params(fitted)==params(baseline),'fitted/baseline final live parameters differ'
   assert fitted.g('sp')==baseline.g('sp'),'stack continuation differs'
   for reg in ('s0','s1','s2','s3','s4','s5','s6','s7','fp','gp'):
    assert fitted.g(reg)==baseline.g(reg),(name,reg)
   assert fitted.status==baseline.status,'Status differs'
   assert rb==rf,('return differs',hex(rb),hex(rf))
   ordinary=lambda c:[a for a in c.sent if a>>16 not in PRIVATE]
   assert ordinary(fitted)==ordinary(baseline),'ordinary command continuation differs'
   assert fitted.delays==baseline.delays,'stock delay sequence differs'
   final=params(fitted);after=feedback(fitted,old);assert params(fitted)==final
   changed=[p for p in range(4) if fitted.read(S+16*p,4)!=old[p]]
   assert all(not after[p] for p in changed),'old epoch accepted for replaced context'
   assert fitted.read(S+44,4)==0,'bulk depth left set'
   if name not in ('startup','load_bypass'):
    pcs={pc for pc,_ in fitted.trace};assert any(int(x,16) in pcs for x in hook_checks[name]['stock_resume_targets'])
   row.update(status='PASS_MODELED_DEPENDENCIES',stock_body_executed=True,
              baseline_equivalent=True,return_value=hex(rf),instructions=len(fitted.trace),
              stale_during=injections,stale_after_accepted=after,advanced_pairs=changed,
              live_parameter_sha256=hashlib.sha256(final).hexdigest(),ordinary_commands=len(ordinary(fitted)))
  except Exception as error:
   row.update(status='NOT VERIFIED',error=repr(error),last_trace=[(hex(pc),r) for pc,r in fitted.trace[-6:]])
  row['models']=sorted(set(fitted.models));cases.append(row)
  print(name,args,'IE='+str(irq),row['status'],row.get('error',''),flush=True)
 report={'status':'PASS_MODELED_DEPENDENCIES' if all(x['status']=='PASS_MODELED_DEPENDENCIES' for x in cases) else 'NOT VERIFIED',
  'fitted_sha256':hashlib.sha256(v.img).hexdigest(),'hook_resumes':hook_checks,'cases':cases,
  'method':'Real fitted root and stock lifecycle body execution; same seeded state/dependency contracts on baseline1.7; compare complete live parameter arrays, ordinary command transcript, delays, return, continuation stack/callee-saved registers and Status. Old feedback delivered before, during and after via emitted receiver, with no fresh B15 feedback.',
  'limits':'Seeded callers/data, modeled SPI readiness/content, SysEx input, physical transport, device query IRQ completion, metadata/audio reconciliation and gain hardware. No actual IRQ, file medium, QNX runtime, hardware or full outer UI/startup execution. No-reply hardware waits and every possible stock input/failure route are NOT VERIFIED.'}
 (O/'absolute_lifecycle_results.json').write_text(json.dumps(report,indent=2)+'\n')
 print(report['status'],'cases',len(cases),flush=True)
if __name__=='__main__':main()
