# SPDX-License-Identifier: GPL-2.0-or-later
"""Focused additional validation of the final compact overlay; no image writes."""
from pathlib import Path
import json,struct
import measure_compact as m
import setter_harness as sh
ROOT=Path(__file__).resolve().parent
sh.overlay=m.image;sh.RETURN=0x9d02df10
sites=set();setter_cases=0
for inst in (0,1):
 for edit in (0,1,2):
  for old in ((0,0),(16,16),(0,16),(16,0),(2,3),(2,12),(5,5)):
   for counts in ((1,1),(2,1),(1,2),(17,4)):
    for remembered in ((0,0),(1,1),(255,255)):
     for manual in (False,True):
      for direction in (-1,1):
       c=sh.scenario(inst,edit,old,counts,remembered,manual,direction)
       setter_cases+=1;sites.update(set(c.trace)&{0x9d04debc,0x9d04e010,0x9d04e54c,0x9d04e624})
group_cases=0
for group in range(65):
 for inst in (0,1):
  for edit in (0,1,2):
   for old in ((0,16),(2,3),(2,12)):
    for counts in ((1,1),(2,1),(1,2),(17,4)):
     for selected in ((0,0),(1,1),(255,255)):
      for direction in (-1,0,1):
       m.run(inst,edit,old,counts,selected,direction,groups=(group,(group+1)%65));group_cases+=1
# Exercise the exact final helper on nonmanual saved return identities, including
# the same low halfword in every other PIC 64 KiB region. Full identity is required.
identity_cases=0
for upper in range(0x9d00,0x9d09):
 ret=(upper<<16)|0xdf10
 if ret==0x9d02df10:continue
 for bank in (0,1):
  c=sh.CPU(m.image);sp=c.r[29];c.r[4]=bank;c.r[5]=0x24;c.r[6]=0;c.r[19]=5;c.r[31]=0x9d0267c0
  c.store(sp+0x2c,4,ret);c.store(sp+0x24,4,2);c.store(sp+0x28,4,3)
  base=sh.PARAM+bank*0xd6e;c.store(base+0x22*2,2,1);c.store(0x80037e90+8*(17+5),4,2)
  c.run(m.helper_entry,{0x9d0267c0});assert c.r[2]==0;identity_cases+=1
recall_cases=0
for count in (1,2,256):
 c=sh.CPU(m.image);ret=0x9d0267c0;c.r[31]=ret
 for bank in (0,1):
  for cat in (0x24,0x65):
   c.store(sh.PARAM+bank*0xd6e+(cat-2)*2,2,0);c.store(sh.PARAM+bank*0xd6e+cat*2,2,5);c.store(sh.PARAM+bank*0xd6e+(cat-1)*2,2,0)
   for k in range(17):c.store(0x80037e90+8*k,4,count)
 c.run(0x9d04d6d4,{ret},limit=100000)
 assert all(c.load(sh.PARAM+b*0xd6e+(cat-1)*2,2)==0 for b in (0,1) for cat in (0x24,0x65));recall_cases+=1
# Preserve established ownership; exact four ranges plus four call-site words.
owned=[(a,z) for a,z,_ in m.sections]
call_sites={0x9d04debc,0x9d04e010,0x9d04e54c,0x9d04e624}
assert all(p in call_sites or any(a<=p<z for a,z in owned) for p in m.image)
assert len(m.image)*4==220 # 204 owned Type bytes + 16 existing call-site bytes.
assert owned==[(0x9d02a74c,0x9d02a794),(0x9d02d428,0x9d02d464),(0x9d02dd08,0x9d02dd2c),(0x9d02def8,0x9d02df1c)]
# Re-audit raw direct incoming edges / aligned literal pointers into owned areas.
b=sh.pic.b; incoming=[]
for i in range(0,len(b)-3,4):
 p=0x9d000000+i;w=struct.unpack_from('<I',b,i)[0];op=w>>26;targets=[]
 if op in (2,3):targets.append(((p+4)&0xf0000000)|((w&0x3ffffff)<<2))
 elif op in (1,4,5,6,7,20,21,22,23):
  n=w&65535;targets.append(p+4+4*(n if n<32768 else n-65536))
 if any(a<=w<z for a,z in owned):targets.append(w)
 for target in targets:
  if any(a<=target<z for a,z in owned) and not any(a<=p<z for a,z in owned):incoming.append({'source':hex(p),'target':hex(target)})
assert incoming==[{'source':'0x9d029348','target':'0x9d02a74c'}],incoming
summary={'actual_setter_cases':setter_cases,'replacement_sites_executed':[hex(a) for a in sorted(sites)],'additional_all_group_routing_cases':group_cases,'nonmanual_full_return_identity_cases':identity_cases,'bulk_recall_zero_cases':recall_cases,'ownership':'PASS: only four established Type ranges and four approved clamp call-site words','external_incoming':incoming,'additional_pic_storage_bytes':0,'cache_correction_included':False,'firmware_modified':False,'limits':'external effects stubbed; raw incoming audit does not prove absence of arbitrary computed entries; hardware testing follows implementation approval'}
(ROOT/'compact/extended_results.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary,indent=2))
