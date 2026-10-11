from pathlib import Path
import sys,hashlib,json,itertools,struct
OUT=Path(__file__).resolve().parent;ROOT=OUT.parent
sys.path.insert(0,str(OUT));from mips_check import *
old=(ROOT/'b9_candidate_work/pic_2.2.2.1.1.bin').read_bytes();new=(OUT/'pic_2.2.2.1.2.bin').read_bytes()
assert hashlib.sha256((ROOT/'PxUpdate_V2.2.2.1.1.bin').read_bytes()).hexdigest()=='061248f2d8e4e11e9dec78d6b5c74b87d16a283c273e2eba35ae84c2e592a012'
allowed=set(range(0xd84,0xdf4))|set(range(0x235e4,0x235e8))|set(range(0x1394,0x1398))|set(range(0x13a0,0x13a4))
diff=[i for i,(a,b) in enumerate(zip(old,new)) if a!=b];assert set(diff)<=allowed
callers=[BASE+i for i in range(0,len(old)-3,4) if struct.unpack_from('<I',old,i)[0]==(3<<26|((WRAPPER>>2)&0x3ffffff))]
cases=0
for site,mode,c,gate in itertools.product(callers,(0,1,2),(-1,0,1,249,250,500),(0,1)):
 a,b=CPU(old,gate),CPU(new,gate);slot=int(mode==1)
 for m in (a,b):m.write(GP-0x7c84+4*slot,c,4);m.call(site,11,127,mode)
 panel=site+8 in PANEL;changed=panel and gate and c<=0
 assert b.count(slot)==(250 if changed else a.count(slot))
 assert a.pending(0)==b.pending(0) and a.pending(1)==b.pending(1) and a.calls==b.calls
 permit=set(range(GP-0x7c84+4*slot,GP-0x7c84+4*slot+4)) if changed else set()
 assert all(a.mem.get(x,0)==b.mem.get(x,0) or x in permit for x in set(a.mem)|set(b.mem))
 for i,n in enumerate(REGS):
  if n not in ('t0','t1','t2','t3') and not(changed and n=='v0'):assert a.r[i]==b.r[i]
 cases+=1
# Interrupt at every reached helper instruction for each panel caller, positive=1.
interrupts=0
for ret,pc in itertools.product(PANEL,range(BASE+0xd84,BASE+0xdf4,4)):
 m=CPU(new);m.write(GP-0x7c84,1,4);fired=[]
 def inject(cpu,where):
  if where==pc and not fired:fired.append(where);cpu.tick()
 m.inject=inject;m.call(ret-8,9,109);m.inject=None
 if not fired:continue
 assert m.count()==0 and m.pending()==(9,109,0,2) and not m.calls
 m.expire();assert m.count()==-1 and m.applied(0)==m.applied(1)==(9,109)
 interrupts+=1
result={'status':'PASS','hardware_tested_parent':'2.2.2.1.1','differential_cases':cases,'all_panel_helper_interrupt_cases':interrupts,'changed_PIC_bytes_vs_parent':len(diff),'unchanged_parent_ranges':True,'only_behavior_difference':'Active panel immediate reload 250 instead of 500; positive countdown unchanged, nonpanel unchanged.'}
(OUT/'previous_candidate_validation.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
