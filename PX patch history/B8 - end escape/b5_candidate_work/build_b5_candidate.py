#!/usr/bin/env python3
"""Append/install the authorized B5 objects into a separate tested-voice ELF copy.
No container output, target execution, alternative layout or loader research.
"""
import argparse,hashlib,json,struct,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT.parent))
from b5_elf_placement_check import ExactElf,ELF_HASH,decode_index,encode_index
from emit_b5_candidate import object_info,ALLOCATIONS
from emit_b5_objects import JUMPS,CALLS,BINDINGS

def sha(data):return hashlib.sha256(data).hexdigest()
def align(n,a):return (n+a-1)//a*a

def object_layout(manifest,code_base,frame_base):
    objects=[];symbols=dict(BINDINGS);functions=[];code=bytearray();frames=bytearray();relocations=[]
    for item in manifest['objects']:
        path=ROOT/item['object'];raw,e,_,_=object_info(path)
        if sha(raw)!=item['sha256']:raise ValueError('object hash mismatch: '+path.name)
        locations={};tables={}
        for i,(name,s) in enumerate(zip(e.names,e.sh)):
            if name=='.text' or name.startswith('.rodata'):
                code.extend(b'\0'*(align(len(code),max(1,s[8]))-len(code)))
                locations[i]=code_base+len(code);code.extend(raw[s[4]:s[4]+s[5]])
            elif name=='.eh_frame':
                frames.extend(b'\0'*(align(len(frames),max(8,s[8]))-len(frames)))
                locations[i]=frame_base+len(frames);frames.extend(raw[s[4]:s[4]+s[5]])
            elif s[2]&2 and s[5]:raise ValueError('unexpected allocated object section '+name)
        for i,s in enumerate(e.sh):
            if s[1]!=2:continue
            strings_section=e.sh[s[6]];strings=raw[strings_section[4]:strings_section[4]+strings_section[5]];table=[]
            for p in range(s[4],s[4]+s[5],s[9]):
                no,info,other,ndx,val,size=struct.unpack_from('<IBBHQQ',raw,p)
                name=strings[no:strings.find(b'\0',no)].decode();table.append((name,ndx,val,size))
                if ndx in locations and info>>4:
                    if name in symbols:raise ValueError('duplicate binding '+name)
                    symbols[name]=locations[ndx]+val
                if ndx in locations and info&15==2 and size:
                    functions.append({'object':path.name,'name':name,'va':locations[ndx]+val,'size':size})
            tables[i]=table
        objects.append((path.name,raw,e,locations,tables))
    for name,raw,e,locations,tables in objects:
        for s in e.sh:
            if s[1]!=4:continue
            if s[7] not in locations:
                if s[5]:raise ValueError('relocation in unsupported section')
                continue
            for p in range(s[4],s[4]+s[5],s[9]):
                offset,info,add=struct.unpack_from('<QQq',raw,p);kind=info&0xffffffff
                symbol,ndx,value,_=tables[s[6]][info>>32]
                if kind not in (2,4):raise ValueError(f'unsupported relocation {kind}: {symbol}')
                if ndx in locations:target=locations[ndx]+value
                elif ndx==0 and symbol in symbols:target=symbols[symbol]
                else:raise ValueError('unresolved target binding '+symbol)
                site=locations[s[7]]+offset;delta=target+add-site
                if not -2**31<=delta<2**31:raise ValueError('rel32 overflow '+symbol)
                if e.names[s[7]]=='.eh_frame':blob,base=frames,frame_base
                else:blob,base=code,code_base
                struct.pack_into('<i',blob,site-base,delta)
                relocations.append({'object':name,'section':e.names[s[7]],'site':site,'type':kind,'symbol':symbol,'target':target,'addend':add,'value':delta})
    return code,frames,symbols,functions,relocations,objects

def frame_pairs(blob,base):
    pairs=[];at=0
    while at<len(blob):
        length=struct.unpack_from('<I',blob,at)[0]
        if not length:raise ValueError('early unwind terminator in concatenated objects')
        if length==0xffffffff or at+4+length>len(blob):raise ValueError('invalid unwind record extent')
        cie_delta=struct.unpack_from('<I',blob,at+4)[0]
        if cie_delta:
            pc=base+at+8+struct.unpack_from('<i',blob,at+8)[0]
            pairs.append((pc,base+at))
        at+=length+4
    return pairs

def build():
    base_path=ROOT.parent/'voice_2.2.2.0.2_qnx.elf';base=base_path.read_bytes()
    if sha(base)!=ELF_HASH:raise ValueError('exact tested voice ELF hash mismatch')
    original=ExactElf(base);objmanifest=json.loads((ROOT/'b5_objects_manifest.json').read_text())
    for n,digest in objmanifest['source_hashes'].items():
        if sha((ROOT/n).read_bytes())!=digest:raise ValueError('source checkpoint hash mismatch: '+n)
    code_base=align(len(base),0x1000);code_reservation=0x3000
    frame_base=align(code_base+code_reservation,0x1000);frame_reservation=0x1000
    index_base=align(frame_base+frame_reservation,0x1000)
    code,frames,symbols,functions,relocations,objects=object_layout(objmanifest,code_base,frame_base)
    if len(code)>code_reservation or len(frames)+4>frame_reservation:raise ValueError('authorized code/frame reservation exceeded')
    oldeh=next(p for p in original.phdr if p['type']==0x6474e550)
    frame_pointer,old_pairs=decode_index(original.read(oldeh['va'],oldeh['filesz']),oldeh['va'])
    if len(old_pairs)!=839:raise ValueError('original index count mismatch')
    new_pairs=frame_pairs(frames,frame_base)
    if len(new_pairs)!=24 or len(functions)!=24:raise ValueError('new frame/function count mismatch')
    index=encode_index(sorted(old_pairs+new_pairs),index_base,frame_pointer)
    index_reservation=align(len(index),0x1000);rx_end=index_base+index_reservation
    oldnames_section=original.sections[original.shstrndx]
    oldnames=base[oldnames_section[4]:oldnames_section[4]+oldnames_section[5]]
    names=oldnames+b'.b5.text\0.b5.eh_frame\0';names_offset=rx_end
    table_offset=align(names_offset+len(names),8)
    section_table=[list(s) for s in original.sections]
    section_table[original.section_names.index('.eh_frame_hdr')][3:6]=[index_base,index_base,len(index)]
    section_table[original.shstrndx][4:6]=[names_offset,len(names)]
    section_table += [[len(oldnames),1,6,code_base,code_base,len(code),0,0,16,0],
                      [len(oldnames)+len(b'.b5.text\0'),1,2,frame_base,frame_base,len(frames)+4,0,0,8,0]]
    out=bytearray(base);out.extend(b'\0'*(table_offset+len(section_table)*original.shentsize-len(out)))
    out[code_base:code_base+len(code)]=code;out[frame_base:frame_base+len(frames)]=frames
    out[index_base:index_base+len(index)]=index;out[names_offset:names_offset+len(names)]=names
    for i,s in enumerate(section_table):struct.pack_into('<IIQQQQIIQQ',out,table_offset+i*original.shentsize,*s)
    changes=[]
    def edit(offset,old,new,label):
        if base[offset:offset+len(old)]!=old:raise ValueError('original-byte guard failed: '+label)
        if len(old)!=len(new):raise ValueError('invalid in-place edit extent')
        out[offset:offset+len(new)]=new
        changes.append({'label':label,'offset':offset,'size':len(new),'old':old.hex(),'new':new.hex()})
    def va_offset(va,n):
        for p in original.phdr:
            if p['type']==1 and p['va']<=va and va+n<=p['va']+p['filesz']:return p['offset']+va-p['va']
        raise ValueError('unmapped edit '+hex(va))
    hooks=[]
    for name,site,oldhex,continuation,cfa in JUMPS:
        old=guarded(original.read,site,oldhex);target=symbols['b5_hook_'+name]
        new=b'\xe9'+struct.pack('<i',target-site-5)+b'\x90'*(len(old)-5)
        edit(va_offset(site,len(old)),old,new,'JMP '+name)
        hooks.append({'name':name,'kind':'JMP','site':site,'size':len(old),'target':target,'continuation':continuation,'cfa':cfa})
    for name,site,target,event in CALLS:
        old=b'\xe8'+struct.pack('<i',target-site-5);wrapper=symbols['b5_wrap_'+name]
        new=b'\xe8'+struct.pack('<i',wrapper-site-5)
        edit(va_offset(site,5),old,new,'CALL '+name)
        hooks.append({'name':name,'kind':'CALL','site':site,'size':5,'target':wrapper,'original_target':target,'continuation':site+5})
    for site,oldhex,newhex in ALLOCATIONS:edit(va_offset(site,5),guarded(original.read,site,oldhex),bytes.fromhex(newhex),'owned allocation '+hex(site))
    edit(40,struct.pack('<Q',original.shoff),struct.pack('<Q',table_offset),'ELF e_shoff')
    edit(60,struct.pack('<H',original.shnum),struct.pack('<H',len(section_table)),'ELF e_shnum')
    rx_idx=next(i for i,p in enumerate(original.phdr) if p['type']==1 and p['flags']==5 and p['offset']==0 and p['va']==0)
    rx=original.phdr[rx_idx];pos=original.phoff+rx_idx*original.phentsize
    edit(pos+32,struct.pack('<QQ',rx['filesz'],rx['memsz']),struct.pack('<QQ',rx_end,rx_end),'RX filesz/memsz')
    eh_idx=next(i for i,p in enumerate(original.phdr) if p['type']==0x6474e550);pos=original.phoff+eh_idx*original.phentsize
    edit(pos+8,struct.pack('<QQQQQ',oldeh['offset'],oldeh['va'],oldeh['pa'],oldeh['filesz'],oldeh['memsz']),struct.pack('<QQQQQ',index_base,index_base,index_base,len(index),len(index)),'PT_GNU_EH_FRAME location/size')
    manifest={'status':'relocated_candidate_pending_validation','base_file':base_path.name,'base_sha256':sha(base),'candidate_sha256':sha(out),'base_length':len(base),'candidate_length':len(out),
              'layout':{'code_base':code_base,'code_bytes':len(code),'code_reservation':code_reservation,'frame_base':frame_base,'frame_bytes':len(frames),'frame_bytes_with_terminator':len(frames)+4,'frame_reservation':frame_reservation,'index_base':index_base,'index_bytes':len(index),'index_reservation':index_reservation,'rx_end':rx_end,'names_offset':names_offset,'names_size':len(names),'section_table_offset':table_offset,'section_count':len(section_table)},
              'policy':objmanifest['policy'],'extra_heap_bytes':objmanifest['extra_heap_bytes'],'symbols':symbols,'functions':functions,'relocations':relocations,'hooks':hooks,'original_byte_whitelist':changes,
              'original_index_count':len(old_pairs),'new_index_count':len(new_pairs),'combined_index_count':len(old_pairs)+len(new_pairs),'original_index_semantic_sha256':sha(b''.join(struct.pack('<QQ',*p) for p in old_pairs)),
              'source_sha256':{n:sha((ROOT/n).read_bytes()) for n in ['build_b5_candidate.py','validate_b5_candidate.py','emit_b5_objects.py','emit_b5_candidate.py','b5_core.c','b5_adapters.c','b5_hooks.objects.s','b5_policy.generated.h']},'input_objects':objmanifest['objects'],
              'pending':['QNX loader/runtime execution','target CPU performance','acoustic/listening tests'],'packaged':False}
    # Save diagnostic relocation products even if independent validation rejects.
    (ROOT/'b5_target_code.bin').write_bytes(code);(ROOT/'b5_target_frames.bin').write_bytes(frames+b'\0'*4)
    from validate_b5_candidate import validate
    validation=validate(base,bytes(out),manifest,objects)
    manifest['validation']=validation;manifest['status']='validated_structural_host_candidate'
    destination=ROOT/'voice_2.2.2.0.2_qnx_B5_candidate.elf';destination.write_bytes(out)
    destination.chmod(base_path.stat().st_mode&0o777)
    manifest['candidate_file']=destination.name
    (ROOT/'b5_candidate_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps({k:manifest[k] for k in ['status','candidate_file','candidate_sha256','candidate_length','layout']},indent=2))
    return destination

def main():
    try:build()
    except Exception as error:
        (ROOT/'b5_candidate_blocker.json').write_text(json.dumps({'status':'blocked','reason':str(error),'candidate_emitted_by_this_run':False},indent=2)+'\n')
        raise

def guarded(read, address, guard):
    data=read(address,guard['size'])
    if len(data)!=guard['size'] or hashlib.sha256(data).hexdigest()!=guard['sha256']:
        raise ValueError(f'Original-byte SHA-256 guard failed at {address:#x}')
    return data

if __name__=='__main__':main()
