# SPDX-License-Identifier: GPL-2.0-or-later
"""Execute original x86 equality branches; intercept destinations as host returns.
Does not execute installation, filesystem writes or USB handling.
"""
from pathlib import Path
import mmap,ctypes as C,struct,json
ROOT=Path(__file__).resolve().parent
results=[]
for label,name,own in [('baseline','baseline_qnx.elf',[2,2,2,1,2]),('candidate','candidate_qnx.elf',[2,2,2,1,3])]:
 b=(ROOT/name).read_bytes();m=mmap.mmap(-1,0x26000,prot=mmap.PROT_READ|mmap.PROT_WRITE|mmap.PROT_EXEC)
 addr=C.addressof(C.c_char.from_buffer(m))
 m[0x24f21:0x24f2e]=b[0x24f21:0x24f2e];m[0x250c2:0x250fb]=b[0x250c2:0x250fb]
 m[0x24f2e:0x24f35]=b'\xb8\x01\x00\x00\x00\x5d\xc3'
 m[0x24f39:0x24f3d]=b'\x31\xc0\x5d\xc3'
 # Save host RBP, select input-field base, and jump to exact original first compare.
 code=b'\x55\x48\x8d\xaf\x90\x05\x00\x00\xe9'+struct.pack('<i',0x24f21-13);m[:len(code)]=code
 gate=C.CFUNCTYPE(C.c_int,C.c_void_p)(addr)
 cases=[('own',own,0),('other build',[2,2,2,1,3 if label=='baseline' else 2],1)]
 for field in range(5):
  different=own.copy();different[field]^=1;cases.append(('field-'+str(field),different,1))
 for case,header,expected in cases:
  a=(C.c_ubyte*5)(*header);actual=gate(a);assert actual==expected
  results.append({'application':label,'case':case,'header':header,'install_flag':actual})
 m.close()
print(json.dumps({'checks':results,'status':'all pass','scope':'Executed candidate/baseline five-field equality instructions, not the complete installer.'},indent=2))
