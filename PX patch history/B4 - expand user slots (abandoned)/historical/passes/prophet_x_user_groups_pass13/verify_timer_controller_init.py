from pathlib import Path
import json,struct
from unicorn import Uc,UC_ARCH_MIPS,UC_MODE_MIPS32,UC_MODE_LITTLE_ENDIAN,UC_HOOK_CODE,UC_HOOK_MEM_WRITE
from unicorn import mips_const as mr
b=Path('pic.bin').read_bytes()
u=Uc(UC_ARCH_MIPS,UC_MODE_MIPS32|UC_MODE_LITTLE_ENDIAN)
u.mem_map(0x1d000000,0x90000);u.mem_write(0x1d000000,b);u.mem_map(0,0x100000);u.mem_map(0x1f800000,0x80000)
mmio=[];substituted=[];segment_end=None
def read(a):return struct.unpack('<I',u.mem_read(a&0x1fffffff,4))[0]
def hook(uc,pc,size,data):
 if pc==segment_end:uc.emu_stop();return
 if pc==0x9d080f4c:
  addr=uc.reg_read(mr.UC_MIPS_REG_A0);n=uc.reg_read(mr.UC_MIPS_REG_A2);val=uc.reg_read(mr.UC_MIPS_REG_A1)&255
  uc.mem_write(addr&0x1fffffff,bytes([val])*n);uc.reg_write(mr.UC_MIPS_REG_V0,addr);uc.reg_write(mr.UC_MIPS_REG_PC,uc.reg_read(mr.UC_MIPS_REG_RA))
  substituted.append({'pc':hex(pc),'helper':'memset','bytes':n})
def write(uc,access,address,size,value,data):
 if 0x1f800000<=address<0x1f880000:mmio.append({'pc':hex(uc.reg_read(mr.UC_MIPS_REG_PC)),'address':hex(address|0xa0000000),'size':size,'value':hex(value)})
u.hook_add(UC_HOOK_CODE,hook);u.hook_add(UC_HOOK_MEM_WRITE,write)
u.reg_write(mr.UC_MIPS_REG_GP,0x80007ff0);u.reg_write(mr.UC_MIPS_REG_SP,0x8007f000)
# Execute caller and configuration-copy prefix; stop before peripheral helpers.
segment_end=0x9d05bad4
u.emu_start(0x9d06bf44,0x9d0817f0,count=10000)
assert u.reg_read(mr.UC_MIPS_REG_PC)==0x9d05bad4
parent=0x800539b8
fields={hex(off):hex(read(parent+off)) for off in [8,0xc,0x10,0x14,0x1c]}
assert read(parent+0xc)==3 and read(parent+0x14)==28 and read(parent+0x1c)==1
# Independently execute the caller's priority-field writes with supplied return value.
u.reg_write(mr.UC_MIPS_REG_V0,parent)
segment_end=0x9d06bfa4
u.emu_start(0x9d06bf68,0x9d0817f0,count=100)
assert (read(0xbf8101b0)&0x1f)==4 and read(0x80032b5c)==parent
# Execute controller address calculation and both stores; stop before dispatch.
u.reg_write(mr.UC_MIPS_REG_A0,parent+0x24);u.mem_write((parent+0x24)&0x1fffffff,struct.pack('<I',parent))
segment_end=0x9d05b5e0
u.emu_start(0x9d05b59c,0x9d0817f0,count=100)
assert mmio[-2]['address']=='0xbf810044' and mmio[-1]['address']=='0xbf8100c8'
assert all(int(x['value'],16)==0x10000000 for x in mmio[-2:])
result={'executed_segments':[['0x9d06bf44','0x9d05bad4'],['0x9d06bf68','0x9d06bfa4'],['0x9d05b59c','0x9d05b5e0']],'config':'0x9d07f2e0','config_words':[hex(v) for v in struct.unpack_from('<7I',b,0x7f2e0)],'copied_parent_fields':fields,'priority_register_low5':hex(read(0xbf8101b0)&31),'mmio_writes':mmio,'simulated_helpers':substituted,'object_bytes_cleared':60,'validator_aligned_offsets_accepted':[off for off in range(0,121,4) if ((-(off//4)*0x11111111)&0xffffffff)<2],'limitations':'Three separate instruction segments, not a complete initialization transaction. Memset substituted; peripheral configuration helpers not executed, their successful return supplied for priority segment. MMIO is plain memory without device alias semantics. No actual interrupts, exhaustive writer proof or global stack bound.'}
assert result['validator_aligned_offsets_accepted']==[0,60]
Path('branch4/timer_controller_init_results.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
