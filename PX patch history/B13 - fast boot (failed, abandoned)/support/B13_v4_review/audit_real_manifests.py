# SPDX-License-Identifier: GPL-2.0-or-later
import hashlib
import ctypes as C,mmap,struct,json,collections
from pathlib import Path
import argparse,subprocess
ap=argparse.ArgumentParser()
ap.add_argument("manifest_root",type=Path)
ap.add_argument("--version",choices=["v3","v4"],default="v4")
ap.add_argument("--baseline",type=Path,default=Path(__file__).resolve().parent/"v10_exact_reconstructed.elf")
ap.add_argument("--source",type=Path)
args=ap.parse_args()
source=args.source or Path(__file__).resolve().parent/("b13_fast_uuid_"+args.version+".S")
subprocess.run(["gcc","-shared","-fPIC","-Wl,-z,noexecstack","-o","/tmp/b13_real_audit.so",str(Path(__file__).resolve().parent/"real_audit_wrappers.c"),str(source)],check=True)
base=args.baseline.read_bytes()
mem=mmap.mmap(-1,0x3000,prot=mmap.PROT_READ|mmap.PROT_WRITE|mmap.PROT_EXEC)
addr=C.addressof(C.c_char.from_buffer(mem))
# Extract original token/line/GUID machine code; redirect only external dependencies.
mem[0:0x100]=base[0x34260:0x34360]
# StrToGUID at local +0x60 loads stock guard-pointer slot via RIP.
struct.pack_into('<i',mem,0x68,0x1800-(0x68+4))
struct.pack_into('<Q',mem,0x1800,addr+0x1808)
struct.pack_into('<Q',mem,0x1808,0xabcdef)
# Unreachable stack-check failure redirects to a nearby trap.
struct.pack_into('<i',mem,0xfc,0x1820-0x100)
mem[0x1820:0x1822]=b'\x0f\x0b'
mem[0x200:0x2e2]=base[0x332a0:0x33382]
mem[0x400:0x4d0]=base[0x34070:0x34140]
libc=C.CDLL(None)
mem[0x1000:0x100c]=b'\x48\xb8'+struct.pack('<Q',C.cast(libc.memcpy,C.c_void_p).value)+b'\xff\xe0'
struct.pack_into('<i',mem,0x27a,0x1000-0x27e)
struct.pack_into('<i',mem,0x49f,0x1000-0x4a3)
guid=C.CFUNCTYPE(None,C.c_char_p,C.c_void_p)(addr+0x60)
token=C.CFUNCTYPE(C.c_int,C.POINTER(C.c_void_p),C.c_void_p)(addr+0x200)
getline=C.CFUNCTYPE(C.c_bool,C.c_void_p,C.c_void_p)(addr+0x400)
helper=C.CDLL('/tmp/b13_real_audit.so'); helper.set_converter(C.c_void_p(addr+0x60))
fast=getattr(helper,"b13_fast_uuid_"+args.version)
fast.argtypes=[C.c_void_p,C.c_char_p,C.c_char_p,C.c_void_p,C.c_void_p,C.c_void_p,C.c_void_p,C.c_void_p]
def tokens(line):
 b=C.create_string_buffer(line);p=C.c_void_p(C.addressof(b));out=C.create_string_buffer(4096);result=[]
 while token(C.byref(p),out):result.append(out.value)
 return result
def lines(data):
 b=C.create_string_buffer(data);reader=(C.c_uint64*4)(0,C.addressof(b),len(data),0);out=C.create_string_buffer(4096)
 while getline(reader,out):yield out.value
# Stock converter has low-nibble-first ordering; independent literal check.
out=C.create_string_buffer(17);guid(b'0123456789ABCDEF0123456789abcdef',out)
assert hashlib.sha256(out.raw).hexdigest()=='c5463983878846b6b741266bdc78b5ece918b426aa393296496e38d964a36098',out.raw.hex()
assert tokens(b'\tA\t\tB\t')==[b'A',b'B']
files=sorted(args.manifest_root.rglob('*.grp'))
stats=collections.Counter();bad=[];maxprefix=0;headers=collections.Counter();maxline=0
for path in files:
 data=path.read_bytes();rows=list(lines(data));ts=tokens(rows[0]);headers[tuple(ts)]+=1
 stats['files']+=1;stats['bytes']+=len(data);stats['embedded_nul']+=int(b'\0' in data)
 stats['duplicate_uuid_header']+=int(ts.count(b'UUID')>1)
 names=[b'File Path',b'Low Midi Note',b'High Midi Note',b'Low Velocity',b'High Velocity',b'Loop Start',b'Loop End',b'Round Robin Number',b'Pitch in Hertz',b'Mono Pitch',b'Stereo/Mono File',b'Category',b'Instrument Name',b'Mono Collapse',b'UUID']
 mapping=[15]*15
 for i,t in enumerate(ts):
  for j,name in enumerate(names):
   if t==name:mapping[j]=i
 expected=C.create_string_buffer(17);found=False
 for row in rows[1:]:
  for i,t in enumerate(tokens(row)):
   matches=[j for j,col in enumerate(mapping) if col==i]
   if matches and matches[0]==14 and not found:
    guid(t,expected);found=True
 stats['stock_uuid_found']+=int(found)
 actual=C.create_string_buffer(17);rc=fast(C.c_void_p(0x11),str(path).encode(),b'vel',None,None,None,None,actual)
 stats['fast_success' if rc==0 else 'fallback']+=1
 if rc==0 and actual.raw!=expected.raw:bad.append({'path':str(path),'actual':actual.raw.hex(),'expected':expected.raw.hex()})
 maxline=max(maxline,max(map(len,rows)))
print(json.dumps({'counts':dict(stats),'mismatches':bad,'unique_headers':len(headers),'max_line_bytes':maxline,'scope':'Actual assembled helper vs UUID projection using extracted stock line, token and GUID routines. Full GroupFileParse/velocity parsing not executed.'},indent=2))
