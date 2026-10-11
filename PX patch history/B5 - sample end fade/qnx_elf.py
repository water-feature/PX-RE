# SPDX-License-Identifier: GPL-2.0-or-later
"""Shared ELF address mapping used by the retained QNX feature builders."""
import struct

class Elf:
 def __init__(self,b):
  self.b=b;self.phoff=struct.unpack_from('<Q',b,32)[0];self.shoff=struct.unpack_from('<Q',b,40)[0]
  self.phents,self.phnum,self.shents,self.shnum,self.shstr=struct.unpack_from('<HHHHH',b,54)
  self.ph=[struct.unpack_from('<IIQQQQQQ',b,self.phoff+i*self.phents) for i in range(self.phnum)]
  self.sh=[struct.unpack_from('<IIQQQQIIQQ',b,self.shoff+i*self.shents) for i in range(self.shnum)]
  s=self.sh[self.shstr];st=b[s[4]:s[4]+s[5]]
  self.names=[st[x[0]:st.find(b'\0',x[0])].decode() for x in self.sh]
 def off(self,va,n=1):
  for typ,flags,o,v,p,f,m,a in self.ph:
   if typ==1 and v<=va and va+n<=v+f:return o+va-v
  raise ValueError(f'VA {va:#x} not wholly file backed')
