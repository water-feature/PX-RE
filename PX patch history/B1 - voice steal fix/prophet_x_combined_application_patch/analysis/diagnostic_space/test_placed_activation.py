# SPDX-License-Identifier: GPL-2.0-or-later
"""Execute candidate helper/hook bytes; all QNX threading is mocked."""
import hashlib
import struct, os
from pathlib import Path
from unicorn import Uc, UC_ARCH_X86, UC_MODE_64, UC_HOOK_CODE
from unicorn.x86_const import *
from elftools.elf.elffile import ELFFile
P=Path(__file__).resolve().parent
with (P/'placed.elf').open('rb') as f:
    e=ELFFile(f)
    syms={s.name:s['st_value'] for s in e.get_section_by_name('.symtab').iter_symbols()}
with (P.parent/'ProphetX.elf').open('rb') as f:
    e=ELFFile(f)
    def stock(addr,n):
        for s in e.iter_segments():
            if s['p_type']=='PT_LOAD' and s['p_vaddr']<=addr<s['p_vaddr']+s['p_filesz']:
                return s.data()[addr-s['p_vaddr']:addr-s['p_vaddr']+n]
    setgate=stock(0xead0,18)
    assert hashlib.sha256(stock(0x216bf,7)).hexdigest()=='0c82d794207db714513f8de87db297995c04b7a35b3edd777da26312beb7d738'
    assert hashlib.sha256(stock(0x1b49e,11)).hexdigest()=='1e6a78c2b8af4e1fd0ad6dc842cb653cdb9f51265a5f8e6bf13aac47b1af6eb0'
    for site,target in [(0x21484,0xead0),(0x2174c,0x7a10),(0x1b7e5,0x7a10)]:
        b=stock(site,5);assert b[0]==0xe8 and site+5+int.from_bytes(b[1:],'little',signed=True)==target
INTEGRATED=os.environ.get('PX_CANDIDATE_ELF')
L,E,S,STOP=0x100000,0x200000,0x300000,0x400000
savedregs=[UC_X86_REG_RBX,UC_X86_REG_RBP,UC_X86_REG_R12,UC_X86_REG_R13,UC_X86_REG_R14,UC_X86_REG_R15]
volatile=[UC_X86_REG_RAX,UC_X86_REG_RCX,UC_X86_REG_RDX,UC_X86_REG_RSI,UC_X86_REG_RDI,UC_X86_REG_R8,UC_X86_REG_R9,UC_X86_REG_R10,UC_X86_REG_R11]
def run(kind,voice=0,fresh=True,spurious=0):
    u=Uc(UC_ARCH_X86,UC_MODE_64)
    for a,n in [(0x7000,0x1000),(0xe000,0x1000),(0x1b000,0x1000),(0x21000,0x1000),(L,0x5000),(E,0x1000),(0x2a5000,0x1000),(S,0x10000),(STOP,0x1000),(0x600000,0x1000),(0x49000,0x2000),(0x8f000,0x1000)]:u.mem_map(a,n)
    if INTEGRATED:
        candidate=Path(INTEGRATED).read_bytes()
        for a,n in [(0x49fd0,189),(0x8fed0,73),(0x21399,7),(0x21489,5),(0x215b8,7),(0x216bf,7),(0x2174c,5),(0x1b49e,11),(0x1b7e5,5)]:u.mem_write(a,candidate[a:a+n])
    else:
        with (P/'placed.elf').open('rb') as f:
            elf=ELFFile(f)
            for name in ['.quiet','.hooks','.stub']:
                sec=elf.get_section_by_name(name);u.mem_write(sec['sh_addr'],sec.data())
    u.mem_write(0xead0,setgate)
    for a in [0x7a10,0x7640,0x79a0]:u.mem_write(a,b'\xc3')
    u.mem_write(L+0x298,struct.pack('<Q',E))
    u.mem_write(E+voice,b'\x01');u.mem_write(E+0x22+voice,b'\x01');u.mem_write(E+0x44+voice,b'\x01')
    rbp=S+0x8000;u.mem_write(rbp-0x808,struct.pack('<I',voice));u.mem_write(rbp-0x834,struct.pack('<i',voice*2))
    original={r:0x111100+r for r in savedregs};original.update({UC_X86_REG_RBX:voice,UC_X86_REG_RBP:rbp,UC_X86_REG_R14:int(fresh),UC_X86_REG_R15:L})
    for r,v in original.items():u.reg_write(r,v)
    direct=kind in ['gateoff','activation'] and not INTEGRATED;rsp=S+0xf000-(8 if direct else 0)
    u.reg_write(UC_X86_REG_RSP,rsp);u.mem_write(rsp,struct.pack('<Q',STOP))
    u.mem_write(rsp+0x3c,struct.pack('<I',32))
    u.reg_write(UC_X86_REG_RDI,E if kind=='gateoff' else 0x2a57a0)
    u.reg_write(UC_X86_REG_RSI,voice);u.reg_write(UC_X86_REG_RDX,0)
    target={'gateoff':'px_gateoff_hook','fresh':'px_fresh_hook','activation':'px_activation_lock_hook','coordinator':'px_coordinator_hook'}[kind]
    end={'fresh':0x216c6,'coordinator':0x1b4a9}.get(kind,STOP)
    if INTEGRATED and kind=='activation':end=0x21751
    events=[];heldquiet=False;heldstartup=False;waits=0
    def hook(uc,a,n,data):
        nonlocal heldquiet,heldstartup,waits
        if a not in [0x7a10,0x7640,0x79a0]:return
        assert uc.reg_read(UC_X86_REG_RSP)%16==8
        arg=uc.reg_read(UC_X86_REG_RDI)
        if a==0x7a10:
            if arg==L+0x3648:
                assert not heldstartup and not heldquiet;heldquiet=True;events.append('quiet lock')
            else:
                assert arg==0x2a57a0 and not heldquiet;heldstartup=True;events.append('startup lock')
        elif a==0x7640:
            assert heldquiet and not heldstartup and arg==L+0x3650
            assert uc.reg_read(UC_X86_REG_RSI)==L+0x3648
            assert int.from_bytes(uc.mem_read(L+0x3644,4),'little')==1<<voice
            waits+=1;events.append('wait')
            if waits>spurious:uc.mem_write(L+0x3644,b'\x00'*4)
        else:
            assert heldquiet and arg==L+0x3648;heldquiet=False;events.append('quiet unlock')
        # Exercise hooks against maximal legal integer-register clobbering.
        for r in volatile:uc.reg_write(r,0xdead0000+r)
        uc.reg_write(UC_X86_REG_RAX,0)
    u.hook_add(UC_HOOK_CODE,hook);u.emu_start({'fresh':0x216bf,'activation':0x2174c,'coordinator':0x1b49e}[kind] if INTEGRATED else syms[target],end,count=10000)
    assert u.reg_read(UC_X86_REG_RIP)==end and not heldquiet
    assert u.reg_read(UC_X86_REG_RSP)==rsp+(8 if direct else 0)
    for r,v in original.items():assert u.reg_read(r)==v,(kind,r)
    q=['quiet lock']+['wait']*(spurious+1)+['quiet unlock']
    if kind=='gateoff':
        assert events==q and not heldstartup
        assert bytes(u.mem_read(E+0x22+voice,1))==b'\0'
        assert bytes(u.mem_read(E+0x44+voice,1))==b'\1'
    elif kind=='fresh':
        assert events==['startup lock'] and heldstartup
        assert bytes(u.mem_read(E+voice,1))==b'\0'
        assert bytes(u.mem_read(E+0x44+voice,1))==b'\0'
        assert u.reg_read(UC_X86_REG_RAX)==voice*2
    elif kind=='activation':assert events==([] if fresh else ['startup lock'])
    else:
        assert events==['startup lock'] and heldstartup
        assert u.reg_read(UC_X86_REG_RSI)==32 and u.reg_read(UC_X86_REG_RAX)==L+0x2020
for v in [0,7,15,31]:run('fresh',v)
run('activation',fresh=True);run('activation',fresh=False);run('coordinator')
print('PASS: seven activation/coordinator hook cases and five baseline stock-site byte checks.')
print('Checks: startup acquisition, no per-voice quiet wait, flag clearing, fresh/legato lock choice, displaced instructions, volatile-register clobbering, callee-saved registers and stack alignment.')
print('Mocked QNX calls; no worker/coordinator concurrency or DSP validation.')

if INTEGRATED:print('Installed candidate tested: all activation entries start at real patched sites; no reconstructed branches.')
