"""Execute actual QNX sender and actual PIC receiver to a modeled SPI flash."""
from pathlib import Path
from collections import deque, Counter
import hashlib,json,struct
from unicorn import *
from unicorn.x86_const import *
from unicorn.mips_const import *
raw=Path('version_sysex_work/voice_sysex_2.2.2.0.3.bin').read_bytes()
assert hashlib.sha256(raw).hexdigest()=='bbc3c2ad26bef7310fc15cac8edee22a1792d8ced3788f7080acccc047304857'
elf=raw[13:986533];pic=raw[0x273055:0x273055+530784];BASE=0x9d000000
u=Uc(UC_ARCH_X86,UC_MODE_64);u.mem_map(0,0x400000);u.mem_write(0,elf)
for a in [0x11000000,0x12000000,0x13000000]:u.mem_map(a,0x10000)
OBJ,RBP=0x12000000,0x11008000
u.reg_write(UC_X86_REG_RBP,RBP);u.reg_write(UC_X86_REG_RSP,RBP-0x1000);u.reg_write(UC_X86_REG_R15,OBJ)
u.mem_write(OBJ+0x1ff0,struct.pack('<Q',0x13002000))
u.mem_write(0x13002000,struct.pack('<Q',0x13002100));u.mem_write(0x13002110,struct.pack('<Q',0x300000))
for a in [0x300000,0x7b90]:u.mem_write(a,b'\xc3')
u.mem_write(OBJ+0x36d8,struct.pack('<Q',0x13002200));u.mem_write(0x13002200,struct.pack('<Q',0x13003000))
u.mem_write(OBJ+0x36a0,struct.pack('<Q',0x13003000))
for o,v in [(0x3700,0x1000),(0x371c,0x40),(0x370c,129)]:u.mem_write(OBJ+o,struct.pack('<I',v))
ctx=u.context_save();frames=[];blocks=[]
def tx(e,a,size,_):frames.append(bytes(e.mem_read(e.reg_read(UC_X86_REG_RSI),4)))
def done(e,a,size,_):e.emu_stop()
u.hook_add(UC_HOOK_CODE,tx,begin=0x300000,end=0x300000)
u.hook_add(UC_HOOK_CODE,done,begin=0x1e453,end=0x1e453)
for start in range(0,len(pic),4096):
 block=pic[start:start+4096];full=len(block)==4096
 u.context_restore(ctx);u.mem_write(0x13003000,block);u.reg_write(UC_X86_REG_R14,0)
 for o,v in [(0x3744,0),(0x3724,2 if full else 3),(0x3710,0 if full else len(block)),(0x36f4,0),(0x36f8,0),(0x36fc,0)]:u.mem_write(OBJ+o,struct.pack('<I',v))
 frames.clear();u.emu_start(0x26738 if full else 0x26626,0,count=500000)
 assert u.reg_read(UC_X86_REG_RIP)==0x1e453
 assert all(f[2:]==b'\x00\xf1' for f in frames)
 data=b''.join(f[:2] for f in frames[:-1]) if full else bytes(f[0] for f in frames[:-1])
 assert data==block
 assert int.from_bytes(frames[-1][:2],'little')==sum(int.from_bytes(block[i:i+2],'little') for i in range(0,len(block),2))&65535
 blocks.append(list(frames))

def run(corrupt_indices=(),abort=False):
 m=Uc(UC_ARCH_MIPS,UC_MODE_MIPS32|UC_MODE_LITTLE_ENDIAN)
 m.mem_map(0x1d000000,0x90000);m.mem_write(0x1d000000,pic)
 m.mem_map(0,0x80000);m.mem_map(0x1f800000,0x100000)
 m.reg_write(UC_MIPS_REG_GP,0x80007ff0);m.reg_write(UC_MIPS_REG_SP,0x80070000)
 m.reg_write(UC_MIPS_REG_RA,BASE+0x81958)
 # Receiver byte-swaps the length delivered by the link protocol.
 m.mem_write(0x2a8,len(pic).to_bytes(4,'big'))
 pending=deque();requests=[];erases=[];pages=[];attempts=Counter();resets=[]
 flash=bytearray(b'\xff'*0x200000)
 def request(e,a,size,_):
  word=e.reg_read(UC_MIPS_REG_A0);assert word>>16==0x4019,hex(word)
  arg=word&65535;requests.append(arg)
  if arg==0x10f7:return
  if abort:
   pending.append(struct.pack('<I',0xf1f110f9));return
  index=129 if arg==0x10f4 else arg
  assert 0<=index<len(blocks),(index,len(blocks))
  attempts[index]+=1
  packet=list(blocks[index])
  if index in corrupt_indices and attempts[index]==1:
   bad=bytearray(packet[-1]);bad[0]^=1;packet[-1]=bytes(bad)
  pending.extend(packet)
 def feed(e,a,size,_):
  head=struct.unpack('<H',e.mem_read(0x294,2))[0];tail=struct.unpack('<H',e.mem_read(0x29c,2))[0]
  if head==tail and pending:
   e.mem_write(0x8634+4*tail,pending.popleft())
   e.mem_write(0x29c,struct.pack('<H',(tail+1)&8191))
 def lwx(e,a,size,_):
  assert hashlib.sha256(struct.pack('<I',struct.unpack_from('<I',pic,0x4439c)[0])).hexdigest()=='cb7a369df05f93663805e26a654c601be378fd2dace0d6ca478a827875b4964d'
  addr=(e.reg_read(UC_MIPS_REG_S1)+e.reg_read(UC_MIPS_REG_V0))&0x1fffffff
  e.reg_write(UC_MIPS_REG_V0,struct.unpack('<I',e.mem_read(addr,4))[0]);e.reg_write(UC_MIPS_REG_PC,a+4)
 def erase(e,a,size,_):
  address=e.reg_read(UC_MIPS_REG_A0);assert address&4095==0
  assert 0x200000<=address<0x282000,hex(address)
  erases.append(address);flash[address-0x200000:address-0x200000+4096]=b'\xff'*4096
 def page(e,a,size,_):
  address=e.reg_read(UC_MIPS_REG_A0);assert address&255==0
  assert 0x200000<=address<0x282000,hex(address)
  data=bytes(e.mem_read(0x10dac+(address&0xf00),256))
  pages.append(address);flash[address-0x200000:address-0x200000+256]=data
 def reset(e,a,size,_):resets.append(a);e.emu_stop()
 mocks={0x75c1c:request,0x421ac:erase,0x42340:page}
 for a in [0x81194,0x7e408,0x68d64,0x7e3dc,0x67a2c,0x5f770,0x80f4c]:
  # memset must run real instructions; UI/time may return zero.
  if a==0x80f4c:continue
  mocks[a]=None
 for off,callback in mocks.items():
  m.mem_write(0x1d000000+off,struct.pack('<II',0x03e00008,0))
  if callback:m.hook_add(UC_HOOK_CODE,callback,begin=BASE+off,end=BASE+off)
 m.hook_add(UC_HOOK_CODE,feed,begin=BASE+0x44374,end=BASE+0x44374)
 m.hook_add(UC_HOOK_CODE,lwx,begin=BASE+0x4439c,end=BASE+0x4439c)
 m.hook_add(UC_HOOK_CODE,reset,begin=BASE+0x81790,end=BASE+0x81790)
 m.hook_add(UC_HOOK_CODE,done,begin=BASE+0x81958,end=BASE+0x81958)
 m.emu_start(BASE+0x442a4,0,count=100000000)
 pc=m.reg_read(UC_MIPS_REG_PC)
 if abort:
  assert pc==BASE+0x81958 and not erases and not pages and not resets
 else:
  assert pc==BASE+0x81790,(hex(pc),requests[-10:],len(erases),attempts)
  assert bytes(flash[:len(pic)])==pic
  assert flash[len(pic):0x82000]==bytes(0x82000-len(pic))
  assert flash[0x82000:]==b'\xff'*(len(flash)-0x82000)
  assert erases==list(range(0x200000,0x282000,4096))
  assert pages==list(range(0x200000,0x282000,256))
  assert all(attempts[i]==(2 if i in corrupt_indices else 1) for i in range(130))
  assert requests[-1]==0x10f7
 return {'abort':abort,'corrupted_then_retried':list(corrupt_indices),'block_requests':len(requests),
 'sector_erases':len(erases),'page_programs':len(pages),'reset_reached':bool(resets),
 'end_pc':hex(pc),'payload_equal':not abort,'staged_range':'0x200000..0x281fff' if erases else None}

cases=[]
for corrupt,abort in [((),False),((1,37,41,81,129),False),((),True)]:
 result=run(corrupt,abort);cases.append(result);print(json.dumps(result),flush=True)
out=Path('resolved_research');out.mkdir(exist_ok=True)
summary={'firmware_sha256':hashlib.sha256(raw).hexdigest(),'pic_sha256':hashlib.sha256(pic).hexdigest(),
 'receiver':'0x9D0442A4, called for updater state 3 at 0x9D025CBC',
 'cases':cases,'qnx_blocks_verified':len(blocks),
 'mocks':['link queue supplied one frame at a time from actual QNX sender output','SPI erase/page helpers modeled in bytearray','time/UI helpers returned; one exact DSP lwx implemented'],
 'scope':'Full PIC receive state machine, queue consumption, checksums, retry, 130 flushes and reset boundary. Internal copier and actual SPI peripheral effects excluded.',
 'prior_evidence_correction':'Earlier validate_pic_transfer.py executed 0x9D0448AC accumulation/checksum fragments, the FPGA receiver. New evidence uses actual PIC receiver 0x9D0442A4.'}
(out/'pic_staging.json').write_text(json.dumps(summary,indent=2)+'\n')
