#!/usr/bin/env python3
"""Reproducible size comparison and exact-baseline additional-placement triage.
No payload mutation. Reference scans are evidence, not a proof against arbitrary computed jumps.
"""
from pathlib import Path
import json,struct,hashlib,sys
O=Path(__file__).resolve().parent;R=O.parent
sys.path.insert(0,str(R/'b9_250_candidate_work'));import mips_check as m
b=(R/'b14_stable_frame_packaging_work/pic_2.2.2.1.7.bin').read_bytes()
assert hashlib.sha256(b).hexdigest()=='75dc34043b8c4c259eef8182f6bd7dd75c8dc5ca096244e4e5cba5836705de62'
new=json.loads((O/'pic_emission_results.json').read_text())
old=json.loads((O/'size_before/pic_helpers_assembly.json').read_text());names=list(new['helper_sizes'])
labels={k:int(v,16) for k,v in old['labels'].items()};end=int(old['base'],16)+len(old['rows'])*4
before={n:(labels[names[i+1]] if i+1<len(names) else end)-labels[n] for i,n in enumerate(names)}
def scan(lo,hi):
 aliases=[lo,lo-0x40000000,lo-0x80000000]
 inside=lambda x:any(a<=x<a+hi-lo for a in aliases)
 literals=[];controls=[];constructed=[]
 for off in range(len(b)-3):
  w=struct.unpack_from('<I',b,off)[0]
  if inside(w):literals.append([hex(m.BASE+off),hex(w)])
  if off%4:continue
  pc=m.BASE+off;op=w>>26;t=None
  if op in (2,3):t=((pc+4)&0xf0000000)|((w&0x3ffffff)<<2)
  if op in (1,4,5,6,7,20,21,22,23):
   im=w&65535;t=pc+4+(im if im<32768 else im-65536)*4
  if t is not None and inside(t):controls.append([hex(pc),hex(t)])
  if op==15:
   reg=w>>16&31;upper=(w&65535)<<16
   for j in range(off+4,min(off+68,len(b)-3),4):
    v=struct.unpack_from('<I',b,j)[0];o=v>>26
    if v>>21&31==reg and o in (9,13):
     im=v&65535;t=(upper+(im if im<32768 else im-65536))&0xffffffff if o==9 else upper|im
     if inside(t):constructed.append([hex(pc),hex(m.BASE+j),hex(t)])
 return dict(start=hex(lo),end=hex(hi),bytes=hi-lo,literal_hits=literals,direct_control_hits=controls,nearby_constructed_hits=constructed)
large=scan(0x9d07a210,0x9d07a468)
assert ['0x9d0538c8','0x9d07a258'] in large['direct_control_hits']
assert ['0x9d07a590','0x9d07a298'] in large['direct_control_hits']
small=scan(0x9d07a210,0x9d07a258);tail=scan(0x9d07a4f8,0x9d07a56c)
assert not small['literal_hits'] and not small['nearby_constructed_hits']
assert all(0x9d07a210<=int(pc,16)<0x9d07a258 for pc,t in small['direct_control_hits'])
assert not tail['literal_hits'] and not tail['nearby_constructed_hits']
# The residual canonical acceleration branch is itself dead by B14's removed ingress.
assert tail['direct_control_hits']==[['0x9d0768c4','0x9d07a500']]
assert b[0x768c4:0x768c8]==bytes([14,15,17,18])
assert m.decode(b,0x9d07a208)==('j',0x9d07a468) and m.decode(b,0x9d07a20c)==('nop',)
# Planning reserve, NOT measured code, nor a ceiling/proof of whole-operation implementation.
budget={'common_operation_gate_pump_deadline_and_terminal_error':256,
        'save_load_import_export_entry_adapters_and_continuations':256,
        'bulk_begin_end_raw_reset_and_init_adapters':192,
        'alignment_detours_and_unresolved_integration_margin':64}
report={'historical_reserve_superseded':True,'operation_measurement_report':'pic_operation_results.json','complete_size_still_unestablished':True,'status':'SIZE_PASS_COMPLETE_IMPLEMENTATION_BLOCKED','baseline_sha256':hashlib.sha256(b).hexdigest(),
 'before_bytes':sum(before.values()),'after_bytes':new['helper_bytes'],
 'per_helper':{n:{'before':before[n],'after':new['helper_sizes'][n],'delta':new['helper_sizes'][n]-before[n]} for n in names},
 'size_attribution':'Contiguous function-entry spans; capture_commit includes shared capture loop/epilogue used also by prepare, service and context.',
 'planning_reserve_bytes':budget,'planning_reserve_total':sum(budget.values()),
 'planning_requirement':new['helper_bytes']+sum(budget.values()),
 'reserve_limit':'Engineering allocation only; gate semantics/actual emission still unfinished. Increase if traced implementation needs more; never remove checks to fit.',
 'large_region_rejected':large,
 'reclaim_candidates':[small,tail],
 'candidate_bytes':small['bytes']+tail['bytes'],
 'candidate_ownership':'72B obsolete service body bypassed by unconditional inherited B14 entry jump; 116B residual acceleration body under existing B14 dead-code authority. Preserve live service wrapper 7a258, decoder 7a298, anchor exit 7a450..468, inherited helper 7a468..4f8.',
 'candidate_limit':'Static direct/literal/nearby-constructed reference closure with inherited B14 CFG evidence; not yet approved or installed placement. Arbitrary computed pointers are not exhaustively excluded.',
 'shortfall_even_if_candidates_approved':new['helper_bytes']+sum(budget.values())-2400-small['bytes']-tail['bytes'],
 'next_step':'Emit complete bounded whole-operation gates against measured reserve and audit a larger dead-code region or supported PIC flash extension; do not fragment/install current helpers or package.',
 'firmware_modified':False}
(O/'pic_size_results.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
if __name__=='__main__':pass
