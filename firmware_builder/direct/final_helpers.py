# SPDX-License-Identifier: GPL-2.0-or-later
"""Compose final B5 endpoint fixes directly from linked source helpers."""
from pathlib import Path
import struct
from core import sha
from elf_objects import Object, Linked, frame_pairs, bounded, unpack, align
from helpers import link_helpers

HERE = Path(__file__).resolve().parent

def final_b5(cache, initial):
    code,frames = bytearray(initial.code),bytearray(initial.frames)
    code_base,frame_base = 0xf1000,0xf4000
    original = 0xf13bb
    body = bytearray(bounded(code,original-code_base,44))
    if sha(body) != '31dbbdc480a5005df938358a3ff524917bb5da1f570885a84891b10e4ba06447':
        raise ValueError('Source-generated endpoint helper guard failed')
    body[22:24] = b'\x90\x90'
    helper = align(len(code),16)+code_base
    code.extend(bytes(helper-code_base-len(code))+body)
    # These checks address source-generated helper bytes, not a historical image.
    def hook(site,size,target,opcode,expected):
        offset = site-code_base
        if sha(bounded(code,offset,size)) != expected:
            raise ValueError('Source-generated endpoint call guard failed')
        code[offset:offset+size] = bytes([opcode])+struct.pack('<i',target-site-5)+b'\x90'*(size-5)
    hook(0xf15dc,5,helper,0xe8,'552ad56a62d0c055a5f4306a074d3235cdf62fd5326a75e61b047f89c8fb16d8')
    original_fde = next(f for pc,f in frame_pairs(frames,frame_base) if pc==original)
    offset = original_fde-frame_base
    length,cie_delta = unpack('<II',frames,offset)
    cie = original_fde+4-cie_delta
    if unpack('<I',frames,offset+12)[0] != 44:
        raise ValueError('Endpoint original FDE extent changed')
    clone = bytearray(bounded(frames,offset,length+4))
    dest = frame_base+len(frames)
    struct.pack_into('<I',clone,4,dest+4-cie)
    struct.pack_into('<i',clone,8,helper-(dest+8))
    frames.extend(clone)
    key = next(k for k in cache.manifest['entries'] if k.startswith('0f41c6969c9b'))
    obj = Object('completion',cache.restore(key,{'helpers.s':(HERE/'sources/completion_helpers.s').read_bytes()})[0])
    if any(s[1] in (4,9) and s[5] for s in obj.sections):
        raise ValueError('Completion helper unexpectedly needs relocation')
    section = obj.sections[obj.names.index('.text')]
    completion = bounded(obj.data,section[4],section[5])
    symbols = {n:v for table in obj.symbols.values() for n,_,index,v,_ in table if index==obj.names.index('.text')}
    base = 0xf3c40
    if code_base+len(code)>base:
        raise ValueError('Endpoint helpers overlap')
    code.extend(bytes(base-code_base-len(code))+completion)
    geometry = base+symbols['completion_geom']
    for site,size,target,opcode,expected in [
        (0xf122c,5,base,0xe8,'b1d090e8ab50878f563e76d89b5f007a26603f3768d31156d61ad89af0344eab'),
        (0xf126e,5,base,0xe8,'4141f176166314c5f7b7b3fb30f71f1a6602cc6683d1e5b142ee408c097416d1'),
        (0xf1bc2,6,geometry,0xe9,'2af933f0692fff19a577eabc19ad8a1b404e8cc17a788b58cb147519f7c1915e')]:
        hook(site,size,target,opcode,expected)
    for pc,size,cfi in [(base,symbols['completion_geom'],b''),
                        (geometry,len(completion)-symbols['completion_geom'],bytes.fromhex('0e6083078c068d058e048f038602'))]:
        dest = frame_base+len(frames)
        body = struct.pack('<I',dest+4-cie)+struct.pack('<iI',pc-(dest+8),size)+b'\0'+cfi
        body += bytes((-len(body))%4)
        frames.extend(struct.pack('<I',len(body))+body)
    if len(code)>0x3000 or len(frames)+4>0x1000:
        raise ValueError('Final B5 source helpers exceed reservations')
    return Linked(bytes(code),bytes(frames),dict(initial.symbols,endpoint_identity=helper,
                  completion_apply=base,completion_geom=geometry),initial.relocations)

def final_helpers(cache):
    b5,b8 = link_helpers(cache)
    return final_b5(cache,b5),b8
