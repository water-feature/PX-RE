#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Emit standalone objects only. No ELF writer and no reservation stop."""
import re,json,subprocess
from pathlib import Path
from emit_b5_candidate import object_info,sha,HOOKS,ALLOCATIONS,FADE_DURATION_MS,fade_intervals,prediction_horizon
ROOT=Path(__file__).resolve().parent
REGS=['rax','rcx','rdx','rsi','rdi','r8','r9','r10','r11','rbx','rbp','r12','r13','r14','r15']
INHERITED={'rbx':-56,'rbp':-48,'r12':-40,'r13':-32,'r14':-24,'r15':-16}
JUMPS=HOOKS+[('eof',0x40060,{'size': 7, 'sha256': '083d481d167567303eb1b342a5b0f715280710ac77d53a5aaec8849fea711d77'},0x40067,176)]
CALLS=[('read',0x3cc81,0x3f840,8),('load',0x37363,0x2e2e0,9),('filter',0x37446,0x36b20,10),('publish',0x3cd69,0x417f0,11)]
BINDINGS={'b5_ram_vtable':0x29e4e8,'b5_stack_guard_got':0x29ffa8,'b5_geometry_default':0x40c40}
BINDINGS.update({'b5_continue_'+n:c for n,_,_,c,_ in JUMPS})
BINDINGS.update({'b5_original_'+n:t for n,_,t,_ in CALLS})
def assembly():
    out=['.text']
    for name,cfa,event,call in [(n,c,i,False) for i,(n,_,_,_,c) in enumerate(JUMPS)]+[(n,8,e,True) for n,_,_,e in CALLS]:
        label='b5_wrap_'+name if call else 'b5_hook_'+name
        dummy=call or name=='reset';extra=8 if dummy else 0
        out+=['.p2align 4',f'.globl {label}',f'.hidden {label}',f'.type {label},@function',label+':','.cfi_startproc',f'.cfi_def_cfa %rsp,{cfa}','.cfi_offset %rip,-8']
        if not dummy:
            out += [f'.cfi_offset %{r},{o}' for r,o in INHERITED.items()]
        if dummy:out+=['pushq $0','.cfi_adjust_cfa_offset 8']
        out+=['pushfq','.cfi_adjust_cfa_offset 8']
        for i,r in enumerate(REGS):
            out += [f'pushq %{r}','.cfi_adjust_cfa_offset 8']
            if dummy or r not in INHERITED:out += [f'.cfi_offset %{r},-{cfa+extra+16+8*i}']
        out+=['subq $256,%rsp','.cfi_adjust_cfa_offset 256']
        out += [f'movdqu %xmm{i},{i*16}(%rsp)' for i in range(16)]
        def dispatch(e):return ['movq %rsp,%rdi',f'movl ${e},%esi',f'leaq {384+extra}(%rsp),%rdx','call b5_dispatch']
        out+=dispatch(event)
        if call:
            out += [f'movdqu {i*16}(%rsp),%xmm{i}' for i in range(16)]
            out += [f'movq {376-8*(i+1)}(%rsp),%{r}' for i,r in enumerate(REGS)]
            out += ['pushq 376(%rsp)','.cfi_adjust_cfa_offset 8','popfq','.cfi_adjust_cfa_offset -8',f'call b5_original_{name}']
            if name=='read':out += ['.globl b5_read_original_return','.hidden b5_read_original_return','b5_read_original_return:']
            out += [f'movq %{r},{376-8*(i+1)}(%rsp)' for i,r in enumerate(REGS[:9])]
            out += ['pushfq','.cfi_adjust_cfa_offset 8','popq %r11','.cfi_adjust_cfa_offset -8','movq %r11,376(%rsp)']
            out += [f'movdqu %xmm{i},{i*16}(%rsp)' for i in range(16)]
            out+=dispatch(event|128)
        out += [f'movdqu {i*16}(%rsp),%xmm{i}' for i in range(16)]
        out += ['leaq 256(%rsp),%rsp','.cfi_adjust_cfa_offset -256']
        for r in reversed(REGS):
            out += [f'popq %{r}']
            if dummy or r not in INHERITED:out += [f'.cfi_restore %{r}']
            out += ['.cfi_adjust_cfa_offset -8']
        out += ['popfq','.cfi_adjust_cfa_offset -8']
        if dummy:out += ['leaq 8(%rsp),%rsp','.cfi_adjust_cfa_offset -8']
        if call:out+=['retq']
        else:
            if name in ('forward','reverse'):out+=['cmpb $0,0x20(%rsp)','movzbl 0x3c(%rsp),%r11d']
            elif name=='geometry':out+=['cmpl $-1,%edx','je b5_geometry_default']
            elif name=='prepare':out+=['movq (%rdi),%rax','call *0x68(%rax)']
            elif name=='note_on':out+=['movq 0x30(%rbp),%rdi','movq (%rdi),%rax']
            elif name=='return':out+=['movq b5_stack_guard_got(%rip),%rbx']
            elif name=='eof':out+=['movq (%rsp),%rax','testq %rax,%rax']
            elif name=='reset':out+=['pushq %r12','.cfi_adjust_cfa_offset 8','.cfi_offset %r12,-16','xorl %r12d,%r12d','pushq %rbp','.cfi_adjust_cfa_offset 8','.cfi_offset %rbp,-24']
            out += [f'jmp b5_continue_{name}']
        out += ['.cfi_endproc',f'.size {label},.-{label}']
    return '\n'.join(out)+'\n'
def main():
    (ROOT/'b5_policy.generated.h').write_text(f'/* Generated from shared Python policy, {FADE_DURATION_MS:g} ms. */\n#define B5_FADE_INTERVALS {fade_intervals()}\n#define B5_PREDICTION_HORIZON {prediction_horizon()}\n')
    src=(ROOT/'b5_core.c').read_text()
    types=src[src.index('typedef unsigned int'):src.index('#define EXPORT')]
    prototypes='\n'.join(m.replace('EXPORT ','')+';' for m in re.findall(r'^EXPORT [^{]+(?= \{)',src,re.M))
    (ROOT/'b5_core.generated.h').write_text('#pragma once\n'+types+prototypes+'\n')
    (ROOT/'b5_hooks.objects.s').write_text(assembly())
    flags=['-target','x86_64-unknown-linux-gnu','-Os','-ffreestanding','-fno-builtin','-fno-stack-protector','-fPIC','-fvisibility=hidden','-mno-red-zone','-ffp-contract=off','-fasynchronous-unwind-tables','-fno-strict-aliasing']
    names=['b5_core','b5_adapters','b5_hooks.objects'];info=[];code=frames=0
    for n in names:
        subprocess.run(['clang',*(flags[:2] if n.endswith('objects') else flags),'-c',str(ROOT/(n+('.s' if n.endswith('objects') else '.c'))),'-o',str(ROOT/(n+'.o'))],check=True)
        raw,e,sections,symbols=object_info(ROOT/(n+'.o'))
        for sn,s in zip(e.names,e.sh):
            if sn=='.text' or sn.startswith('.rodata'):
                code+=(-code)%max(1,s[8]);code+=s[5]
        frames+=(-frames)%8+sections['.eh_frame']['size']
        for args,suffix in [(['-dr','--x86-asm-syntax=intel'],'disassembly'),(['--dwarf=frames'],'cfi')]:
            subprocess.run(['objdump',*args,str(ROOT/(n+'.o'))],stdout=(ROOT/(n+'.o.'+suffix+'.txt')).open('w'),check=True)
        cfi=(ROOT/(n+'.o.cfi.txt')).read_text()
        info.append({'object':n+'.o','sha256':sha(raw),'text':sections['.text']['size'],'constants':sum(s[5] for sn,s in zip(e.names,e.sh) if sn.startswith('.rodata')),'eh_frame':sections['.eh_frame']['size'],'fde_count':len(re.findall(r' FDE ',cfi)),'functions':symbols})
    manifest={'status':'standalone_objects_uninstalled','code_and_constants_aligned':code,'eh_frame_aligned':frames,'objects':info,'bindings':{k:hex(v) for k,v in BINDINGS.items()},'policy':{'shared_source':'../b5_fade_prototype.py:FADE_DURATION_MS','duration_ms':FADE_DURATION_MS,'intervals':fade_intervals(),'horizon':prediction_horizon()},'state_per_stream':256,'core_fields':176,'bridge':80,'extra_heap_bytes':17408,'old_reservations_not_stopping_emission':True,'placement_changed':False,'candidate_emitted':False,'source_hashes':{n:sha((ROOT/n).read_bytes()) for n in ['b5_core.c','b5_adapters.c','b5_core.generated.h','b5_policy.generated.h','b5_hooks.objects.s']}}
    (ROOT/'b5_objects_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps({k:v for k,v in manifest.items() if k not in ['objects','bindings','source_hashes']},indent=2))
if __name__=='__main__':main()
