#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Validate installed B5 candidate bytes/CFI, without executing a QNX ELF."""
import hashlib
import bisect,json,re,struct,subprocess,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parent
from b5_elf_placement_check import ExactElf,decode_index,callback_lookup,leb,encoded
from emit_b5_candidate import ALLOCATIONS
from emit_b5_objects import JUMPS,CALLS,BINDINGS

# DWARF rows decoded from the final records, not a textual source assertion.
def cie_state(elf,address):
    data=elf.read(address,4+struct.unpack('<I',elf.read(address,4))[0]);v=data[8];z=data.index(0,9);aug=data[9:z].decode();p=z+1
    if v>=4:p+=2
    ca,p=leb(data,p);da,p=leb(data,p,True)
    if v==1:rr,p=data[p],p+1
    else:rr,p=leb(data,p)
    if aug.startswith('z'):n,p=leb(data,p);p+=n
    initial={'cfa':(7,8),'rules':{}}
    rows=interpret(data[p:],0,ca,da,initial,initial)
    return ca,da,rows[-1][1],aug

def interpret(data,pc,ca,da,initial,restore):
    state={'cfa':initial['cfa'],'rules':dict(initial['rules'])};rows=[(pc,{'cfa':state['cfa'],'rules':dict(state['rules'])})];p=0;saved=[]
    def snapshot():
        row=(pc,{'cfa':state['cfa'],'rules':dict(state['rules'])})
        if rows[-1][0]==pc:rows[-1]=row
        else:rows.append(row)
    while p<len(data):
        op=data[p];p+=1;primary=op&0xc0
        if primary==0x40:pc+=(op&63)*ca
        elif primary==0x80:n,p=leb(data,p);state['rules'][op&63]=('offset',n*da)
        elif primary==0xc0:
            reg=op&63
            if reg in restore['rules']:state['rules'][reg]=restore['rules'][reg]
            else:state['rules'].pop(reg,None)
        elif op==0:continue
        elif op in (2,3,4):
            fmt={2:'B',3:'H',4:'I'}[op];size=struct.calcsize(fmt);pc+=struct.unpack_from('<'+fmt,data,p)[0]*ca;p+=size
        elif op in (5,17):
            reg,p=leb(data,p);value,p=leb(data,p,op==17);state['rules'][reg]=('offset',value*da)
        elif op==6:
            reg,p=leb(data,p)
            if reg in restore['rules']:state['rules'][reg]=restore['rules'][reg]
            else:state['rules'].pop(reg,None)
        elif op in (7,8):reg,p=leb(data,p);state['rules'][reg]=('undefined' if op==7 else 'same',0)
        elif op==9:reg,p=leb(data,p);other,p=leb(data,p);state['rules'][reg]=('register',other)
        elif op==10:saved.append({'cfa':state['cfa'],'rules':dict(state['rules'])})
        elif op==11:state=saved.pop()
        elif op==12:reg,p=leb(data,p);off,p=leb(data,p);state['cfa']=(reg,off)
        elif op==13:reg,p=leb(data,p);state['cfa']=(reg,state['cfa'][1])
        elif op==14:off,p=leb(data,p);state['cfa']=(state['cfa'][0],off)
        elif op==0x2e:_,p=leb(data,p) # GNU_args_size changes no register rule
        else:raise ValueError('unsupported installed CFI opcode '+hex(op))
        snapshot()
    return rows

def fde_rows(elf,va):
    rec=elf.fde(va);data=elf.read(va,rec['length']+4);cie=rec['cie'];ca,da,initial,aug=cie_state(elf,cie['va'])
    _,p=encoded(data,8,cie['encoding'],va);_,p=encoded(data,p,cie['encoding']&15,va)
    if aug.startswith('z'):n,p=leb(data,p);p+=n
    return interpret(data[p:],rec['pc'],ca,da,initial,initial)

def row_at(rows,pc):return next(row for start,row in reversed(rows) if start<=pc)

def validate(base,out,m,objects):
    original=ExactElf(base);elf=ExactElf(out);checks=[]
    def check(name,condition,detail=None):
        checks.append({'name':name,'passed':bool(condition),'detail':detail})
        if not condition:
            (ROOT/'b5_candidate_validation.failed.json').write_text(json.dumps({'checks':checks,'blocker':name},indent=2)+'\n')
            raise ValueError('installed candidate validation: '+name)
    layout=m['layout'];symbols=m['symbols']
    check('PHDR count, entry, ELF type and machine preserved',elf.phnum==original.phnum==8 and elf.entry==original.entry and elf.type==original.type and elf.machine==original.machine)
    check('code and frames fit authorized reservations',layout['code_bytes']<=0x3000 and layout['frame_bytes_with_terminator']<=0x1000)
    check('measured sequential page-aligned append layout',layout['code_base']%4096==0 and layout['frame_base']==layout['code_base']+0x3000 and layout['index_base']==layout['frame_base']+0x1000 and layout['rx_end']==layout['index_base']+layout['index_reservation'])
    check('original program headers unchanged except RX sizes/EH location',all(elf.phdr[i]==original.phdr[i] for i in [0,1,3,4,5,7]) and all(elf.phdr[2][k]==original.phdr[2][k] for k in ['type','flags','offset','va','pa','align']) and all(elf.phdr[6][k]==original.phdr[6][k] for k in ['type','flags','align']))
    check('extended RX covers reservations and terminates before RW mapping',elf.phdr[2]['filesz']==elf.phdr[2]['memsz']==layout['rx_end'] and layout['rx_end']<elf.phdr[3]['va'])
    check('existing PT_LOAD alignment congruence retained',all(p['filesz']<=p['memsz'] and p['offset']%p['align']==p['va']%p['align'] for p in elf.phdr if p['type']==1))
    check('RX/RW page-rounded ranges remain disjoint',all((layout['rx_end']+a-1)//a*a<=elf.phdr[3]['va']//a*a for a in [4096,0x200000]))
    check('all original section indices/descriptors preserved except redirected tables',all(elf.sections[i]==original.sections[i] for i in range(original.shnum) if i not in [original.shstrndx,original.section_names.index('.eh_frame_hdr')]) and elf.shstrndx==original.shstrndx and elf.shnum==original.shnum+2)
    check('new code/frame sections describe actual payloads',elf.sections[-2][3:6]==(layout['code_base'],layout['code_base'],layout['code_bytes']) and elf.sections[-1][3:6]==(layout['frame_base'],layout['frame_base'],layout['frame_bytes_with_terminator']))
    check('new unwind terminator and section tables outside RX',elf.read(layout['frame_base']+layout['frame_bytes'],4)==b'\0'*4 and elf.sections[elf.shstrndx][4]==layout['rx_end'] and elf.shoff>=layout['rx_end']+layout['names_size'])
    # Explicit independent whitelist; no allowance for obsolete section-table or
    # payload mutation. Manifest must match these ranges exactly.
    whitelist={40:8,60:2,original.phoff+2*original.phentsize+32:16,original.phoff+6*original.phentsize+8:40}
    whitelist.update({h[1]:h[2]['size'] for h in JUMPS})
    whitelist.update({h[1]:5 for h in CALLS});whitelist.update({a[0]:5 for a in ALLOCATIONS})
    check('manifest edits exactly equal explicit B5 whitelist',{c['offset']:c['size'] for c in m['original_byte_whitelist']}==whitelist)
    allowed=set()
    for c in m['original_byte_whitelist']:
        at=c['offset'];n=c['size'];allowed.update(range(at,at+n))
        check('edit guard and final bytes: '+c['label'],hashlib.sha256(base[at:at+n]).hexdigest()==(c['old_sha256'] if 'old_sha256' in c else hashlib.sha256(bytes.fromhex(c['old'])).hexdigest()) and out[at:at+n].hex()==c['new'])
    changed=[i for i,(a,b) in enumerate(zip(base,out)) if a!=b]
    check('all changed original bytes lie in explicit whitelist',set(changed)<=allowed)
    check('original bytes not explicitly changed remain identical',all(base[i]==out[i] for i in range(len(base)) if i not in allowed))
    check('tested voice code/hook/metadata preserved',base[0x49fd0:0x4a08c]==out[0x49fd0:0x4a08c] and base[0x89c38:0x89c98]==out[0x89c38:0x89c98] and base[0x1b49e:0x1b4a3]==out[0x1b49e:0x1b4a3] and base[0x1b7e5:0x1b7ea]==out[0x1b7e5:0x1b7ea])
    for h in m['hooks']:
        raw=elf.read(h['site'],h['size']);destination=h['site']+5+struct.unpack_from('<i',raw,1)[0]
        check('installed branch target: '+h['name'],raw[0]==(0xe9 if h['kind']=='JMP' else 0xe8) and destination==h['target'] and raw[5:]==b'\x90'*(h['size']-5))
        check('continuation bytes preserved: '+h['name'],elf.read(h['continuation'],8)==original.read(h['continuation'],8))
    check('owned allocation immediates installed',all(elf.read(site,5)==bytes.fromhex(new) for site,old,new in ALLOCATIONS))
    check('target RAM vtable Client slot binding',struct.unpack('<Q',elf.read(BINDINGS['b5_ram_vtable']+0x68,8))[0]==0x3cb50)
    read_return=symbols['b5_read_original_return']
    check('Read ownership marker is actual original-call return',elf.read(read_return-5,1)==b'\xe8' and read_return+struct.unpack('<i',elf.read(read_return-4,4))[0]==BINDINGS['b5_original_read'])
    # Decode the installed text sections separately: constants between objects
    # must never desynchronize instruction decoding at the next text section.
    decoded=[];dumps=[]
    with tempfile.TemporaryDirectory(prefix='b5-installed-') as tmp:
        path=Path(tmp)/'candidate.elf';path.write_bytes(out)
        for name,raw,e,locations,tables in objects:
            i=e.names.index('.text');start=locations[i];size=e.sh[i][5]
            dump=subprocess.check_output(['objdump','-d','--x86-asm-syntax=intel',f'--start-address={start:#x}',f'--stop-address={start+size:#x}',str(path)],text=True)
            dumps.append(dump)
            for line in dump.splitlines():
                match=re.match(r'\s*([0-9a-f]+):\s+((?:[0-9a-f]{2}\s+)+)(\w+)\s*(.*)',line)
                if match:decoded.append((int(match[1],16),bytes.fromhex(match[2]),match[3],match[4].strip()))
    (ROOT/'b5_candidate.disassembly.txt').write_text('\n'.join(dumps))
    code_rel=[r for r in m['relocations'] if r['section']!='.eh_frame'];frame_rel=[r for r in m['relocations'] if r['section']=='.eh_frame']
    for r in m['relocations']:
        delta=struct.unpack('<i',elf.read(r['site'],4))[0]
        check('resolved relocation '+hex(r['site']),delta==r['target']+r['addend']-r['site'])
        if r['section']!='.eh_frame':
            inst=next((i for i in decoded if i[0]<=r['site'] and r['site']+4<=i[0]+len(i[1])),None)
            check('relocated displacement inside decoded instruction '+hex(r['site']),inst is not None)
            check('CPU-relative target equals bound symbol '+hex(r['site']),inst[0]+len(inst[1])+delta==r['target'] and (inst[2] in ['call','jmp','je'] or 'rip' in inst[3]))
    # Validate the actual replay and outgoing continuation instructions. The
    # expected displaced bytes come from the guarded tested-voice hook sites.
    for name,site,oldhex,cont,cfa in JUMPS:
        f=next(f for f in m['functions'] if f['name']=='b5_hook_'+name)
        instructions=[i for i in decoded if f['va']<=i[0]<f['va']+f['size']]
        last=instructions[-1]
        check('JMP final continuation instruction '+name,last[2]=='jmp' and last[1][0]==0xe9 and last[0]+5+struct.unpack_from('<i',last[1],1)[0]==cont)
        original_bytes=guarded(original.read,site,oldhex)
        if name in ['forward','reverse','prepare','note_on','eof']:
            replay=b''.join(i[1] for i in instructions[-3:-1])
            check('displaced instruction replay '+name,replay==original_bytes)
        elif name=='reset':
            check('displaced instruction replay reset',b''.join(i[1] for i in instructions[-4:-1])==original_bytes)
        elif name=='geometry':
            cmp_,branch=instructions[-3:-1]
            check('geometry displaced CMP/JE and taken continuation',cmp_[1]==original_bytes[:3] and branch[1][:2]==b'\x0f\x84' and branch[0]+6+struct.unpack_from('<i',branch[1],2)[0]==BINDINGS['b5_geometry_default'])
        elif name=='return':
            mov=instructions[-2]
            check('return displaced GOT load',mov[1][:3]==original_bytes[:3] and mov[0]+7+struct.unpack_from('<i',mov[1],3)[0]==BINDINGS['b5_stack_guard_got'])
    for name,site,target,event in CALLS:
        f=next(f for f in m['functions'] if f['name']=='b5_wrap_'+name)
        instructions=[i for i in decoded if f['va']<=i[0]<f['va']+f['size']]
        check('CALL wrapper returns to installed continuation '+name,instructions[-1][1]==b'\xc3' and sum(i[2]=='call' for i in instructions)==3)
    check('owned allocations exactly cover all slots and reader extensions',0xc00+64*256==0x4c00 and 0x1b8+8==0x1c0 and m['extra_heap_bytes']==64*256+128*8)
    # Prove object code/constants/CFI are byte-identical except listed resolved
    # fields. Accept previous host oracle/integration results for these objects.
    for name,raw,e,locations,tables in objects:
        for i,location in locations.items():
            section=e.sh[i];actual=bytearray(elf.read(location,section[5]));expected=raw[section[4]:section[4]+section[5]]
            for r in m['relocations']:
                if r['object']==name and r['section']==e.names[i]:actual[r['site']-location:r['site']-location+4]=expected[r['site']-location:r['site']-location+4]
            check('installed bytes preserve tested object section '+name+':'+e.names[i],bytes(actual)==expected)
    oldeh=original.phdr[6];oldpointer,oldpairs=decode_index(original.read(oldeh['va'],oldeh['filesz']),oldeh['va'])
    eh=elf.phdr[6];pointer,pairs=decode_index(elf.read(eh['va'],eh['filesz']),eh['va'])
    check('863-entry index preserves all 839 absolute original pairs',len(pairs)==863 and set(oldpairs)<=set(pairs) and len(set(pairs))==863 and all(pairs[i][0]<pairs[i+1][0] for i in range(862)))
    check('original EH frame pointer preserved',pointer==oldpointer)
    check('section/program header agree on active unwind index',elf.sections[elf.section_names.index('.eh_frame_hdr')][3:6]==(eh['va'],eh['offset'],eh['filesz']) and eh['filesz']==eh['memsz']==6916)
    functions={f['va']:f for f in m['functions']};newpairs=[p for p in pairs if p not in set(oldpairs)];ranges={}
    check('24 new FDEs cover every emitted function exactly once',len(newpairs)==len(functions)==24 and set(pc for pc,fde in newpairs)==set(functions))
    cfi_rows={};record_report=[]
    for pc,fde in pairs:
        record=elf.fde(fde);ranges[fde]=(record['pc'],record['range'])
        check('indexed FDE start matches indexed PC '+hex(pc),record['pc']==pc)
        if (pc,fde) in oldpairs:
            check('original FDE bytes immutable '+hex(fde),elf.read(fde,record['length']+4)==original.read(fde,record['length']+4))
        else:
            check('new FDE range and CIE match emitted function '+hex(pc),record['range']==functions[pc]['size'] and record['cie']['encoding']==0x1b and record['cie']['return_register']==16 and record['cie']['code_align']==1 and record['cie']['data_align']==-8)
            rows=fde_rows(elf,fde);cfi_rows[pc]=rows
            check('new CFI rows remain within actual function '+hex(pc),all(pc<=p<=pc+record['range'] for p,row in rows))
            record_report.append({'function':functions[pc]['name'],'pc':pc,'size':record['range'],'fde':fde,'cie':record['cie']['va'],'rows':rows})
    # The installed JMP starts must inherit the original caller's actual CFI.
    old_starts=[p for p,_ in oldpairs]
    for name,site,old,cont,cfa in JUMPS:
        original_fde=oldpairs[bisect.bisect_right(old_starts,site)-1][1]
        original_row=row_at(fde_rows(original,original_fde),site)
        newrow=row_at(cfi_rows[symbols['b5_hook_'+name]],symbols['b5_hook_'+name])
        regs=[3,6,12,13,14,15,16]
        check('JMP inherited CFI equals original hook-site CFI '+name,newrow['cfa']==original_row['cfa'] and all(newrow['rules'].get(reg)==original_row['rules'].get(reg) for reg in regs),{'original':original_row,'new':newrow})
    cfa_checks=aligned_calls=0;gpr_map={'rax':0,'rdx':1,'rcx':2,'rbx':3,'rsi':4,'rdi':5,'rbp':6,'r8':8,'r9':9,'r10':10,'r11':11,'r12':12,'r13':13,'r14':14,'r15':15}
    for f in m['functions']:
        name=f['name']
        if not name.startswith(('b5_hook_','b5_wrap_')):continue
        ordinary=name.startswith('b5_wrap_') or name=='b5_hook_reset';initial=8 if ordinary else next(h[4] for h in JUMPS if name=='b5_hook_'+h[0]);delta=0
        rows=cfi_rows[f['va']];initialrow=row_at(rows,f['va']);expectedrules=dict(initialrow['rules']);saved=[]
        for pc,bytes_,op,arg in [i for i in decoded if f['va']<=i[0]<f['va']+f['size']]:
            row=row_at(rows,pc)
            check('installed instruction/CFA '+hex(pc),row['cfa']==(7,initial-delta) and row['rules'].get(16)==('offset',-8));cfa_checks+=1
            # Callee saves are inherited in body JMP shims; at normal CALL/Reset
            # entry they come from these real pushes. Verify their offset rules.
            check('installed callee-register CFI '+hex(pc),all(row['rules'].get(r)==expectedrules.get(r) for r in [3,6,12,13,14,15]))
            if op=='call':check('installed call stack alignment '+hex(pc),((8 if ordinary else 0)+delta)%16==0);aligned_calls+=1
            if op in ['push','pushfq']:
                delta-=8
                if op=='push' and arg in gpr_map:
                    reg=gpr_map[arg]
                    if ordinary or (name=='b5_hook_reset'):expectedrules[reg]=('offset',delta-initial)
                    saved.append(reg)
            elif op in ['pop','popfq']:
                if op=='pop' and arg in gpr_map and ordinary:
                    reg=gpr_map[arg]
                    if reg in initialrow['rules']:expectedrules[reg]=initialrow['rules'][reg]
                    else:expectedrules.pop(reg,None)
                delta+=8
            elif op=='sub' and arg.startswith('rsp,'):delta-=int(arg.split(',')[1],0)
            elif op=='lea' and arg.startswith('rsp,'):delta+=int(re.search(r'\+ (0x[0-9a-f]+|\d+)',arg)[1],0)
        check('installed shim/wrapper balanced stack '+name,delta==(-16 if name=='b5_hook_reset' else 0))
    lookup_checks=0
    for bias in [0,0x100000,0x7f3000000000]:
        for pc,fde in pairs:
            check('combined index lookup '+hex(pc)+' bias '+hex(bias),callback_lookup(pairs,ranges,bias+pc,elf.phdr,bias)==bias+fde);lookup_checks+=1
        for pc,fde in newpairs:
            end=pc+ranges[fde][1]
            check('new final-byte/range lookup '+hex(pc),callback_lookup(pairs,ranges,bias+end-1,elf.phdr,bias)==bias+fde and callback_lookup(pairs,ranges,bias+end,elf.phdr,bias)!=bias+fde);lookup_checks+=2
    result={'scope':'Installed candidate structural/relocation/CFI/index checks; prior unchanged object host execution accepted','passed':len(checks),'changed_original_byte_count':len(changed),'code_relocations':len(code_rel),'frame_relocations':len(frame_rel),'new_fdes':len(newpairs),'instruction_cfa_checks':cfa_checks,'aligned_call_sites':aligned_calls,'combined_index_lookup_checks':lookup_checks,'all_original_unwind_targets_preserved':839,'target_loader_runtime_validated':False,'target_performance_validated':False,'acoustics_validated':False,'checks':checks}
    (ROOT/'b5_candidate_validation.json').write_text(json.dumps(result,indent=2)+'\n')
    (ROOT/'b5_candidate_cfi_rows.json').write_text(json.dumps(record_report,indent=2)+'\n')
    return {k:v for k,v in result.items() if k!='checks'}

def guarded(read, address, guard):
    data=read(address,guard['size'])
    if len(data)!=guard['size'] or hashlib.sha256(data).hexdigest()!=guard['sha256']:
        raise ValueError(f'Original-byte SHA-256 guard failed at {address:#x}')
    return data

