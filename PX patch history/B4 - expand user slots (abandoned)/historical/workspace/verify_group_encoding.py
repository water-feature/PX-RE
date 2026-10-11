from pathlib import Path
import struct,json
from unicorn import Uc,UC_ARCH_MIPS,UC_MODE_MIPS32,UC_MODE_LITTLE_ENDIAN,UC_HOOK_CODE
from unicorn.mips_const import *
BASE=0x9d000000; STOP=0x9d081900; PARAM=0x8000046c; GP=0x80080000
b=Path('pic.bin').read_bytes()
u=Uc(UC_ARCH_MIPS,UC_MODE_MIPS32|UC_MODE_LITTLE_ENDIAN)
u.mem_map(0x1d000000,0x90000);u.mem_write(0x1d000000,b);u.mem_map(0,0x100000)
def phys(p): return p&0x1fffffff
def wr(p,data):u.mem_write(phys(p),data)
def rd(p,n):return bytes(u.mem_read(phys(p),n))
def h(p,x):wr(p,struct.pack('<H',x))
def run(pc,args=(),limit=200000):
 u.reg_write(UC_MIPS_REG_SP,0x800f0000);u.reg_write(UC_MIPS_REG_RA,STOP);u.reg_write(UC_MIPS_REG_GP,GP)
 for r,a in zip([UC_MIPS_REG_A0,UC_MIPS_REG_A1,UC_MIPS_REG_A2,UC_MIPS_REG_A3],args):u.reg_write(r,a)
 u.emu_start(pc,STOP,count=limit)
 assert u.reg_read(UC_MIPS_REG_PC)==STOP,hex(u.reg_read(UC_MIPS_REG_PC))
 return u.reg_read(UC_MIPS_REG_V0)
# Unicorn does not implement PIC's DSP indexed byte load. Execute only those two
# instructions with their documented byte-load semantics; all other code is stock.
def indexed(uc,address,size,data):
 if address in [0x9d07889c,0x9d0788f0]:
  reg=UC_MIPS_REG_V0 if address==0x9d07889c else UC_MIPS_REG_A2
  addr=uc.reg_read(reg)+uc.reg_read(UC_MIPS_REG_T2)
  uc.reg_write(reg,rd(addr,1)[0]);uc.reg_write(UC_MIPS_REG_PC,address+4)
u.hook_add(UC_HOOK_CODE,indexed)
res={'limiter':{},'byte_roundtrips':0,'sanitizer':{}}
for maximum in [64,96,132]:
 for p in [0x22,0x63]:h(0x9d047498+12*p,maximum)
 for p in [0x22,0x63]:
  for val in [0,1,8,9,40,41,64,65,96,97,127,128,132,133,255]:
   got=run(0x9d04d4fc,[0,p,val]);assert got==min(val,maximum)
  res['limiter'][f'{maximum}:{p}']='PASS'
 # Bulk preset sanitizer changes above-limit values to DEFAULT, not to maximum.
 for val in [0,64,65,96,97,127,128,132,133,255]:
  wr(PARAM,bytes(2*0x6b7*2))
  for part in [0,1]:
   for p in [0x22,0x63]:h(PARAM+2*(part*0x6b7+p),val)
  run(0x9d04d6d4)
  expect=val if val<=maximum else 0
  for part in [0,1]:
   for p in [0x22,0x63]:assert struct.unpack('<H',rd(PARAM+2*(part*0x6b7+p),2))[0]==expect
 res['sanitizer'][str(maximum)]='PASS'
# Actual getter returns full halfword. Byte storage takes low byte downstream.
for val in [65,96,127,128,132,255]:
 for part in [0,1]:
  for p in [0x22,0x63]:
   h(PARAM+2*(part*0x6b7+p),val);assert run(0x9d04d300,[part,p])==val
# Actual SysEx packer and decoder, all 256 byte values in all seven positions.
for val in range(256):
 raw=bytes((val+37*i)&255 for i in range(7))
 wr(0x80090000,b'\0'+raw);run(0x9d078830,[0x80090000]);packed=rd(0x80090000,8)
 assert all(x<128 for x in packed)
 wr(0x80022b34,packed);h(GP-0x7cd8,0)
 run(0x9d078878,[0x80091000,7]);assert rd(0x80091000,7)==raw
 res['byte_roundtrips']+=1
# Restore stock metadata inside emulator. No modified file emitted.
u.mem_write(0x1d000000,b)
Path('branch4/group_encoding_results.json').write_text(json.dumps(res,indent=2)+'\n')
print(json.dumps(res))
