# SPDX-License-Identifier: GPL-2.0-or-later
"""Emit B5/B8 source inputs and link their helpers without firmware staging."""
from pathlib import Path
import re
from elf_objects import Object, link
from sources import b5_assembly, b8_assembly

HERE = Path(__file__).resolve().parent
KEYS = {
    'b5_core':'1f7104cf94ff', 'b5_adapters':'ea0a420016ae', 'b5_hooks':'74e3e0bf03ce',
    'b8_adapters':'064cc239cb70','b8_hooks':'62085832ed06',
}

def source_inputs():
    core = (HERE/'sources/b5_core.c').read_bytes()
    text = core.decode('utf-8')
    types = text[text.index('typedef unsigned int'):text.index('#define EXPORT')]
    prototypes = '\n'.join(m.replace('EXPORT ','')+';' for m in re.findall(r'^EXPORT [^{]+(?= \{)',text,re.M))
    header = ('#pragma once\n'+types+prototypes+'\n').encode('utf-8')
    # Exact recorded policy: 48 kHz, 5 ms, 32-sample block.
    policy = b'/* Generated from shared Python policy, 5 ms. */\n#define B5_FADE_INTERVALS 240\n#define B5_PREDICTION_HORIZON 304\n'
    return {
        'b5_core':{'b5_core.c':core,'b5_policy.generated.h':policy},
        'b5_adapters':{'b5_adapters.c':(HERE/'sources/b5_adapters.c').read_bytes(),'b5_core.generated.h':header},
        'b5_hooks':{'b5_hooks.objects.s':b5_assembly.assembly().encode('utf-8')},
        'b8_adapters':{'b8_adapters.c':(HERE/'sources/b8_adapters.c').read_bytes(),'../b5_candidate_work/b5_core.generated.h':header},
        'b8_hooks':{'b8_hooks.s':b8_assembly.assembly().encode('utf-8')},
    }

def restore_helpers(cache):
    inputs = source_inputs()
    result = {}
    for name,prefix in KEYS.items():
        keys = [key for key in cache.manifest['entries'] if key.startswith(prefix)]
        if len(keys) != 1:
            raise ValueError('Object recipe key is not unique')
        restored = cache.restore(keys[0],inputs[name])
        if len(restored) != 1:
            raise ValueError('Expected one helper object per recipe')
        result[name] = Object(name,restored[0])
    return result

def link_helpers(cache):
    objects = restore_helpers(cache)
    b5 = link([objects[n] for n in ('b5_core','b5_adapters','b5_hooks')],
              0xf1000,0xf4000,b5_assembly.BINDINGS)
    bindings = {name:b5.symbols[name] for name in ('b5_ram_vtable','b5_read_original_return','b5_note_on')}
    bindings.update({'b8_continue_'+n:c for n,_,_,c,_ in b8_assembly.JUMPS})
    bindings.update(b8_zero=0x40060,b8_original_open=0x42660,
                    b8_original_resampler_reset=0x2e260,b8_note_skip=0x3644f)
    b8 = link([objects[n] for n in ('b8_adapters','b8_hooks')],0xf8000,0xfa000,bindings)
    if len(b5.code)>0x3000 or len(b5.frames)+4>0x1000 or len(b8.code)>0x2000 or len(b8.frames)+4>0x1000:
        raise ValueError('Helper reservation exceeded')
    return b5,b8
