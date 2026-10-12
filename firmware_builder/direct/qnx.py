# SPDX-License-Identifier: GPL-2.0-or-later
"""Final QNX composition from factory, authored recipes and source-linked helpers."""
from pathlib import Path
import json
import struct as S
from core import Component, Write, sha
from helpers import link_helpers
from final_helpers import final_b5
from remaining_helpers import remaining_helpers
from sources import b5_assembly,b8_assembly

HERE=Path(__file__).resolve().parent
FMT='<IIQQQQIIQQ'
def align(n,a=8):return (n+a-1)//a*a
def index(pairs,base,frame):
    pairs=sorted(pairs)
    if len(set(pc for pc,fde in pairs))!=len(pairs):raise ValueError('Duplicate unwind PC')
    return bytes.fromhex('011b033b')+S.pack('<iI',frame-base-4,len(pairs))+b''.join(S.pack('<ii',pc-base,fde-base) for pc,fde in pairs)
def decode(data,base):
    if data[:4]!=bytes.fromhex('011b033b'):raise ValueError('Unsupported unwind index encoding')
    delta,count=S.unpack_from('<iI',data,4)
    if len(data)!=12+8*count:raise ValueError('Invalid unwind index extent')
    return base+4+delta,[(base+pc,base+fde) for pc,fde in S.iter_unpack('<ii',data[12:])]
def frames(data,base):
    pairs=[];at=0
    while at+4<=len(data):
        length=S.unpack_from('<I',data,at)[0]
        if not length:at+=4;continue # Explicit padding/terminators between object frames.
        if length<4 or at+4+length>len(data):raise ValueError('Invalid helper CFI extent')
        if S.unpack_from('<I',data,at+4)[0]:pairs.append((base+at+8+S.unpack_from('<i',data,at+8)[0],base+at))
        at+=length+4
    if at!=len(data):raise ValueError('Trailing helper CFI fragment')
    return pairs

def build(factory,cache):
    if sha(factory)!='7db8a8276f0bda34d22fdd2e8744b304dc7d62f80f9189836b107a4d7b178cff':raise ValueError('Factory QNX identity mismatch')
    shoff=S.unpack_from('<Q',factory,40)[0];count,strings_idx=S.unpack_from('<HH',factory,60)
    sections=[list(S.unpack_from(FMT,factory,shoff+i*64)) for i in range(count)]
    s=sections[strings_idx];names=factory[s[4]:s[4]+s[5]]
    section_names=[names[s[0]:].split(b'\0')[0].decode() for s in sections]
    sec=lambda name:sections[section_names.index(name)]
    phoff=S.unpack_from('<Q',factory,32)[0];phcount=S.unpack_from('<H',factory,56)[0]
    programs=[list(S.unpack_from('<IIQQQQQQ',factory,phoff+i*56)) for i in range(phcount)]
    def offset(va,size):
        for p in programs:
            if p[0]==1 and p[3]<=va and va+size<=p[3]+p[5]:return p[2]+va-p[3]
        raise ValueError('Unmapped original QNX hook')
    initial,b8=link_helpers(cache);b5=final_b5(cache,initial);remaining=remaining_helpers(cache)
    document=json.loads((HERE/'b1_recipe.json').read_text());recipe=document['recipe']
    original_index=next(p for p in programs if p[0]==0x6474e550)
    frame,basepairs=decode(factory[original_index[2]:original_index[2]+original_index[5]],original_index[3])
    for pair in document['index_recipe']['remove']:basepairs.remove(tuple(pair))
    basepairs.extend(tuple(pair) for pair in document['index_recipe']['add'])
    # Tables retained in the accepted layout are authored metadata residues, not
    # intermediate application images. Generate each explicitly from factory rows.
    b5pairs=basepairs+frames(initial.frames,0xf4000)
    b8pairs=b5pairs+frames(b8.frames,0xfa000)
    finalpairs=basepairs+frames(b5.frames,0xf4000)+frames(b8.frames,0xfa000)+frames(remaining.frames,0x102000)
    if (len(basepairs),len(b5pairs),len(b8pairs),len(finalpairs))!=(839,863,870,910):raise ValueError('Unwind ownership count mismatch')
    hdr=index(finalpairs,0x103000,frame)
    # Logical B1 section descriptors, followed by retained B5/B8 table artifacts.
    sec('.rodata')[5]-=8
    sec('.eh_frame_hdr')[3:6]=[0x91590,0x91590,12+8*839]
    def table_artifact(rows,strings,base,code_name,code_base,code,frame_base,frame_data,index_base,pairs):
        rows=[list(s) for s in rows];oldsize=len(strings)
        strings+=code_name.encode()+b'\0'+code_name.replace('.text','.eh_frame').encode()+b'\0'
        rows[section_names.index('.eh_frame_hdr')][3:6]=[index_base,index_base,12+len(pairs)*8]
        rows[strings_idx][4:6]=[base,len(strings)]
        rows.extend([[oldsize,1,6,code_base,code_base,len(code),0,0,16,0],
                     [oldsize+len(code_name)+1,1,2,frame_base,frame_base,len(frame_data)+4,0,0,8,0]])
        artifact=strings+bytes(align(base+len(strings))-base-len(strings))+b''.join(S.pack(FMT,*s) for s in rows)
        return rows,strings,artifact
    rows5,names5,artifact5=table_artifact(sections,names,0xf7000,'.b5.text',0xf1000,initial.code,0xf4000,initial.frames,0xf5000,b5pairs)
    rows8,names8,artifact8=table_artifact(rows5,names5,0xfd000,'.b8.text',0xf8000,b8.code,0xfa000,b8.frames,0xfb000,b8pairs)
    finalrows=[list(s) for s in rows8]
    for s in finalrows:
        if s[1]!=8 and s[4]>=0xfd000:s[4]+=0x8000
    finalrows[section_names.index('.bss')][5]=0x2b21c0-sec('.bss')[3]
    finalrows[section_names.index('.eh_frame_hdr')][3:6]=[0x103000,0x103000,len(hdr)]
    finalrows[-4][5]=len(b5.code);finalrows[-3][5]=len(b5.frames)+4
    strings=names8
    for name,base,data in [('.b15_text',0x100000,remaining.code),('.b15_eh_frame',0x102000,remaining.frames)]:
        finalrows.append([len(strings),1,6 if 'text' in name else 2,base,base,len(data),0,0,16,0]);strings+=name.encode()+b'\0'
    stroff=align(0x105000+len(artifact8));tableoff=align(stroff+len(strings))
    finalrows[strings_idx][4:6]=[stroff,len(strings)]
    finalsize=tableoff+len(finalrows)*64
    c=Component('QNX',factory,finalsize)
    def put(off,data,owner):c.add(Write(off,data,sha(factory[off:off+len(data)]),owner,'Reviewed QNX generator/source recipe'))
    def hook(pc,size,target,owner,call=False):put(offset(pc,size),bytes([0xe8 if call else 0xe9])+S.pack('<i',target-pc-5)+b'\x90'*(size-5),owner)
    for span in recipe['spans']:
        off=int(span['offset'],0)
        if off==0x190:continue # Owned by final program descriptor.
        data=bytes.fromhex(span['replacement_hex'])
        if sha(factory[off:off+len(data)])!=span['expected_sha256']:raise ValueError('B1 factory guard failed')
        put(off,data,'B1 '+span['reason'])
    put(0x91590,index(basepairs,0x91590,frame),'B1 index generated from factory entries')
    # All extension bytes have one final owner, including zero padding.
    artifacts=[(0xf1000,b5.code,'B5 final helpers'),(0xf4000,b5.frames+b'\0'*4,'B5 final frames'),
               (0xf5000,index(b5pairs,0xf5000,frame),'Retained B5 index'),(0xf7000,artifact5,'Retained B5 table'),
               (0xf8000,b8.code,'B8 helpers'),(0xfa000,b8.frames+b'\0'*4,'B8 frames'),
               (0xfb000,index(b8pairs,0xfb000,frame),'Retained B8 index'),
               (0x100000,remaining.code,'Combined final helpers'),(0x102000,remaining.frames,'Combined final frames'),
               (0x103000,hdr,'Final unwind index'),(0x105000,artifact8,'Retained relocated B8 table'),
               (stroff,strings,'Final section names'),(tableoff,b''.join(S.pack(FMT,*s) for s in finalrows),'Final section table')]
    end=len(factory)
    for off,data,owner in sorted(artifacts):
        if off<end:raise ValueError('QNX artifact overlap')
        if off>end:put(end,bytes(off-end),'Explicit layout padding')
        put(off,data,owner);end=off+len(data)
    for prefix,module,result in [('b5',b5_assembly,b5),('b8',b8_assembly,b8)]:
        for name,site,guard,continuation,cfa in module.JUMPS:hook(site,guard['size'],result.symbols[prefix+'_hook_'+name],prefix+' '+name)
        for name,site,target,event in module.CALLS:hook(site,5,result.symbols[prefix+'_wrap_'+name],prefix+' call '+name,True)
    for site,value in [(0x3d010,0x4c00),(0x3d0fc,0x1c8),(0x3d11a,0x1c8)]:put(offset(site,5),b'\xbf'+S.pack('<I',value),'Final helper allocation')
    for site,size,name,call in [(0x1e050,6,'b15_message_entry',False),(0x23b2d,5,'b15_noteon_thunk',True),(0x23a3a,5,'b15_attempt_thunk',True),(0x22280,12,'b15_group_clear_thunk',False),
                              (0x1a87b,12,'center_thunk',False),(0x3f840,8,'entry_read',False),(0x41870,6,'entry_update',False),(0x42510,8,'close_hook',False),(0x42cd1,5,'open_hook',False),
                              (0x3f01d,5,'entry_allocate',True),(0x40bc7,5,'reverse_read_hook',True)]:hook(site,size,remaining.symbols[name],'Final '+name,call)
    for site in (0x4056f,0x40849,0x40e5d,0x40f79,0x40ad0,0x40c27,0x3fd79,0x41390):hook(site,5,remaining.symbols['fade_hook'],'Final scroll fade',True)
    hook(0x1ae55,7,0x101700,'Final sync mapper')
    put(offset(0x22344,5),bytes.fromhex('31c0909090'),'Final group selection')
    for s in sections:
        if s[1] not in (2,11):continue
        st=sections[s[6]];strings0=factory[st[4]:st[4]+st[5]]
        for j in range(0,s[5],s[9]):
            no,info,other,ndx,value,size=S.unpack_from('<IBBHQQ',factory,s[4]+j)
            if strings0[no:].split(b'\0')[0] in (b'end',b'_end') and value==0x2b1eb0:put(s[4]+j+8,S.pack('<Q',0x2b21c0),'Final heap end symbol')
    put(40,S.pack('<Q',tableoff),'Final ELF section offset');put(60,S.pack('<H',len(finalrows)),'Final ELF section count')
    for i,p in enumerate(programs):
        if p[0]==1 and p[1]==5 and p[2]==0:p[5]=p[6]=0x105000;put(phoff+i*56,S.pack('<IIQQQQQQ',*p),'Final RX descriptor')
        elif p[0]==1 and p[1]==6:p[6]=0x2b21c0-p[3];put(phoff+i*56,S.pack('<IIQQQQQQ',*p),'Final RW descriptor')
        elif p[0]==0x6474e550:p[2]=p[3]=p[4]=0x103000;p[5]=p[6]=len(hdr);put(phoff+i*56,S.pack('<IIQQQQQQ',*p),'Final unwind descriptor')
    put(offset(0x1f4e3,4),S.pack('<I',0x40139222),'Final DSP revision')
    for site in (0x250e2,0x250ef):put(offset(site,1),b'\x02','Final updater revision')
    return c.render(),c.receipt()
