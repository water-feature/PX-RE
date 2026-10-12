# SPDX-License-Identifier: GPL-2.0-or-later
"""Final PIC stretch helper placement and hooks, directly from factory/source."""
import struct
from core import sha, Write
from mips import emit, encode
from sources import b15_pic

PIC_SHA256 = '14e9c9b9dc562b0384fc43b3c5e0eb7fea84a5792d1a19b9b3ea8276ef7646f5'
BASE = 0x9d000000

def writes(factory):
    if sha(factory) != PIC_SHA256:
        raise ValueError('Factory PIC identity mismatch')
    a = b15_pic.generate(factory)
    start = b15_pic.BASE
    ends = {name:a.labels[a.functions[i+1]] if i+1<len(a.functions) else start+len(a.rows)*4
            for i,name in enumerate(a.functions)}
    fragments = {'b15_capture_enable':0x9d07a210,'b15_setter':0x9d07a4f8,
                 'b15_setter_bank':0x9d07a54c,'b15_format':0x9d07a408}
    labels,pieces = {},[]
    cursor = start
    for name in a.functions:
        lo,hi = a.labels[name],ends[name]
        pc = fragments.get(name,cursor)
        if name not in fragments: cursor += hi-lo
        labels.update({label:pc+address-lo for label,address in a.labels.items() if lo<=address<hi})
        pieces.append((name,pc,a.rows[(lo-start)//4:(hi-start)//4]))
    if cursor>0x9d000c00:
        raise ValueError('PIC stretch main reservation exceeded')
    caps = {'b15_capture_enable':72,'b15_setter':84,'b15_setter_bank':32,'b15_format':72}
    result = []
    def put(pc,data,owner):
        offset = pc-BASE
        if offset<0 or offset+len(data)>len(factory): raise ValueError('PIC recipe out of bounds')
        result.append(Write(offset,data,sha(factory[offset:offset+len(data)]),owner,
                            'B15 reviewed PIC source and explicit placement recipe'))
    for name,pc,rows in pieces:
        data = emit(rows,pc,labels)
        if name in caps and len(data)>caps[name]: raise ValueError('PIC fragment reservation exceeded')
        put(pc,data,'B15 helper '+name)
    entries = {0x9d04dacc:'b15_setter',0x9d04fa6c:'b15_encoder',0x9d075c1c:'b15_transport',
               0x9d0511a4:'b15_rx_entry',0x9d029118:'b15_main_entry',0x9d05f7f4:'b15_format'}
    entries.update({pc:'b15_'+name for name,pc in [
        ('replay',0x9d07c368),('load',0x9d040418),('import',0x9d0744cc),('edit_apply',0x9d046e4c),
        ('defaults',0x9d04cd14),('reset',0x9d07c2ac),('compare',0x9d04feb4),('restore',0x9d04ffc4)]})
    for pc,name in entries.items(): put(pc,emit([('j',labels[name]),('nop',)],pc),'B15 entry '+name)
    calls = {0x9d035748:'b15_effective_get',0x9d035f2c:'b15_effective_get',0x9d031da0:'b15_effective_get',
             0x9d02ae50:'b15_capture_enable',0x9d02f26c:'b15_capture_enable',
             0x9d02ae94:'b15_capture_commit',0x9d02f2bc:'b15_capture_commit',
             0x9d052d0c:'b15_cold_defaults',
             **{pc:'b15_setter_bank' for pc in (0x9d04e230,0x9d04e250,0x9d04e0fc,0x9d04e11c)}}
    for pc,name in calls.items(): put(pc,emit([('jal',labels[name])],pc),'B15 call '+name)
    put(0x9d02f2a8,bytes(4),'B15 remove post-clear velocity read')
    for pc in (0x9d081868,0x9d07fb40):
        word = struct.unpack_from('<I',factory,pc-BASE)[0]
        if word&65535 != 0x4000: raise ValueError('Factory heap initialization changed')
        put(pc,struct.pack('<I',(word&0xffff0000)|0x3fc0),'B15 state reservation')
    return result
