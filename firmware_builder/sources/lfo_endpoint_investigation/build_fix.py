# SPDX-License-Identifier: GPL-2.0-or-later
"""Isolated B15 rate-independent endpoint identity candidate; no packaging."""
from pathlib import Path
import sys,struct,json,hashlib,subprocess
O=Path(__file__).resolve().parent;R=O.parents[1];sys.path.insert(0,str(R))
from b5_elf_placement_check import ExactElf,decode_index,encode_index
sha=lambda b:hashlib.sha256(b).hexdigest()
source=O.parent/'voice_2.2.2.1.8_B15_candidate_qnx.elf';old=source.read_bytes()
assert sha(old)=='b819511abcace5c271d13145bbc3499fafed8f442af91d7343663cd71c3892c7'
e=ExactElf(old);out=bytearray(old)
m=json.loads((R/'b5_candidate_work/b5_candidate_manifest.json').read_text())
lo=m['layout']['code_base'];used=m['layout']['code_bytes'];helper=(lo+used+15)&~15
assert helper+44<=lo+m['layout']['code_reservation']
original=0xf13bb;body=bytearray(e.read(original,44))
assert hashlib.sha256(body).hexdigest()=='31dbbdc480a5005df938358a3ff524917bb5da1f570885a84891b10e4ba06447'
# Ignore rate only for the render endpoint-identity check. Control comparisons remain exact.
body[22:24]=b'\x90\x90'
assert hashlib.sha256(body[16:24]).hexdigest()=='e92cc0e2b309c13535dc6838d2827befacf7c2bf11f5c53e8794041eac45b745'
out[helper:helper+44]=body
site=0xf15dc;assert hashlib.sha256(old[site:site+5]).hexdigest()=='552ad56a62d0c055a5f4306a074d3235cdf62fd5326a75e61b047f89c8fb16d8'
out[site:site+5]=b'\xe8'+struct.pack('<i',helper-site-5)
# Clone original leaf helper's real FDE and reuse its original CIE.
hp=next(p for p in e.phdr if p['type']==0x6474e550)
frame,pairs=decode_index(e.read(hp['va'],hp['filesz']),hp['va'])
oldfde=next(fde for pc,fde in pairs if pc==original);d=e.fde(oldfde)
assert d['range']==44 and d['cie']['encoding']==0x1b
fb=m['layout']['frame_base'];dest=fb+m['layout']['frame_bytes'];fde=bytearray(e.read(oldfde,d['length']+4))
assert dest+len(fde)+4<=fb+m['layout']['frame_reservation']
assert e.read(dest,4)==b'\0'*4 # terminator in manifest-owned frame reservation
struct.pack_into('<I',fde,4,dest+4-d['cie']['va'])
struct.pack_into('<i',fde,8,helper-(dest+8))
out[dest:dest+len(fde)+4]=fde+b'\0'*4
newpairs=sorted(pairs+[(helper,dest)]);hdr=encode_index(newpairs,hp['va'],frame)
assert hp['va']==0x103000 and hp['va']+len(hdr)<=0x105000
out[hp['offset']:hp['offset']+len(hdr)]=hdr
# Extend only owned section extents and indexed unwind header size.
for name,size in [('.b5.text',helper+44-lo),('.b5.eh_frame',dest+len(fde)+4-fb),('.eh_frame_hdr',len(hdr))]:
 i=e.section_names.index(name);struct.pack_into('<Q',out,e.shoff+i*e.shentsize+32,size)
i=e.phdr.index(hp);struct.pack_into('<QQ',out,e.phoff+i*e.phentsize+32,len(hdr),len(hdr))
x=ExactElf(bytes(out));fp,ps=decode_index(x.read(hp['va'],len(hdr)),hp['va']);assert fp==frame and ps==newpairs
for pc,f in ps:assert x.fde(f)['pc']==pc
for pc,f in pairs:assert x.read(f,e.fde(f)['length']+4)==e.read(f,e.fde(f)['length']+4)
assert x.fde(dest)['range']==44 and x.fde(dest)['cie']==d['cie']
allowed=[(helper,helper+44),(site,site+5),(dest,dest+len(fde)+4),(hp['offset'],hp['offset']+len(hdr)),(e.phoff+i*e.phentsize+32,e.phoff+i*e.phentsize+48)]
for name in ('.b5.text','.b5.eh_frame','.eh_frame_hdr'):
 j=e.section_names.index(name);allowed.append((e.shoff+j*e.shentsize+32,e.shoff+j*e.shentsize+40))
changed=[j for j,(a,b) in enumerate(zip(old,out)) if a!=b]
assert all(any(a<=j<b for a,b in allowed) for j in changed) and len(out)==len(old)
name='voice_B15_LFO_endpoint_fix_UNPACKAGED.elf';(O/name).write_bytes(out)
results=[]
for label,path,fixed in [('original',source,0),('fixed',O/name,1)]:
 asm=O/(label+'.s');asm.write_text('.section __TEXT,__text,regular,pure_instructions\n.p2align 4\n.globl _b5_image\n_b5_image:\n.incbin "'+str(path)+'",987136,12288\n')
 exe=O/(label+'_tests')
 subprocess.run(['clang','-arch','x86_64','-O2','-fno-strict-aliasing','-DFIXED='+str(fixed),str(O/'reproduce.c'),str(asm),str(R/'b5_candidate_work/b5_wrapper_fixture.s'),'-o',str(exe)],check=True)
 run=subprocess.run([str(exe)],capture_output=True,text=True)
 results.append({'variant':label,'exit':run.returncode,'stdout':run.stdout,'stderr':run.stderr})
assert all(row['exit']==0 for row in results),results
report={'status':'PASS','scope':'actual fitted dispatch/core bytes under Rosetta; reader/Load and control packets modeled; target acoustics NOT VERIFIED','input_sha256':sha(old),'output_sha256':sha(out),'output':name,'file_bytes':len(out),'different_bytes':len(changed),'allowed_file_ranges':allowed,'render_call_site':hex(site),'region_helper':hex(helper),'new_fde':hex(dest),'inherited_fdes_unchanged':len(pairs),'tests':results,'fade_ms':5,'short_region_policy_unchanged':True,'packaged':False}
(O/'results.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
