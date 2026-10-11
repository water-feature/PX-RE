#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Validate cave ownership and emulate relocated gate in memory; no BIN output."""
from pathlib import Path
import hashlib,json,struct,sys
from unicorn import Uc,UC_ARCH_MIPS,UC_MODE_MIPS32,UC_MODE_LITTLE_ENDIAN,UC_HOOK_CODE
from unicorn.mips_const import *

p,out=map(Path,sys.argv[1:]);raw=p.read_bytes()
assert hashlib.sha256(raw).hexdigest()=='f6b5205fc40e635305445bb19dd1a41d12f2ee4c64b7284ccd432868ef0c5898'
BASE,OFF,SIZE=0x9D000000,0x273055,530784
b=raw[OFF:OFF+SIZE];CAVE=BASE+0x1200;HOOK=BASE+0x295B0;RESUME=HOOK+8
assert b[0x11c4:0x1480]==b'\xff'*700
assert hashlib.sha256(struct.pack('<I',struct.unpack_from('<I',b,0x11bc)[0])).hexdigest()=='85fd965f1d2ec9de5c26f6ceeb0ee2803823fc81817aacbaed440b2d4075d930'
assert hashlib.sha256(struct.pack('<I',struct.unpack_from('<I',b,0x11c0)[0])).hexdigest()=='df3f619804a92fdb4057192dc43dd748ea778adc52bc498ce80524c014b81119'
assert hashlib.sha256(struct.pack('<I',struct.unpack_from('<I',b,0x81098)[0])).hexdigest()=='063b3e7331b556a31fa138dc3e170026e0e411329357aa0ae8b4a483a86d70f8'
# Pin EBase setter and its constants, including its uniqueness in the image.
assert [n for n in range(0,len(b),4) if struct.unpack_from('<I',b,n)[0]&0xffe0ffff==0x40807801]==[0x112c]
assert hashlib.sha256(struct.pack('<III',*struct.unpack_from('<III',b,0x1120))).hexdigest()=='5ba5fd829d3c510663d4cbe53b23ae286a731c265d4a9c4206a1bd2f0ccb4c82'
records=[];vectors={};n=0x1480
while True:
    dest=struct.unpack_from('<I',b,n)[0]
    if dest==0:break
    count,kind=struct.unpack_from('<II',b,n+4)
    assert kind in [0,1] and count>0
    source=BASE+n+12 if kind else None
    records.append({'record':BASE+n,'destination':dest,'length':count,'kind':kind,'source':source})
    if source is not None:assert source>=BASE+0x148c
    assert not (dest<CAVE+32 and dest+count>CAVE)
    if 0xbf810540<=dest<0xbf810900:
        assert kind==1 and count%4==0
        data=b[n+12:n+12+count]
        for j in range(0,count,4):vectors[(dest+j-0xbf810540)//4]=struct.unpack_from('<I',data,j)[0]
    n=(n+12+(count if kind else 0)+3)&~3
    assert n<len(b)
assert len(records)==93 and n==0x1a84c
assert len(vectors)==192 and set(vectors.values())==set(range(0x200,0x259,8))
assert all(not (0x1200<=v<0x1220) for v in vectors.values())
# Relocation encodings are derived, not copied from the rejected table cave.
def jump(va,link=False):return (3 if link else 2)<<26 | ((va>>2)&0x3ffffff)
words=[0x90A30005,0x386300F0,0x10600003,0x00001021,
       jump(BASE+0x5ee4c,True),0x90A40004,jump(RESUME),0]
patched=bytearray(b)
struct.pack_into('<I',patched,0x295b0,jump(CAVE))
struct.pack_into('<8I',patched,0x1200,*words)
assert jump(CAVE)==0x0b400480
assert CAVE+8+4+3*4==CAVE+24
def machine(code):
    u=Uc(UC_ARCH_MIPS,UC_MODE_MIPS32|UC_MODE_LITTLE_ENDIAN)
    u.mem_map(0x1d000000,0x90000);u.mem_write(0x1d000000,bytes(code))
    u.mem_map(0,0x80000);u.mem_map(0x1f810000,0x10000)
    return u
images=[]
for code in [b,patched]:
    u=machine(code);u.reg_write(UC_MIPS_REG_RA,BASE+0x81958)
    u.emu_start(BASE+0x81090,BASE+0x81958,count=2000000)
    assert u.reg_read(UC_MIPS_REG_PC)==BASE+0x81958
    for r in records:
        address=r['destination']&0x1fffffff
        expected=bytes(r['length']) if r['kind']==0 else b[r['source']-BASE:r['source']-BASE+r['length']]
        assert bytes(u.mem_read(address,r['length']))==expected
    images.append((bytes(u.mem_read(0,0x80000)),bytes(u.mem_read(0x1f810000,0x10000))))
assert images[0]==images[1]
machines=[machine(code) for code in [b,patched]]
contexts=[u.context_save() for u in machines]
SP,EVENT,STATE,RETURN=0x80070000,0x80040000,0x80041000,BASE+0x81958
kept=[UC_MIPS_REG_S0,UC_MIPS_REG_S1,UC_MIPS_REG_S2,UC_MIPS_REG_S3,UC_MIPS_REG_S4,UC_MIPS_REG_S5,UC_MIPS_REG_S6,UC_MIPS_REG_S7,UC_MIPS_REG_FP,UC_MIPS_REG_GP,UC_MIPS_REG_SP]
cases=0;sysex_cases=0;ordinary_cases=0
statuses=[0x80,0x90,0xa0,0xb0,0xc0,0xd0,0xe0,0xf0]
for setting in range(17):
 for multi in [0,1]:
  for channel in range(16):
   for status in statuses:
    outputs=[]
    for idx,u in enumerate(machines):
      u.context_restore(contexts[idx])
      for reg in kept:u.reg_write(reg,0x11110000+reg)
      u.reg_write(UC_MIPS_REG_SP,SP);u.reg_write(UC_MIPS_REG_GP,0x80007ff0)
      u.reg_write(UC_MIPS_REG_S0,STATE);u.reg_write(UC_MIPS_REG_S1,EVENT)
      u.reg_write(UC_MIPS_REG_A1,EVENT);u.reg_write(UC_MIPS_REG_RA,RETURN)
      u.reg_write(UC_MIPS_REG_V1,0xdeadbeef)
      u.mem_write(EVENT&0x1fffffff,bytes([11,0,0,0,channel,status,6,0]))
      u.mem_write((SP+0x34)&0x1fffffff,struct.pack('<I',RETURN))
      u.mem_write(0x6fe0,struct.pack('<H',setting));u.mem_write(0x6ffc,struct.pack('<H',multi))
      before=[u.reg_read(reg) for reg in kept]
      for slot,reg in [(0x30,UC_MIPS_REG_S5),(0x2c,UC_MIPS_REG_S4),(0x28,UC_MIPS_REG_S3),(0x24,UC_MIPS_REG_S2),(0x20,UC_MIPS_REG_S1),(0x1c,UC_MIPS_REG_S0)]:
        u.mem_write((SP+slot)&0x1fffffff,struct.pack('<I',0x22220000+reg))
      observed={}
      def observe(engine,address,size,user):
        if address==RESUME:
          observed['result']=engine.reg_read(UC_MIPS_REG_V0)
          observed['kept']=[engine.reg_read(reg) for reg in kept]
        if address in [BASE+0x295cc,RETURN]:
          observed['boundary']=address;engine.emu_stop()
      handle=u.hook_add(UC_HOOK_CODE,observe)
      u.emu_start(HOOK,0,count=500)
      u.hook_del(handle)
      assert 'result' in observed,(setting,multi,channel,status,idx,hex(u.reg_read(UC_MIPS_REG_PC)))
      result=observed['result']
      assert observed['kept']==before
      outputs.append(result)
      if result<2:
        assert observed['boundary']==BASE+0x295cc
        assert u.reg_read(UC_MIPS_REG_A0)==0
      else:
        assert observed['boundary']==RETURN
        assert u.reg_read(UC_MIPS_REG_SP)==SP+0x38
        assert u.reg_read(UC_MIPS_REG_RA)==RETURN
    expected=0 if setting==0 or channel==setting-1 else (1 if multi and channel==(setting&15) else 2)
    assert outputs[0]==expected,(setting,multi,channel,status,outputs,expected)
    assert outputs[1]==(0 if status==0xf0 else expected)
    cases+=1
    if status==0xf0:sysex_cases+=1
    else:ordinary_cases+=1
out.mkdir(parents=True,exist_ok=True)
result={'base_sha256':hashlib.sha256(raw).hexdigest(),'candidate_va':hex(CAVE),'candidate_raw_offset':hex(OFF+0x1200),'trampoline_words':[hex(w) for w in words],'hook_word':hex(jump(CAVE)),
 'candidate_decision':'selected for offline patch development within supplied-image evidence',
 'dinit_records':len(records),'dinit_end':hex(BASE+n),'initialized_vector_registers':len(vectors),'vector_offsets':sorted(set(vectors.values())),
 'dinit_emulation':'all record destinations verified; baseline and relocated in-memory candidate produce identical RAM/MMIO',
 'gate_matrix_cases':cases,'machine_executions':cases*2,'sysex_cases':sysex_cases,'ordinary_cases':ordinary_cases,
 'scope':'real matcher/getter, hook, trampoline and immediate acceptance/rejection boundary; not complete SysEx handler execution',
 'unresolved':['Complete class-11/SysEx handler runtime','PIC checksum/version/install semantics','Unseen boot/recovery copier and arbitrary indirect-reference completeness','Hardware behavior'],
 'firmware_file_written':False}
(out/'gap_gate_result.json').write_text(json.dumps(result,indent=2)+'\n')
(out/'dinit_records.json').write_text(json.dumps(records,indent=2)+'\n')
(out/'vector_offsets.json').write_text(json.dumps(vectors,indent=2)+'\n')
print(json.dumps(result,indent=2))
