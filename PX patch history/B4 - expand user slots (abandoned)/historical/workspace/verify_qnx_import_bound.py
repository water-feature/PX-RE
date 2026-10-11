from pathlib import Path
from elftools.elf.elffile import ELFFile
from unicorn import *
from unicorn.x86_const import *
import struct,json
u=Uc(UC_ARCH_X86,UC_MODE_64)
with open('stock.elf','rb') as f:
 e=ELFFile(f)
 for seg in e.iter_segments():
  if seg['p_type']!='PT_LOAD':continue
  start=seg['p_vaddr']&~4095;end=(seg['p_vaddr']+seg['p_memsz']+4095)&~4095
  u.mem_map(start,end-start);u.mem_write(seg['p_vaddr'],seg.data())
u.mem_map(0x70000000,0x20000);u.mem_map(0x71000000,0x10000);u.mem_map(0x72000000,4096)
STOP=0x72000000
# External libc semantics only; QNX validator instructions and tables are stock.
def cstr(a):
 out=bytearray()
 while True:
  v=bytes(u.mem_read(a+len(out),1))[0]
  if not v:return bytes(out)
  out.append(v)
def hook(uc,pc,size,data):
 if pc not in [0x74e0,0x74f0,0x73a0]:return
 a=uc.reg_read(UC_X86_REG_RDI);b=uc.reg_read(UC_X86_REG_RSI)
 if pc==0x74e0:uc.mem_write(a,cstr(b)+b'\0');ret=a
 elif pc==0x74f0:
  s=cstr(a);idx=(s+b'\0').rfind(bytes([b&255]));ret=0 if idx<0 else a+idx
 else:
  x=cstr(a);y=cstr(b);ret=(x>y)-(x<y)
 sp=uc.reg_read(UC_X86_REG_RSP);ra=struct.unpack('<Q',bytes(uc.mem_read(sp,8)))[0]
 uc.reg_write(UC_X86_REG_RAX,ret&0xffffffffffffffff);uc.reg_write(UC_X86_REG_RSP,sp+8);uc.reg_write(UC_X86_REG_RIP,ra)
u.hook_add(UC_HOOK_CODE,hook)
results=[]
for groups in [65,97]:
 # LEA r12,[r15+groups*8] displacement only, in emulator memory.
 u.mem_write(0x1542d,struct.pack('<I',groups*8));u.ctl_flush_tb()
 for group in ['u00','u07','p00','p31','u08','u31','u32','u63','u64','u99','x00']:
  u.mem_write(0x71000000,f'/fs/usb0/px/{group}/01 Ambience/test.zip\0'.encode());u.mem_write(0x71001000,group.encode()+b'\0')
  sp=0x7001fff0;u.mem_write(sp,struct.pack('<Q',STOP));u.reg_write(UC_X86_REG_RSP,sp)
  for reg,val in [(UC_X86_REG_RDI,0x71000000),(UC_X86_REG_RSI,0x71001000),(UC_X86_REG_RDX,0),(UC_X86_REG_RCX,0),(UC_X86_REG_R8,0)]:u.reg_write(reg,val)
  u.emu_start(0x15350,STOP,count=100000);assert u.reg_read(UC_X86_REG_RIP)==STOP
  result=u.reg_read(UC_X86_REG_RAX)&0xffffffff
  expected=group in ['u00','u07','p00','p31','u08','u31'] or (groups==97 and group in ['u32','u63'])
  assert bool(result)==expected,(groups,group,result)
  results.append({'groups_scanned':groups,'folder':group,'accepted':bool(result)})
Path('branch4/qnx_import_bound_results.json').write_text(json.dumps(results,indent=2)+'\n')
print('PASS: actual QNX validator, stock65 and hypothetical97-group endpoints, 22 cases')
