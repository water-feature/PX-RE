#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Emit only B8 additions. Never modifies or recompiles inherited B5 objects."""
import sys,json,subprocess,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT.parent/'b5_candidate_work'),str(ROOT.parent)]
from emit_b5_candidate import object_info
BASE_SHA='07ff1fd635505114945fc4dcab11a212f4bc9164b1a7ab8beb681482cb7c2b35'
JUMPS=[('prepare',0x372d4,{'size': 7, 'sha256': 'c64495f9ceed5b96c965b8444405f3fa843a01fd10846a72498d35ec32deab55'},0x372db,144),
       ('gate',0x3fc2d,{'size': 6, 'sha256': '0123a39e28cb9c884592372bdfb8ba10d1c00e83e5d6f6fb942094a6ad55b64c'},0x3fc33,176),
       ('reset',0x3c8f6,{'size': 6, 'sha256': '8050aa90b16beae254509d9741ff0580be72f0c95adf59fe9478b7a5f83b5fea'},0x3c8fc,24),
       ('note',0x3643f,{'size': 9, 'sha256': '8a987a7b556f1599b2ce4332be797b0540ae8c5115bfb69bd5d6eb0a654a609e'},0x36448,64),
       ('return',0x3749d,{'size': 5, 'sha256': '603ee83db6782f4c499fe945f3c08012e2ee658261921f1427f98af9558a1a44'},0x374a2,144)]
CALLS=[('open',0x3d492,0x42660,3)]
ALLOCATIONS=[(0x3d0fc,{'size': 5, 'sha256': 'b7039ca0c440dd3005b97a91ae0555f0138639846733b22e379b49f514f3b4e4'},'bfc8010000'),(0x3d11a,{'size': 5, 'sha256': 'b7039ca0c440dd3005b97a91ae0555f0138639846733b22e379b49f514f3b4e4'},'bfc8010000')]
B5=json.loads((ROOT.parent/'b5_candidate_work/b5_candidate_manifest.json').read_text())
BINDINGS={k:B5['symbols'][k] for k in ['b5_ram_vtable','b5_read_original_return']}
BINDINGS.update({'b8_continue_'+n:c for n,_,_,c,_ in JUMPS})
BINDINGS.update(b8_zero=0x40060,b8_original_open=0x42660,b8_original_resampler_reset=0x2e260,b8_note_skip=0x3644f,b5_note_on=B5['symbols']['b5_note_on'])
REGS=['rax','rcx','rdx','rsi','rdi','r8','r9','r10','r11','rbx','rbp','r12','r13','r14','r15']
def sha(b):return hashlib.sha256(b).hexdigest()
def assembly():
 out=['.text']
 for name,cfa,event,call in [(n,c,{'note':4,'return':5}.get(n,i),False) for i,(n,_,_,_,c) in enumerate(JUMPS)]+[('open',8,3,True)]:
  label='b8_wrap_open' if call else 'b8_hook_'+name
  extra=16 if name in ['gate','note'] else (8 if cfa%16==8 else 0)
  inherited={} if call else ({'r12':-16,'rbp':-24} if name=='reset' else {'rbx':-56,'rbp':-48,'r12':-40,'r13':-32,'r14':-24,'r15':-16})
  out+=['.p2align 4',f'.globl {label}',f'.hidden {label}',f'.type {label},@function',label+':','.cfi_startproc',f'.cfi_def_cfa %rsp,{cfa}','.cfi_offset %rip,-8']
  out += [f'.cfi_offset %{r},{o}' for r,o in inherited.items()]
  if extra:out += [f'leaq -{extra}(%rsp),%rsp',f'.cfi_adjust_cfa_offset {extra}']
  out+=['pushfq','.cfi_adjust_cfa_offset 8']
  for i,r in enumerate(REGS):
   out += [f'pushq %{r}','.cfi_adjust_cfa_offset 8']
   if r not in inherited:out += [f'.cfi_offset %{r},-{cfa+extra+16+8*i}']
  out+=['subq $256,%rsp','.cfi_adjust_cfa_offset 256']
  out += [f'movdqu %xmm{i},{i*16}(%rsp)' for i in range(16)]
  def dispatch(e):return ['movq %rsp,%rdi',f'movl ${e},%esi',f'leaq {384+extra}(%rsp),%rdx','call b8_dispatch']
  if name!='note':out+=dispatch(event)
  if call or name=='note':
   out += [f'movdqu {i*16}(%rsp),%xmm{i}' for i in range(16)]
   out += [f'movq {376-8*(i+1)}(%rsp),%{r}' for i,r in enumerate(REGS)]
   out += ['pushq 376(%rsp)','.cfi_adjust_cfa_offset 8','popfq','.cfi_adjust_cfa_offset -8']
   if call:out += ['pushq 408(%rsp)','.cfi_adjust_cfa_offset 8','pushq 408(%rsp)','.cfi_adjust_cfa_offset 8',
                  'call b8_original_open','leaq 16(%rsp),%rsp','.cfi_adjust_cfa_offset -16']
   else:out += ['movq 0x18(%rbp),%rdi','call b8_original_resampler_reset']
   out += [f'movq %{r},{376-8*(i+1)}(%rsp)' for i,r in enumerate(REGS[:9])]
   out += ['pushfq','.cfi_adjust_cfa_offset 8','popq %r11','.cfi_adjust_cfa_offset -8','movq %r11,376(%rsp)']
   out += [f'movdqu %xmm{i},{i*16}(%rsp)' for i in range(16)]
   out+=dispatch(event|128 if call else event)
  out += [f'movdqu {i*16}(%rsp),%xmm{i}' for i in range(16)]
  out += ['leaq 256(%rsp),%rsp','.cfi_adjust_cfa_offset -256']
  for r in reversed(REGS):
   out += [f'popq %{r}']
   if r not in inherited:out += [f'.cfi_restore %{r}']
   out += ['.cfi_adjust_cfa_offset -8']
  out += ['popfq','.cfi_adjust_cfa_offset -8']
  if extra:out += [f'leaq {extra}(%rsp),%rsp',f'.cfi_adjust_cfa_offset -{extra}']
  if call:out+=['retq']
  elif name=='prepare':out+=['movq 0x30(%r15),%rdi','movaps %xmm1,%xmm0','jmp b8_continue_prepare']
  elif name=='gate':out+=['movl %eax,0x94(%rdi)','jmp *-16(%rsp)']
  elif name=='reset':out+=['xorl %ebp,%ebp','pushq %rbx','.cfi_adjust_cfa_offset 8','.cfi_offset %rbx,-32','movq %rdi,%rbx','jmp b8_continue_reset']
  elif name=='note':out+=['movq 0x30(%rbp),%rdi','movq (%rdi),%rax','jmp *-16(%rsp)']
  else:out+=['movq 0x48(%rsp),%rcx','jmp b8_continue_return']
  out += ['.cfi_endproc',f'.size {label},.-{label}']
 return '\n'.join(out)+'\n'
def main():
 (ROOT/'b8_hooks.s').write_text(assembly())
 flags=['-target','x86_64-unknown-linux-gnu','-Os','-ffreestanding','-fno-builtin','-fno-stack-protector','-fPIC','-fvisibility=hidden','-mno-red-zone','-ffp-contract=off','-fasynchronous-unwind-tables','-fno-strict-aliasing']
 info=[]
 for n in ['b8_adapters','b8_hooks']:
  subprocess.run(['clang',*flags,'-c',str(ROOT/(n+('.s' if n.endswith('hooks') else '.c'))),'-o',str(ROOT/(n+'.o'))],check=True)
  raw,e,sec,symbols=object_info(ROOT/(n+'.o'))
  info.append({'object':n+'.o','sha256':sha(raw),'text_bytes':sec['.text']['size'],'constant_bytes':sum(s['size'] for k,s in sec.items() if k.startswith('.rodata')),'eh_frame_bytes':sec['.eh_frame']['size'],'symbols':symbols})
  for args,suffix in [(['-dr','--x86-asm-syntax=intel'],'.disassembly.txt'),(['--dwarf=frames'],'.cfi.txt')]:
   subprocess.run(['objdump',*args,str(ROOT/(n+'.o'))],stdout=(ROOT/(n+'.o'+suffix)).open('w'),check=True)
 m={'objects':info,'source_hashes':{n:sha((ROOT/n).read_bytes()) for n in ['b8_adapters.c','b8_hooks.s','emit_b8.py']},'base_sha256':BASE_SHA,'new_heap_bytes':1024}
 (ROOT/'b8_objects_manifest.json').write_text(json.dumps(m,indent=2)+'\n');print(json.dumps(info,indent=2))
if __name__=='__main__':main()
