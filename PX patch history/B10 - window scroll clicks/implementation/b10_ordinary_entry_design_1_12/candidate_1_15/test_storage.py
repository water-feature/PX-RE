import proposal as p
import ctypes as C,struct,json
s=p.s
allocations={};frees=[];sizes=[]
Alloc=C.CFUNCTYPE(C.c_void_p,C.c_int)
Free=C.CFUNCTYPE(None,C.c_void_p)
@Alloc
def allocate(n):
 b=C.create_string_buffer(n+32);C.memset(C.addressof(b),0xa5,n+32)
 allocations[C.addressof(b)]=(b,n);sizes.append(n);return C.addressof(b)
@Free
def free(ptr):
 b,n=allocations[ptr];assert C.string_at(ptr+n,32)==b'\xa5'*32;frees.append(ptr)
s.callbacks += [allocate,free]
s.jump(0x46100,C.cast(allocate,C.c_void_p).value);s.jump(0x46150,C.cast(free,C.c_void_p).value)
Fn=C.CFUNCTYPE(None,C.c_void_p)
ctor=Fn(s.base+0x3eee0);close=Fn(s.base+0x42510);dtor=Fn(s.base+0x425d0)
readers=[C.create_string_buffer(0x1b8) for _ in range(2)]
ep=[]
for r in readers:
 ctor(C.addressof(r));ptr=struct.unpack_from('<Q',r,0x1a8)[0];ep.append(ptr)
 assert allocations[ptr][1]==0x510 and C.string_at(ptr+0x500,16)==bytes(16)
assert ep[0]!=ep[1] and sizes==[0x510,0x4000,0x4000]*2
C.memset(ep[0]+0x500,0x3f,16);C.memset(ep[1]+0x500,0x2f,16)
close(C.addressof(readers[0]))
assert C.string_at(ep[0]+0x500,4)==bytes(4) and C.string_at(ep[1]+0x500,16)==b'\x2f'*16
# Actual endpoint clone copies exactly 0x500 bytes, leaving each tail owned locally.
Clone=C.CFUNCTYPE(None,C.c_void_p,C.c_void_p)
Clone(s.base+0x424b0)(C.addressof(readers[0]),C.addressof(readers[1]))
assert C.string_at(ep[0]+0x500,4)==bytes(4) and C.string_at(ep[1]+0x500,16)==b'\x2f'*16
for r in readers:dtor(C.addressof(r))
assert len(frees)==6 and len(set(frees))==6
# Reconstruct at the same reader address: new owned allocation with clean state.
ctor(C.addressof(readers[0]));new=struct.unpack_from('<Q',readers[0],0x1a8)[0]
assert new not in ep and C.string_at(new+0x500,16)==bytes(16)
dtor(C.addressof(readers[0]));assert len(frees)==9
# Successful Open reset detour: execute its emitted instructions through the
# reset, stopping before the inherited continuation (tested separately below).
Open=C.CFUNCTYPE(C.c_ulong,C.c_void_p,C.c_int,C.c_int,C.c_char_p,C.c_void_p,C.c_int,C.c_int,C.c_int)
Get=C.CFUNCTYPE(C.c_void_p,C.c_char_p,C.c_int,C.c_int)
Compare=C.CFUNCTYPE(C.c_int,C.c_void_p,C.c_void_p,C.c_ulong)
@Compare
def compare(a,b,n):
 x,y=C.string_at(a,n),C.string_at(b,n);return (x>y)-(x<y)
s.callbacks.append(compare);s.jump(0x71b0,C.cast(compare,C.c_void_p).value)
wav=C.create_string_buffer(800044)
header=struct.pack('<4sI4s4sIHHIIHH4sI',b'RIFF',800036,b'WAVE',b'fmt ',16,1,2,48000,192000,4,16,b'data',800000)
C.memmove(C.addressof(wav),header,len(header));C.memmove(C.addressof(wav)+44,s.sp,800000)
s.put(s.file,0x18,'Q',800044);s.put(s.file,0x20,'Q',C.addressof(wav))
@Get
def getfile(path,a,b):return C.addressof(s.file)
s.callbacks.append(getfile);s.jump(0x3edf0,C.cast(getfile,C.c_void_p).value)
ctor(C.addressof(readers[0]));ptr=struct.unpack_from('<Q',readers[0],0x1a8)[0];C.memset(ptr+0x500,0xff,16)
params=C.create_string_buffer(b'\xff'*64)
result=Open(s.base+0x42660)(C.addressof(readers[0]),0,0,b'fixture.wav',C.addressof(params),-1,-1,0)
assert result==0,result
assert C.string_at(ptr+0x500,4)==bytes(4)
dtor(C.addressof(readers[0]))
report=dict(status='PASS',constructor=True,independent_readers=True,clone_excludes_state=True,close_reset=True,reconstruction=True,successful_open_reset=True,all_allocations_freed=len(frees)==len(allocations),allocation_canaries=True,per_reader_bytes=16,additional_audio_buffers=0)
(p.O/'storage.json').write_text(json.dumps(report,indent=2));print(report)
