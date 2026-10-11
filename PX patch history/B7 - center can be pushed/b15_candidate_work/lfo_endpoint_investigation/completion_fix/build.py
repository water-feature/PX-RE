# SPDX-License-Identifier: GPL-2.0-or-later
from pathlib import Path
import sys,struct,json,hashlib,subprocess
O=Path(__file__).resolve().parent;R=O.parents[2]
sys.path[:0]=[str(R),str(R/'b5_candidate_work')]
from b5_elf_placement_check import ExactElf,decode_index,encode_index
from emit_b5_candidate import object_info
sha=lambda b:hashlib.sha256(b).hexdigest()
p=R/'b14_sample_acceleration_work/voice_2.2.2.1.10_B14_sample_acceleration_candidate_qnx.elf';old=p.read_bytes()
assert sha(old)=='7322f41979a70d72b740b1a967770f71ef706822343d2582eab0b08caea69ddc'
e=ExactElf(old);out=bytearray(old);base=0xf3c40
subprocess.run(['clang','-target','x86_64-unknown-linux-gnu','-c',str(O/'helpers.s'),'-o',str(O/'helpers.o')],check=True)
raw,_,secs,syms=object_info(O/'helpers.o');s=secs['.text'];code=raw[s['offset']:s['offset']+s['size']]
assert not any(n.startswith('.rela') for n in secs)
symbols={s['name']:s['offset'] for s in syms};geom=base+symbols['completion_geom']
m=json.loads((R/'b5_candidate_work/b5_candidate_manifest.json').read_text())['layout']
assert base>=0xf3c3c and base+len(code)<=m['code_base']+m['code_reservation']
out[base:base+len(code)]=code
patches=[]
for site,expected,target,op in [(0xf122c,{'size': 5, 'sha256': 'b1d090e8ab50878f563e76d89b5f007a26603f3768d31156d61ad89af0344eab'},base,0xe8),(0xf126e,{'size': 5, 'sha256': '4141f176166314c5f7b7b3fb30f71f1a6602cc6683d1e5b142ee408c097416d1'},base,0xe8),(0xf1730+0x492,{'size': 6, 'sha256': '2af933f0692fff19a577eabc19ad8a1b404e8cc17a788b58cb147519f7c1915e'},geom,0xe9)]:
 assert sha(old[site:site+expected['size']])==expected['sha256']
 value=bytes([op])+struct.pack('<i',target-site-5)+b'\x90'*(expected['size']-5)
 out[site:site+len(value)]=value;patches.append((site,site+len(value)))
h=next(p for p in e.phdr if p['type']==0x6474e550);frame,pairs=decode_index(e.read(h['va'],h['filesz']),h['va'])
# Existing .1.9 helper FDE ends at f4be4. Append two FDEs in owned reservation.
dest=max(f+e.fde(f)['length']+4 for pc,f in pairs if m['frame_base']<=f<m['frame_base']+m['frame_reservation'])
assert e.read(dest,4)==b'\0'*4
newpairs=list(pairs);fde_start=dest
cie=e.fde(next(f for pc,f in pairs if pc==0xf13bb))['cie']['va']
for pc,size,cfi in [(base,symbols['completion_geom'],b''),(geom,len(code)-symbols['completion_geom'],bytes.fromhex('0e6083078c068d058e048f038602'))]:
 # zR CIE: zero augmentation length; leaf uses rsp+8; GEOM inherits dispatch rsp+96.
 body=struct.pack('<I',dest+4-cie)+struct.pack('<iI',pc-(dest+8),size)+b'\0'+cfi
 body+=b'\0'*((-len(body))%4);fde=struct.pack('<I',len(body))+body
 out[dest:dest+len(fde)]=fde;newpairs.append((pc,dest));dest+=len(fde)
assert dest+4<=m['frame_base']+m['frame_reservation'];out[dest:dest+4]=b'\0'*4
newpairs.sort();hdr=encode_index(newpairs,h['va'],frame);out[h['offset']:h['offset']+len(hdr)]=hdr
for name,size in [('.b5.text',base+len(code)-m['code_base']),('.b5.eh_frame',dest+4-m['frame_base']),('.eh_frame_hdr',len(hdr))]:
 i=e.section_names.index(name);struct.pack_into('<Q',out,e.shoff+i*e.shentsize+32,size)
i=e.phdr.index(h);struct.pack_into('<QQ',out,e.phoff+i*e.phentsize+32,len(hdr),len(hdr))
x=ExactElf(bytes(out));_,xp=decode_index(x.read(h['va'],len(hdr)),h['va']);assert xp==newpairs
for pc,f in pairs:assert x.read(f,e.fde(f)['length']+4)==e.read(f,e.fde(f)['length']+4)
for pc,f in xp:assert x.fde(f)['pc']==pc
from validate_b5_candidate import fde_rows,row_at
leaf_row=row_at(fde_rows(e,next(f for pc,f in pairs if pc==0xf13bb)),0xf13bb)
geom_row=row_at(fde_rows(e,next(f for pc,f in pairs if pc==0xf1730)),0xf1730+0x492)
for pc,size,want in [(base,symbols['completion_geom'],leaf_row),(geom,len(code)-symbols['completion_geom'],geom_row)]:
 f=next(f for at,f in xp if at==pc);rows=fde_rows(x,f)
 for at in range(pc,pc+size):assert row_at(rows,at)==want,(hex(at),row_at(rows,at),want)
allowed=patches+[(base,base+len(code)),(fde_start,dest+4),(h['offset'],h['offset']+len(hdr)),(e.phoff+i*e.phentsize+32,e.phoff+i*e.phentsize+48)]
for name in ['.b5.text','.b5.eh_frame','.eh_frame_hdr']:
 i=e.section_names.index(name);allowed.append((e.shoff+i*e.shentsize+32,e.shoff+i*e.shentsize+40))
changed=[i for i,(a,b) in enumerate(zip(old,out)) if a!=b];assert len(out)==len(old) and all(any(a<=i<b for a,b in allowed) for i in changed)
(O/'fixed_qnx.elf').write_bytes(out)
report=dict(status='PASS',baseline_sha256=sha(old),candidate_sha256=sha(out),code_bytes=len(code),apply_helper=base,geom_helper=geom,patches=patches,allowed=allowed,changed_bytes=len(changed),inherited_FDEs_unchanged=len(pairs),new_FDEs=2,all_FDE_headers_decodable=len(xp),helper_CFI_rows_match=True,heap_stack_growth=0,fade_ms=5)
(O/'build_results.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
