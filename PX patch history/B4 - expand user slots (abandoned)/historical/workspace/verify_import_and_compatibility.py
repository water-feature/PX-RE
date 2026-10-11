# SPDX-License-Identifier: GPL-2.0-or-later
from pathlib import Path
import struct,json,hashlib
from unicorn import *
from unicorn.mips_const import *
stock=Path('inputs/PX RE/PxUpdate_V2.2.2.0.0.bin').read_bytes()
voice=Path('compatibility/voice_sysex/voice_sysex_2.2.2.0.3.bin').read_bytes()
assert hashlib.sha256(stock).hexdigest()=='a4b304b3bb48ca933ae63c99c0098698c497ebfc7c38ab2a823b5e0df4919fa9'
assert hashlib.sha256(voice).hexdigest()=='bbc3c2ad26bef7310fc15cac8edee22a1792d8ced3788f7080acccc047304857'
diffs=[i for i,(a,b) in enumerate(zip(stock,voice)) if a!=b];ranges=[]
for i in diffs:
 if ranges and i==ranges[-1][1]+1:ranges[-1][1]=i
 else:ranges.append([i,i])
picstart=0x273055;picend=0x2f49b5
picdiffs=[i-picstart for i in diffs if picstart<=i<picend]
knownsites=[0x47,0x22] # use explicit audited sites below, not these parameter numbers
sites=[0x47630,0x4793c,0x40eec,0x40ef0,0x40fc8,0x40fd0,0x41044,0x42d9c,0x42d64,0x80e2c,0x80e60,0x1b7c4,0x1b9b8,0x799a30,0x34288,0x1b8ec]
assert not any(s<=x<s+4 for s in sites for x in picdiffs)
b=Path('pic.bin').read_bytes();u=Uc(UC_ARCH_MIPS,UC_MODE_MIPS32|UC_MODE_LITTLE_ENDIAN);u.mem_map(0x1d000000,0x90000);u.mem_write(0x1d000000,b);u.mem_map(0,0x100000)
STOP=0x9d0817f0
def wr(a,b):u.mem_write(a&0x1fffffff,b)
def rd(a,n):return bytes(u.mem_read(a&0x1fffffff,n))
def run(pc,args=()):
 u.reg_write(UC_MIPS_REG_SP,0x8007f000);u.reg_write(UC_MIPS_REG_GP,0x80007ff0);u.reg_write(UC_MIPS_REG_RA,STOP)
 for reg,arg in zip([UC_MIPS_REG_A0,UC_MIPS_REG_A1,UC_MIPS_REG_A2],args):u.reg_write(reg,arg)
 u.emu_start(pc,STOP,count=2000000);assert u.reg_read(UC_MIPS_REG_PC)==STOP
 return u.reg_read(UC_MIPS_REG_V0)
for maxcursor in [63,95]:
 for cursor in range(maxcursor+1):
  for delta in [-1,1]:assert run(0x9d0816e0,[cursor,delta&0xffffffff,maxcursor])==max(0,min(maxcursor,cursor+delta))
# Actual sbrk boundary enforcement with initialized range; does not test malloc callers.
wr(0x80053a64,struct.pack('<I',0x80057ad0));wr(0x80053a68,struct.pack('<I',0x80057ae0));wr(0x80053a6c,struct.pack('<I',0x80053ae0))
assert run(0x9d080b98,[16])==0x80057ad0
assert run(0x9d080b98,[1])==0xffffffff
assert struct.unpack('<I',rd(0x80053a64,4))[0]==0x80057ae0
# Execute actual count/index initializer for stock layout, mocking serial byte reads.
reads=[];instrument_count=255
def hook(uc,pc,size,data):
 if pc==0x9d040a4c:
  addr=uc.reg_read(UC_MIPS_REG_A0);reads.append(addr)
  uc.reg_write(UC_MIPS_REG_V0,255 if addr==0x5fd000 else instrument_count)
  uc.reg_write(UC_MIPS_REG_PC,uc.reg_read(UC_MIPS_REG_RA))
h=u.hook_add(UC_HOOK_CODE,hook)
run(0x9d040ed8);u.hook_del(h)
entries=[struct.unpack('<II',rd(0x80037e90+i*8,8)) for i in range(65*17)]
assert all(count==256 for count,index in entries)
assert all(index==i*256 for i,(count,index) in enumerate(entries))
firstoutside=next((i,index) for i,(count,index) in enumerate(entries) if index>=65536)
assert firstoutside==(256,65536)
out={'stock_sha256':hashlib.sha256(stock).hexdigest(),'voice_sysex_sha256':hashlib.sha256(voice).hexdigest(),'changed_bytes':len(diffs),'changed_container_ranges_inclusive':[[hex(a),hex(b)] for a,b in ranges],'pic_changed_offsets':[hex(i) for i in picdiffs],'audited_group_instruction_sites_disjoint_from_voice_sysex':True,'audited_sites':[hex(0x9d000000+s) for s in sites],'import_cursor_clamp_test':'passed all +/- boundary cases for max63 and95','sbrk_configured_upper_bound':'passed exact-end allocation and overrun rejection','stock_count_initializer_first_outside_name_region':{'entry':256,'group':256//17,'category':256%17,'record_index':65536,'serial_address':hex(0xc00000+65536*64)},'last_stock_entry_record_index':entries[-1][1],'hardware_tested':False}
# Count-derived out-of-region index reaches actual reader without a capacity gate.
first_read=[]
def capture(uc,pc,size,data):
 if pc==0x9d040a4c:
  first_read.append(uc.reg_read(UC_MIPS_REG_A0));uc.emu_stop()
h=u.hook_add(UC_HOOK_CODE,capture)
u.reg_write(UC_MIPS_REG_SP,0x8007f000);u.reg_write(UC_MIPS_REG_RA,STOP)
for reg,val in [(UC_MIPS_REG_A0,15),(UC_MIPS_REG_A1,1),(UC_MIPS_REG_A2,1)]:u.reg_write(reg,val)
u.emu_start(0x9d041e8c,STOP,count=1000);u.hook_del(h)
assert first_read==[0x1000040]
out['actual_name_reader_first_address_for_overflow_entry_instrument1']=hex(first_read[0])
assert stock[picstart+0x1480:picstart+0x1a84c]==voice[picstart+0x1480:picstart+0x1a84c]
out['voice_sysex_pic_dinit_bytes_identical_to_stock']=True
from elftools.elf.elffile import ELFFile
with open('stock.elf','rb') as f:
 elf=ELFFile(f);checked=[]
 for va,size in [(0x33390,0x200),(0x33c10,0x60),(0x33c70,0x60),(0x2a0160,0x428)]:
  seg=next(seg for seg in elf.iter_segments() if seg['p_type']=='PT_LOAD' and seg['p_vaddr']<=va<seg['p_vaddr']+seg['p_filesz'])
  offset=13+seg['p_offset']+va-seg['p_vaddr']
  assert stock[offset:offset+size]==voice[offset:offset+size],hex(va)
  checked.append({'va':hex(va),'bytes':size})
 out['qnx_audited_group_regions_identical_to_stock']=checked
Path('branch4/import_compatibility_results.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps({k:v for k,v in out.items() if k not in ['changed_container_ranges_inclusive','pic_changed_offsets','audited_sites']},indent=2))
