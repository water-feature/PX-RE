from pathlib import Path
import json,struct
from unicorn import Uc,UC_ARCH_MIPS,UC_MODE_MIPS32,UC_MODE_LITTLE_ENDIAN
from unicorn.mips_const import *
b=Path('pic.bin').read_bytes()
u=Uc(UC_ARCH_MIPS,UC_MODE_MIPS32|UC_MODE_LITTLE_ENDIAN)
u.mem_map(0x1d000000,0x90000);u.mem_write(0x1d000000,b);u.mem_map(0,0x100000)
def put(a,v):u.mem_write(a&0x1fffffff,struct.pack('<I',v))
def get(a):return struct.unpack('<I',u.mem_read(a&0x1fffffff,4))[0]
parent=0x800539b8;handle=parent+0x24;sp=0x8007f000;arg=0x80053810;cb=0x9d074f0c
put(handle,parent);put(handle+8,1);put(parent+0x1c,1);put(sp+0x10,cb)
for r,v in [(UC_MIPS_REG_SP,sp),(UC_MIPS_REG_A0,handle),(UC_MIPS_REG_A1,100),(UC_MIPS_REG_A2,1),(UC_MIPS_REG_A3,arg)]:u.reg_write(r,v)
u.emu_start(0x9d05c4e4,0x9d05c550,count=100)
assert get(parent+0x34)==cb and get(parent+0x38)==arg
cases=[]
for old,new in [(0,1),(12,12),(12,13),(12,0),(0xffffffff,0)]:
 put(arg+0x14,old);put(arg+0x1c,7);put(arg+0x28,0)
 u.reg_write(UC_MIPS_REG_A0,arg);u.reg_write(UC_MIPS_REG_A1,new);u.reg_write(UC_MIPS_REG_RA,0x9d0817f0);u.reg_write(UC_MIPS_REG_SP,sp)
 u.emu_start(cb,0x9d0817f0,count=100)
 assert get(arg+0x14)==new and get(arg+0x1c)==7+(new<old)
 assert bytes(u.mem_read((arg+0x28)&0x1fffffff,1))==b'\x01'
 assert u.reg_read(UC_MIPS_REG_SP)==sp
 cases.append({'previous':old,'incoming':new,'wrap_counter':get(arg+0x1c),'stack_unchanged':True})
refs={}
for target in [0x9d05c4e4,0x9d05c764,0x9d05c76c]:
 direct=[];literal=[]
 for i in range(0,len(b)-3,4):
  w=struct.unpack_from('<I',b,i)[0];pc=0x9d000000+i
  if w>>26 in (2,3) and ((pc+4)&0xf0000000)|((w&0x3ffffff)<<2)==target:direct.append(hex(pc))
  if w==target:literal.append(hex(pc))
 refs[hex(target)]={'raw_direct_jump_call_candidates':direct,'aligned_literal_pointer_candidates':literal}
result={'registration_prefix_executed_to':'0x9d05c550','target':hex(cb),'parent_target_offset':'0x34','parent_argument_offset':'0x38','references':refs,'leaf_callback_cases':cases,'limitations':'Registration prefix and callback leaf only; no MMIO execution, whole IRQ transaction, exhaustive alias proof or stack bound.'}
Path('branch4/timer_callback_results.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
