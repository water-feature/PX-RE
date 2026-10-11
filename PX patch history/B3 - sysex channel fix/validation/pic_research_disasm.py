from pathlib import Path
import sys, struct, hashlib
from capstone import *
p=Path('version_sysex_work/voice_sysex_2.2.2.0.3.bin')
raw=p.read_bytes()
assert hashlib.sha256(raw).hexdigest()=='bbc3c2ad26bef7310fc15cac8edee22a1792d8ced3788f7080acccc047304857'
b=raw[0x273055:0x273055+530784]; base=0x9d000000
md=Cs(CS_ARCH_MIPS,CS_MODE_MIPS32|CS_MODE_LITTLE_ENDIAN)
for n in range(1,len(sys.argv),2):
 lo,hi=[int(v,16) for v in sys.argv[n:n+2]]
 for a in range(lo,hi,4):
  ins=list(md.disasm(b[a-base:a-base+4],a))
  print(f'{a:08x} {struct.unpack_from("<I",b,a-base)[0]:08x} '+(ins[0].mnemonic+' '+ins[0].op_str if ins else '?'))
