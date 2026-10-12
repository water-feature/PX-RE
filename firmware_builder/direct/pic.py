# SPDX-License-Identifier: GPL-2.0-or-later
"""Compose final PIC recipes once against factory bytes; no intermediate images."""
from pathlib import Path
import json
import struct
from core import Component, Write, sha
from mips import R, emit, encode, assemble_lines
from pic_stretch import writes as stretch_writes, PIC_SHA256, BASE
from sources import b7_pic

HERE=Path(__file__).resolve().parent

def b11_words(cache,sections):
    labels,instructions={},[]
    for start,end,source in sections:
        pc=start
        for line in source.strip().splitlines():
            line=line.split('#',1)[0].strip()
            if not line:continue
            if line.endswith(':'):
                if line[:-1] in labels:raise ValueError('Duplicate B11 assembly label')
                labels[line[:-1]]=pc
            else:pc+=4
    for start,end,source in sections:
        data,local,rows=assemble_lines(source.strip().splitlines(),start,labels)
        # Cross-fragment labels resolve after collecting all definitions.
        labels.update(local)
        instructions.extend((start+i*4,row) for i,row in enumerate(rows))
        if len(data)!=end-start:raise ValueError('B11 source fragment extent changed')
    # Reconstruct the exact compiler source for independent cached-object verification.
    external={0x9d02ebe8:'group1',0x9d02eae8:'group2',0x9d02a794:'refresh1',0x9d02d464:'refresh2',0x9d04d4fc:'clamp'}
    assembly=['.set noreorder','.set noat','.text']
    for start,end,source in sorted(sections+[[addr,addr+4,name+':\nnop\n'] for addr,name in external.items()]):
        assembly.append(f'.org {start-BASE}')
        for line in source.strip().splitlines():
            if line.endswith(':') or line=='nop':assembly.append(line);continue
            op,args=line.split(' ',1);a=args.split(',')
            if op in ('beq','bne','beql'):
                dest=external.get(int(a[2],0),a[2]) if a[2].startswith('0x') else a[2]
                assembly.append(f'{op} ${a[0]},${a[1]},{dest}')
            elif op in ('lhu','lw','sh','sw'):assembly.append(f'{op} ${a[0]},{a[1]}(${a[2]})')
            elif op in ('j','jal'):assembly.append(line)
            else:assembly.append(op+' '+','.join('$'+v if v in R else v for v in a))
    source=('#![feature(no_core, rustc_attrs, asm_experimental_arch)]\n#![no_core]\n#![no_main]\n#[rustc_builtin_macro]\nmacro_rules! global_asm { () => {} }\nglobal_asm!('+json.dumps('\n'.join(assembly)+'\n')+');\n').encode()
    key=next(k for k in cache.manifest['entries'] if k.startswith('1622f6ba229e'))
    obj=cache.restore(key,{'candidate.rs':source})[0]
    if obj[:6]!=b'\x7fELF\x01\x01' or struct.unpack_from('<H',obj,18)[0]!=8:
        raise ValueError('Expected MIPS ELF32 object')
    offset=struct.unpack_from('<I',obj,32)[0];width,count,names=struct.unpack_from('<HHH',obj,46)
    if width!=40 or names>=count or offset+count*width>len(obj):raise ValueError('Invalid MIPS section table')
    headers=[struct.unpack_from('<10I',obj,offset+i*width) for i in range(count)]
    table=headers[names];strings=obj[table[4]:table[4]+table[5]]
    if any(h[1] in (4,9) and h[5] for h in headers):raise ValueError('Unexpected B11 object relocations')
    text=next(h for h in headers if strings[h[0]:].split(b'\0')[0]==b'.text')
    if text[4]+text[5]>len(obj):raise ValueError('B11 object text exceeds bounds')
    result={}
    for pc,row in instructions:
        word=encode(pc,row,labels)
        if pc-BASE+4>text[5] or struct.unpack_from('<I',obj,text[4]+pc-BASE)[0]!=word:
            raise ValueError('B11 source encoder and recorded compiler disagree')
        result[pc]=word
    for pc in (0x9d04debc,0x9d04e010,0x9d04e54c,0x9d04e624):result[pc]=encode(pc,('jal',labels['adjust']))
    return result

def build(factory,cache):
    if sha(factory)!=PIC_SHA256:raise ValueError('Factory PIC identity mismatch')
    recipes=json.loads((HERE/'pic_recipes.json').read_text())
    component=Component('PIC',factory,len(factory))
    def put(pc,data,owner,source='Reviewed authored PIC recipe'):
        off=pc-BASE
        component.add(Write(off,data,sha(factory[off:off+len(data)]),owner,source))
    def word(pc,value,owner):put(pc,struct.pack('<I',value),owner)
    def block(pc,rows,owner,labels=None):put(pc,emit(rows,pc,labels),owner)
    for w in stretch_writes(factory):component.add(w)
    # B3 SysEx matcher. Revision words are owned by final metadata below.
    block(BASE+0x1200,[('raw',w) for w in (0x90a30005,0x386300f0,0x10600003,0x00001021,0x0f417b93,0x90a40004,0x0b40a56e,0)],'B3 matcher')
    word(BASE+0x295b0,encode(BASE+0x295b0,('j',BASE+0x1200)),'B3 matcher hook')
    for pc,row in {**b7_pic.BLOCKS,**b7_pic.OVERLAY}.items():
        if pc==BASE+0x1224:continue # Final owner is B6 center/window hook.
        word(pc,encode(pc,row),'B7 window helper/hook')
    rows=recipes['b6_rows']; labels={};pc=BASE+0xc00;body=[]
    for row in rows:
        if row[0].endswith(':'):labels[row[0][:-1]]=pc
        else:body.append(row);pc+=4
    block(BASE+0xc00,body,'B6 center/window helper',labels)
    word(BASE+0x1224,encode(BASE+0x1224,('j',BASE+0xc00)),'B6 center/window hook')
    panel=(0x9d02a3d0,0x9d02a808,0x9d02aabc,0x9d02bcc8,0x9d02dcf0,0x9d02e0c0)
    helper=BASE+0xd84
    rows=[('addu','s0','s3','s0'),('j',helper+20),('addiu','t3','zero',0),('addiu','t3','zero',1),('addiu','v0','zero',500),('lw','t1',0x44,'sp'),('lui','t0',0x9d02)]
    skip=helper+(7+13+2)*4
    for ret in panel:rows.extend([('ori','t2','t0',ret&65535),('beq','t1','t2',skip)])
    rows.extend([('nop',),('j',BASE+0x23558),('nop',),('beq','t3','zero',helper+26*4),('nop',),('j',BASE+0x23558),('addiu','v0','zero',250),('j',BASE+0x2355c),('nop',)])
    block(helper,rows,'B9 browsing helper')
    for pc,target in [(BASE+0x23550,helper),(BASE+0x235e4,helper+12)]:word(pc,encode(pc,('j',target)),'B9 browsing hook')
    # Final B14 replay helper includes its sample-acceleration sign hook.
    rows=recipes['b14_rows']; rows[20:22]=[['j',BASE+0x7a440],['nop']]
    block(BASE+0x7a468,rows,'B14 replay helper',{'loop':BASE+0x7a468+24*4,'exit':BASE+0x7a468+30*4})
    block(BASE+0x7a208,[('j',BASE+0x7a468),('nop',)],'B14 service hook')
    block(BASE+0x411c8,recipes['metadata_rows'],'B14 metadata helper',{'byte':BASE+0x411c8+4*4})
    block(BASE+0x41278,[('j',BASE+0x412ac),('nop',)],'B14 metadata tail')
    blocks=recipes['stable_blocks'];starts={};pc=BASE+0x13ac
    for name,rows in blocks.items():starts[name]=pc;pc+=len(rows)*4
    labels={'busy':starts['guard']+40,'full_original':starts['fullclear']+20,'clear_original':starts['clear']+20}
    for name,rows in blocks.items():block(starts[name],rows,'B14 stable '+name,labels)
    for off,name,op in [(0x3ed0c,'guard','j'),(0x3ecb0,'page','j'),(0x7e408,'fullclear','j'),(0x7e274,'clear','j'),(0x298d8,'resume','jal')]:
        block(BASE+off,[(op,starts[name]),('nop',)],'B14 stable hook '+name)
    word(BASE+0x29ce0,encode(BASE+0x29ce0,('jal',starts['blank'])),'B14 blank hook')
    word(BASE+0x3ee54,encode(BASE+0x3ee54,('bne','v1','zero',BASE+0x3ed24)),'B14 stable render')
    decoder,_,_=assemble_lines(recipes['acceleration_decoder'],BASE+0x7a298)
    put(BASE+0x7a298,decoder,'B14 sample acceleration decoder')
    rows=['andi t0,s1,0xfffe','li t1,4','beq t0,t1,full','li t1,18','beq t0,t1,full','nop','slt t0,s0,zero','sll t0,t0,1','j 0x9d07a4c0','nop']
    classifier,_,_=assemble_lines(rows,BASE+0x7a440,{'full':BASE+0x7a244})
    put(BASE+0x7a440,classifier,'B14 sample acceleration classifier')
    block(BASE+0x7a244,[('j',BASE+0x7a4c8),('addu','s2','s0','zero')],'B14 snapshot continuation')
    for pc,value in b11_words(cache,recipes['b11_sections']).items():word(pc,value,'B11 real instrument on Type')
    for pc,value in recipes['b16_words']:word(pc,value,'B16 sync mapping')
    put(BASE+0x62074,b'1/32 Step\0'+b'1/64 Step\0'+bytes([156,144,132,120,108,96,84,76,64,56,48,40,32,24,12,0,232,242])+b'\0\0',
        'B16 sync labels and division lookup',
        'B16 in_place_validation/integrate.py authored labels and lookup data')
    for pc,value in recipes['geometry_words']:word(pc,value,'B16 geometry')
    for off in (0x475f4,0x47900):put(BASE+off,struct.pack('<H',17),'B16 division descriptor bound')
    for off in (0x1394,0x13a0):
        target=BASE+(0x75c1c if off==0x1394 else 0x75b18)
        block(BASE+off,[('addiu','a0','a0',2),('j',target),('nop',)],'Final PIC fifth-field report thunk')
    for off,target in [(0x258c0,0x1394),(0x51bc8,0x13a0)]:word(BASE+off,encode(BASE+off,('jal',BASE+target)),'Final PIC report hook')
    for off in (0x258b4,0x51bc4):word(BASE+off,0x24842222,'Final PIC first-four-field report')
    word(BASE+0x52fec,0x24020002,'Final M formatter revision')
    return component.render(),component.receipt()
