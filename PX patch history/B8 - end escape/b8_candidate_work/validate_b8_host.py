#!/usr/bin/env python3
"""Execute emitted object bytes in a host fixture; no firmware ELF output."""
import json,struct,subprocess,re
from pathlib import Path
ROOT=Path(__file__).resolve().parent
import sys,time
sys.path[:0]=[str(ROOT),str(ROOT.parent/'b5_candidate_work'),str(ROOT.parent)]
from emit_b5_candidate import object_info,sha
from emit_b5_objects import BINDINGS as OLD_BINDINGS
from emit_b8 import BINDINGS as NEW_BINDINGS
BINDINGS=dict(OLD_BINDINGS);BINDINGS.update({k:v for k,v in NEW_BINDINGS.items() if k not in BINDINGS})

def resolve():
    payload=bytearray();objects=[];exports={};relocations=[]
    for n in ['b5_core.o','b5_adapters.o','b5_hooks.objects.o','b8_adapters.o','b8_hooks.o']:
        raw,e,_,_=object_info((ROOT.parent/'b5_candidate_work'/n) if n.startswith('b5_') else ROOT/n);loc={};tables={}
        for i,(name,s) in enumerate(zip(e.names,e.sh)):
            if name=='.text' or name.startswith('.rodata'):
                payload.extend(b'\0'*((-len(payload))%max(1,s[8])));loc[i]=len(payload)
                payload.extend(raw[s[4]:s[4]+s[5]])
        for i,s in enumerate(e.sh):
            if s[1]!=2:continue
            st=e.sh[s[6]];strings=raw[st[4]:st[4]+st[5]];table=[]
            for p in range(s[4],s[4]+s[5],s[9]):
                no,info,other,ndx,val,size=struct.unpack_from('<IBBHQQ',raw,p)
                name=strings[no:strings.find(b'\0',no)].decode();table.append((name,ndx,val,size))
                if ndx in loc and info>>4:exports[name]=loc[ndx]+val
            tables[i]=table
        objects.append((n,raw,e,loc,tables))
    object_bytes=len(payload)
    # Host-only binding area is outside the measured object payload. Original
    # function substitutes jump through pointers relocated by the Mach-O linker.
    payload.extend(b'\0'*((-len(payload))%16));fixups=[]
    for name in BINDINGS:
        if name in exports:continue # inherited functions/return markers are real object definitions
        exports[name]=len(payload)
        if name=='b5_continue_prepare':
            payload.extend(bytes.fromhex('ff25020000009090')+b'\0'*8);fixups.append((exports[name],'_fixture_continue_prepare'))
        elif name.startswith('b8_continue_') or name in ['b8_note_skip','b8_zero']:
            payload.extend(bytes.fromhex('ff25020000009090')+b'\0'*8)
            target='_fixture_continue_'+name[len('b8_continue_'):] if name.startswith('b8_continue_') else {'b8_note_skip':'_fixture_note_skip','b8_zero':'_fixture_zero_gate'}[name]
            if name=='b8_continue_prepare':target='_fixture_prepare_route'
            fixups.append((exports[name],target))
        elif name.startswith(('b5_original_','b8_original_')):
            payload.extend(bytes.fromhex('ff25020000009090')+b'\0'*8)
            fixups.append((exports[name],'_fixture_'+name.split('_original_')[1]))
        elif name=='b5_ram_vtable':payload.extend(b'\0'*128)
        elif name=='b5_stack_guard_got':payload.extend(b'\0'*8)
        else:payload.extend(b'\xc3'+b'\x90'*15)
    for n,raw,e,loc,tables in objects:
        for s in e.sh:
            if s[1]!=4 or s[7] not in loc:continue
            for p in range(s[4],s[4]+s[5],s[9]):
                off,info,add=struct.unpack_from('<QQq',raw,p);typ=info&0xffffffff
                name,ndx,val,size=tables[s[6]][info>>32]
                assert typ in [2,4],(n,name,typ)
                target=loc[ndx]+val if ndx in loc else exports[name]
                at=loc[s[7]]+off;delta=target+add-at
                struct.pack_into('<i',payload,at,delta)
                relocations.append({'object':n,'offset':at,'symbol':name,'type':typ,'target':target})
    (ROOT/'b8_integration.host.bin').write_bytes(payload)
    asm=['.section __TEXT,__text,regular,pure_instructions','.p2align 4','.globl _b5_image','_b5_image:']
    last=0
    pieces=[(off,symbol,16) for off,symbol in fixups]+[(exports['b5_ram_vtable']+0x68,'_fixture_client_process',8)]
    for off,symbol,n in sorted(pieces):
        asm += [f'.incbin "{ROOT}/b8_integration.host.bin",{last},{off-last}']
        asm += [f'jmp {symbol}', '.space 11,0x90'] if n==16 else [f'.quad {symbol}']
        last=off+n
    asm += [f'.incbin "{ROOT}/b8_integration.host.bin",{last},{len(payload)-last}']
    (ROOT/'b8_integration.host.s').write_text('\n'.join(asm)+'\n')
    (ROOT/'b8_offsets.generated.h').write_text('\n'.join(f'#define OFF_{name} {offset}' for name,offset in exports.items())+'\n')
    (ROOT/'b8_wrapper_fixture.host.s').write_text((ROOT/'b8_wrapper_fixture.s').read_text().replace('OFF_MARKER',str(exports['b5_read_original_return'])).replace('OFF_PREPARE',str(exports['b5_hook_prepare'])))
    return object_bytes,relocations,sha(payload)

def main():
    size,rels,digest=resolve()
    exe=ROOT/'b8_integration_x86_tests'
    subprocess.run(['clang','-arch','x86_64','-O2','-fno-strict-aliasing','-Wl,-no_pie',str(ROOT/'b8_integration_tests.c'),str(ROOT/'b8_integration.host.s'),str(ROOT/'b8_wrapper_fixture.host.s'),'-o',str(exe)],check=True)
    run=subprocess.run([str(exe)],capture_output=True,text=True)
    names=['b5_core.o','b5_adapters.o','b5_hooks.objects.o','b8_adapters.o','b8_hooks.o']
    result={'scope':'Emitted ELF object machine code in non-PIE x86-64 Mach-O/Rosetta fixtures; actual B8 JMP shims/Open wrapper and inherited B5 adapters/Prepare/Read/Publish wrappers; stock QNX methods and continuations simulated','host_exit':run.returncode,'stdout':run.stdout,'stderr':run.stderr,'object_payload_bytes':size,'host_binding_payload_sha256':digest,'resolved_code_relocations':rels,'input_objects':{n:sha(((ROOT.parent/'b5_candidate_work'/n) if n.startswith('b5_') else ROOT/n).read_bytes()) for n in names},'test_sources':{n:sha((ROOT/n).read_bytes()) for n in ['b8_integration_tests.c','b8_wrapper_fixture.s','validate_b8_host.py']},'candidate_emitted':False,'pending':['installed QNX hook execution','QNX loader/runtime','target CPU cost','acoustics','legacy splice/ping-pong audio integration on target']}
    (ROOT/'b8_integration_validation.json').write_text(json.dumps(result,indent=2)+'\n')
    print(run.stdout,end='');print(run.stderr,end='')
    if run.returncode:raise SystemExit(run.returncode)
if __name__=='__main__':main()
