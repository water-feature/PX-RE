# SPDX-License-Identifier: GPL-2.0-or-later
"""Explicit bounded MIPS32 encoder for authored PIC recipes."""
import struct

NAMES = 'zero at v0 v1 a0 a1 a2 a3 t0 t1 t2 t3 t4 t5 t6 t7 s0 s1 s2 s3 s4 s5 s6 s7 t8 t9 k0 k1 gp sp fp ra'.split()
R = dict(zip(NAMES,range(32)))

def encode(pc,row,labels=None):
    labels = labels or {}
    op,*a = row
    def immediate(value,signed=True):
        if not (-32768 <= value <= 32767 if signed else 0 <= value <= 65535):
            raise ValueError('MIPS immediate out of range')
        return value&65535
    if op=='nop': return 0
    if op=='raw':
        if not 0<=a[0]<2**32: raise ValueError('Raw MIPS word out of range')
        return a[0]
    if op=='move': op,a='addu',[a[0],a[1],'zero']
    if op=='li': op,a='addiu',[a[0],'zero',a[1]]
    if op=='ehb': return 0xc0
    if op in ('di','mtc0_status','mfc0_status','mfc0_count'):
        return {'di':0x41606000,'mtc0_status':0x40806000,'mfc0_status':0x40006000,'mfc0_count':0x40004800}[op]|R[a[0]]<<16
    if op=='lui': return 15<<26|R[a[0]]<<16|immediate(a[1],False)
    if op in ('sll','srl'):
        if not 0<=a[2]<32: raise ValueError('MIPS shift out of range')
        return R[a[1]]<<16|R[a[0]]<<11|a[2]<<6|{'sll':0,'srl':2}[op]
    if op=='sllv': return R[a[2]]<<21|R[a[1]]<<16|R[a[0]]<<11|4
    arithmetic = {'addu':33,'subu':35,'slt':42,'sltu':43,'and':36,'or':37,'xor':38,'movz':10,'movn':11}
    if op in arithmetic: return R[a[1]]<<21|R[a[2]]<<16|R[a[0]]<<11|arithmetic[op]
    if op in ('addiu','sltiu','andi','ori','xori'):
        return {'addiu':9,'sltiu':11,'andi':12,'ori':13,'xori':14}[op]<<26|R[a[1]]<<21|R[a[0]]<<16|immediate(a[2],op in ('addiu','sltiu'))
    if op in ('lw','sw','lhu','sh','lbu','sb'):
        dst,base,value = a if isinstance(a[1],str) else (a[0],a[2],a[1])
        return {'lw':35,'sw':43,'lhu':37,'sh':41,'lbu':36,'sb':40}[op]<<26|R[base]<<21|R[dst]<<16|immediate(value)
    if op in ('j','jal'):
        target = labels.get(a[0],a[0])
        if not isinstance(target,int) or target%4 or target>>28 != (pc+4)>>28:
            raise ValueError('MIPS jump target out of range')
        return {'j':2,'jal':3}[op]<<26|(target>>2)&0x3ffffff
    if op in ('beq','bne','beql','bnel'):
        target = labels.get(a[2],a[2])
        if not isinstance(target,int) or target%4: raise ValueError('Invalid MIPS branch target')
        displacement = immediate((target-pc-4)//4)
        return {'beq':4,'bne':5,'beql':20,'bnel':21}[op]<<26|R[a[0]]<<21|R[a[1]]<<16|displacement
    if op=='jr': return R[a[0]]<<21|8
    if op=='jalr': return R[a[0]]<<21|31<<11|9
    if op=='label_hi': return encode(pc,('lui',a[0],labels[a[1]]>>16))
    if op=='label_lo': return encode(pc,('ori',a[0],a[0],labels[a[1]]&65535))
    raise ValueError('Unsupported authored MIPS instruction: '+op)

def emit(rows,base,labels=None):
    return b''.join(struct.pack('<I',encode(base+i*4,row,labels)) for i,row in enumerate(rows))

def assemble_lines(lines,base,labels=None):
    labels = dict(labels or {})
    rows = []
    for line in lines:
        line=line.split('#',1)[0].strip()
        if not line:continue
        if line.endswith(':'):
            label=line[:-1]
            if label in labels and labels[label]!=base+4*len(rows):raise ValueError('Conflicting assembly label')
            labels[label]=base+4*len(rows)
        else:rows.append(line)
    parsed=[]
    for line in rows:
        op,*tail=line.split(None,1)
        args=tail[0].split(',') if tail else []
        if op in ('lw','sw','lhu','sh','lbu','sb') and len(args)==2 and '(' in args[1]:
            immediate,register=args[1][:-1].split('(')
            args=[args[0],register,immediate]
        values=[]
        for value in args:
            value=value.strip()
            try:values.append(int(value,0))
            except ValueError:values.append(value)
        parsed.append((op,*values))
    return emit(parsed,base,labels),labels,parsed
