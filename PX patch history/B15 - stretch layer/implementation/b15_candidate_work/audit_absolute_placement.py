#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Close two bounded B14-dead regions using exact guards and recovered ingress."""
from pathlib import Path
import ast,json,struct,hashlib
import validate_pic_operations as p
O=Path(__file__).resolve().parent;R=O.parent;m=p.m
b=(R/'b14_stable_frame_packaging_work/pic_2.2.2.1.7.bin').read_bytes()
assert hashlib.sha256(b).hexdigest()=='75dc34043b8c4c259eef8182f6bd7dd75c8dc5ca096244e4e5cba5836705de62'
t=ast.parse((O/'audit_pic_size.py').read_text());f=next(x for x in t.body if isinstance(x,ast.FunctionDef) and x.name=='scan');exec(compile(ast.Module(body=[f],type_ignores=[]),'scan','exec'))
regions=[scan(0x9d07a210,0x9d07a258),scan(0x9d07a4f8,0x9d07a56c),scan(0x9d07a408,0x9d07a450)]
assert not regions[0]['literal_hits'] and not regions[0]['nearby_constructed_hits']
assert regions[0]['direct_control_hits']==[['0x9d07a230','0x9d07a24c']]
assert not regions[1]['literal_hits'] and not regions[1]['nearby_constructed_hits']
assert regions[1]['direct_control_hits']==[['0x9d0768c4','0x9d07a500']]
assert b[0x768c4:0x768c8]==bytes([14,15,17,18])
assert m.decode(b,0x9d07a208)==('j',0x9d07a468) and m.decode(b,0x9d07a20c)==('nop',)
for pc in (0x9d07a34c,0x9d07a350,0x9d07a3c8,0x9d07a3cc):assert m.decode(b,pc)==('nop',)
assert m.decode(b,0x9d07a4f0)==('jr','ra')
assert m.decode(b,0x9d07a4f4)==('addiu','sp','sp',32)
# Every recovered direct/constructed entry to surrounding service+decoder+helper
# is included. External calls terminate within this bounded ownership audit and
# their return fallthrough is explored. The decoder has no computed jump table.
roots=[0x9d07a208,0x9d07a258,0x9d07a298,0x9d07a384,0x9d07a468]
seen=set();todo=roots[:];returns=[]
while todo:
 pc=todo.pop()
 if pc in seen or not 0x9d07a208<=pc<0x9d07a56c:continue
 seen.add(pc)
 try:row=m.decode(b,pc)
 except AssertionError:
  w=struct.unpack_from('<I',b,pc-m.BASE)[0]
  assert w>>26 in (28,31),(hex(pc),hex(w)) # SPECIAL2/3 arithmetic/bitfields, never control
  row=('arithmetic',)
 op=row[0]
 if op in m.CONTROL:
  seen.add(pc+4)
  assert m.decode(b,pc+4)[0] not in m.CONTROL
  if op=='jr':assert row[1]=='ra';returns.append(hex(pc));continue
  if op=='j':todo.append(row[1]);continue
  if op=='jal':todo.extend([row[1],pc+8]);continue
  if op in ('beq','bne','beql','bnel'):todo.extend([row[3],pc+8]);continue
  raise AssertionError((hex(pc),row))
 todo.append(pc+4)
for r in regions:
 lo=int(r['start'],16);hi=int(r['end'],16);assert not any(lo<=pc<hi for pc in seen)
 r.update(placement_approved=True,original_sha256=hashlib.sha256(b[lo-m.BASE:hi-m.BASE]).hexdigest())
assert not regions[2]['literal_hits'] and not regions[2]['nearby_constructed_hits']
assert regions[2]['direct_control_hits']==[['0x9d0767e0','0x9d07a41c']]
assert b[0x767e0:0x767e4]==bytes([14,15,15,16])
table=b[0x767bc:0x7683c];assert len(table)==128 and table[0]==0 and table[-1]==127 and list(table)==sorted(table)
assert m.decode(b,0x9d06f54c)==('lui','s1',0x9d07) and m.decode(b,0x9d06f550)==('addiu','s1','s1',0x67bc)
regions[2]['excluded_lookup_data_hit']='767e0 is bytes0e0f0f10 in128-byte monotonic velocity table767bc..7683c, constructed at6f54c/550; no executable ingress. Negative fast region remains bypassed by B14.'
# Ghidra original reference metadata is supplemental, exact-image raw guards
# and B14 CFG are the ownership authority, not stale original function bodies.
e=(R/'b15_investigation/placement_closure_evidence.txt').read_text()
assert 'SITE 9d0768c4 FUNCTION none' in e
report={'status':'BOUNDED_PLACEMENT_PASS','regions':regions,'approved_total_bytes':2660,'main_cave_bytes':2400,'additional_bytes':260,'roots':[hex(x) for x in roots],'recovered_live_words':len(seen),'return_sites':returns,'fragment_plan':{'b15_capture_enable':['0x9d07a210',72],'b15_setter':['0x9d07a4f8',116],'b15_format':['0x9d07a408',72]},'extra_trampoline_bytes':0,'authority':'Exact1.7 inherited B14 unconditional service bypass and disabled acceleration ingress; recovered CFG plus all-byte aliased literals, direct controls and nearby constructed pointer scan. Tail region was reserved dead code by B14. No FF inference.','limits':'Static recovered ingress closure, matching inherited B14 audit scope; arbitrary fabricated/computed code addresses are not mathematically excluded.','preserved':['live service7a258','decoder7a298/7a384','anchor exit7a450..468','inherited helper7a468..4f8','vectors/startup/DINIT','bootloader']}
(O/'absolute_placement_results.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({'status':report['status'],'approved_total_bytes':2660,'additional_bytes':260},indent=2))
