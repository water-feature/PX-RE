#!/usr/bin/env python3
"""Place whole helpers in audited regions and install guarded1.7 detours."""
from pathlib import Path
import json,struct,hashlib
import build_pic_helpers as h
O=Path(__file__).resolve().parent;R=O.parent;BASE=0x9d000000
placement=json.loads((O/'absolute_placement_results.json').read_text());assert placement['status']=='BOUNDED_PLACEMENT_PASS'
j=json.loads((O/'pic_absolute_assembly.json').read_text());rows=j['rows'];oldL={k:int(v,16) for k,v in j['labels'].items()};start=int(j['base'],16)
funcs=j['functions'];ends={n:oldL[funcs[i+1]] if i+1<len(funcs) else start+len(rows)*4 for i,n in enumerate(funcs)}
move={'b15_capture_enable':0x9d07a210,'b15_setter':0x9d07a4f8,'b15_setter_bank':0x9d07a54c,'b15_format':0x9d07a408}
newL={};pieces=[];cursor=start
for name in funcs:
 lo=oldL[name];hi=ends[name];pc=move.get(name,cursor)
 if name not in move:cursor+=hi-lo
 for label,addr in oldL.items():
  if lo<=addr<hi:newL[label]=pc+addr-lo
 pieces.append((name,pc,rows[(lo-start)//4:(hi-start)//4]))
assert cursor<=0x9d000c00
assert ends['b15_format']-oldL['b15_format']<=72
assert ends['b15_capture_enable']-oldL['b15_capture_enable']<=72
assert ends['b15_setter']-oldL['b15_setter']<=0x54
assert ends['b15_setter_bank']-oldL['b15_setter_bank']<=0x20
old=(R/'b14_stable_frame_packaging_work/pic_2.2.2.1.7.bin').read_bytes();new=bytearray(old);writes=[];pcrows=[]
def put(pc,data,why):
 off=pc-BASE;assert 0<=off and off+len(data)<=len(old)
 assert not any(max(pc,int(x['pc'],16))<min(pc+len(data),int(x['pc'],16)+len(bytes.fromhex(x['after']))) for x in writes)
 writes.append({'pc':hex(pc),'before':old[off:off+len(data)].hex(),'after':data.hex(),'reason':why});new[off:off+len(data)]=data
for name,pc,rs in pieces:
 a=h.Asm();a.rows=[tuple(r) for r in rs];a.labels=newL
 for i,row in enumerate(rs):
  if row[0] in ('beq','bne'):
   target=newL.get(row[3],row[3]);d=target-(pc+4*i+4);assert d%4==0 and -32768<=d//4<32768,(name,row,hex(pc+4*i))
 h.BASE=pc;data=a.bytes();h.BASE=start;assert (start<=pc and pc+len(data)<=0x9d000c00) or any(int(r['start'],16)<=pc and pc+len(data)<=int(r['end'],16) and r['placement_approved'] for r in placement['regions'])
 put(pc,data,'helper '+name)
 pcrows.extend([[hex(pc+4*i),r] for i,r in enumerate(rs)])
assert old[0x611bc:0x611c0]==b'---\0'
word=lambda pc:struct.unpack_from('<I',old,pc-BASE)[0]
def detour(pc,name,expected=None):
 if expected is not None:assert [word(pc),word(pc+4)]==expected
 put(pc,struct.pack('<II',0x08000000|((newL[name]>>2)&0x3ffffff),0),'entry '+name)
expected={0x9d04dacc:('b15_setter',[0x27bdffd0,0xafbf002c]),0x9d04fa6c:('b15_encoder',[0x27bdffe0,0xafbf001c]),0x9d075c1c:('b15_transport',[0x27bdffe8,0xafbf0014]),0x9d0511a4:('b15_rx_entry',[0x8fa20014,0x2403402e]),0x9d029118:('b15_main_entry',[0x27bdffc8,0xafbf0034]),0x9d05f7f4:('b15_format',[0x27bdffd0,0xafbf002c])}
for pc,(name,words) in expected.items():detour(pc,name,words)
p=json.loads((O/'pic_absolute_results.json').read_text())
for x in p['hooks']:detour(int(x['pc'],16),x['target'],[int(w,16) for w in x['expected_words']])
calls={0x9d035748:('b15_effective_get',0x9d04d300),0x9d035f2c:('b15_effective_get',0x9d04d300),0x9d031da0:('b15_effective_get',0x9d04d300),0x9d02ae50:('b15_capture_enable',0x9d04dacc),0x9d02f26c:('b15_capture_enable',0x9d04dacc),0x9d02ae94:('b15_capture_commit',0x9d04dacc),0x9d02f2bc:('b15_capture_commit',0x9d04dacc),0x9d052d0c:('b15_cold_defaults',0x9d04cd14),**{pc:('b15_setter_bank',0x9d031b70) for pc in (0x9d04e230,0x9d04e250,0x9d04e0fc,0x9d04e11c)}}
for pc,(name,target) in calls.items():
 assert word(pc)==0x0c000000|((target>>2)&0x3ffffff)
 put(pc,struct.pack('<I',0x0c000000|((newL[name]>>2)&0x3ffffff)),'call '+name)
assert word(0x9d02f2a8)==0x0c000000|((0x9d0649fc>>2)&0x3ffffff)
put(0x9d02f2a8,b'\0'*4,'remove post-clear instrument2 velocity read')
for pc in (0x9d081868,0x9d07fb40):
 w=word(pc);assert w&65535==0x4000;put(pc,struct.pack('<I',(w&0xffff0000)|0x3fc0),'reserve64B from both heap initialization paths')
# Verify every difference belongs to exact manifest; inherited bytes elsewhere untouched.
allow=set()
for x in writes:allow.update(range(int(x['pc'],16)-BASE,int(x['pc'],16)-BASE+len(bytes.fromhex(x['after']))))
assert all(a==b or i in allow for i,(a,b) in enumerate(zip(old,new))) and len(new)==len(old)
# Inherited helper/layout preservation, not just arbitrary FF claims.
protected=[(0,0x2a0),(0xc00,0x1480),(0x7a258,0x7a298),(0x7a298,0x7a408),(0x7a450,0x7a4f8)]
for lo,hi in protected:assert new[lo:hi]==old[lo:hi],(hex(lo),hex(hi))
out=O/'pic_B15_absolute_INCOMPLETE.bin';out.write_bytes(new)
report={'status':'PLACED_HOOKS_COMPONENT_ONLY','ready_for_hardware':False,'pic_bytes':p['bytes'],'main_used':cursor-start,'main_capacity':2400,'fragment_used':sum(ends[n]-oldL[n] for n in move),'fragment_capacity':260,'total_capacity':2660,'total_unused':2660-p['bytes'],'trampoline_overhead':0,'labels':{k:hex(v) for k,v in newL.items()},'pc_rows':pcrows,'pieces':[{'name':n,'pc':hex(pc),'bytes':len(rs)*4} for n,pc,rs in pieces],'writes':writes,'protected_spans':[[hex(lo+BASE),hex(hi+BASE)] for lo,hi in protected],'payload_bytes':len(new),'sha256':hashlib.sha256(new).hexdigest(),'hook_installation':True,'remaining':'Full command allocation, lifecycle/ABI/IRQ/caller ownership and paired integration validation; no release version or packaging.'}
(O/'absolute_pic_integration.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:report[k] for k in ('status','pic_bytes','main_used','fragment_used','total_unused','sha256')},indent=2))
