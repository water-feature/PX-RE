#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Run real QNX x86 type-3 record parser with mocked libc I/O/allocation."""
from pathlib import Path
import hashlib,json,struct,sys
from unicorn import *
from unicorn.x86_const import *
p,out=map(Path,sys.argv[1:]);raw=p.read_bytes()
assert hashlib.sha256(raw).hexdigest()=='f6b5205fc40e635305445bb19dd1a41d12f2ee4c64b7284ccd432868ef0c5898'
elf=raw[13:986533]
# All parsed code addresses are identity-mapped by the first PT_LOAD.
phoff=struct.unpack_from('<Q',elf,32)[0];phsize,phnum=struct.unpack_from('<HH',elf,54)
loads=[]
for i in range(phnum):
 kind,flags,offset,va,pa,fs,ms,align=struct.unpack_from('<IIQQQQQQ',elf,phoff+i*phsize)
 if kind==1:loads.append((offset,va,fs,ms))
assert any(off==va and va<=0x24a0c and va+fs>0x25279 for off,va,fs,ms in loads)
PIC=raw[0x273055:0x273055+530784]
base_record=raw[0x27304a:len(raw)-1]
cases=[('stock_same',False,0x2220,0,b'00',True),
       ('combined_install',True,0x2220,0,b'00',False),
       ('combined_same',True,0x2221,0,b'00',True),
       ('official_rollback',False,0x2221,0,b'00',False),
       ('ignored_trailer',True,0x2220,0,b'\x34\x12',False)]
results=[]
for name,changed,reported,tail,trailer,skip in cases:
 record=bytearray(base_record);record[4]=int(changed);record[-2:]=trailer
 u=Uc(UC_ARCH_X86,UC_MODE_64);u.mem_map(0,0x400000)
 for off,va,fs,ms in loads:
  if va<0x400000:u.mem_write(va,elf[off:off+fs])
 u.mem_map(0x11000000,0x10000);u.mem_map(0x12000000,0x10000);u.mem_map(0x13000000,0x1000000)
 RBP=0x11008000;OBJ=0x12000000
 u.reg_write(UC_X86_REG_RBP,RBP);u.reg_write(UC_X86_REG_RSP,RBP-0x1000)
 u.reg_write(UC_X86_REG_R15,OBJ);u.reg_write(UC_X86_REG_EBX,17)
 u.mem_write(RBP-0x7c8,struct.pack('<Q',RBP-0x7b1))
 for offset,value in [(0x3700,0x1000),(0x374c,reported),(0x3750,tail)]:u.mem_write(OBJ+offset,struct.pack('<I',value))
 position=[0];heap=[0x13000000];checksum_calls=[0]
 def read(e,a,size,user):
  count=e.reg_read(UC_X86_REG_EDX);data=record[position[0]:position[0]+count]
  assert len(data)==count;e.mem_write(e.reg_read(UC_X86_REG_RSI),bytes(data))
  position[0]+=count;e.reg_write(UC_X86_REG_RAX,count)
 def alloc(e,a,size,user):
  length=e.reg_read(UC_X86_REG_RDI);addr=heap[0];heap[0]+=(length+15)&~15
  assert heap[0]<0x14000000;e.reg_write(UC_X86_REG_RAX,addr)
 def seek(e,a,size,user):
  assert e.reg_read(UC_X86_REG_EDX)==1;position[0]+=e.reg_read(UC_X86_REG_RSI)
  e.reg_write(UC_X86_REG_RAX,position[0])
 def checksum(e,a,size,user):checksum_calls[0]+=1
 def done(e,a,size,user):e.emu_stop()
 for address,callback in [(0x78c0,read),(0x7930,alloc),(0x7360,seek)]:
  u.mem_write(address,b'\xc3');u.hook_add(UC_HOOK_CODE,callback,begin=address,end=address)
 u.mem_write(0x78b0,b'\xc3')
 u.hook_add(UC_HOOK_CODE,checksum,begin=0x1d840,end=0x1d840)
 u.hook_add(UC_HOOK_CODE,done,begin=0x24426,end=0x24426)
 u.emu_start(0x24a0c,0,count=20000000)
 assert u.reg_read(UC_X86_REG_RIP)==0x24426
 assert position[0]==len(record) and checksum_calls[0]==0
 def dword(o):return struct.unpack('<I',u.mem_read(OBJ+o,4))[0]
 def ptr(o):return struct.unpack('<Q',u.mem_read(OBJ+o,8))[0]
 assert dword(0x3744)==int(skip) and dword(0x36ec)==len(PIC)
 if not skip:
  count=dword(0x370c);remainder=dword(0x3710)
  data=bytearray()
  for i in range(count):
   address=struct.unpack('<Q',u.mem_read(ptr(0x36d8)+8*i,8))[0]
   data.extend(u.mem_read(address,0x1000))
  data.extend(u.mem_read(ptr(0x36a0),remainder))
  assert bytes(data)==PIC
 else:assert ptr(0x36d8)==0 and ptr(0x36a0)==0
 results.append({'case':name,'skip':skip,'bytes_consumed':position[0],'trailer_hex':trailer.hex(),'checksum_calls':checksum_calls[0],'payload_verified':not skip})
out.mkdir(parents=True,exist_ok=True)
summary={'cases':results,'scope':'real type3 parser/version gate/length/payload/trailer/splitting; libc mocked; stops at parser loop reentry',
 'result':'type3 container trailer consumed but not validated; version gating permits combined install and official rollback',
 'planned_pic_version':[2,2,2,1,0],'normal_transfer_checksum':'separately recalculated per transmitted block; receiver validation remains separate'}
(out/'pic_parser_result.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary,indent=2))
