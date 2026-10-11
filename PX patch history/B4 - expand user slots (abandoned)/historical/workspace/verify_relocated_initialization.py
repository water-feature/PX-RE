from pathlib import Path
import struct,json
from unicorn import *
from unicorn.mips_const import *
u=Uc(UC_ARCH_MIPS,UC_MODE_MIPS32|UC_MODE_LITTLE_ENDIAN);u.mem_map(0x1d000000,0x90000);u.mem_write(0x1d000000,Path('pic.bin').read_bytes());u.mem_map(0,0x100000)
BASE=0x80058000;SIZE=97*17*8;STOP=0x9d0817f0;fixture={};reads=[]
def wr(a,b):u.mem_write(a&0x1fffffff,b)
def patch(pc,imm):
 old=struct.unpack('<I',bytes(u.mem_read(pc&0x1fffffff,4)))[0];wr(pc,struct.pack('<I',(old&0xffff0000)|imm))
for pc,imm in [(0x9d040eec,0x8006),(0x9d040ef0,0x8000),(0x9d040f40,0x8000),(0x9d040f44,0x8000),(0x9d041038,0x8000),(0x9d041044,96),(0x9d040fc8,97),(0x9d040fd0,SIZE),(0x9d0792f0,0x8006),(0x9d0792f4,0x8000),(0x9d07930c,0x8006),(0x9d079310,0x8000)]:patch(pc,imm)
u.ctl_flush_tb()
def hook(uc,pc,size,data):
 if pc in [0x9d0792f8,0x9d079324]:
  base=uc.reg_read(UC_MIPS_REG_V1 if pc==0x9d0792f8 else UC_MIPS_REG_A2);index=uc.reg_read(UC_MIPS_REG_V0 if pc==0x9d0792f8 else UC_MIPS_REG_V1)
  value=struct.unpack('<I',bytes(uc.mem_read((base+index)&0x1fffffff,4)))[0];uc.reg_write(UC_MIPS_REG_V0 if pc==0x9d0792f8 else UC_MIPS_REG_A0,value);uc.reg_write(UC_MIPS_REG_PC,uc.reg_read(UC_MIPS_REG_RA) if pc==0x9d0792f8 else pc+4)
  return
 if pc==0x9d040a4c:
  a=uc.reg_read(UC_MIPS_REG_A0);reads.append(a);v=255 if fixture['extended'] and a==0x5fd000 else fixture['count']
  uc.reg_write(UC_MIPS_REG_V0,v);uc.reg_write(UC_MIPS_REG_PC,uc.reg_read(UC_MIPS_REG_RA))
u.hook_add(UC_HOOK_CODE,hook)
def run(pc,args=()):
 u.reg_write(UC_MIPS_REG_SP,0x8007f000);u.reg_write(UC_MIPS_REG_GP,0x80007ff0);u.reg_write(UC_MIPS_REG_RA,STOP)
 for r,v in zip([UC_MIPS_REG_A0,UC_MIPS_REG_A1],args):u.reg_write(r,v)
 u.emu_start(pc,STOP,count=1000000);assert u.reg_read(UC_MIPS_REG_PC)==STOP
 return u.reg_read(UC_MIPS_REG_V0)
results=[]
for extended,count in [(False,0),(False,1),(True,0),(True,1),(True,255)]:
 fixture.update(extended=extended,count=count);reads.clear();wr(BASE-4,b'ABCD');wr(BASE+SIZE,b'EFGH');wr(0x80037e90,b'OLD!')
 run(0x9d040ed8)
 entries=[struct.unpack('<II',bytes(u.mem_read((BASE&0x1fffffff)+i*8,8))) for i in range(97*17)]
 active=(97 if extended else 41)*17
 for i,(n,idx) in enumerate(entries):
  assert n==(count+1 if i<active else 1)
  assert idx==(i*(count+1) if i<active and count else 0xffffffff)
 assert bytes(u.mem_read((BASE-4)&0x1fffffff,4))==b'ABCD' and bytes(u.mem_read((BASE+SIZE)&0x1fffffff,4))==b'EFGH'
 assert bytes(u.mem_read(0x37e90,4))==b'OLD!'
 for group in [0,40,41,64,65,96]:
  assert run(0x9d0792e0,[group,16])==entries[group*17+16][0]
  assert run(0x9d079300,[group])==(17*count if group<(97 if extended else 41) else 0)
 results.append({'extended':extended,'instrument_count':count,'initialized_groups':97,'serial_reads':len(reads),'boundary_canaries_preserved':True,'old_base_untouched':True})
Path('branch4/relocated_initialization_results.json').write_text(json.dumps(results,indent=2)+'\n');print('PASS: five relocated initializer fixtures and both getter paths; RAM ownership NOT proven')
