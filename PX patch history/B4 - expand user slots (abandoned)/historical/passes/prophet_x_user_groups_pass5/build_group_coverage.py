# SPDX-License-Identifier: GPL-2.0-or-later
from pathlib import Path
import re,json,struct,hashlib
from elftools.elf.elffile import ELFFile
from capstone import *
from capstone.x86_const import X86_OP_MEM,X86_REG_RIP,X86_OP_IMM
pic=Path('pic.bin').read_bytes()
qnxseeds={'group_names':(0x2a0160,0x428),'group_size_cache':(0x2a4a20,0x208),'group_file_index_pointer':(0x2a9028,8),'group_counts_pointer':(0x2a9030,8)}
qnxrefs=[];calls=[];indirect=[];symbols=[];candidates=[]
with open('stock.elf','rb') as f:
 e=ELFFile(f)
 syms=sorted([(s['st_value'],s['st_size'],s.name) for s in e.get_section_by_name('.symtab').iter_symbols() if s['st_info']['type']=='STT_FUNC' and s['st_size']],key=lambda x:x[0])
 def owner(a):
  return next((n for v,z,n in syms if v<=a<v+z),'unresolved')
 md=Cs(CS_ARCH_X86,CS_MODE_64);md.detail=True;md.skipdata=True
 for section in e.iter_sections():
  if not section['sh_flags']&4:continue
  for i in md.disasm(section.data(),section['sh_addr']):
   if i.id==0:continue
   for op in i.operands:
    if op.type==X86_OP_MEM and op.mem.base==X86_REG_RIP:
     a=i.address+i.size+op.mem.disp
     for seed,(base,size) in qnxseeds.items():
      if base<=a<base+size:qnxrefs.append({'pc':hex(i.address),'owner':owner(i.address),'seed':seed,'target':hex(a),'instruction':i.mnemonic+' '+i.op_str})
   if i.mnemonic in ['call','jmp']:
    if i.operands[0].type==X86_OP_IMM:calls.append({'pc':hex(i.address),'owner':owner(i.address),'target':hex(i.operands[0].imm),'target_owner':owner(i.operands[0].imm),'kind':i.mnemonic})
    elif i.mnemonic=='call':indirect.append({'pc':hex(i.address),'owner':owner(i.address),'instruction':i.mnemonic+' '+i.op_str})
 seedowners={r['owner'] for r in qnxrefs}
 relevantcalls=[r for r in calls if r['owner'] in seedowners or any(s in r['owner']+r['target_owner'] for s in ['CSampleGroups','LibraryCopy','MakeNewUser'])]
 for v,z,n in syms:
  if n in seedowners or any(t in n for t in ['CSampleGroups','LibraryCopy','MakeNewUser']):symbols.append({'va':hex(v),'size':z,'name':n})
# PIC direct edges and data pointer references: aligned words, code/data classification unresolved.
targets={0x9d0792e0:'count getter',0x9d079300:'group availability',0x9d079978:'count query',0x9d079340:'name query',0x9d079744:'size query',0x9d080e2c:'internal to display',0x9d080e60:'display to internal',0x9d040ed8:'count initializer',0x9d042a8c:'count rebuild',0x9d042b80:'name rebuild',0x9d041e8c:'name reader',0x9d04d300:'parameter getter',0x9d04dacc:'parameter setter'}
edges=[];pointers=[];param_literals=[]
for off in range(0,len(pic)-3,4):
 w=struct.unpack_from('<I',pic,off)[0];pc=0x9d000000+off
 if w>>26 in [2,3]:
  target=((pc+4)&0xf0000000)|((w&0x3ffffff)<<2)
  if target in targets:edges.append({'pc':hex(pc),'target':hex(target),'name':targets[target],'kind':'jal' if w>>26==3 else 'j','classification':'candidate until code ownership verified'})
 if w in targets or w in [0x80037e90,0x8003a118,0x9d063f60]:pointers.append({'offset':hex(off),'value':hex(w),'classification':'aligned raw word; may be data or accidental'})
 if w>>26 in [9,13] and (w>>21)&31==0 and w&0xffff in [0x22,0x63]:param_literals.append({'pc':hex(pc),'word':hex(w),'value':w&0xffff,'classification':'candidate; parameter role not proven'})
out={'method':'QNX executable-section Capstone linear disassembly with RIP-relative seed matching and ELF function ownership; PIC aligned-word direct-edge/pointer/literal enumeration. Not whole-program dataflow.','input_sha256':{'pic':hashlib.sha256(pic).hexdigest(),'qnx':hashlib.sha256(Path('stock.elf').read_bytes()).hexdigest()},'qnx_seed_references':qnxrefs,'qnx_relevant_functions':symbols,'qnx_relevant_direct_edges':relevantcalls,'qnx_indirect_calls_in_relevant_functions':[r for r in indirect if r['owner'] in {s['name'] for s in symbols}],'pic_candidate_direct_edges':edges,'pic_raw_pointer_candidates':pointers,'pic_group_parameter_literal_candidates':param_literals}
Path('branch4/group_coverage_map.json').write_text(json.dumps(out,indent=2)+'\n')
print({k:len(v) for k,v in out.items() if isinstance(v,list)})
