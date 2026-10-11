# SPDX-License-Identifier: GPL-2.0-or-later
from pathlib import Path
import json,struct
from unicorn import *
from unicorn import mips_const as mr
b=Path('pic.bin').read_bytes();u=Uc(UC_ARCH_MIPS,UC_MODE_MIPS32|UC_MODE_LITTLE_ENDIAN)
u.mem_map(0x1d000000,0x90000);u.mem_write(0x1d000000,b);u.mem_map(0,0x100000)
stop=0x9d0817f0
u.mem_write(0x538e0,b[0x1a3f0:0x1a440])
parent=0x800536bc;driver=0x8003a27c
put=lambda a,v:u.mem_write(a&0x1fffffff,struct.pack('<I',v))
get=lambda a:struct.unpack('<I',u.mem_read(a&0x1fffffff,4))[0]
put(parent+0xe8,0x800538e0);put(parent+0x18,driver)
u.mem_write((parent+0xd8)&0x1fffffff,b'\x01');u.mem_write((driver+1)&0x1fffffff,b'\x01')
for r,v in [(mr.UC_MIPS_REG_A0,parent),(mr.UC_MIPS_REG_A1,0x9d06bda0),(mr.UC_MIPS_REG_A2,0),(mr.UC_MIPS_REG_RA,stop)]:u.reg_write(r,v)
u.emu_start(0x9d066840,stop,count=100)
assert get(parent+0xdc)==0x9d06bda0 and get(parent+0xe0)==0
assert get(driver+0x88)==parent and get(driver+0x8c)==0x9d066ba8
# Decode the guard-bounded driver event table.
targets=struct.unpack_from('<9I',b,0x66bec)
assert all(0x9d000000<=t<0x9d000000+len(b) and t%4==0 for t in targets)
result={'executed_registration':'0x9d066840 -> vtable+8 -> 0x9d07ad3c','parent_callback':hex(get(parent+0xdc)),'parent_context':hex(get(parent+0xe0)),'driver_argument':hex(get(driver+0x88)),'driver_callback':hex(get(driver+0x8c)),'bounded_driver_events':[hex(t) for t in targets],'vtable_source':'DINIT 0x9d01a3f0 -> 0x800538e0','limitations':'Synthetic initialized parent and enabled driver objects; registration only. No real USB IRQ or exhaustive alias proof.'}
# Execute two forwarded driver events and one ignored event.
forwarded=[]
def hook(uc,pc,size,data):
 if pc==0x9d06bda0:forwarded.append(uc.reg_read(mr.UC_MIPS_REG_A0))
 if pc in [0x9d066be0,0x9d06bdb8]:
  if pc==0x9d066be0:
   addr=uc.reg_read(mr.UC_MIPS_REG_V0)+uc.reg_read(mr.UC_MIPS_REG_V1);dst=mr.UC_MIPS_REG_V0
  else:
   addr=uc.reg_read(mr.UC_MIPS_REG_A0)+uc.reg_read(mr.UC_MIPS_REG_V0);dst=mr.UC_MIPS_REG_A0
  uc.reg_write(dst,get(addr));uc.reg_write(mr.UC_MIPS_REG_PC,pc+4)
u.hook_add(UC_HOOK_CODE,hook);cases=[]
put(parent+4,1);put(parent+0xd4,1)
for event,initial,expected,forward in [(3,0x80,0,[3]),(4,0,0x80,[4]),(6,0x80,0x80,[])]:
 u.mem_write(parent&0x1fffffff,bytes([initial]));forwarded.clear()
 for r,v in [(mr.UC_MIPS_REG_A0,parent),(mr.UC_MIPS_REG_A1,event),(mr.UC_MIPS_REG_A2,0),(mr.UC_MIPS_REG_SP,0x8007f000),(mr.UC_MIPS_REG_RA,stop)]:u.reg_write(r,v)
 u.emu_start(0x9d066ba8,stop,count=1000)
 assert bytes(u.mem_read(parent&0x1fffffff,1))==bytes([expected]) and forwarded==forward
 assert u.reg_read(mr.UC_MIPS_REG_SP)==0x8007f000
 cases.append({'event':event,'parent_byte_before':initial,'parent_byte_after':expected,'forwarded_events':list(forwarded),'stack_restored':True})
result['event_cases']=cases
result['limitations']='Synthetic initialized objects; registration and events3/4/6 only. DSP indexed loads explicitly emulated. Reset event2 not executed. No real USB IRQ, exhaustive alias proof or global stack bound.'
Path('branch4/usb_event_registration_results.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
