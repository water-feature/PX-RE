#!/usr/bin/env python3
"""Build an UNPACKAGED QNX integration image; no release-approval implication."""
from pathlib import Path
import sys,struct,json,hashlib,subprocess
ROOT=Path(__file__).resolve().parents[1];OUT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT));from patch_b4_minimal_qnx import Elf
from b5_elf_placement_check import ExactElf,decode_index,encode_index
BASE=0x100000;EH=0x102000;INDEX=0x103000;END=0x105000
EXTERNAL={'b15_stock_message_continue':0x1e056,'b15_stock_noteon':0x36400,
          'b15_stock_getparam':0x9760,'b15_stock_group_continue':0x2228c,
          'b15_runtime_storage':0x2b1ec0,'b15_stock_mutex':0x2a57a0,
          **{f'b15_stock_fn_0x{v:x}':v for v in (0x7a10,0x79a0,0x9700,0x1d7f0,0x35940,0x36180,0x3ed50)}}
sha=lambda b:hashlib.sha256(b).hexdigest()
def align(n,a=16):return (n+a-1)&-a
def compile_objects():
 flags=['clang','-target','x86_64-unknown-linux-gnu','-Os','-ffreestanding','-fno-builtin',
 '-fno-stack-protector','-fPIE','-mno-red-zone','-fno-vectorize','-fno-slp-vectorize',
 '-fasynchronous-unwind-tables','-fno-jump-tables','-Wall','-Wextra','-Werror']
 paths=[]
 for name in ('b15_absolute_core','b15_absolute_qnx_adapter','b15_qnx_thunks'):
  src=OUT/(name+('.s' if name.endswith('thunks') else '.c'));obj=OUT/(name+'.o')
  subprocess.run((['clang','-target','x86_64-unknown-linux-gnu'] if src.suffix=='.s' else flags)+['-c',str(src),'-o',str(obj)],check=True)
  paths.append(obj)
 return paths

def build():
 paths=compile_objects();objects=[];symbols=dict(EXTERNAL);code_pc=BASE;eh_pc=EH
 # Assign all section and symbol addresses before relocation.
 for path in paths:
  b=path.read_bytes();e=Elf(b);placements={};tables={}
  for j,s in enumerate(e.sh):
   name=e.names[j]
   if name=='.text' or (name.startswith('.rodata') and s[5]):
    code_pc=align(code_pc,max(s[8],1));placements[j]=code_pc;code_pc+=s[5]
   elif name=='.eh_frame':
    eh_pc=align(eh_pc,max(s[8],1));placements[j]=eh_pc;eh_pc+=s[5]
   elif s[2]&2 and s[5]:raise ValueError('unexpected allocated section '+name)
  for j,s in enumerate(e.sh):
   if s[1]!=2:continue
   strow=e.sh[s[6]];st=b[strow[4]:strow[4]+strow[5]];table=[]
   for off in range(s[4],s[4]+s[5],s[9]):
    no,info,other,ndx,value,size=struct.unpack_from('<IBBHQQ',b,off)
    name=st[no:st.find(b'\0',no)].decode();table.append((name,ndx,value,size))
    if ndx in placements and name and info>>4 in (1,2):
     assert name not in symbols,name;symbols[name]=placements[ndx]+value
   tables[j]=table
  objects.append((path,b,e,placements,tables))
 assert code_pc<=0x102000 and eh_pc<=INDEX
 old=(ROOT/'b14_stable_frame_packaging_work/voice_2.2.2.1.7_qnx.elf').read_bytes()
 assert sha(old)=='4bcac9801d1d9f8306271a7ab42bb93e5e8fa9462664e16c6889ffcd050ea635'
 e=Elf(old);rxidx=next(j for j,p in enumerate(e.ph) if p[0]==1 and p[1]==5)
 rwidx=next(j for j,p in enumerate(e.ph) if p[0]==1 and p[1]==6)
 hdridx=next(j for j,p in enumerate(e.ph) if p[0]==0x6474e550)
 assert e.ph[rxidx][5:7]==(0xfd000,0xfd000)
 assert e.ph[rwidx][3]+e.ph[rwidx][6]==0x2b1eb0
 out=bytearray(old[:0xfd000]);out.extend(b'\0'*(END-len(out)));relocs=[]
 for path,b,oe,placements,tables in objects:
  for j,address in placements.items():
   s=oe.sh[j];out[address:address+s[5]]=b[s[4]:s[4]+s[5]]
  for s in oe.sh:
   if s[1]!=4:continue
   if s[7] not in placements:raise ValueError('unowned relocation target')
   for off in range(s[4],s[4]+s[5],s[9]):
    loc,info,add=struct.unpack_from('<QQq',b,off);typ=info&0xffffffff
    name,ndx,value,size=tables[s[6]][info>>32]
    target=placements[ndx]+value if ndx in placements else symbols[name]
    place=placements[s[7]]+loc
    if typ in (2,4):struct.pack_into('<i',out,place,target+add-place)
    elif typ in (1,10,11):raise ValueError('ET_DYN absolute relocation must not be embedded in helpers')
    else:raise ValueError('unsupported relocation '+str(typ))
    relocs.append({'object':path.name,'place':hex(place),'type':typ,'symbol':name,'target':hex(target),'addend':add})
 # Guard every exact original instruction window.
 hooks=[(0x1e050,{'size': 6, 'sha256': 'f909b8f17e0b649494430b8edcbf48a7bd51781dbdbb327ef8bf85744198ef45'},'b15_message_entry',False),
        (0x23b2d,{'size': 5, 'sha256': 'b3fb2491c4a20e8741d3bf75a9a47f8122b16d588ead31a54db4ebebee2cbaaa'},'b15_noteon_thunk',True),
        (0x23a3a,{'size': 5, 'sha256': '9d415d5f7cda824101fb26839450684a8e53a705dfff3c972e3fff0d73faf2b8'},'b15_attempt_thunk',True),
        (0x22280,{'size': 12, 'sha256': '97f8cc9c3054577ce36409ecec171f9a51a6046db1278252cefe34f05eabac12'},'b15_group_clear_thunk',False)]
 changes=[]
 for va,expected,name,call in hooks:
  off=e.off(va,expected['size']);before=old[off:off+expected['size']];assert sha(before)==expected['sha256']
  after=bytes([0xe8 if call else 0xe9])+struct.pack('<i',symbols[name]-va-5)+b'\x90'*(len(before)-5)
  out[off:off+len(before)]=after;changes.append({'va':hex(va),'file_offset':off,'before':before.hex(),'after':after.hex(),'label':name})
 va=0x22344;off=e.off(va,5);assert hashlib.sha256(old[off:off+5]).hexdigest()=='1a79e1930d6f83f25cbbad5e41f980b1e466aaca765824af8da8bcc253701bd1'
 out[off:off+5]=bytes.fromhex('31c0909090');changes.append({'va':hex(va),'file_offset':off,'before':old[off:off+5].hex(),'after':out[off:off+5].hex(),'label':'defer legacy group selection to common helper'})
 oldhdr=e.ph[hdridx];frame,oldpairs=decode_index(old[oldhdr[2]:oldhdr[2]+oldhdr[5]],oldhdr[3]);newpairs=[]
 # Decode relocated real compiler FDEs using their supported zR CIE encoding.
 for path,b,oe,placements,tables in objects:
  for j,base in placements.items():
   if oe.names[j]!='.eh_frame':continue
   pos=0;limit=oe.sh[j][5]
   while pos+4<=limit:
    n=struct.unpack_from('<I',out,base+pos)[0]
    if not n:break
    assert pos+4+n<=limit
    delta=struct.unpack_from('<I',out,base+pos+4)[0]
    if delta:
     pc=base+pos+8+struct.unpack_from('<i',out,base+pos+8)[0]
     count=struct.unpack_from('<I',out,base+pos+12)[0]
     assert BASE<=pc<code_pc and pc+count<=code_pc
     newpairs.append((pc,base+pos))
    pos+=n+4
 pairs=sorted(oldpairs+newpairs);assert len({x[0] for x in pairs})==len(pairs)
 hdr=encode_index(pairs,INDEX,frame);assert INDEX+len(hdr)<=END
 out[INDEX:INDEX+len(hdr)]=hdr
 # Move original unmapped tail; preserve its bytes before creating new names/table.
 tailshift=END-0xfd000;out.extend(old[0xfd000:]);sections=[list(s) for s in e.sh]
 for s in sections:
  if s[1]!=8 and s[4]>=0xfd000:s[4]+=tailshift
 # Own the new zero-fill range and move heap end symbols; preserve fixed frame-cache limit.
 bssidx=e.names.index('.bss');assert sections[bssidx][3]+sections[bssidx][5]==0x2b1eb0
 sections[bssidx][5]=0x2b21c0-sections[bssidx][3]
 end_symbols=[]
 for si,s in enumerate(e.sh):
  if s[1] not in (2,11):continue
  sr=e.sh[s[6]];st=old[sr[4]:sr[4]+sr[5]]
  for off in range(0,s[5],s[9]):
   no,info,other,ndx,value,size=struct.unpack_from('<IBBHQQ',old,s[4]+off)
   name=st[no:st.find(b'\0',no)].decode()
   if name in ('_end','end') and value==0x2b1eb0:
    dest=sections[si][4]+off+8;struct.pack_into('<Q',out,dest,0x2b21c0)
    end_symbols.append({'name':name,'table':e.names[si],'file_offset':dest})
 assert end_symbols
 hsec=e.names.index('.eh_frame_hdr');sections[hsec][3]=INDEX;sections[hsec][4]=INDEX;sections[hsec][5]=len(hdr)
 stringsrow=e.sh[e.shstr];strings=bytearray(old[stringsrow[4]:stringsrow[4]+stringsrow[5]])
 def addsection(name,address,size):
  no=len(strings);strings.extend(name.encode()+b'\0');sections.append([no,1,2| (4 if 'text' in name else 0),address,address,size,0,0,16,0])
 addsection('.b15_text',BASE,code_pc-BASE);addsection('.b15_eh_frame',EH,eh_pc-EH)
 stroff=align(len(out),8);out.extend(b'\0'*(stroff-len(out)));out.extend(strings)
 sections[e.shstr][4]=stroff;sections[e.shstr][5]=len(strings)
 shoff=align(len(out),8);out.extend(b'\0'*(shoff-len(out)))
 for s in sections:out.extend(struct.pack('<IIQQQQIIQQ',*s))
 struct.pack_into('<Q',out,40,shoff);struct.pack_into('<H',out,60,len(sections))
 for j in (rxidx,rwidx,hdridx):
  p=list(e.ph[j])
  if j==rxidx:p[5]=p[6]=END
  elif j==rwidx:p[6]=0x2b21c0-p[3]
  else:p[2]=p[3]=p[4]=INDEX;p[5]=p[6]=len(hdr)
  struct.pack_into('<IIQQQQQQ',out,e.phoff+j*e.phents,*p)
 # Independent loaded-address unwind decode, inherited FDE identity and exact byte guards.
 exact=ExactElf(bytes(out));newframe,decoded=decode_index(exact.read(INDEX,len(hdr)),INDEX)
 assert newframe==frame and decoded==pairs
 for pc,fde in decoded:
  d=exact.fde(fde);assert d['pc']==pc
 for pc,fde in oldpairs:
  d=ExactElf(old).fde(fde);assert exact.read(fde,d['length']+4)==ExactElf(old).read(fde,d['length']+4)
 assert exact.read(0x4ea94,7)==ExactElf(old).read(0x4ea94,7)
 allowed=[(x['file_offset'],x['file_offset']+len(bytes.fromhex(x['before']))) for x in changes]
 allowed += [(40,48),(60,62)]+[(e.phoff+j*e.phents,e.phoff+(j+1)*e.phents) for j in (rxidx,rwidx,hdridx)]
 allowed += [(x['file_offset'],x['file_offset']+8) for x in end_symbols if x['file_offset']<0xfd000]
 diff=[j for j in range(0xfd000) if old[j]!=out[j]]
 assert all(any(lo<=j<hi for lo,hi in allowed) for j in diff)
 name='voice_B15_absolute_QNX_UNPLACED.elf';(OUT/name).write_bytes(out)
 report={'status':'STATIC_COMPONENT_PASS_NOT_RELEASE','ready_for_hardware':False,
 'baseline_sha256':sha(old),'candidate_sha256':sha(out),'candidate':name,
 'text_bytes':code_pc-BASE,'new_unwind_bytes':eh_pc-EH,'index_bytes':len(hdr),
 'inherited_FDEs_preserved':len(oldpairs),'new_FDEs':len(newpairs),'program_headers':len(e.ph),
 'RX_end':hex(END),'RW_end':hex(0x2b21c0),'state_reservation':[hex(0x2b1ec0),hex(0x2b21c0)],
 'end_symbols_moved':end_symbols,'fixed_frame_cache_endpoint_preserved':True,
 'old_loaded_byte_changes_guarded':True,'new_helpers_position_independent':True,'absolute_relocations_rejected':True,'hooks':changes,'symbols':{n:hex(v) for n,v in symbols.items()},
 'relocations':relocs,'limits':'PIC not integrated; runtime ABI/ownership/transport tests still required; not a flashable candidate.'}
 (OUT/'absolute_qnx_integration_results.json').write_text(json.dumps(report,indent=2)+'\n')
 print(json.dumps({k:v for k,v in report.items() if k not in ('relocations','symbols','hooks')},indent=2))
if __name__=='__main__':build()
