# SPDX-License-Identifier: GPL-2.0-or-later
"""Recheck baseline padding, aliases and inherited vector/reservation evidence."""
from pathlib import Path
import struct,json,hashlib
ROOT=Path(__file__).resolve().parent.parent;OUT=Path(__file__).resolve().parent
old=(ROOT/'b6_candidate_work/pic_2.2.2.0.9.bin').read_bytes();new=(OUT/'pic_2.2.2.1.1.bin').read_bytes();prior=(ROOT/'b7_candidate_work/pic_2.2.2.0.8.bin').read_bytes()
assert hashlib.sha256(old).hexdigest()=='80723ffbd381e1e6cf401f09cff99591d43a07d91d00d57570fe2dea5265e2f3'
lo,hi=0xd84,0xe00;aliases=[(x+lo,x+hi) for x in (0x9d000000,0xbd000000,0x1d000000)]
inside=lambda v:any(a<=v<z for a,z in aliases)
assert old[lo:hi]==b'\xff'*124
refs=[]
for i in range(len(old)-3):
 w=struct.unpack_from('<I',old,i)[0]
 if inside(w):refs.append(('literal',hex(i),hex(w)))
 if i%4==0 and w>>26 in (2,3) and inside((w&0x3ffffff)<<2|0x90000000):refs.append(('direct',hex(i)))
 if i%4==0 and w>>26==15:
  reg=(w>>16)&31;upper=(w&65535)<<16
  for j in range(i+4,min(i+68,len(old)-3),4):
   v=struct.unpack_from('<I',old,j)[0];op=v>>26
   if ((v>>21)&31)==reg and op in (9,13):
    imm=v&65535;value=((upper+(imm-65536 if imm&32768 else imm)) if op==9 else upper|imm)&0xffffffff
    if inside(value):refs.append(('construction',hex(i),hex(j),hex(value)))
assert not refs
# These exact .9/.8 spans cover inherited installed vectors and their startup,
# OFF initialization records, EBase/IntCtl setup used in B6's resolved report.
for a,z in [(0,0xc00),(0x1000,0x1200),(0x1480,0x1a84c)]:assert old[a:z]==prior[a:z] and new[a:z]==old[a:z]
protected=[(0xc00,0xd84),(0x1200,0x1394),(0x1398,0x13a0),(0x13a4,0x1480)]
assert all(old[a:z]==new[a:z] for a,z in protected)
assert new[0xde8:0xe00]==b'\xff'*24
report={'status':'PASS','baseline_hash':hashlib.sha256(old).hexdigest(),'helper_range':['0x9d000d84','0x9d000de8'],'baseline_free_tail_bytes':124,'used_bytes':100,'remaining_FF_bytes':24,'baseline_direct_literal_nearby_construction_refs':refs,'reserved_B6_helper_preserved':['0x9d000c00','0x9d000d84'],'B3_B7_code_and_report_thunk_bodies_preserved':True,'version_thunk_ADDIU_metadata_only':True,'installed_vectors_startup_OFF_records_identical_to_B6_resolved_vector_evidence':True,'vector_authority':'b6_investigation/vector_reservation_report.md (PIC32MZ2048EFG100; C00-E00 excluded)','other_branch_reservation_review':'Only existing B6 occupancy and B9 proposal found for this tail; unfinished B7 revision 2.2.2.1.0 retained, no other branch incorporated.','limits':'Static references supplemented by inherited exact vector configuration; arbitrary dynamic pointer arithmetic is not exhaustively proven.'}
(OUT/'b9_placement_validation.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
