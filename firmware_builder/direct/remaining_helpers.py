# SPDX-License-Identifier: GPL-2.0-or-later
"""Directly link the final stretch, center, scrolling and sync helper regions."""
from pathlib import Path
import json
import struct
from elf_objects import Object, link, Linked
from core import sha

HERE = Path(__file__).resolve().parent

def load_objects(cache):
    recipes = json.loads((HERE/'object_recipes.json').read_text())
    result = {}
    for name,recipe in recipes.items():
        inputs = {}
        for original,item in recipe['inputs'].items():
            path = (HERE/item['file']).resolve()
            if not path.is_relative_to(HERE):
                raise ValueError('Source path escapes direct-builder source root')
            data = path.read_bytes()
            if sha(data) != item['sha256']:
                raise ValueError('Direct object recipe source identity mismatch')
            inputs[original] = data
        outputs = cache.restore(recipe['key'],inputs)
        if len(outputs) != 1:
            raise ValueError('Expected one helper object')
        result[name] = Object(name,outputs[0])
    return result

def remaining_helpers(cache):
    objects = load_objects(cache)
    external = {'b15_stock_message_continue':0x1e056,'b15_stock_noteon':0x36400,
                'b15_stock_getparam':0x9760,'b15_stock_group_continue':0x2228c,
                'b15_runtime_storage':0x2b1ec0,'b15_stock_mutex':0x2a57a0}
    external.update({f'b15_stock_fn_0x{v:x}':v for v in (0x7a10,0x79a0,0x9700,0x1d7f0,0x35940,0x36180,0x3ed50)})
    stretch = link([objects[n] for n in ('b15_core','b15_adapter','b15_thunks')],
                   0x100000,0x102000,external,frame_alignment=1)
    center = link([objects[n] for n in ('center_probe','center_thunk')],0x100f60,0x1024e8,
                  {'center_get_mod':0x27040,'center_get_param':0x9760,'center_map':0x2a5188,
                   'center_diffs':0x2a5180,'center_continue':0x1a887},frame_alignment=1)
    scroll = link([objects[n] for n in ('scroll_patch','scroll_hooks')],0x1012c0,0x1025a4,
                  {'image_anchor':0x1012c0,'read_resume':0x3f848,'update_resume':0x41876,
                   'close_resume':0x42518,'open_resume':0x42cd6,'original_fade':0x3f2f0,
                   'local_read':0x3f080,'allocate':0x46100},frame_alignment=4,fixed_alignment=True)
    sync = link([objects['sync_helper']],0x101700,0,
                {'resume_old':0x1ae5c,'resume_positive':0x1ae64,
                 'resume_duration':0x1aea6,'runtime_s0':0x2a5140},frame_alignment=1)
    if sync.frames or len(sync.code)!=156:
        raise ValueError('Sync helper layout changed')
    code,frames = bytearray(),bytearray()
    symbols,relocations = {},[]
    def place(pool,base,address,data):
        offset = address-base
        if offset < len(pool):
            raise ValueError('Final helper overlap')
        pool.extend(bytes(offset-len(pool))+data)
    for result,cp,fp in [(stretch,0x100000,0x102000),(center,0x100f60,0x1024e8),
                          (scroll,0x1012c0,0x1025a4),(sync,0x101700,0)]:
        place(code,0x100000,cp,result.code)
        if result.frames:
            place(frames,0x102000,fp,result.frames)
        for name,value in result.symbols.items():
            if name in symbols and symbols[name]!=value:
                raise ValueError('Conflicting final helper symbol')
            symbols[name]=value
        relocations.extend(result.relocations)
    # Sync FDE is source-authored and reuses the factory CIE at 0x92fd8.
    fde,cie = 0x10277c,0x92fd8
    cfi = bytes.fromhex('0f03765806 1006027600 100f027678 100e027670 100d027668 100c027660 1003027650')
    body = struct.pack('<IiI',fde+4-cie,0x101700-(fde+8),136)+b'\0'+cfi
    body += bytes((-len(body)-4)%8)
    place(frames,0x102000,fde,struct.pack('<I',len(body))+body)
    if len(code)!=0x179c or len(frames)!=0x7b4:
        raise ValueError('Final helper section extents changed')
    return Linked(bytes(code),bytes(frames),symbols,relocations)
