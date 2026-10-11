#!/usr/bin/env python3
"""Dispatcher-to-reply validation, real sender with mocked byte transport."""
from pathlib import Path
import hashlib,json,struct,sys
from unicorn import *
from unicorn.mips_const import *

p,out=map(Path,sys.argv[1:]);raw=p.read_bytes()
assert hashlib.sha256(raw).hexdigest()=='f6b5205fc40e635305445bb19dd1a41d12f2ee4c64b7284ccd432868ef0c5898'
base=0x9d000000;b=raw[0x273055:0x273055+530784]
codes=[bytearray(b),bytearray(b)]
struct.pack_into('<I',codes[1],0x295b0,0x0b400480)
struct.pack_into('<8I',codes[1],0x1200,0x90a30005,0x386300f0,0x10600003,0x1021,0xf417b93,0x90a40004,0xb40a56e,0)
final_file=Path('deliverables/voice_fade_and_sysex/PxUpdate_V2.2.2.0.1.bin')
if final_file.exists():
 final=final_file.read_bytes()
 assert hashlib.sha256(final).hexdigest()=='d2775bd0e017e4442ce7d5bbc7d089022a1cf8c02714d89427462938e934d166'
 codes[1]=bytearray(final[0x273055:0x273055+530784])
results=[];reference=None
for patched,code in enumerate(codes):
 for setting in range(17):
  for multi in [0,1]:
   u=Uc(UC_ARCH_MIPS,UC_MODE_MIPS32|UC_MODE_LITTLE_ENDIAN)
   u.mem_map(0x1d000000,0x90000);u.mem_write(0x1d000000,bytes(code))
   u.mem_map(0,0x80000);u.mem_map(0x1f800000,0x100000)
   # Transport only is replaced by jr ra/nop. Header, packed sender and
   # parameter serialization run real instructions against a zeroed fixture.
   u.mem_write(0x1d0780ac,struct.pack('<II',0x03e00008,0))
   u.reg_write(UC_MIPS_REG_SP,0x80070000);u.reg_write(UC_MIPS_REG_GP,0x80007ff0)
   u.reg_write(UC_MIPS_REG_A0,0x80041000);u.reg_write(UC_MIPS_REG_A1,0x80040000)
   u.reg_write(UC_MIPS_REG_RA,base+0x81958)
   u.mem_write(0x40000,bytes([11,0,0,0,1,0xf0,6,0]))
   u.mem_write(0x6fe0,struct.pack('<H',setting));u.mem_write(0x6ffc,struct.pack('<H',multi))
   sent=[];reached=[]
   def tx(e,address,size,user):
    sent.append(e.reg_read(UC_MIPS_REG_A0)&255)
    if sent[-1]==0xf7:e.emu_stop()
   def lwx(e,address,size,user):
    # Unicorn lacks this DSP indexed-word-load instruction. Its exact word
    # and Capstone decode are pinned; implement only this dispatcher load.
    w=struct.unpack_from('<I',b,0x29160)[0];assert w==0x7c62100a
    addr=(e.reg_read(UC_MIPS_REG_V1)+e.reg_read(UC_MIPS_REG_V0))&0x1fffffff
    e.reg_write(UC_MIPS_REG_V0,struct.unpack('<I',e.mem_read(addr,4))[0])
    e.reg_write(UC_MIPS_REG_PC,address+4)
   def returned(e,address,size,user):reached.append('return');e.emu_stop()
   def handler(e,address,size,user):reached.append('sysex_handler')
   u.hook_add(UC_HOOK_CODE,tx,begin=base+0x780ac,end=base+0x780ac)
   u.hook_add(UC_HOOK_CODE,lwx,begin=base+0x29160,end=base+0x29160)
   u.hook_add(UC_HOOK_CODE,returned,begin=base+0x81958,end=base+0x81958)
   u.hook_add(UC_HOOK_CODE,handler,begin=base+0x2d710,end=base+0x2d710)
   u.emu_start(base+0x29118,0,count=500000)
   expected=bool(patched or setting in [0,2] or (setting==1 and multi))
   if expected:
    assert sent[:4]==[0xf0,1,0x30,3] and sent[-1]==0xf7,(patched,setting,multi,len(sent),hex(u.reg_read(UC_MIPS_REG_PC)))
    assert 'sysex_handler' in reached and all(x<128 for x in sent[1:-1])
    if reference is None:reference=bytes(sent)
    assert bytes(sent)==reference
   else:assert not sent and reached==['return']
   results.append({'patched':bool(patched),'channel_setting':setting,'multi':multi,'reply_bytes':len(sent),'expected_reply':expected})
out.mkdir(parents=True,exist_ok=True)
(out/'sysex_reply_cases.json').write_text(json.dumps(results,indent=2)+'\n')
summary={'executions':len(results),'fixture':'queued class11/statusF0/field1/command6; zero parameter RAM',
 'baseline_replies':sum(x['expected_reply'] for x in results if not x['patched']),
 'candidate_replies':sum(x['expected_reply'] for x in results if x['patched']),
 'reply_size':len(reference),'reply_sha256':hashlib.sha256(reference).hexdigest(),
 'mocks':['byte-output transport replaced by jr ra/nop','one exact unsupported DSP lwx instruction implemented'],
 'scope':'full class dispatcher, handler gate, command6 sender and F7; stops before post-reply UI cleanup',
 'not_tested':['physical DIN/USB','other SysEx commands end-to-end','post-reply cleanup','real patch/program data']}
(out/'sysex_reply_result.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps(summary,indent=2))
