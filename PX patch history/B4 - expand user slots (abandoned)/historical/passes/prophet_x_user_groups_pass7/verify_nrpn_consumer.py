# SPDX-License-Identifier: GPL-2.0-or-later
from pathlib import Path
import json,struct
from unicorn import *
from unicorn.mips_const import *
u=Uc(UC_ARCH_MIPS,UC_MODE_MIPS32|UC_MODE_LITTLE_ENDIAN);u.mem_map(0x1d000000,0x90000);u.mem_write(0x1d000000,Path('pic.bin').read_bytes());u.mem_map(0,0x100000)
STOP=0x9d0817f0;captured=[]
def wr(a,b):u.mem_write(a&0x1fffffff,b)
def hook(uc,pc,size,data):
 if pc==0x9d04dacc:
  captured.append([uc.reg_read(r) for r in [UC_MIPS_REG_A0,UC_MIPS_REG_A1,UC_MIPS_REG_A2,UC_MIPS_REG_A3]]);uc.emu_stop()
u.hook_add(UC_HOOK_CODE,hook)
results=[]
for maximum in [64,96,132]:
 for p in [0x22,0x63]:
  wr(0x9d047498+p*12,struct.pack('<H',maximum))
  for part in [0,1]:
   for current in [0,64,65,96,132]:
    wr(0x8000046c+(p+part*0x6b7)*2,struct.pack('<H',current))
    for value in [65,96,132,0xffff,0xfff3]:
     wr(0x80060006,struct.pack('<HH',p+part*0x800,value));captured.clear()
     u.reg_write(UC_MIPS_REG_S1,0x80060000);u.reg_write(UC_MIPS_REG_GP,0x80007ff0);u.reg_write(UC_MIPS_REG_SP,0x8007f000);u.reg_write(UC_MIPS_REG_RA,STOP)
     u.emu_start(0x9d02ce14,STOP,count=10000)
     expected=value if value<0xfff3 else max(0,min(maximum,current+(1 if value==0xffff else -1)))
     assert captured==[[1,part,p,expected]],(maximum,p,part,current,value,captured,expected)
     results.append({'max':maximum,'parameter':hex(p),'part':part,'current':current,'message_value':hex(value),'setter_value':expected})
Path('branch4/nrpn_consumer_results.json').write_text(json.dumps(results,indent=2)+'\n')
print('PASS: 300 actual consumer/mapping/relative-helper cases captured at setter boundary')
