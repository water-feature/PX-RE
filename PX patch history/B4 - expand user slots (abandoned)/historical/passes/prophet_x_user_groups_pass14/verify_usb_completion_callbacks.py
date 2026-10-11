from pathlib import Path
import struct,json
from unicorn import *
from unicorn import mips_const as mr
b=Path('pic.bin').read_bytes();u=Uc(UC_ARCH_MIPS,UC_MODE_MIPS32|UC_MODE_LITTLE_ENDIAN)
u.mem_map(0x1d000000,0x90000);u.mem_write(0x1d000000,b);u.mem_map(0,0x100000)
STOP=0x9d0817f0;end=STOP;events=[]
def put(a,v):u.mem_write(a&0x1fffffff,struct.pack('<I',v))
def get(a):return struct.unpack('<I',u.mem_read(a&0x1fffffff,4))[0]
def hook(uc,pc,size,data):
 if pc==end:uc.emu_stop();return
 if pc==0x9d06bda0:
  arg=uc.reg_read(mr.UC_MIPS_REG_A1)
  events.append({'event':uc.reg_read(mr.UC_MIPS_REG_A0),'packet':[get(arg+off) for off in [0,4,8]],'context':uc.reg_read(mr.UC_MIPS_REG_A2)})
 if pc==0x9d06bdb8:
  address=uc.reg_read(mr.UC_MIPS_REG_V0)+uc.reg_read(mr.UC_MIPS_REG_A0)
  uc.reg_write(mr.UC_MIPS_REG_A0,get(address));uc.reg_write(mr.UC_MIPS_REG_PC,pc+4)
u.hook_add(UC_HOOK_CODE,hook)
parent=0x800536bc;request=0x8003a33c;sp=0x8007f000;gp=0x80007ff0;results=[]
for start,target in [(0x9d07ba7c,0x9d07b860),(0x9d07bc1c,0x9d07b8fc)]:
 for index in [0,1]:
  slot=request+index*36;u.mem_write(request&0x1fffffff,b'\0'*80)
  for r,v in [(mr.UC_MIPS_REG_A0,request),(mr.UC_MIPS_REG_V0,index),(mr.UC_MIPS_REG_S0,parent),(mr.UC_MIPS_REG_S4,0x80031000),(mr.UC_MIPS_REG_SP,sp)]:u.reg_write(r,v)
  put(sp+0x38,123);put(sp+0x3c,0x80031100)
  end=0x9d07bab0 if target==0x9d07b860 else 0x9d07bc48
  u.emu_start(start,STOP,count=100)
  assert get(slot+0xc)==target and get(slot+0x14)==parent
  results.append({'kind':'registration segment','callback':hex(target),'slot_index':index,'slot_bytes':36})
# Install documented registration target and simulate transfer completion statuses.
put(parent+0xdc,0x9d06bda0);put(parent+0xe0,0);u.mem_write((parent+0x14)&0x1fffffff,b'\0\0')
for callback,event,counter_off,flag in [(0x9d07b860,16,6,0x10),(0x9d07b8fc,15,4,0x11)]:
 for status,expected in [(0,0),(1,0),(-3,-0x62),(-4,-0x61),(2,-0x60)]:
  put(request+0x14,parent);put(request+8,status&0xffffffff);put(request+4,123)
  u.mem_write((gp-0x7b98+counter_off)&0x1fffffff,struct.pack('<H',5))
  u.mem_write((0x8002ab34+flag)&0x1fffffff,b'\x01')
  for r,v in [(mr.UC_MIPS_REG_A0,request),(mr.UC_MIPS_REG_SP,sp),(mr.UC_MIPS_REG_GP,gp),(mr.UC_MIPS_REG_RA,STOP)]:u.reg_write(r,v)
  end=STOP;events.clear();u.emu_start(callback,STOP,count=1000)
  assert events==[{'event':event,'packet':[request,123,expected&0xffffffff],'context':0}],events
  assert bytes(u.mem_read((0x8002ab34+flag)&0x1fffffff,1))==b'\0'
  assert int.from_bytes(u.mem_read((gp-0x7b98+counter_off)&0x1fffffff,2),'little')==4
  assert u.reg_read(mr.UC_MIPS_REG_SP)==sp
  results.append({'kind':'completion execution','callback':hex(callback),'status':status,'event':event,'mapped_status':expected,'pending_flag_cleared':True,'stack_restored':True})
# Verify DINIT source of driver vtable and bounded event dispatch.
dest,n,copy=struct.unpack_from('<III',b,0x1a3e4)
assert (dest,n,copy)==(0x800538e0,80,1)
vtable=struct.unpack_from('<20I',b,0x1a3f0)
targets=struct.unpack_from('<17I',b,0x6bdc4)
assert targets[15]==0x9d06be10 and targets[16]==0x9d06bf0c
assert all(0x9d000000<=t<0x9d000000+len(b) and t%4==0 for t in targets)
Path('branch4/usb_completion_results.json').write_text(json.dumps({'cases':results,'vtable_ram':hex(dest),'vtable_source':'0x9d01a3f0','vtable':[hex(v) for v in vtable],'bounded_event_table':[hex(v) for v in targets],'limitations':'Four registration segments and ten callback executions using synthetic RAM objects. Event indexed load explicitly emulated. No transfer queue, real USB hardware, exhaustive callback-writer/alias proof or global stack bound.'},indent=2)+'\n')
print('PASS: four registration segments, ten completion executions; actual registered event targets clear flags without further calls')
