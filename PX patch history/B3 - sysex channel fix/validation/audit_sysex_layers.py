# SPDX-License-Identifier: GPL-2.0-or-later
"""Read-only intraprocedural CFG + differential handler-boundary emulation."""
from pathlib import Path
import struct, json, hashlib
from capstone import *
from unicorn import *
from unicorn.mips_const import *

BASE=0x9d000000
raw=Path('version_sysex_work/voice_sysex_2.2.2.0.3.bin').read_bytes()
assert hashlib.sha256(raw).hexdigest()=='bbc3c2ad26bef7310fc15cac8edee22a1792d8ced3788f7080acccc047304857'
b=raw[0x273055:0x273055+530784]
m=Cs(CS_ARCH_MIPS,CS_MODE_MIPS32|CS_MODE_LITTLE_ENDIAN)
def instruction(a):
 i=list(m.disasm(b[a-BASE:a-BASE+4],a));assert len(i)==1,hex(a)
 return i[0]
todo=[BASE+0x2d710];seen=set();calls=set();indirect=[]
while todo:
 a=todo.pop()
 if a in seen:continue
 assert BASE<=a<BASE+len(b)
 seen.add(a);i=instruction(a);op=i.mnemonic
 if op in ['jal','bal']:
  seen.add(a+4);calls.add(int(i.op_str,16));todo.append(a+8)
 elif op=='j':
  seen.add(a+4);todo.append(int(i.op_str,16))
 elif op=='jr':
  seen.add(a+4)
  if i.op_str!='$ra':indirect.append((hex(a),i.op_str))
 elif op.startswith('b'):
  seen.add(a+4);todo.extend([int(i.op_str.split(',')[-1].strip(),16),a+8])
 else:todo.append(a+4)
uses=[]
for a in sorted(seen):
 i=instruction(a)
 if '$s2' in i.op_str or '$s3' in i.op_str:
  uses.append({'address':hex(a),'instruction':i.mnemonic+' '+i.op_str})
assert not indirect
assert all(instruction(int(x['address'],16)).mnemonic=='lw' and '$sp' in x['instruction'] for x in uses),uses

def execute_unicorn(command,layer,field,fixture):
 u=Uc(UC_ARCH_MIPS,UC_MODE_MIPS32|UC_MODE_LITTLE_ENDIAN)
 u.ctl_set_cpu_model(UC_CPU_MIPS32_74KF)
 u.mem_map(0x1d000000,0x90000);u.mem_write(0x1d000000,b)
 u.mem_map(0,0x80000)
 # Both alternatives use the same RAM contents. Layer value enters in s2/s3
 # exactly as the dispatcher stores the matcher result. Calls are boundaries:
 # record all ABI arguments then return a fixed fixture-dependent value.
 ram=bytes((n*17+fixture*31)&255 for n in range(0x60000))
 u.mem_write(0,ram)
 u.mem_write(0x41000,bytes(0x1000))
 u.mem_write(0x40000,bytes([11,0,0,0,field,0xf0,command,0,3,0,7,0]))
 u.mem_write(0x70034,struct.pack('<I',BASE+0x81958))
 for r,v in [(UC_MIPS_REG_GP,0x80007ff0),(UC_MIPS_REG_SP,0x80070000),
 (UC_MIPS_REG_S0,0x80041000),(UC_MIPS_REG_S1,0x80040000),
 (UC_MIPS_REG_S2,layer),(UC_MIPS_REG_S3,layer),
 (UC_MIPS_REG_RA,BASE+0x81958)]:u.reg_write(r,v)
 trace=[];writes=[];pcs=[]
 def pc_trace(e,a,size,_):
  pcs.append((hex(a),hex(e.reg_read(UC_MIPS_REG_SP)),hex(e.reg_read(UC_MIPS_REG_RA))))
  if len(pcs)>40:pcs.pop(0)
 def callback(e,a,size,_):
  sp=e.reg_read(UC_MIPS_REG_SP)&0x1fffffff
  trace.append((hex(a),*[e.reg_read(r) for r in [UC_MIPS_REG_A0,UC_MIPS_REG_A1,UC_MIPS_REG_A2,UC_MIPS_REG_A3]],bytes(e.mem_read(sp+16,8)).hex()))
  e.reg_write(UC_MIPS_REG_V0,fixture)
 def write(e,access,a,size,v,_):
  if (a&0x1fffffff)<0x60000:writes.append((a&0x1fffffff,size,v&((1<<(8*size))-1)))
 def stop(e,a,size,_):e.emu_stop()
 for a in calls:
  u.mem_write(a&0x1fffffff,struct.pack('<II',0x03e00008,0))
  u.hook_add(UC_HOOK_CODE,callback,begin=a,end=a)
 u.hook_add(UC_HOOK_MEM_WRITE,write)
 def intr(e,n,_):raise RuntimeError(('interrupt',n,hex(e.reg_read(UC_MIPS_REG_PC)),hex(e.reg_read(UC_MIPS_REG_RA)),hex(e.reg_read(UC_MIPS_REG_SP)),calls))
 u.hook_add(UC_HOOK_INTR,intr)
 # Keep code hooks scoped to boundaries to avoid needless tracing overhead.
 u.hook_add(UC_HOOK_CODE,stop,begin=BASE+0x81958,end=BASE+0x81958)
 try:u.emu_start(BASE+0x2d710,0,count=20000)
 except UcError as e:raise RuntimeError((command,layer,field,fixture,hex(u.reg_read(UC_MIPS_REG_PC)),pcs,trace[-3:])) from e
 assert u.reg_read(UC_MIPS_REG_PC)==BASE+0x81958,(command,layer,field)
 return trace,writes,u.reg_read(UC_MIPS_REG_V0),bytes(u.mem_read(0,0x60000))

def execute(command,layer,field,fixture):
 """Independent, fail-closed interpreter for the 161 decoded handler words."""
 ram=bytearray(0x80000)
 ram[:0x60000]=bytes((n*17+fixture*31)&255 for n in range(0x60000))
 ram[0x41000:0x42000]=bytes(0x1000)
 ram[0x40000:0x4000c]=bytes([11,0,0,0,field,0xf0,command,0,3,0,7,0])
 ram[0x70034:0x70038]=struct.pack('<I',BASE+0x81958)
 r=[0]*32
 for k,v in [(28,0x80007ff0),(29,0x80070000),(16,0x80041000),(17,0x80040000),(18,layer),(19,layer),(31,BASE+0x81958)]:r[k]=v
 trace=[];writes=[]
 def sx(v):return v-65536 if v&32768 else v
 def normal(a):
  w=struct.unpack_from('<I',b,a-BASE)[0];op=w>>26;rs=(w>>21)&31;rt=(w>>16)&31;rd=(w>>11)&31;imm=w&65535
  if w==0:return
  if op==0 and w&63==0x21:r[rd]=(r[rs]+r[rt])&0xffffffff
  elif op==9:r[rt]=(r[rs]+sx(imm))&0xffffffff
  elif op==11:r[rt]=int(r[rs]<(sx(imm)&0xffffffff))
  elif op==12:r[rt]=r[rs]&imm
  elif op==15:r[rt]=imm<<16
  elif op in [32,35,36,37]:
   addr=(r[rs]+sx(imm))&0x1fffffff;n={32:1,35:4,36:1,37:2}[op]
   assert addr+n<=len(ram)
   value=int.from_bytes(ram[addr:addr+n],'little')
   if op==32 and value&128:value-=256
   r[rt]=value&0xffffffff
  elif op in [40,41,43]:
   addr=(r[rs]+sx(imm))&0x1fffffff;n={40:1,41:2,43:4}[op];value=r[rt]&((1<<(8*n))-1)
   assert addr+n<=len(ram)
   ram[addr:addr+n]=value.to_bytes(n,'little')
   if addr<0x60000:writes.append((addr,n,value))
  else:raise AssertionError(('unsupported normal instruction',hex(a),hex(w)))
  r[0]=0
 pc=BASE+0x2d710
 for count in range(20000):
  if pc==BASE+0x81958:return trace,writes,r[2],bytes(ram[:0x60000])
  assert pc in seen,hex(pc)
  w=struct.unpack_from('<I',b,pc-BASE)[0];op=w>>26;rs=(w>>21)&31;rt=(w>>16)&31
  if op in [4,5,20,21]:
   take=(r[rs]==r[rt]) if op in [4,20] else (r[rs]!=r[rt])
   if take or op in [4,5]:normal(pc+4)
   pc=(pc+4+4*sx(w&65535))&0xffffffff if take else pc+8
  elif op in [2,3]:
   target=((pc+4)&0xf0000000)|((w&0x3ffffff)<<2)
   if op==3:r[31]=pc+8
   normal(pc+4)
   if op==3:
    assert target in calls
    sp=r[29]&0x1fffffff
    trace.append((hex(target),*r[4:8],bytes(ram[sp+16:sp+24]).hex()))
    r[2]=fixture;pc=r[31]
   else:pc=target
  elif op==0 and w&63==8:
   target=r[rs];normal(pc+4);pc=target
  else:normal(pc);pc+=4
 raise AssertionError('interpreter instruction bound exceeded')

cases=[];crosschecks=0
for command in range(128):
 for field in [1,2]:
  for fixture in [0,1]:
   x=execute(command,0,field,fixture);y=execute(command,1,field,fixture)
   assert x==y,(command,field,fixture)
   # Unicorn raises interrupt 20 at command 0x0E's final send. Static CFG and
   # the independent interpreter cover that case; do not suppress the error.
   if not (command==14 and field==1):
    assert execute_unicorn(command,0,field,fixture)==x,(command,field,fixture,'unicorn0')
    assert execute_unicorn(command,1,field,fixture)==y,(command,field,fixture,'unicorn1')
    crosschecks+=2
   cases.append({'command':command,'field':field,'fixture':fixture,'calls':len(x[0]),'writes':len(x[1]),'equivalent':True})
out=Path('resolved_research');out.mkdir(exist_ok=True)
summary={'firmware_sha256':hashlib.sha256(raw).hexdigest(),
 'cfg_instructions':len(seen),'direct_callees':[hex(a) for a in sorted(calls)],
 'matcher_register_mentions':uses,'unresolved_indirect_jumps':indirect,
 'differential_cases':len(cases),'executions':2*len(cases),
 'independent_interpreter_unicorn_crosschecks':crosschecks,
 'result':'All dispatcher handler paths ignore matcher s2/s3 until stack restoration; layer 0/1 produce identical call arguments, non-stack writes, return result and RAM in boundary fixtures.',
 'limits':'Direct callees mocked at ABI boundary, not a full handler or hardware test; starts at SysEx handler after prior routing gate. Includes every seven-bit command, accepted/rejected field and two callee return fixtures. Command 0x0E accepted-field executions covered by independent instruction interpreter and static CFG; Unicorn raises interrupt 20 at final-send instruction.'}
(out/'sysex_layers.json').write_text(json.dumps(summary,indent=2)+'\n')
(out/'sysex_layer_cases.json').write_text(json.dumps(cases,indent=2)+'\n')
(out/'sysex_handler_cfg.txt').write_text('\n'.join(f'{a:08x} {instruction(a).mnemonic} {instruction(a).op_str}' for a in sorted(seen))+'\n')
print(json.dumps(summary,indent=2))
