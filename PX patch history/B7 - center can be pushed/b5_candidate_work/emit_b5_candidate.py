#!/usr/bin/env python3
"""Stage B5 machine code/CFI; stop at reservations or unestablished adapters.

Never edits its input or packages firmware. A stopped stage emits only partial
objects/payloads and a manifest, not a misleading complete ELF candidate.
"""
import hashlib
import json
import struct
import subprocess
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT.parent))
from b5_fade_prototype import FADE_DURATION_MS,fade_intervals,prediction_horizon
from b5_elf_placement_check import ELF_HASH,ExactElf,decode_index
from patch_b4_minimal_qnx import Elf

HOOKS=[
 ('forward',0x405bd,'807c242000440fb65c243c',0x405c8,176),
 ('reverse',0x40474,'807c242000440fb65c243c',0x4047f,176),
 ('geometry',0x3fbe9,'83faff0f844e100000',0x3fbf2,176),
 ('prepare',0x372e5,'488b07ff5068',0x372eb,144),
 ('note_on',0x36448,'488b7d30488b07',0x3644f,64),
 ('reset',0x3c8f0,'41544531e455',0x3c8f6,8),
 ('return',0x37496,'488b1d0b8b2600',0x3749d,144),
]
CALL_HOOKS=[('read',0x3cc81,0x3f840,64),('load',0x37363,0x2e2e0,144),('filter',0x37446,0x36b20,144)]
ALLOCATIONS=[(0x3d010,'bf000c0000','bf004c0000'),(0x3d0fc,'bfb8010000','bfc0010000'),(0x3d11a,'bfb8010000','bfc0010000')]
VOLATILE=['rax','rcx','rdx','rsi','rdi','r8','r9','r10','r11']
def sha(b): return hashlib.sha256(b).hexdigest()
def shims():
    lines=['.text']
    for number,(name,site,old,cont,cfa) in enumerate(HOOKS):
        label='b5_hook_'+name
        lines+=['.p2align 4',f'.globl {label}',f'.hidden {label}',f'.type {label},@function',label+':','.cfi_startproc',f'.cfi_def_cfa %rsp,{cfa}','.cfi_offset %rip,-8']
        if name!='reset':
            for reg,offset in [('rbx',-56),('rbp',-48),('r12',-40),('r13',-32),('r14',-24),('r15',-16)]:
                lines.append(f'.cfi_offset %{reg},{offset}')
        lines+=['pushfq','.cfi_adjust_cfa_offset 8']
        for i,reg in enumerate(VOLATILE):
            lines += [f'pushq %{reg}','.cfi_adjust_cfa_offset 8',f'.cfi_offset %{reg},-{cfa+16+i*8}']
        allocation=264 if name=='reset' else 256
        lines += [f'subq ${allocation},%rsp',f'.cfi_adjust_cfa_offset {allocation}']
        for i in range(16): lines.append(f'movdqu %xmm{i},{i*16}(%rsp)')
        lines += ['movq %rsp,%rdi',f'movl ${number},%esi','call b5_dispatch']
        for i in range(16): lines.append(f'movdqu {i*16}(%rsp),%xmm{i}')
        lines += [f'addq ${allocation},%rsp',f'.cfi_adjust_cfa_offset -{allocation}']
        for reg in reversed(VOLATILE): lines += [f'popq %{reg}',f'.cfi_same_value %{reg}','.cfi_adjust_cfa_offset -8']
        lines += ['popfq','.cfi_adjust_cfa_offset -8']
        if name in ['forward','reverse']:
            lines+=['cmpb $0,0x20(%rsp)','movzbl 0x3c(%rsp),%r11d']
        elif name=='geometry': lines+=['cmpl $-1,%edx','je b5_geometry_default']
        elif name=='prepare': lines+=['movq (%rdi),%rax','call *0x68(%rax)']
        elif name=='note_on': lines+=['movq 0x30(%rbp),%rdi','movq (%rdi),%rax']
        elif name=='return': lines+=['movq b5_stack_guard_got(%rip),%rbx']
        else:
            lines+=['pushq %r12','.cfi_adjust_cfa_offset 8','.cfi_offset %r12,-16','xorl %r12d,%r12d','pushq %rbp','.cfi_adjust_cfa_offset 8','.cfi_offset %rbp,-24']
        lines += [f'jmp b5_continue_{name}','.cfi_endproc',f'.size {label},.-{label}']
    return '\n'.join(lines)+'\n'

def object_info(path):
    raw=path.read_bytes();e=Elf(raw)
    sections={name:{'offset':s[4],'size':s[5],'align':s[8]} for name,s in zip(e.names,e.sh)}
    symbols=[]
    for s in e.sh:
        if s[1]!=2: continue
        ss=e.sh[s[6]];strings=raw[ss[4]:ss[4]+ss[5]]
        for o in range(s[4],s[4]+s[5],s[9]):
            no,info,other,ndx,val,size=struct.unpack_from('<IBBHQQ',raw,o)
            name=strings[no:strings.find(b'\0',no)].decode()
            if name and (info&15)==2: symbols.append({'name':name,'section':e.names[ndx] if ndx<len(e.names) else ndx,'offset':val,'size':size})
    return raw,e,sections,symbols

def main():
    base_path=ROOT.parent/'voice_2.2.2.0.2_qnx.elf'
    base=base_path.read_bytes()
    if sha(base)!=ELF_HASH: raise ValueError('tested voice ELF identity mismatch')
    elf=ExactElf(base)
    guards=[]
    for name,site,old,cont,cfa in HOOKS:
        expected=bytes.fromhex(old)
        actual=elf.read(site,len(expected))
        guards.append({'name':name,'site':hex(site),'expected':old,'actual':actual.hex(),'matches':actual==expected,'continuation':hex(cont),'inherited_cfa':cfa})
    for name,site,target,cfa in CALL_HOOKS:
        actual=elf.read(site,5)
        expected=b'\xe8'+struct.pack('<i',target-site-5)
        guards.append({'name':name,'site':hex(site),'expected':expected.hex(),'actual':actual.hex(),'matches':actual==expected,'target':hex(target),'inherited_cfa':cfa})
    for site,old,new in ALLOCATIONS:
        guards.append({'name':'owned allocation','site':hex(site),'expected':old,'actual':elf.read(site,5).hex(),'matches':elf.read(site,5)==bytes.fromhex(old),'proposed':new})
    if not all(g['matches'] for g in guards):
        (ROOT/'guard_failure.json').write_text(json.dumps(guards,indent=2)+'\n')
        raise ValueError('hook byte guard failed; saved actual bytes, do not change guards blindly')
    (ROOT/'b5_policy.generated.h').write_text(f'/* Generated from shared Python policy, {FADE_DURATION_MS:g} ms. */\n#define B5_FADE_INTERVALS {fade_intervals()}\n#define B5_PREDICTION_HORIZON {prediction_horizon()}\n')
    (ROOT/'b5_hooks.partial.s').write_text(shims())
    flags=['-target','x86_64-unknown-linux-gnu','-Os','-ffreestanding','-fno-builtin','-fno-stack-protector','-fPIC','-fvisibility=hidden','-mno-red-zone','-ffp-contract=off','-fasynchronous-unwind-tables']
    subprocess.run(['clang',*flags,'-c',str(ROOT/'b5_core.c'),'-o',str(ROOT/'b5_core.o')],check=True)
    subprocess.run(['clang','-target','x86_64-unknown-linux-gnu','-c',str(ROOT/'b5_hooks.partial.s'),'-o',str(ROOT/'b5_hooks.partial.o')],check=True)
    info=[];total_code=total_frames=0
    for name in ['b5_core.o','b5_hooks.partial.o']:
        raw,e,sections,symbols=object_info(ROOT/name)
        text=sections['.text']['size'];frames=sections['.eh_frame']['size']
        constants=sum(s[5] for n,s in zip(e.names,e.sh) if n.startswith('.rodata'))
        for section_name,section in zip(e.names,e.sh):
            if section_name=='.text' or section_name.startswith('.rodata'):
                total_code+=(-total_code)%max(1,section[8])
                total_code+=section[5]
        total_frames+=(frames+7)//8*8
        subprocess.run(['objdump','-dr','--x86-asm-syntax=intel',str(ROOT/name)],stdout=(ROOT/(name+'.disassembly.txt')).open('w'),check=True)
        subprocess.run(['objdump','--dwarf=frames',str(ROOT/name)],stdout=(ROOT/(name+'.cfi.txt')).open('w'),check=True)
        info.append({'object':name,'sha256':sha(raw),'text_bytes':text,'constant_bytes':constants,'eh_frame_bytes':frames,'symbols':symbols})
    old_header=elf.read(0x91590,0x1a44)
    _,pairs=decode_index(old_header,0x91590)
    blockers=[]
    if total_code>0x1000: blockers.append(f'Partial emitted code/constants {total_code} bytes exceed fixed 4096-byte reservation, before target adapters and CALL wrappers.')
    if total_frames>0x400: blockers.append(f'Partial emitted unwind records {total_frames} bytes exceed fixed 1024-byte reservation, before target adapters and CALL wrappers.')
    blockers.append('Target b5_dispatch adapters and Read/Load/Filter CALL wrappers not emitted/installed; endpoint-bank hold/restore must respect next-block UpdateLoc and active/pending reader swap. Core API alone is not firmware integration.')
    manifest={'status':'blocked_partial_no_candidate','base':base_path.name,'base_sha256':sha(base),'base_length':len(base),'base_modified':False,
              'compiler':subprocess.check_output(['clang','--version'],text=True).splitlines()[0],'core_compile_flags':flags,
              'source_sha256':{n:sha((ROOT/n).read_bytes()) for n in ['b5_core.c','b5_policy.generated.h','b5_hooks.partial.s']},
              'policy':{'shared_source':'../b5_fade_prototype.py:FADE_DURATION_MS','duration_ms':FADE_DURATION_MS,'intervals':fade_intervals(),'horizon':prediction_horizon()},
              'layout':{'code':'0xf1000..0xf2000','frames':'0xf2000..0xf2400','index':'0xf2400..0xf4000'},
              'partial_code_and_constants_bytes':total_code,'partial_eh_frame_bytes':total_frames,
              'state_bytes_per_stream':256,'streams':64,'reader_extension_each':8,'extra_heap_bytes':64*256+128*8,
              'objects':info,'original_byte_guards':guards,'planned_original_byte_whitelist':{'hooks':[hex(h[1]) for h in HOOKS]+[hex(h[1]) for h in CALL_HOOKS],'allocation_immediates':[hex(x[0]) for x in ALLOCATIONS],'elf_header_fields':['e_shoff','e_shnum'],'program_header_fields':['RX p_filesz/p_memsz','PT_GNU_EH_FRAME offset/vaddr/paddr/filesz/memsz']},
              'applied_original_byte_changes':[],'original_unwind_targets_preserved':len(pairs),'candidate_emitted':False,
              'blockers':blockers,'pending':['QNX loader/runtime','target CPU performance','acoustic validation']}
    (ROOT/'b5_partial_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps({k:manifest[k] for k in ['status','partial_code_and_constants_bytes','partial_eh_frame_bytes','candidate_emitted','blockers']},indent=2))
if __name__=='__main__': main()
