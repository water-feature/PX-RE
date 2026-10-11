"""Execute actual stock selection loop with candidate batch hooks.
Thread/scheduler calls mocked: instruction-order test, not audio runtime proof.
"""
import struct, os
from pathlib import Path
from unicorn import Uc, UC_ARCH_X86, UC_MODE_64, UC_HOOK_CODE
from unicorn.x86_const import *
from elftools.elf.elffile import ELFFile
P=Path(__file__).resolve().parent
with (P/'placed.elf').open('rb') as f:
 e=ELFFile(f);SY={s.name:s['st_value'] for s in e.get_section_by_name('.symtab').iter_symbols()}
with (P.parent/'ProphetX.elf').open('rb') as f:
 e=ELFFile(f);LOAD=[(s['p_vaddr'],s.data()) for s in e.iter_segments() if s['p_type']=='PT_LOAD']
def stock(a,n):
 for b,d in LOAD:
  if b<=a<b+len(d):return d[a-b:a-b+n]
# Exact displaced instruction checks.
assert stock(0x21399,7)==bytes.fromhex('0f 1f 80 00 00 00 00')
assert stock(0x21489,5)==bytes.fromhex('4d 63 ec 89 d9')
assert stock(0x215b8,7)==bytes.fromhex('44 8b 9d f0 f7 ff ff')
INTEGRATED=os.environ.get('PX_CANDIDATE_ELF')
if INTEGRATED:
 with open(INTEGRATED,'rb') as f:
  elf=ELFFile(f);LOAD=[(s['p_vaddr'],s.data()) for s in elf.iter_segments() if s['p_type']=='PT_LOAD']
def jump(site,name,n,call=False):
 return bytes([0xe8 if call else 0xe9])+struct.pack('<i',SY[name]-site-5)+b'\x90'*(n-5)
L,E,S,SAMPLE,PART,TARGET=0x100000,0x200000,0x300000,0x800000,0x700000,0x701000
VOL=[UC_X86_REG_RAX,UC_X86_REG_RCX,UC_X86_REG_RDX,UC_X86_REG_RSI,UC_X86_REG_RDI,UC_X86_REG_R8,UC_X86_REG_R9,UC_X86_REG_R10,UC_X86_REG_R11]
MOCK=[0xeb10,0xeb00,0x18970,0x363c0,0x363e0,0x36b10,0x29f20,0x29f00,0x29ee0,0x7a10,0x79a0,0x7640]
def case(parts,lo,hi,limit,retrigger=True,external=False,spurious=0):
 u=Uc(UC_ARCH_X86,UC_MODE_64)
 for a,n in [(0,0x100000),(L,0x10000),(E,0x10000),(S,0x10000),(0x600000,0x1000),(PART,0x2000),(SAMPLE,0x10000)]:u.mem_map(a,n)
 for a,d in LOAD:
  if a<0x100000:u.mem_write(a,d)
 if not INTEGRATED:
  with (P/'placed.elf').open('rb') as f:
   elf=ELFFile(f)
   for name in ['.quiet','.hooks','.stub']:
    sec=elf.get_section_by_name(name);u.mem_write(sec['sh_addr'],sec.data())
  for site,name,n,call in [(0x21399,'px_batch_init',7,True),(0x21489,'px_collect_hook',5,False),(0x215b8,'px_batch_wait_hook',7,False)]:u.mem_write(site,jump(site,name,n,call))
 for a in MOCK:u.mem_write(a,b'\xc3')
 def put(a,v,n=4):u.mem_write(a,int(v).to_bytes(n,'little',signed=v<0))
 rbp=S+0x9000;rsp=S+0x8000
 u.reg_write(UC_X86_REG_RBP,rbp);u.reg_write(UC_X86_REG_RSP,rsp);u.reg_write(UC_X86_REG_R15,L)
 for off,v,n in [(0x838,lo,4),(0x7d0,hi,4),(0x828,PART+lo*4,8),(0x834,lo*2,4),(0x7d8,TARGET,8),(0x7f0,limit,4),(0x7e8,int(retrigger),1),(0x840,L+0x365c,8),(0x850,L+0x3664,8)]:put(rbp-off,v,n)
 put(TARGET,0);put(L+0x298,E,8);put(L+0x1fd8,SAMPLE,8);put(L+0x290,0x900000,8)
 for v,p in enumerate(parts):
  put(PART+v*4,p);put(L+0x190+v*8,60);put(E+0x6c+v*16,4);put(E+0x22+v,1,1)
 chosen=[v for v in range(lo,hi) if parts[v]==0][:limit]
 expected=0 if not retrigger and external else sum(1<<v for v in chosen)
 requests=[];waits=0;quietheld=False;events=[];closed=set()
 def hook(uc,a,n,_):
  nonlocal waits,quietheld
  if a not in MOCK:return
  assert uc.reg_read(UC_X86_REG_RSP)%16==8,(hex(a),'alignment')
  arg=uc.reg_read(UC_X86_REG_RDI);voice=uc.reg_read(UC_X86_REG_RSI)&0xffffffff;ret=0
  if a==0xeb10:ret=int.from_bytes(uc.mem_read(E+0x6c+voice*16,4),'little')
  elif a==0xeb00:ret=int.from_bytes(uc.mem_read(E+0x22+voice,1),'little')
  elif a==0x18970:ret=int(external)
  elif a==0x363c0:ret=int(arg not in closed)
  elif a==0x363e0:ret=0
  elif a in [0x36b10,0x29ee0]:
   assert expected and requests==[expected] and events.count('ack')==1,'shutdown before group acknowledgement'
   closed.add(arg);events.append('osc close')
  elif a==0x29f20:ret=1
  elif a==0x29f00:ret=0
  elif a==0x7a10:
   if arg==L+0x3648:quietheld=True;events.append('quiet lock')
   else:assert arg==L+0x365c;events.append('osc lock')
  elif a==0x79a0:
   if arg==L+0x3648:assert quietheld;quietheld=False;events.append('quiet unlock')
   else:assert arg==L+0x365c;events.append('osc unlock')
  elif a==0x7640:
   if arg==L+0x3650:
    assert quietheld
    mask=int.from_bytes(uc.mem_read(L+0x3644,4),'little');assert mask==expected and expected
    if not requests:requests.append(mask)
    waits+=1;events.append('quiet wait')
    if waits>spurious:
     put(L+0x3644,0);events.append('ack')
     for v in chosen:put(E+0x6c+v*16,0);put(E+0x22+v,0,1);put(L+0x190+v*8,-1)
   else:
    assert arg==L+0x3664;put(L+0x3658,0);events.append('osc ack')
  for r in VOL:uc.reg_write(r,0xdead0000+r)
  uc.reg_write(UC_X86_REG_RAX,ret)
 u.hook_add(UC_HOOK_CODE,hook)
 # Stop before fresh activation. Oscillator mocks may still be open after fake quiet ack
 # to exercise stock close/wait/retry paths; this is deliberately not realistic DSP timing.
 u.emu_start(0x21399,0x215d5,count=200000)
 assert u.reg_read(UC_X86_REG_RIP)==0x215d5
 assert u.reg_read(UC_X86_REG_RSP)==rsp and u.reg_read(UC_X86_REG_RBP)==rbp and u.reg_read(UC_X86_REG_R15)==L
 assert not quietheld
 assert int.from_bytes(u.mem_read(rbp-0x814,4),'little')==expected
 assert requests==([expected] if expected else [])
 assert waits==(spurious+1 if expected else 0)
 assert bytes(u.mem_read(rbp-0x817,1))==b'\x01'
 return events
cases=0
for parts,lo,hi,limit in [([0]*32,0,8,1),([0]*32,0,8,8),([0]*32,0,32,32),([0,1]*16,0,32,8),([1]*16+[0]*16,16,32,8),([1]*31+[0],0,32,1),([0]*32,0,8,0),([1]*32,0,32,8)]:
 for wakes in [0,2]:case(parts,lo,hi,limit,spurious=wakes);cases+=1
case([0]*32,0,8,8,retrigger=False,external=True);cases+=1
case([0]*32,0,8,8,retrigger=False,external=False);cases+=1
print(f'PASS: {cases} complete stock selection-loop cases with batch hooks; three hook-site byte checks.')
print('One quiet request per selected group, selection limits/parts, voice 31, empty groups, retained external gate, spurious wakeups, close ordering, oscillator wait/retry and stack preservation.')
print('Mocked QNX/scheduler behavior; no real coordinator, DSP, CV or analog hardware validation.')

if INTEGRATED:print('Installed candidate tested: code and integration branches loaded from candidate ELF; no hook overlays.')
