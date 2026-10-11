from pathlib import Path
import struct,json
from unicorn import *
from unicorn import mips_const as mr
b=Path('pic.bin').read_bytes();u=Uc(UC_ARCH_MIPS,UC_MODE_MIPS32|UC_MODE_LITTLE_ENDIAN)
u.mem_map(0x1d000000,0x90000);u.mem_write(0x1d000000,b);u.mem_map(0,0x100000);u.mem_map(0x1f810000,0x1000)
STOP=0x9d0817f0;end=STOP;writes=[]
def get(a):return struct.unpack('<I',u.mem_read(a&0x1fffffff,4))[0]
def hook(uc,pc,size,data):
 if pc==end:uc.emu_stop()
def write(uc,access,address,size,value,data):
 if 0x1f810000<=address<0x1f811000:writes.append({'pc':hex(uc.reg_read(mr.UC_MIPS_REG_PC)),'address':hex(address|0xa0000000),'value':hex(value)})
u.hook_add(UC_HOOK_CODE,hook);u.hook_add(UC_HOOK_MEM_WRITE,write)
driver=0x8003a27c
for r,v in [(mr.UC_MIPS_REG_A0,0),(mr.UC_MIPS_REG_A1,0x9d07f2a8),(mr.UC_MIPS_REG_RA,STOP)]:u.reg_write(r,v)
u.emu_start(0x9d07a720,STOP,count=1000)
assert get(driver+0x64)==132 and get(driver+0x68)==133 and get(driver+0x60)==1
u.reg_write(mr.UC_MIPS_REG_S0,0xbf810140);u.reg_write(mr.UC_MIPS_REG_S2,0x80030000)
end=0x9d06bff8;u.emu_start(0x9d06bfc4,STOP,count=100)
assert get(0xbf810350)==0x1010
for start,end in [(0x9d07aba4,0x9d07abcc),(0x9d07ac24,0x9d07ac50)]:
 u.reg_write(mr.UC_MIPS_REG_S0,driver);u.emu_start(start,STOP,count=100)
assert [(w['address'],w['value']) for w in writes[-2:]]==[('0xbf810084','0x10'),('0xbf810084','0x20')]
r={'configuration':'0x9d07f2a8','driver':hex(driver),'controller_indices':[get(driver+0x64),get(driver+0x68)],'priority_field_register':'0xbf810350','priority_field_word':hex(get(0xbf810350)),'writes':writes,'limitations':'Complete simple driver initialization plus isolated priority and controller-clear segments. Plain mapped MMIO; no real USB interrupt, device-specific register-map confirmation or global stack bound.'}
Path('branch4/usb_controller_init_results.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))
