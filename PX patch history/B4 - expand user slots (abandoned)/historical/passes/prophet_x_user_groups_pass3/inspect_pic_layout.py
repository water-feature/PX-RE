# SPDX-License-Identifier: GPL-2.0-or-later
from pathlib import Path
import struct,json
b=Path('pic.bin').read_bytes();off=0x1480;desc=[]
while True:
 dest=struct.unpack_from('<I',b,off)[0]
 if not dest:break
 n,copy=struct.unpack_from('<II',b,off+4);start=off;off+=12
 desc.append({'descriptor':hex(0x9d000000+start),'start':hex(dest),'end':hex(dest+n),'bytes':n,'copy':copy})
 if copy:off+=n
 off=(off+3)&~3
Path('branch4/pic_dinit_layout.json').write_text(json.dumps(desc,indent=2)+'\n')
print('Descriptors:',len(desc),'table ends',hex(0x9d000000+off))
for d in desc:
 a=int(d['start'],16);z=int(d['end'],16)
 if a<0x8003c000 and z>0x80037000 or a>=0x80050000: print(d)
