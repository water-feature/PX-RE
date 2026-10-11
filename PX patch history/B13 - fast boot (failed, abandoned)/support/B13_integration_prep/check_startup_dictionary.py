# SPDX-License-Identifier: GPL-2.0-or-later
"""Execute original startup worker and dictionary Insert with controlled cache outputs.
This checks downstream argument preservation, not QNX full-parser execution or SSD index ordering.
"""
import argparse,ctypes as C,mmap,struct,json,collections,subprocess
from pathlib import Path
ap=argparse.ArgumentParser();ap.add_argument('manifest_root',type=Path)
ap.add_argument('--baseline',type=Path,default=Path(__file__).resolve().parent.parent/'B13_v4_review/v10_exact_reconstructed.elf')
ap.add_argument('--candidate',type=Path,default=Path(__file__).resolve().parent.parent/'B13_v4_review/v10_b13_uuid_v4_candidate.elf')
args=ap.parse_args();base=args.baseline.read_bytes();candidate=args.candidate.read_bytes()
assert base[0x350e0:0x35320][:0x19d]==candidate[0x350e0:0x35320][:0x19d]
assert base[0x35281:0x35320]==candidate[0x35281:0x35320]
assert base[0x11950:0x11a90]==candidate[0x11950:0x11a90]
mem=mmap.mmap(-1,0x6000,prot=mmap.PROT_READ|mmap.PROT_WRITE|mmap.PROT_EXEC)
addr=C.addressof(C.c_char.from_buffer(mem));libc=C.CDLL(None);keep=[]
def fp(fn):return C.cast(fn,C.c_void_p).value
def writeq(o,v):struct.pack_into('<Q',mem,o,v)
next_tramp=0x2000
def tramp(fn):
 global next_tramp
 o=next_tramp;next_tramp+=16
 mem[o:o+12]=b'\x48\xb8'+struct.pack('<Q',fp(fn) if not isinstance(fn,int) else fn)+b'\xff\xe0';return o
def rel(field,target):struct.pack_into('<i',mem,field,target-field-4)
zero=0x2f00;mem[zero:zero+3]=b'\x31\xc0\xc3'
cache=0x2f10;mem[cache:cache+6]=b'\xb8\x11\x11\x11\x11\xc3'
trap=0x2f20;mem[trap:trap+2]=b'\x0f\x0b'
writeq(0x3000,addr+0x3010);writeq(0x3010,0x12345678)
writeq(0x3020,addr+0x3030);writeq(0x3030,addr+0x3040)
mem[0x800:0x940]=base[0x11950:0x11a90]
for field,target in [(0x84a,tramp(libc.malloc)),(0x8c3,tramp(libc.strcpy)),(0x8e3,zero),(0x91a,zero)]:rel(field,target)
insert=C.CFUNCTYPE(None,C.c_void_p,C.c_void_p,C.c_char_p,C.c_uint,C.c_uint,C.c_uint)(addr+0x800)
# Fixture nodes preserve actual paths/names. Group numbers and order are deterministic
# fixture values, not a claim to reproduce the SSD's missing index table.
files=sorted(args.manifest_root.rglob('*.grp'));assert files
root=args.manifest_root
if not (root/'f00').is_dir():root=next(p for p in root.rglob('f00') if p.is_dir()).parent
group_names=sorted(set(p.relative_to(root).parts[0] for p in files));group_ids={n:i for i,n in enumerate(group_names)}
groups=C.create_string_buffer(0x1148+65*17*8);heads={};tails={}
for path in files:
 parts=path.relative_to(root).parts;g=group_ids[parts[0]];cat=int(parts[1].split(' ',1)[0])-1
 assert 0<=g<65 and 0<=cat<17
 node=C.create_string_buffer(0x408);keep.append(node);na=C.addressof(node)
 grp=str(path.resolve()).encode();vel=str(path.parent.resolve()).encode();assert len(grp)<512 and len(vel)<512
 C.memmove(na,vel,len(vel)+1);C.memmove(na+0x200,grp,len(grp)+1)
 key=(g,cat)
 if key in tails:C.c_uint64.from_address(tails[key]+0x400).value=na
 else:heads[key]=na
 tails[key]=na
for (g,cat),na in heads.items():C.c_uint64.from_address(C.addressof(groups)+0x1148+(g*17+cat)*8).value=na
records=[];parser_calls=0;return_mode=0
CACHE=C.CFUNCTYPE(C.c_int,C.c_void_p,C.c_char_p,C.c_char_p,C.c_void_p,C.c_void_p,C.c_void_p,C.c_void_p,C.c_void_p)
@CACHE
def stock_projection(thiz,p,v,a,b,c,d,out):
 global parser_calls
 assert thiz==0x11111111 and not any([a,b,c,d]);parser_calls+=1
 # Previous real-manifest audit proves zero UUID for these header shapes.
 C.memset(out,0,17);return 99 if return_mode else 0
keep.append(stock_projection)
DICT=C.CFUNCTYPE(None,C.c_void_p,C.c_void_p,C.c_char_p,C.c_uint,C.c_uint,C.c_uint)
@DICT
def capture(thiz,uuid,name,g,cat,index):
 records.append((C.string_at(uuid,17).hex(),name.decode('utf8'),g,cat,index));insert(thiz,uuid,name,g,cat,index)
keep.append(capture)
vtable=(C.c_uint64*3)(0,0,fp(capture));dictionary=(C.c_uint64*16)();dictionary[0]=C.addressof(vtable)
# Place exact v4 candidate helper and rebind its existing callees for the host.
mem[0x400:0x586]=candidate[0xf9240:0xf93c6]
for field,fn in [(0x426,libc.open),(0x441,libc.read),(0x44d,libc.close),(0x56d,stock_projection)]:rel(field,tramp(fn))
worker=C.CFUNCTYPE(C.c_void_p,C.c_void_p)(addr)
def run(fast,cpus,errors=False):
 global records,parser_calls,return_mode
 records=[];parser_calls=0;return_mode=int(errors);dictionary[1]=0
 mem[:0x240]=base[0x350e0:0x35320]
 rel(0x17,0x3000);rel(0x20c,0x3000);rel(0xbc,0x3020)
 for field,target in [(0x2b,cache),(0x45,zero),(0x53,zero),(0x64,zero),(0x1af,tramp(libc.strrchr)),(0x1bd,tramp(libc.strcpy)),(0x1cc,tramp(libc.strrchr)),(0x233,trap)]:rel(field,target)
 rel(0x19d,0x400 if fast else tramp(stock_projection))
 struct.pack_into('<H',mem,0x3046,cpus)
 for cpu in range(cpus):
  state=(C.c_uint64*3)(cpu,C.addressof(groups),C.addressof(dictionary));worker(state)
  assert C.c_int.from_address(C.addressof(state)).value==-1
 assert len(records)==len(files);assert len(set((r[2],r[3],r[4]) for r in records))==len(files)
 assert dictionary[1]==0 # Original Insert rejects zero-containing UUIDs.
 return sorted(records),parser_calls
results=[]
for cpus in (1,2,4):
 stock,n=run(False,cpus);fast,f=run(True,cpus);failed,_=run(False,cpus,True)
 assert stock==fast==failed
 results.append({'cpus':cpus,'matched_insert_calls':len(stock),'stock_projection_calls':n,'v4_fallback_calls':f,'stored_entries':0,'failure_projection_same':True})
# Positive control: original Insert really stores a UUID with no zero bytes.
uuid=C.create_string_buffer(bytes([0x11])*16+b'\0');insert(dictionary,uuid,b'positive-control',2,3,4)
assert dictionary[1]!=0;node=dictionary[1]
assert C.string_at(node,17)==uuid.raw[:17]
assert C.string_at(node+0x11)==b'positive-control'
assert struct.unpack('<III',C.string_at(node+0x54,12))==(2,3,4)
libc.free.argtypes=[C.c_void_p];libc.free(C.c_void_p(node));dictionary[1]=0
print(json.dumps({'results':results,'original_insert_positive_control':'pass','scope':'Exact stock worker and Insert machine code with controlled cache UUID/return projections. QNX full parser and actual SSD index tables not executed.'},indent=2))
