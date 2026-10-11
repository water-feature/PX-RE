"""Audit calls newly covered by the earlier startup-mutex acquisition.

Normal direct control flow; RAM scheduler virtual dispatch resolved explicitly
from the ELF relocations. No assertion about arbitrary runtime dispatch.
"""
from pathlib import Path
from io import BytesIO
import json
from elftools.elf.elffile import ELFFile
from elftools.dwarf.callframe import FDE
from capstone import Cs, CS_ARCH_X86, CS_MODE_64
from capstone.x86_const import X86_OP_IMM
P=Path(__file__).resolve().parent
raw=(P.parent/'ProphetX.elf').read_bytes();e=ELFFile(BytesIO(raw))
m=Cs(CS_ARCH_X86,CS_MODE_64);m.detail=True
t=e.get_section_by_name('.text');ii=list(m.disasm(t.data(),t['sh_addr']))
assert ii[-1].address+ii[-1].size==t['sh_addr']+t['sh_size']
I={i.address:i for i in ii};N={i.address:i.address+i.size for i in ii}
symtab=e.get_section_by_name('.symtab');funcs={}
for s in symtab.iter_symbols():
    if s['st_info']['type']=='STT_FUNC' and s['st_size'] and s['st_shndx']!='SHN_UNDEF':
        funcs[s['st_value']]=(s.name,s['st_size'])
dyn=e.get_section_by_name('.dynsym')
plt={0x7190+16*n:dyn.get_symbol(r['r_info_sym']).name for n,r in enumerate(e.get_section_by_name('.rela.plt').iter_relocations())}
assert plt[0x7640]=='pthread_cond_wait' and plt[0x7a10]=='pthread_mutex_lock'
pending=[0x216c6];seen=set();exits=set()
while pending:
    a=pending.pop()
    if a==0x2174c:exits.add(a);continue
    if a in seen:continue
    seen.add(a);i=I[a]
    if i.mnemonic=='jmp':
        assert i.operands[0].type==X86_OP_IMM;pending.append(i.operands[0].imm)
    elif i.mnemonic.startswith('j'):
        assert i.operands[0].type==X86_OP_IMM;pending.extend([i.operands[0].imm,N[a]])
    elif i.mnemonic.startswith('ret'):exits.add(a)
    else:pending.append(N[a])
assert exits=={0x2174c}
coordinator={a for a in I if 0x1b49e<=a<0x1b7e5}
sites=[I[a] for a in sorted(seen|coordinator) if I[a].mnemonic=='call']
roots=[]
for i in sites:
    assert i.operands[0].type==X86_OP_IMM,(hex(i.address),i.op_str)
    roots.append(i.operands[0].imm)

# NoteOn calls OpenStream via vptr+0x28; NoteOff marks SetQuickClose via
# vptr+0x48. The C++ object address point is vtable symbol+16 = 0x29e4e8.
rel={r['r_offset']:r['r_addend'] for r in e.get_section_by_name('.rela.dyn').iter_relocations()}
assert rel[0x29e4e8+0x28]==0x3d310 and rel[0x29e4e8+0x48]==0x3ce30
virtual={0x36487:rel[0x29e510],0x36ad5:rel[0x29e530],0x363d1:rel[0x29e500],0x363f1:rel[0x29e508]}
todo=list(roots);visited=set();external=set();unresolved=[];edges=[]
while todo:
    a=todo.pop()
    if a in visited:continue
    visited.add(a)
    if a in plt:external.add(plt[a]);continue
    if a==0x49fd0:continue # actual patched logger is the four-byte return stub
    if a not in funcs:
        unresolved.append({'target':hex(a),'reason':'no complete function symbol'});continue
    name,size=funcs[a]
    for i in m.disasm(raw[a:a+size],a):
        target=None
        if i.mnemonic=='call':
            if i.operands[0].type==X86_OP_IMM:target=i.operands[0].imm
            elif i.address in virtual:target=virtual[i.address]
            else:unresolved.append({'site':hex(i.address),'instruction':i.op_str,'function':name})
        elif i.mnemonic=='jmp' and i.operands[0].type==X86_OP_IMM:
            q=i.operands[0].imm
            if not a<=q<a+size:target=q
        if target is not None:edges.append([hex(i.address),hex(target)]);todo.append(target)
assert not unresolved,unresolved
expected={'pthread_mutex_lock','pthread_mutex_unlock','pthread_cond_broadcast','pthread_rwlock_rdlock','pthread_rwlock_unlock','memcpy','memset','strncmp','strrchr','strcmp','memcmp','rand','__stack_chk_fail'}
assert external<=expected,external-expected
imports={s.name for s in dyn.iter_symbols() if s['st_shndx']=='SHN_UNDEF'}
cancel={s for s in imports if s in {'pthread_cancel','pthread_setcancelstate','pthread_setcanceltype','pthread_testcancel','pthread_exit','ThreadCancel','ThreadCancel_r','longjmp','siglongjmp','_longjmp'}}
assert not cancel,cancel
frames=e.get_dwarf_info().EH_CFI_entries()
wait=next(x for x in frames if isinstance(x,FDE) and x['initial_location']==0x498c0)
assert wait.cie['augmentation']==b'zR' and wait.lsda_pointer is None
result={'fresh_newly_locked_cfg_instructions':len(seen),'fresh_cfg_exit':'0x2174c','coordinator_earlier_locked_interval':['0x1b49e','0x1b7e5'],'root_call_sites':[[hex(i.address),hex(i.operands[0].imm)] for i in sites],'audited_functions':[[hex(a),funcs[a][0]] for a in sorted(visited) if a in funcs and a!=0x49fd0],'external_callees':sorted(external),'resolved_virtual_calls':{hex(a):hex(b) for a,b in virtual.items()},'unresolved_calls':unresolved,'cancellation_or_nonlocal_jump_imports':sorted(cancel),'stock_wait_no_lsda':True,'edges':edges,'decision':'Do not add generic cancellation/exception infrastructure to this minimal patch. New quiet wait has a genuine cancellation limitation, but no supported application cancellation path was found; stock synchronizer wait already lacks cancellation cleanup. Earlier startup acquisition adds no throwing allocation or condition-wait call in the audited RAM path.','limits':['No QNX libc implementation or hardware execution.','RAM scheduler dispatch is the supported assumption, not proof of every runtime object.','No proof against cancellation requested externally, dynamically resolved calls, asynchronous signals, memory corruption, or errors in pthread primitives.','Existing post-acquisition stock regions are retained and are not audited as a general firmware exception-safety project.']}
(P/'unwind_ownership_audit.json').write_text(json.dumps(result,indent=2)+'\n')
print('PASS:',len(seen),'fresh-path instructions; sole original-acquisition exit; newly locked call graph has',len(visited),'targets and no unresolved calls.')
print('External callees:',', '.join(sorted(external)))
print('No throwing allocation or cancellation-point call in earlier startup-lock intervals; no application cancellation imports; stock synchronizer wait has no LSDA cleanup.')
