# SPDX-License-Identifier: GPL-2.0-or-later
from pathlib import Path
import json,struct
from unicorn import *
from unicorn.mips_const import *
u=Uc(UC_ARCH_MIPS,UC_MODE_MIPS32|UC_MODE_LITTLE_ENDIAN);u.mem_map(0x1d000000,0x90000);u.mem_write(0x1d000000,Path('pic.bin').read_bytes());u.mem_map(0,0x100000)
GP=0x80007ff0;STOP=0x9d0817f0;messages=[]
def hook(uc,pc,size,data):
 if pc==0x9d04d780:
  a=uc.reg_read(UC_MIPS_REG_A0);uc.reg_write(UC_MIPS_REG_V0,2 if a==5 else 0);uc.reg_write(UC_MIPS_REG_PC,uc.reg_read(UC_MIPS_REG_RA))
 if pc==0x9d07dc58:
  messages.append([uc.reg_read(r) for r in [UC_MIPS_REG_A0,UC_MIPS_REG_A1,UC_MIPS_REG_A2,UC_MIPS_REG_A3]]);uc.emu_stop()
 if pc in [0x9d05db38,0x9d05db3c]:uc.emu_stop()
u.hook_add(UC_HOOK_CODE,hook)
results=[]
for param in [0x22,0x63,0x822,0x863]:
 for value in [0,64,65,96,127,128,132,255]:
  u.mem_write(0x152,b'\0\0');u.reg_write(UC_MIPS_REG_GP,GP);u.reg_write(UC_MIPS_REG_SP,0x8007f000);u.reg_write(UC_MIPS_REG_RA,STOP)
  for r,a in [(UC_MIPS_REG_A0,0),(UC_MIPS_REG_A1,0),(UC_MIPS_REG_A2,param),(UC_MIPS_REG_A3,value)]:u.reg_write(r,a)
  u.emu_start(0x9d05e9ec,STOP,count=10000);assert u.reg_read(UC_MIPS_REG_PC)==STOP
  raw=bytes(u.mem_read(0x12a10,12));assert raw==bytes([0xb0,99,param>>7,0xb0,98,param&127,0xb0,6,value>>7,0xb0,38,value&127])
  u.mem_write((GP-0x7ec8)&0x1fffffff,b'\0\0');u.mem_write((GP-0x7ece)&0x1fffffff,b'\0\0');messages.clear()
  for pos in [0,3,6,9]:
   u.reg_write(UC_MIPS_REG_A2,raw[pos+1]);u.reg_write(UC_MIPS_REG_T1,raw[pos+2]);u.emu_start(0x9d05dcb8,STOP,count=1000)
  assert messages[-1]==[0xfd,0,param,value],messages
  results.append({'parameter':hex(param),'value':value,'bytes':raw.hex(),'received_value':messages[-1][3]})
Path('branch4/nrpn_results.json').write_text(json.dumps(results,indent=2)+'\n');print('PASS: 32 actual sender and controller-dispatch round trips; queue consumer not tested')
