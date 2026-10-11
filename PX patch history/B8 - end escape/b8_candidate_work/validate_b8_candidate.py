#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Independent installed B8 branch/ABI/unwind checks against inherited B5."""
import hashlib
import bisect,json,re,struct,subprocess,tempfile,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT.parent),str(ROOT.parent/'b5_candidate_work')]
from b5_elf_placement_check import ExactElf,decode_index,callback_lookup
from validate_b5_candidate import fde_rows,row_at
from emit_b8 import JUMPS,CALLS,ALLOCATIONS,BINDINGS

def validate(base,out,m,objects):
 old=ExactElf(base);e=ExactElf(out);checks=[];L=m['layout'];S=m['symbols']
 def ck(name,ok,detail=None):
  checks.append({'name':name,'passed':bool(ok),'detail':detail})
  if not ok:
   (ROOT/'b8_candidate_validation.failed.json').write_text(json.dumps({'checks':checks,'blocker':name},indent=2)+'\n')
   raise ValueError('B8 installed validation: '+name)
 ck('ELF identity/entry/PHDR count preserved', (e.type,e.machine,e.entry,e.phnum)==(old.type,old.machine,old.entry,old.phnum))
 ck('append reservations fit',L['code_bytes']<=0x2000 and L['frame_bytes_with_terminator']<=0x1000)
 ck('new RX within original disjoint RW mapping',e.phdr[2]['filesz']==e.phdr[2]['memsz']==L['rx_end'] and all((L['rx_end']+a-1)//a*a<=e.phdr[3]['va']//a*a for a in [4096,0x200000]))
 ck('unaltered PHDRs',all(e.phdr[i]==old.phdr[i] for i in [0,1,3,4,5,7]))
 ck('RX/EH attributes retained',all(e.phdr[2][k]==old.phdr[2][k] for k in ['type','flags','offset','va','pa','align']) and all(e.phdr[6][k]==old.phdr[6][k] for k in ['type','flags','align']))
 ck('LOAD size/alignment',all(p['filesz']<=p['memsz'] and p['offset']%p['align']==p['va']%p['align'] for p in e.phdr if p['type']==1))
 ck('existing section descriptors immutable except EH/shstr',e.shnum==old.shnum+2 and e.shstrndx==old.shstrndx and all(e.sections[i]==old.sections[i] for i in range(old.shnum) if i not in [old.shstrndx,old.section_names.index('.eh_frame_hdr')]))
 ck('new sections and unwind terminator',e.sections[-2][3:6]==(L['code_base'],L['code_base'],L['code_bytes']) and e.sections[-1][3:6]==(L['frame_base'],L['frame_base'],L['frame_bytes_with_terminator']) and e.read(L['frame_base']+L['frame_bytes'],4)==b'\0'*4)
 ck('metadata outside RX',e.shoff>=L['rx_end']+L['names_size'] and e.sections[e.shstrndx][4]==L['rx_end'])
 allowed={40:8,60:2,old.phoff+2*old.phentsize+32:16,old.phoff+6*old.phentsize+8:40}
 allowed.update({site:raw['size'] for _,site,raw,_,_ in JUMPS});allowed.update({site:5 for _,site,_,_ in CALLS});allowed.update({site:5 for site,_,_ in ALLOCATIONS})
 ck('exact explicit edit whitelist',{c['offset']:c['size'] for c in m['original_byte_whitelist']}==allowed)
 mask=set()
 for c in m['original_byte_whitelist']:
  p,n=c['offset'],c['size'];mask.update(range(p,p+n));ck('guard/final '+c['label'],hashlib.sha256(base[p:p+n]).hexdigest()==(c['old_sha256'] if 'old_sha256' in c else hashlib.sha256(bytes.fromhex(c['old'])).hexdigest()) and out[p:p+n].hex()==c['new'])
 changed={i for i,(a,b) in enumerate(zip(base,out)) if a!=b}
 ck('all other baseline bytes preserved',changed<=mask and len(out)>len(base))
 inherited=json.loads((ROOT.parent/'b5_candidate_work/b5_candidate_manifest.json').read_text())
 for h in inherited['hooks']:ck('inherited B5 hook '+h['name'],e.read(h['site'],h['size'])==old.read(h['site'],h['size']))
 for f in inherited['functions']:ck('inherited B5 helper '+f['name'],e.read(f['va'],f['size'])==old.read(f['va'],f['size']))
 ck('inherited B1 helper/hook/NOPs/FDE preserved',all(out[p:p+n]==base[p:p+n] for p,n in [(0x49fd0,0xbc),(0x1b49e,5),(0x1b7e5,5),(0x89c38,0x60)]))
 for h in m['hooks']:
  raw=e.read(h['site'],h['size']);ck('branch target '+h['name'],raw[0]==(0xe9 if h['kind']=='JMP' else 0xe8) and h['site']+5+struct.unpack_from('<i',raw,1)[0]==h['target'] and raw[5:]==b'\x90'*(h['size']-5))
  ck('continuation preserved '+h['name'],e.read(h['continuation'],8)==old.read(h['continuation'],8))
 ck('reader allocations aligned and extend B5 only',all(e.read(site,5)==bytes.fromhex(new) for site,_,new in ALLOCATIONS) and m['incremental_heap_bytes']==128*8==1024 and m['extra_heap_bytes']==18432)
 ck('real Client virtual binding',struct.unpack('<Q',e.read(S['b5_ram_vtable']+0x68,8))[0]==0x3cb50)
 decoded=[];dumps=[]
 with tempfile.TemporaryDirectory(prefix='b8-installed-') as tmp:
  p=Path(tmp)/'candidate.elf';p.write_bytes(out)
  for name,raw,obj,loc,tables in objects:
   i=obj.names.index('.text');a=loc[i];n=obj.sh[i][5]
   dump=subprocess.check_output(['objdump','-d','--x86-asm-syntax=intel',f'--start-address={a:#x}',f'--stop-address={a+n:#x}',str(p)],text=True);dumps.append(dump)
   for line in dump.splitlines():
    mat=re.match(r'\s*([0-9a-f]+):\s+((?:[0-9a-f]{2}\s+)+)(\w+)\s*(.*)',line)
    if mat:decoded.append((int(mat[1],16),bytes.fromhex(mat[2]),mat[3],mat[4].strip()))
 (ROOT/'b8_candidate.disassembly.txt').write_text('\n'.join(dumps))
 for r in m['relocations']:
  d=struct.unpack('<i',e.read(r['site'],4))[0];ck('rel32 '+hex(r['site']),r['type'] in [2,4] and d==r['target']+r['addend']-r['site'])
  if r['section']=='.text':
   inst=next((i for i in decoded if i[0]<=r['site'] and r['site']+4<=i[0]+len(i[1])),None)
   ck('instruction relocation '+hex(r['site']),inst is not None and inst[0]+len(inst[1])+d==r['target'] and (inst[2] in ['call','jmp'] or 'rip' in inst[3]))
  elif r['section'].startswith('.rodata'):
   obj=next(o for o in objects if o[0]==r['object']);loc=obj[3][obj[2].names.index(r['section'])]
   ck('switch table target '+hex(r['site']),any(i[0]==loc+d for i in decoded))
 for name,raw,obj,loc,tables in objects:
  for i,a in loc.items():
   sec=obj.sh[i];expected=raw[sec[4]:sec[4]+sec[5]];actual=bytearray(e.read(a,sec[5]))
   for r in m['relocations']:
    if r['object']==name and r['section']==obj.names[i]:o=r['site']-a;actual[o:o+4]=expected[o:o+4]
   ck('object bytes '+name+':'+obj.names[i],actual==expected)
 for name,site,raw,cont,cfa in JUMPS:
  f=next(f for f in m['functions'] if f['name']=='b8_hook_'+name);ins=[i for i in decoded if f['va']<=i[0]<f['va']+f['size']];last=ins[-1]
  if name in ['gate','note']:
   ck('flags-preserving indirect continuation '+name,hashlib.sha256(last[1]).hexdigest()=='cb096fa36627fd5cd3c17a8e8bc512499bdad839f7685051105a7608bc32f6de')
  else:ck('direct continuation '+name,last[2]=='jmp' and last[0]+5+struct.unpack_from('<i',last[1],1)[0]==cont)
  if name=='prepare':replay=b''.join(i[1] for i in ins[-3:-1])
  elif name=='gate':replay=ins[-2][1]
  elif name=='reset':replay=b''.join(i[1] for i in ins[-4:-1])
  elif name=='return':replay=ins[-2][1]
  else:
   replay=None;ck('NoteOn resampler Reset call preserved',sum(i[2]=='call' and i[0]+5+struct.unpack_from('<i',i[1],1)[0]==BINDINGS['b8_original_resampler_reset'] for i in ins)==1)
   ck('NoteOn scheduler loads replayed',hashlib.sha256(b''.join(i[1] for i in ins[-3:-1])).hexdigest()=='0ae783f1fbea99e134aa4bdbf3f1422dce3c6be80cd27d065beba76d735ce542')
  if replay is not None:ck('displaced replay '+name,hashlib.sha256(replay).hexdigest()==raw['sha256'])
 for name,site,target,event in CALLS:
  f=next(f for f in m['functions'] if f['name']=='b8_wrap_'+name);ins=[i for i in decoded if f['va']<=i[0]<f['va']+f['size']]
  ck('Open three calls and RET',ins[-1][1]==b'\xc3' and sum(i[2]=='call' for i in ins)==3)
 oldeh=old.phdr[6];oldptr,oldpairs=decode_index(old.read(oldeh['va'],oldeh['filesz']),oldeh['va']);eh=e.phdr[6];ptr,pairs=decode_index(e.read(eh['va'],eh['filesz']),eh['va']);oldset=set(oldpairs)
 ck('all 863 inherited unwind targets retained',len(oldpairs)==863 and oldset<=set(pairs) and ptr==oldptr)
 ck('870 unique sorted targets',len(pairs)==len(set(pairs))==870 and all(pairs[i][0]<pairs[i+1][0] for i in range(len(pairs)-1)))
 ck('section/PHDR/index agree',e.sections[e.section_names.index('.eh_frame_hdr')][3:6]==(eh['va'],eh['offset'],eh['filesz']) and eh['memsz']==eh['filesz']==12+8*870)
 funcs={f['va']:f for f in m['functions']};newpairs=[p for p in pairs if p not in oldset];ranges={};rows={}
 ck('7 new functions/FDEs',len(newpairs)==len(funcs)==7 and {p for p,_ in newpairs}==set(funcs))
 for pc,fde in pairs:
  rec=e.fde(fde);ranges[fde]=(rec['pc'],rec['range']);ck('FDE PC '+hex(pc),rec['pc']==pc)
  if (pc,fde) in oldset:ck('immutable inherited FDE '+hex(fde),e.read(fde,rec['length']+4)==old.read(fde,rec['length']+4))
  else:
   ck('new FDE extent/CIE '+hex(pc),rec['range']==funcs[pc]['size'] and rec['cie']['encoding']==0x1b and rec['cie']['return_register']==16 and rec['cie']['code_align']==1 and rec['cie']['data_align']==-8)
   rows[pc]=fde_rows(e,fde);ck('new rows in extent '+hex(pc),all(pc<=p<=pc+rec['range'] for p,row in rows[pc]))
 oldstarts=[p for p,_ in oldpairs]
 for name,site,raw,cont,cfa in JUMPS:
  fde=oldpairs[bisect.bisect_right(oldstarts,site)-1][1];a=row_at(fde_rows(old,fde),site);n=row_at(rows[S['b8_hook_'+name]],S['b8_hook_'+name]);ck('inherited hook CFI '+name,a['cfa']==n['cfa'] and all(a['rules'].get(r)==n['rules'].get(r) for r in [3,6,12,13,14,15,16]),{'old':a,'new':n})
 regs={'rax':0,'rdx':1,'rcx':2,'rbx':3,'rsi':4,'rdi':5,'rbp':6,'r8':8,'r9':9,'r10':10,'r11':11,'r12':12,'r13':13,'r14':14,'r15':15};aligned=0;inschecks=0;maxdelta=0
 for f in m['functions']:
  if f['name']=='b8_dispatch':continue
  call=f['name']=='b8_wrap_open';initial=8 if call else next(h[4] for h in JUMPS if f['name']=='b8_hook_'+h[0]);delta=0;rs=rows[f['va']];initialrow=row_at(rs,f['va']);rules=dict(initialrow['rules']);inheritedregs=set(rules)-{16}
  for pc,raw,op,arg in [i for i in decoded if f['va']<=i[0]<f['va']+f['size']]:
   row=row_at(rs,pc);ck('CFA at '+hex(pc),row['cfa']==(7,initial-delta) and row['rules'].get(16)==('offset',-8));inschecks+=1
   ck('callee rules at '+hex(pc),all(row['rules'].get(r)==rules.get(r) for r in [3,6,12,13,14,15]))
   if op=='call':ck('call alignment '+hex(pc),((initial%16)+delta)%16==0);aligned+=1
   if op in ['push','pushfq']:
    delta-=8
    if op=='push' and arg in regs and regs[arg] not in inheritedregs:rules[regs[arg]]=('offset',delta-initial)
    if f['name']=='b8_hook_reset' and op=='push' and arg=='rbx':rules[3]=('offset',delta-initial)
   elif op in ['pop','popfq']:
    if op=='pop' and arg in regs and regs[arg] not in inheritedregs:
     if regs[arg] in initialrow['rules']:rules[regs[arg]]=initialrow['rules'][regs[arg]]
     else:rules.pop(regs[arg],None)
    delta+=8
   elif op=='sub' and arg.startswith('rsp,'):delta-=int(arg.split(',')[1],0)
   elif op=='lea' and arg.startswith('rsp,'):
    match=re.search(r'([+-]) (0x[0-9a-f]+|\d+)',arg);ck('recognized stack LEA '+hex(pc),match is not None);delta+=(1 if match[1]=='+' else -1)*int(match[2],0)
   maxdelta=max(maxdelta,-delta)
  ck('balanced exit stack '+f['name'],delta==(-8 if f['name']=='b8_hook_reset' else 0))
 lookups=0
 for bias in [0,0x100000,0x7f3000000000]:
  for pc,fde in pairs:ck('index lookup '+hex(pc)+'/'+hex(bias),callback_lookup(pairs,ranges,bias+pc,e.phdr,bias)==bias+fde);lookups+=1
  for pc,fde in newpairs:
   end=pc+ranges[fde][1];ck('new range end '+hex(pc)+'/'+hex(bias),callback_lookup(pairs,ranges,bias+end-1,e.phdr,bias)==bias+fde and callback_lookup(pairs,ranges,bias+end,e.phdr,bias)!=bias+fde);lookups+=2
 result={'scope':'Installed candidate structural/relocation/ABI/CFI/index validation, host execution separate','passed':len(checks),'changed_original_byte_count':len(changed),'new_fdes':7,'inherited_unwind_targets':863,'instruction_cfa_checks':inschecks,'aligned_call_sites':aligned,'index_lookup_checks':lookups,'maximum_capture_stack_bytes':maxdelta,'hardware_validated':False,'checks':checks}
 (ROOT/'b8_candidate_validation.json').write_text(json.dumps(result,indent=2)+'\n');(ROOT/'b8_candidate_cfi_rows.json').write_text(json.dumps(rows,indent=2)+'\n')
 return {k:v for k,v in result.items() if k!='checks'}
