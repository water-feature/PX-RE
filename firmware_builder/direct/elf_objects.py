# SPDX-License-Identifier: GPL-2.0-or-later
"""Bounded in-memory linker for the reviewed x86-64 helper object subset."""
from dataclasses import dataclass
import struct

def bounded(data, offset, size):
    if offset < 0 or size < 0 or offset+size > len(data):
        raise ValueError('ELF extent out of bounds')
    return data[offset:offset+size]

def unpack(fmt, data, offset):
    return struct.unpack(fmt, bounded(data,offset,struct.calcsize(fmt)))

def string(data, offset):
    if offset < 0 or offset >= len(data):
        raise ValueError('ELF string offset out of bounds')
    end = data.find(b'\0',offset)
    if end < 0:
        raise ValueError('ELF string is not terminated')
    return data[offset:end].decode('ascii')

class Object:
    def __init__(self, name, data):
        self.name, self.data = name, data
        if bounded(data,0,6) != b'\x7fELF\x02\x01':
            raise ValueError('Expected little-endian ELF64 object')
        if unpack('<HH',data,16) != (1,62):
            raise ValueError('Expected relocatable x86-64 object')
        offset = unpack('<Q',data,40)[0]
        width,count,names = unpack('<HHH',data,58)
        if width != 64 or not count or names >= count:
            raise ValueError('Unsupported ELF section table')
        self.sections = [unpack('<IIQQQQIIQQ',data,offset+i*width) for i in range(count)]
        table = self.sections[names]
        strings = bounded(data,table[4],table[5])
        self.names = [string(strings,s[0]) for s in self.sections]
        for section in self.sections:
            if section[1] != 8:
                bounded(data,section[4],section[5])
        self.symbols = {}
        for i,s in enumerate(self.sections):
            if s[1] != 2:
                continue
            if s[9] != 24 or s[5] % 24 or s[6] >= count:
                raise ValueError('Invalid ELF symbol table')
            names_section = self.sections[s[6]]
            names_data = bounded(data,names_section[4],names_section[5])
            table = []
            for at in range(s[4],s[4]+s[5],24):
                no,info,other,index,value,size = unpack('<IBBHQQ',data,at)
                table.append((string(names_data,no),info,index,value,size))
            self.symbols[i] = table

def align(n,a):
    if a <= 0 or a & (a-1):
        raise ValueError('ELF alignment must be a power of two')
    return (n+a-1)//a*a

@dataclass
class Linked:
    code: bytes
    frames: bytes
    symbols: dict
    relocations: list

def link(objects, code_base, frame_base, bindings, *, frame_alignment=8, fixed_alignment=False):
    """Match B5/B8 source link order, section order and alignment exactly."""
    code,frames = bytearray(),bytearray()
    symbols, placed = dict(bindings),[]
    for obj in objects:
        locations = {}
        for i,(name,s) in enumerate(zip(obj.names,obj.sections)):
            if name == '.text' or name.startswith('.rodata'):
                pool,base,alignment = code,code_base,16 if fixed_alignment else max(1,s[8])
            elif name == '.eh_frame':
                pool,base,alignment = frames,frame_base,frame_alignment if fixed_alignment else max(frame_alignment,s[8])
            elif s[2]&2 and s[5]:
                raise ValueError('Unsupported allocated section: '+name)
            else:
                continue
            pool.extend(bytes(align(len(pool),alignment)-len(pool)))
            locations[i] = base+len(pool)
            pool.extend(bounded(obj.data,s[4],s[5]))
        for table in obj.symbols.values():
            for name,info,index,value,size in table:
                if index in locations and info>>4 and name:
                    if name in symbols:
                        raise ValueError('Duplicate symbol: '+name)
                    if value > obj.sections[index][5] or value+size > obj.sections[index][5]:
                        raise ValueError('Symbol exceeds source section')
                    symbols[name] = locations[index]+value
        placed.append((obj,locations))
    relocations = []
    for obj,locations in placed:
        for s in obj.sections:
            if s[1] != 4:
                continue
            if s[7] not in locations:
                if s[5]:
                    raise ValueError('Relocation targets unsupported section')
                continue
            if s[9] != 24 or s[5]%24 or s[6] not in obj.symbols:
                raise ValueError('Invalid relocation table')
            for at in range(s[4],s[4]+s[5],24):
                offset,info,addend = unpack('<QQq',obj.data,at)
                kind,index = info&0xffffffff,info>>32
                if kind not in (2,4):
                    raise ValueError('Unsupported x86 relocation type: '+str(kind))
                table = obj.symbols[s[6]]
                if index >= len(table) or offset+4 > obj.sections[s[7]][5]:
                    raise ValueError('Relocation symbol/site out of bounds')
                name,_,section,value,_ = table[index]
                if section in locations:
                    if value > obj.sections[section][5]:
                        raise ValueError('Relocation symbol value out of bounds')
                    target = locations[section]+value
                elif section == 0 and name in symbols:
                    target = symbols[name]
                else:
                    raise ValueError('Unresolved relocation symbol: '+name)
                site = locations[s[7]]+offset
                delta = target+addend-site
                if not -2**31 <= delta < 2**31:
                    raise ValueError('Relocation overflow: '+name)
                pool,base = (frames,frame_base) if obj.names[s[7]] == '.eh_frame' else (code,code_base)
                struct.pack_into('<i',pool,site-base,delta)
                relocations.append({'object':obj.name,'site':site,'kind':kind,'symbol':name,
                                    'target':target,'addend':addend})
    return Linked(bytes(code),bytes(frames),symbols,relocations)

def frame_pairs(data,base):
    pairs = []
    at = 0
    while at < len(data):
        length,cie = unpack('<II',data,at)
        if length < 4 or length == 0xffffffff or at+4+length > len(data):
            raise ValueError('Invalid concatenated CFI record extent')
        if cie:
            pairs.append((base+at+8+unpack('<i',data,at+8)[0],base+at))
        at += length+4
    return pairs
