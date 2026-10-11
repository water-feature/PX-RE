"""Independent byte, placement, direct writer and interrupt-path audit."""
from pathlib import Path
import struct,json,hashlib
ROOT=Path(__file__).resolve().parents[1];OUT=Path(__file__).resolve().parent;BASE=0x9d000000
old=(ROOT/'b14_metadata_packaging_work/pic_2.2.2.1.6.bin').read_bytes()
new=(OUT/'pic_B14_stable_frame_unpackaged.bin').read_bytes()
word=lambda pc:struct.unpack_from('<I',old,pc-BASE)[0]
inside=lambda pc:BASE<=pc<BASE+len(old)
allowed=[(0x13ac,0x146c),(0x3ed0c,0x3ed14),(0x3ecb0,0x3ecb8),(0x7e408,0x7e410),(0x7e274,0x7e27c),(0x298d8,0x298e0),(0x29ce0,0x29ce4),(0x3ee54,0x3ee58)]
diff=[i for i,(a,b) in enumerate(zip(old,new)) if a!=b]
assert len(new)==len(old)==530784 and all(any(lo<=i<hi for lo,hi in allowed) for i in diff)
assert old[0x13ac:0x1480]==bytes([255])*212
lo,hi=BASE+0x13ac,BASE+0x146c
aliases=[lo,lo-0x40000000,lo-0x80000000]
in_cave=lambda t:any(a<=t<a+hi-lo for a in aliases)
interiors={BASE+x for x in (0x3ed10,0x3ecb4,0x7e40c,0x7e278,0x298dc)}
incoming=[];literals=[];constructed=[];interior=[]
for off in range(len(old)-3):
 w=struct.unpack_from('<I',old,off)[0]
 if in_cave(w):literals.append([hex(BASE+off),hex(w)])
 if w in interiors:interior.append(['literal',hex(BASE+off),hex(w)])
 if off%4:continue
 pc=BASE+off;op=w>>26;target=None
 if op in (2,3):target=((pc+4)&0xf0000000)|((w&0x3ffffff)<<2)
 if op in (1,4,5,6,7,20,21,22,23):target=pc+4+struct.unpack('<h',struct.pack('<H',w&65535))[0]*4
 if target is not None:
  if in_cave(target):incoming.append([hex(pc),hex(target)])
  if target in interiors:interior.append(['control',hex(pc),hex(target)])
 if op==15:
  reg=w>>16&31;upper=(w&65535)<<16
  for j in range(off+4,min(off+68,len(old)-3),4):
   q=struct.unpack_from('<I',old,j)[0];o=q>>26
   if q>>21&31==reg and o in (9,13):
    im=q&65535;value=(upper+(im if im<32768 else im-65536))&0xffffffff if o==9 else upper|im
    if in_cave(value):constructed.append([hex(pc),hex(BASE+j),hex(value)])
    if value in interiors:interior.append(['constructed',hex(pc),hex(BASE+j),hex(value)])
assert not incoming and not literals and not constructed and not interior
def calls(target):
 return [BASE+off for off in range(0,len(old),4) if (w:=word(BASE+off))>>26 in (2,3) and (((BASE+off+4)&0xf0000000)|((w&0x3ffffff)<<2))==target]
def constant_a0(site):
 # Only a local proof candidate: delay and preceding straight-line definition.
 for pc in [site+4]+list(range(site-4,max(site-100,BASE),-4)):
  w=word(pc);op=w>>26;rt=w>>16&31;rs=w>>21&31;rd=w>>11&31
  if op==9 and rt==4 and rs==0:return w&65535,pc
  if op==0 and rd==4 and w&63 in (33,37) and rs==0 and rt==0:return 0,pc
  if (op in (2,3) and pc!=site+4) or (op in (9,35,37) and rt==4) or (op==0 and rd==4):return None,None
 return None,None
clear71=[]
for site in calls(BASE+0x7e274):
 value,definition=constant_a0(site);assert value==0
 clear71.append({'site':hex(site),'index':value,'definition':hex(definition)})
assert len(clear71)==71
clear33=[]
for site in calls(BASE+0x7e408):
 value,definition=constant_a0(site)
 clear33.append({'site':hex(site),'local_index':value,'definition':hex(definition) if definition else None})
assert len(clear33)==33
assert [r['site'] for r in clear33 if r['local_index']==1]==['0x9d07e47c']
# Selector has eight draw-side constant writers, all accounted by candidate or
# unaffected secondary rendering. The remaining selector stores are row readers.
selector=[pc for pc in range(BASE,BASE+len(old),4) if word(pc)>>26==43 and word(pc)>>21&31==28 and word(pc)&65535==0x821c]
assert selector==[BASE+x for x in (0x298dc,0x29900,0x29c84,0x29ce4,0x3ddec,0x3de8c,0x3eccc,0x3ed88,0x721cc,0x72360,0x724ac,0x726d4)]

# Recovered ISR control graph, including the established compiler jump-table
# pattern. Unresolved framework callbacks are reported, not silently excluded.
def table(pc):
 ws=[word(pc-i) for i in (12,8,4)]
 if ws[0]>>26!=15 or ws[1]>>26!=9 or ws[2]>>26!=31 or ws[2]&63!=10:return None
 reg=ws[0]>>16&31
 if ws[1]>>21&31!=reg or ws[1]>>16&31!=reg:return None
 im=ws[1]&65535;address=((ws[0]&65535)<<16)+(im if im<32768 else im-65536);count=None
 for at in range(pc-40,pc-12,4):
  if word(at)>>26==11:count=word(at)&65535
 if count is None or not 0<count<=256 or not inside(address+4*(count-1)):return None
 targets=[word(address+4*i) for i in range(count)]
 return targets if all(inside(t) and t%4==0 for t in targets) else None
roots=[0x90000000|((word(BASE+i)&0x3ffffff)<<2) for i in range(0x200,0x258,8)]
irq=[];allseen=set()
draw_targets={BASE+x for x in (0x3ec50,0x3ecb0,0x3ed0c,0x6a8cc,0x6a970,0x7e1c4,0x7e274,0x7e408,0x298d8,0x29ce0)}
for root in roots:
 todo=[root];seen=set();unresolved=[];switches=0
 while todo:
  pc=todo.pop()
  if pc in seen:continue
  if not inside(pc):unresolved.append(['out_of_image',hex(pc)]);continue
  seen.add(pc);w=word(pc);op=w>>26
  if op in (2,3):
   todo.append(((pc+4)&0xf0000000)|((w&0x3ffffff)<<2));seen.add(pc+4)
   if op==3:todo.append(pc+8)
  elif op in (1,4,5,6,7,20,21,22,23):
   im=w&65535;todo.extend([pc+4+(im if im<32768 else im-65536)*4,pc+8]);seen.add(pc+4)
  elif op==0 and w&63 in (8,9):
   seen.add(pc+4)
   if w>>21&31!=31:
    targets=table(pc) if w&63==8 else None
    if targets:todo.extend(targets);switches+=1
    else:unresolved.append([hex(pc),hex(w)])
   if w&63==9:todo.append(pc+8)
  elif w==0x42000018:pass
  else:todo.append(pc+4)
 hits=draw_targets&seen;assert not hits,[hex(x) for x in hits]
 allseen|=seen
 irq.append({'root':hex(root),'reachable_words':len(seen),'resolved_switches':switches,'unresolved_indirects':unresolved,'draw_target_hits':[]})
assert not set(selector)&allseen
protected={'B14_replay':(0x7a208,0x7a4f8),'metadata_reader':(0x41048,0x41374),'B9_helper':(0xd84,0xdf4),'B7_setter_adapter':(0x12c0,0x1390),'version_thunks':(0x1390,0x13ac),'main_row_scheduler':(0x53b6c,0x53da0)}
for name,(a,b) in protected.items():assert old[a:b]==new[a:b],name
report={'status':'PASS','changed_bytes':len(diff),'helper_range':[hex(lo),hex(hi)],
 'incoming_cave_refs':incoming,'literal_cave_refs':literals,'constructed_cave_refs':constructed,'hook_interior_refs':interior,
 'clear71_local_argument_checks':clear71,'clear33_local_arguments':clear33,
 'selector_stores':[hex(pc) for pc in selector],'interrupt_audit':irq,'protected_spans_unchanged':list(protected),
 'limits':['Local constant definitions do not replace complete interprocedural argument analysis.',
 'Computed buffer aliases and unresolved framework callbacks remain static-audit limits.']}
(OUT/'placement_results.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({'status':report['status'],'clear_leaf_calls':len(clear71),'fullclear_calls':len(clear33),'selector_stores':len(selector),'irq_roots':len(irq),'irq_unresolved':sum(len(r['unresolved_indirects']) for r in irq),'protected_spans_unchanged':list(protected)}))
