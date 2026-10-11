"""Execute stock cold cache parser and switch, with host I/O and no-op locks.
Not QNX execution. Includes actual cache list and full stock manifest parser.
"""
import ctypes as C,mmap,struct,re,subprocess,os,time,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
raw=(ROOT/'audit/B13_on_1.2/candidate_qnx.elf').read_bytes()
m=mmap.mmap(-1,0x400000,prot=7);addr=C.addressof(C.c_char.from_buffer(m));keep=[];lib=C.CDLL(None)
def q(o,v):struct.pack_into('<Q',m,o,v)
def jump(o,fn):
 p=fn if isinstance(fn,int) else C.cast(fn,C.c_void_p).value
 m[o:o+12]=b'\x48\xb8'+struct.pack('<Q',p)+b'\xff\xe0'
# ELF load and RELATIVE data relocations
phoff=struct.unpack_from('<Q',raw,32)[0];phnum=struct.unpack_from('<H',raw,56)[0]
for i in range(phnum):
 typ,flags,off,va,pa,fs,ms,al=struct.unpack_from('<IIQQQQQQ',raw,phoff+56*i)
 if typ==1:m[va:va+fs]=raw[off:off+fs]
shoff=struct.unpack_from('<Q',raw,40)[0];shnum=struct.unpack_from('<H',raw,60)[0]
for i in range(shnum):
 sh=struct.unpack_from('<IIQQQQIIQQ',raw,shoff+64*i)
 if sh[1]==4:
  for j in range(sh[4],sh[4]+sh[5],24):
   target,info,add=struct.unpack_from('<QQq',raw,j)
   if info&0xffffffff==8:q(target,addr+add)
# Trap all PLT entries first; replace dependencies used below.
syms={int(a,16):n for a,n in re.findall(r'^([0-9a-f]+) <([^>]+)@plt>:',subprocess.check_output(['objdump','-d','-C',str(ROOT/'audit/B13_on_1.2/candidate_qnx.elf')],text=True),re.M)}
for o in syms:m[o:o+2]=b'\x0f\x0b'
zero=addr+0x300100;m[0x300100:0x300103]=b'\x31\xc0\xc3'
funcs={'open':lib.open,'read':lib.read,'close':lib.close,'strcpy':lib.strcpy,'stpcpy':lib.stpcpy,'strcmp':lib.strcmp,'strrchr':lib.strrchr,'memcpy':lib.memcpy,'memset':lib.memset,'atoi':lib.atoi,'atof':lib.atof,'operator new(unsigned long)':lib.malloc,'operator new[](unsigned long)':lib.malloc,'operator delete(void*)':lib.free,'operator delete[](void*)':lib.free}
STAT=C.CFUNCTYPE(C.c_int,C.c_char_p,C.c_void_p)
@STAT
def stat(path,out):
 try:C.memset(out,0,120);C.c_uint64.from_address(out+8).value=os.stat(path).st_size;return 0
 except OSError:return -1
keep.append(stat);funcs['stat']=stat
for o,n in syms.items():
 if n in funcs:jump(o,funcs[n])
 elif n.startswith('pthread_rwlock_'):jump(o,zero)
jump(0x46100,lib.malloc);jump(0x46150,lib.free);jump(0x49fd0,zero)
q(0x29ffa8,addr+0x300108);q(0x300108,0x12345678)
cachefn=C.CFUNCTYPE(C.c_void_p)(addr+0x34b90)
cache=cachefn()
GET=C.CFUNCTYPE(C.c_int,C.c_void_p,C.c_char_p,C.c_char_p,C.c_void_p,C.c_void_p,C.c_void_p,C.c_void_p,C.c_void_p)
get=GET(addr+0x34ef0);fast=GET(addr+0xf9240)
switch=C.CFUNCTYPE(C.c_int,C.c_void_p,C.c_void_p)(addr+0x35860)
files=sorted((ROOT/'audit/manifests/px-grp-export').rglob('*.grp'))
first=files[0];p=str(first).encode();v=str(first.parent).encode()
print('probe',first,flush=True)
u=C.create_string_buffer(17);print('fast',fast(cache,p,v,None,None,None,None,u),u.raw.hex(),flush=True)
# Same cache initially empty. Execute constructor-equivalent SwitchSampleGroup.
slot=C.create_string_buffer(0x688);folder=C.create_string_buffer(0x408)
C.memmove(folder,v,len(v)+1);C.memmove(C.addressof(folder)+512,p,len(p)+1)
t=time.monotonic();print('cold switch',switch(slot,folder),'seconds',time.monotonic()-t,flush=True)
t=time.monotonic();print('warm switch',switch(slot,folder),'seconds',time.monotonic()-t,flush=True)
print('cache head',hex(C.c_uint64.from_address(cache).value),'wav head',hex(C.c_uint64.from_address(C.addressof(slot)+0x680).value),flush=True)

# Probe all real manifests through the actual stock cache miss path.
results=[]
for path in files:
 out=C.create_string_buffer(17)
 rc=get(cache,str(path).encode(),str(path.parent).encode(),None,None,None,None,out)
 assert rc==0,(path,rc)
 results.append(out.raw.hex())
assert set(results)=={'00'*17}
print('full stock cache parser: all',len(results),'manifests passed',flush=True)

files=sorted((ROOT/'audit/manifests/px-grp-export').rglob('*.grp'));assert files
root=ROOT/'audit/manifests/px-grp-export'
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

import threading
for o,n in syms.items():
 if n in ('ThreadCtl','pthread_self','pthread_setschedprio'):jump(o,zero)
q(0x29ff90,addr+0x300200);q(0x300200,addr+0x300220)
struct.pack_into('<H',m,0x300226,4)
records=[]
DICT=C.CFUNCTYPE(None,C.c_void_p,C.c_void_p,C.c_char_p,C.c_uint,C.c_uint,C.c_uint)
@DICT
def capture(thiz,uuid,name,g,cat,index):
 records.append((C.string_at(uuid,17).hex(),name.decode(),g,cat,index))
keep.append(capture)
vtable=(C.c_uint64*3)(0,0,C.cast(capture,C.c_void_p).value);dictionary=(C.c_uint64*16)();dictionary[0]=C.addressof(vtable)
worker=C.CFUNCTYPE(C.c_void_p,C.c_void_p)(addr+0x350e0)
for trial in range(5):
 records.clear();states=[(C.c_uint64*3)(cpu,C.addressof(groups),C.addressof(dictionary)) for cpu in range(4)]
 threads=[threading.Thread(target=worker,args=(state,)) for state in states]
 for thread in threads:thread.start()
 for thread in threads:thread.join(10);assert not thread.is_alive()
 assert len(records)==927 and all(C.c_int.from_address(C.addressof(state)).value==-1 for state in states)
 print('concurrent exact worker trial',trial+1,'passed',flush=True)
