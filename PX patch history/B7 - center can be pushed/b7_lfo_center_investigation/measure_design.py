"""Assemble isolated design objects; validate placement in memory only.
No patched ELF, firmware or package is written.
"""
from pathlib import Path
import sys, struct, subprocess, json, hashlib
O=Path(__file__).resolve().parent; R=O.parent
sys.path[:0]=[str(R),str(R/'b5_candidate_work')]
from b5_elf_placement_check import ExactElf,decode_index,encode_index
from qnx_elf import Elf
P=R/'b15_candidate_work/lfo_endpoint_investigation/completion_fix/voice_2.2.2.1.11_B5_completion_fade_candidate_qnx.elf'
B=P.read_bytes(); assert hashlib.sha256(B).hexdigest()=='45ee5d94dddb785f0ffa6e3514d42f05671811a669c5f638414d0cd668d66640'
e=ExactElf(B)
flags=['-target','x86_64-unknown-linux-gnu','-Os','-ffreestanding','-fno-builtin','-fno-stack-protector','-fPIE','-mno-red-zone','-ffp-contract=off','-fasynchronous-unwind-tables','-fno-vectorize','-fno-slp-vectorize','-Wall','-Wextra','-Werror']
subprocess.run(['clang',*flags,'-c',str(O/'design_probe.c'),'-o',str(O/'design_probe.o')],check=True)
subprocess.run(['clang','-target','x86_64-unknown-linux-gnu','-c',str(O/'design_thunk.s'),'-o',str(O/'design_thunk.o')],check=True)
def align(x,a):return (x+a-1)&-a
codebase=0x100f60; framebase=0x1024e8; cp=codebase; fp=framebase
symbols={'center_get_mod':0x27040,'center_get_param':0x9760,'center_map':0x2a5188,'center_diffs':0x2a5180,'center_continue':0x1a887}
objects=[];inventory=[]
for name in ['design_probe','design_thunk']:
 b=(O/(name+'.o')).read_bytes();oe=Elf(b);places={};tables={}
 for i,s in enumerate(oe.sh):
  n=oe.names[i]
  if n=='.text' or n.startswith('.rodata'):
   cp=align(cp,max(s[8],1));places[i]=cp;inventory.append(dict(object=name,section=n,start=cp,size=s[5]));cp+=s[5]
  elif n=='.eh_frame':
   fp=align(fp,max(s[8],1));places[i]=fp;inventory.append(dict(object=name,section=n,start=fp,size=s[5]));fp+=s[5]
  elif s[2]&2 and s[5]:raise ValueError('Unexpected allocated section '+n)
 for i,s in enumerate(oe.sh):
  if s[1]!=2:continue
  sr=oe.sh[s[6]];st=b[sr[4]:sr[4]+sr[5]];tab=[]
  for off in range(s[4],s[4]+s[5],s[9]):
   no,info,other,ndx,val,size=struct.unpack_from('<IBBHQQ',b,off);sn=st[no:st.find(b'\0',no)].decode();tab.append((sn,ndx,val,size))
   if sn and ndx in places and info>>4 in (1,2):symbols[sn]=places[ndx]+val
  tables[i]=tab
 objects.append((b,oe,places,tables))
assert cp<=0x102000 and fp+4<=0x103000
# Ownership is established by the current .b15 sections and their original
# builder's 100000..102000 / 102000..103000 reservations, NOT zero bytes.
for n,base,end in [('.b15_text',codebase,cp),('.b15_eh_frame',framebase,fp+4)]:
 s=e.sections[e.section_names.index(n)];assert s[3]+s[5]<=base
 assert e.read(base,end-base)==b'\0'*(end-base) # supplementary collision check
view=bytearray(B);relocs=[]
for b,oe,places,tables in objects:
 for i,va in places.items():s=oe.sh[i];view[va:va+s[5]]=b[s[4]:s[4]+s[5]]
 for s in oe.sh:
  if s[1]!=4:continue
  assert s[7] in places
  for off in range(s[4],s[4]+s[5],s[9]):
   loc,info,add=struct.unpack_from('<QQq',b,off);typ=info&0xffffffff
   sn,ndx,val,size=tables[s[6]][info>>32];target=places[ndx]+val if ndx in places else symbols[sn];site=places[s[7]]+loc
   assert typ in (2,4),typ
   struct.pack_into('<i',view,site,target+add-site)
   relocs.append(dict(site=site,target=target,type=typ,addend=add,symbol=sn))
assert hashlib.sha256(e.read(0x1a87b,12)).hexdigest()=='e4e83aa32850992c5084ec5a5d6d951a03a393ced8c710b2e1a17e746c718b5b'
hook=b'\xe9'+struct.pack('<i',symbols['center_thunk']-0x1a880)+b'\x90'*7
thunkend=next(i['start']+i['size'] for i in inventory if i['object']=='design_thunk' and i['section']=='.text')
assert view[thunkend-17:thunkend-5]==e.read(0x1a87b,12)
assert thunkend+struct.unpack_from('<i',view,thunkend-4)[0]==0x1a887
h=next(p for p in e.phdr if p['type']==0x6474e550);frame,oldpairs=decode_index(e.read(h['va'],h['filesz']),h['va']);new=[]
x=ExactElf(bytes(view))
for b,oe,places,tables in objects:
 for i,base in places.items():
  if oe.names[i]!='.eh_frame':continue
  pos=0
  while pos+4<=oe.sh[i][5]:
   n=struct.unpack_from('<I',view,base+pos)[0]
   if not n:break
   assert pos+n+4<=oe.sh[i][5]
   if struct.unpack_from('<I',view,base+pos+4)[0]:
    f=x.fde(base+pos);new.append((f['pc'],base+pos));assert codebase<=f['pc']<cp
   pos+=n+4
assert len(new)==2
header=encode_index(sorted(oldpairs+new),h['va'],frame);assert h['va']+len(header)<=0x105000
assert decode_index(header,h['va'])[1]==sorted(oldpairs+new)
# New records append contiguously at the old section end, without introducing
# an interior zero terminator that would hide them from a linear frame walk.
fs=e.sections[e.section_names.index('.b15_eh_frame')];pos=fs[3]
while pos<fp:
 n=struct.unpack_from('<I',view,pos)[0];assert n>0;pos+=n+4
assert pos==fp and view[fp:fp+4]==b'\0'*4
for pc,f in oldpairs:assert x.read(f,e.fde(f)['length']+4)==e.read(f,e.fde(f)['length']+4)
# No installed relocation, defined symbol, section or inherited unwind range
# may already own the selected bytes.
occupied=[(s[3],s[3]+s[5]) for s in e.sections if s[2]&2 and s[5]]
for lo,hi in [(codebase,cp),(framebase,fp+4)]:assert not any(lo<b and a<hi for a,b in occupied)
for pc,f in oldpairs:
 rec=e.fde(f);assert not (codebase<pc+rec['range'] and pc<cp)
 for lo,hi in [(codebase,cp),(framebase,fp+4)]:assert not (lo<f+rec['length']+4 and f<hi)
for s in e.sections:
 if s[1] in (4,9):
  for off in range(s[4],s[4]+s[5],s[9]):
   va=struct.unpack_from('<Q',B,off)[0]
   assert not(codebase<=va<cp or framebase<=va<fp+4)
 if s[1] in (2,11):
  for off in range(s[4],s[4]+s[5],s[9]):
   no,info,other,ndx,va,size=struct.unpack_from('<IBBHQQ',B,off)
   if ndx not in (0,0xfff1):assert not(codebase<=va<cp or framebase<=va<fp+4)
(O/'design_payload.bin').write_bytes(view[codebase:cp])
(O/'design_frames.bin').write_bytes(view[framebase:fp+4])
for name in ['design_probe','design_thunk']:
 with (O/(name+'.disassembly.txt')).open('w') as out:subprocess.run(['objdump','-dr','--x86-asm-syntax=intel',str(O/(name+'.o'))],stdout=out,check=True)
 with (O/(name+'.frames.txt')).open('w') as out:subprocess.run(['objdump','--dwarf=frames',str(O/(name+'.o'))],stdout=out,check=True)
report=dict(status='PASS',baseline_sha256=hashlib.sha256(B).hexdigest(),code_base=codebase,code_end=cp,code_and_constants_and_alignment=cp-codebase,frame_base=framebase,frame_end=fp+4,frame_bytes=fp+4-framebase,index_growth=len(header)-h['filesz'],hook_bytes=12,hook=hook.hex(),symbols=symbols,sections=inventory,relocations=relocs,inherited_FDEs_preserved=len(oldpairs),new_FDEs=new,code_capacity_remaining=0x102000-cp,frame_capacity_remaining=0x103000-fp-4,output='isolated raw payload/CFI objects only; no patched firmware or ELF',wrapper_stack_bytes=336)
(O/'measurement.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k not in ('sections','relocations','symbols')},indent=2))
