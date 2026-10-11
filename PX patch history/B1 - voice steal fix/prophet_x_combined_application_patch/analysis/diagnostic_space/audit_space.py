# SPDX-License-Identifier: GPL-2.0-or-later
"""Static reference audit for two potential diagnostic-code reclamation regions."""
from pathlib import Path
from collections import Counter
import json,struct
from elftools.elf.elffile import ELFFile
from capstone import Cs,CS_ARCH_X86,CS_MODE_64
from capstone.x86_const import X86_OP_IMM,X86_OP_MEM,X86_REG_RIP,X86_REG_EDI,X86_REG_RDI
P=Path(__file__).resolve().parent
with (P.parent/'ProphetX.elf').open('rb') as f:
 e=ELFFile(f);t=e.get_section_by_name('.text');m=Cs(CS_ARCH_X86,CS_MODE_64);m.detail=True
 ins=list(m.disasm(t.data(),t['sh_addr']))
 assert ins[-1].address+ins[-1].size==t['sh_addr']+t['sh_size'],'complete .text decoding required'
 by={i.address:i for i in ins};calls=[];refs=[]
 for j,i in enumerate(ins):
  for o in i.operands:
   dest=None
   if o.type==X86_OP_IMM:dest=o.imm
   elif o.type==X86_OP_MEM and o.mem.base==X86_REG_RIP:dest=i.address+i.size+o.mem.disp
   if dest is not None and (0x49fd0<=dest<0x4a08e or 0x8fed0<=dest<0x8ff44):
    refs.append({'site':hex(i.address),'instruction':i.mnemonic+' '+i.op_str,'target':hex(dest)})
  if i.mnemonic in ['call','jmp'] and i.operands[0].type==X86_OP_IMM and i.operands[0].imm==0x49fd0:
   # Nearest textual argument assignment, then ensure no control-flow boundary intervenes.
   for k in range(j-1,max(-1,j-20),-1):
    q=ins[k]
    if q.mnemonic.startswith('j') or q.mnemonic=='call':raise AssertionError(('priority not locally established',hex(i.address)))
    if q.operands and q.operands[0].type!=X86_OP_MEM and q.operands[0].type!=X86_OP_IMM and q.operands[0].reg in [X86_REG_EDI,X86_REG_RDI]:
     assert q.mnemonic=='mov' and q.operands[1].type==X86_OP_IMM,(i.address,q.op_str)
     priority=q.operands[1].imm;assert priority in [3,5]
     calls.append({'site':hex(i.address),'kind':i.mnemonic,'priority':priority,'assignment':hex(q.address)});break
   else:raise AssertionError(('missing argument assignment',i.address))
 assert len(calls)==28
 # External branches must use the preserved entry; internal DebugPrintf control flow is expected.
 external=[r for r in refs if not 0x49fd0<=int(r['site'],16)<0x4a08e]
 assert [r for r in external if 0x49fd4<=int(r['target'],16)<0x4a08e]==[]
 strings=[r for r in refs if 0x8fed0<=int(r['target'],16)<0x8ff44]
 assert [(int(r['site'],16),int(r['target'],16)) for r in strings]==[(0x4431d,0x8fed0),(0x44362,0x8ff08)]
 dyn=[s.name for s in e.get_section_by_name('.dynsym').iter_symbols() if s['st_value']==0x49fd0]
 assert dyn==[]
 relocated=[];pointers=[]
 for s in e.iter_sections():
  if s['sh_type'] in ['SHT_RELA','SHT_REL']:
   for r in s.iter_relocations():
    add=r.entry.get('r_addend',0)
    if 0x49fd0<=add<0x4a08e or 0x8fed0<=add<0x8ff44:relocated.append((s.name,dict(r.entry)))
  if s['sh_flags']&2 and not s['sh_flags']&4 and s['sh_type']=='SHT_PROGBITS':
   d=s.data()
   # Inspect aligned 64-bit literal pointer slots in runtime data.
   for off in range((-s['sh_addr'])%8,len(d)-7,8):
    a=struct.unpack_from('<Q',d,off)[0]
    if 0x49fd0<=a<0x4a08e or 0x8fed0<=a<0x8ff44:pointers.append((s.name,hex(s['sh_addr']+off),hex(a)))
 assert not relocated and not pointers,(relocated,pointers)
 seg=next(s for s in e.iter_segments() if s['p_type']=='PT_LOAD' and s['p_vaddr']<=0x8fed0<s['p_vaddr']+s['p_filesz'])
 assert seg['p_flags']&1
 result={'direct_calls':calls,'code_references':refs,'dynamic_exports':dyn,'relocation_addends_in_regions':relocated,'aligned_runtime_pointer_literals':pointers,'string_segment_flags':seg['p_flags'],'limits':['direct instructions and aligned pointers only','no proof of arbitrary computed runtime pointers','old DebugPrintf unwind metadata covers reclaimed body and needs review']}
 (P/'reference_audit.json').write_text(json.dumps(result,indent=2)+'\n')
 print('PASS: 28 direct DebugPrintf callers; priorities',dict(Counter(x['priority'] for x in calls)))
 print('Two string references, both suppressed DebugPrintf arguments. No external interior code target, dynamic export, relocation addend or aligned runtime pointer literal found in candidate regions.')
 print('Diagnostic strings lie in existing RX PT_LOAD. No ELF segment permissions or size change needed.')
 print('Limits: computed pointers and unwind behavior are not proven.')
