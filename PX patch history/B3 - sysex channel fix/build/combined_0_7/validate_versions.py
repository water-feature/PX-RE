from pathlib import Path
import struct,json
from unicorn import *
from unicorn.x86_const import *
from unicorn.mips_const import *
b=Path(__file__).with_name('PxUpdate_V2.2.2.0.7.bin').read_bytes()
elf=b[13:13+1039304];pic=b[2621061:2621061+530784]
def x86():
 u=Uc(UC_ARCH_X86,UC_MODE_64);u.mem_map(0,0x400000);u.mem_write(0,elf[:0x9d480]);u.mem_map(0x11000000,0x30000);return u
# Actual application reply block; mock only virtual transport output.
u=x86();frame=0x11008000;obj=0x11010000;transport=0x11018000;vtable=0x11019000;send=0x11020000
u.reg_write(UC_X86_REG_RBP,frame);u.reg_write(UC_X86_REG_RSP,frame-0x1000);u.reg_write(UC_X86_REG_R15,obj)
u.mem_write(obj+0x1ff0,struct.pack('<Q',transport));u.mem_write(transport,struct.pack('<Q',vtable));u.mem_write(vtable+0x10,struct.pack('<Q',send));u.mem_write(send,b'\xc3');sent=[]
def capture(e,a,s,d):sent.append(struct.unpack('<I',e.mem_read(e.reg_read(UC_X86_REG_RSI),4))[0])
u.hook_add(UC_HOOK_CODE,capture,begin=send,end=send);u.emu_start(0x1f4bb,0x1e453,count=1000);assert sent==[0x40139207]
# Actual application version gate for stock, dummy/prior voice, current voice and combined.
gates=[]
for version,skip in [([2,2,2,0,0],False),([2,2,2,0,1],False),([2,2,2,0,2],False),([2,2,2,0,7],True)]:
 u=x86();u.reg_write(UC_X86_REG_RBP,frame);u.reg_write(UC_X86_REG_R15,obj);u.mem_write(frame-0x590,bytes(version));u.emu_start(0x24f21,0x24f39,count=1000)
 flag=struct.unpack('<I',u.mem_read(obj+0x373c,4))[0];assert flag==int(not skip);gates.append({'incoming':version,'skip':skip})
# Actual PIC setter, followed by actual PIC version-display argument extraction and formatter.
m=Uc(UC_ARCH_MIPS,UC_MODE_MIPS32|UC_MODE_LITTLE_ENDIAN);m.mem_map(0x1d000000,0x90000);m.mem_write(0x1d000000,pic);m.mem_map(0,0x80000)
stop=0x9d001200;sp=0x80070000;m.reg_write(UC_MIPS_REG_SP,sp);m.reg_write(UC_MIPS_REG_RA,stop);m.reg_write(UC_MIPS_REG_A0,sent[0]&65535)
# Persistence request is outside the version formatting test. Setter executes its actual stores.
m.mem_write(0x1d042634,struct.pack('<II',0x03e00008,0));m.emu_start(0x9d031bdc,stop,count=1000)
assert struct.unpack('<I',m.mem_read(0x10704,4))[0]==0x9207
assert struct.unpack('<I',m.mem_read(0x52f20,4))[0]==0x9207
m.reg_write(UC_MIPS_REG_S2,0x800106f4);m.reg_write(UC_MIPS_REG_S4,0x9d080000);
args=[]
def fmtargs(e,a,s,d):
 args.append([e.reg_read(UC_MIPS_REG_A3)]+[struct.unpack('<I',e.mem_read((sp&0x1fffffff)+i,4))[0] for i in [0x10,0x14,0x18,0x1c]])
m.hook_add(UC_HOOK_CODE,fmtargs,begin=0x9d08127c,end=0x9d08127c)
m.emu_start(0x9d052fd8,0x9d053034,count=1000000)
assert args==[[2,3,0,0,0],[2,2,2,0,7]]
text=bytes(m.mem_read((sp&0x1fffffff)+0x20,100)).split(b'\0')[0].decode();assert text=='M: 2.2.3, DSP: 2.2.2.0.7'

print(json.dumps({'screen':text,'gate_cases':gates,'status':'PASS'}))
