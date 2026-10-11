# SPDX-License-Identifier: GPL-2.0-or-later
from pathlib import Path
import ctypes as C, mmap, struct, math, subprocess, re, json, hashlib, csv, collections, sys
O=Path(__file__).resolve().parent
P=O.parent/'b7_lfo_center_investigation/implementation_1_12/voice_2.2.2.1.12_qnx.elf'
raw=P.read_bytes(); mem=mmap.mmap(-1,0x300000,prot=7); base=C.addressof(C.c_char.from_buffer(mem))
for k in range(struct.unpack_from('<H',raw,56)[0]):
 off=struct.unpack_from('<Q',raw,32)[0]+k*struct.unpack_from('<H',raw,54)[0]
 typ,flags,fo,va,pa,sz,ms,al=struct.unpack_from('<II6Q',raw,off)
 if typ==1: mem[va:va+sz]=raw[fo:fo+sz]
def put(p,o,fmt,v): struct.pack_into('<'+fmt,p,o,v)
def gi(o): return struct.unpack_from('<i',reader,o)[0]
def jump(off,ptr): mem[off:off+12]=b'\x48\xb8'+struct.pack('<Q',ptr)+b'\xff\xe0'
guard=C.c_uint64(12345);put(mem,0x29ffa8,'Q',C.addressof(guard))
reader=C.create_string_buffer(0x200); rp=C.addressof(reader)
bufs=[C.create_string_buffer(16384) for _ in range(2)]; bp=[C.addressof(b) for b in bufs]
sample=(C.c_int16*400000)(); sp=C.addressof(sample)
file=C.create_string_buffer(0x40);ep=C.create_string_buffer(0x500)
Read=C.CFUNCTYPE(C.c_uint64,C.c_void_p,C.c_int,C.c_float,C.c_void_p,C.c_void_p)
Update=C.CFUNCTYPE(C.c_uint64,C.c_void_p,C.c_int)
Fade=C.CFUNCTYPE(None,C.c_void_p,C.c_void_p,*([C.c_int]*9))
Rev=C.CFUNCTYPE(None,C.c_void_p,C.c_int,C.c_int)
read=Read(base+0x3f840);update=Update(base+0x41870);fade=Fade(base+0x3f2f0);revcode=Rev(base+0x49db0)
events=[]; tags=[[-1]*8192 for _ in range(2)]; trace=False
# Tags identify actual source positions, including buffer-to-buffer copies.
def find(p):
 for j,b in enumerate(bp):
  if b<=p<b+16384: return j,(p-b)//2
 return None
Copy=C.CFUNCTYPE(C.c_void_p,C.c_void_p,C.c_void_p,C.c_size_t)
@Copy
def copy(d,s,n):
 if trace:
  dest=find(d)
  if dest:
   j,z=dest; src=find(s)
   if sp<=s<sp+800000: tags[j][z:z+n//2]=[(k//2) for k in range((s-sp)//2,(s-sp)//2+n//2)]
   elif src: tags[j][z:z+n//2]=tags[src[0]][src[1]:src[1]+n//2]
 C.memmove(d,s,n);return d
Zero=C.CFUNCTYPE(C.c_void_p,C.c_void_p,C.c_int,C.c_size_t)
@Zero
def zero(d,c,n):
 if trace and find(d):
  j,z=find(d);tags[j][z:z+n//2]=[-1]*(n//2)
 C.memset(d,c,n);return d
@Rev
def reverse(p,w,n):
 revcode(p,w,n)
 if trace:
  j,z=find(p);tags[j][z:z+2*n]=sum([tags[j][z+2*k:z+2*k+2] for k in range(n-1,-1,-1)],[])
callbacks=[copy,zero,reverse]
jump(0x7b20,C.cast(copy,C.c_void_p).value);jump(0x73f0,C.cast(zero,C.c_void_p).value)
dis=subprocess.check_output(['objdump','-d','--start-address=0x3f840','--stop-address=0x417ea',str(P)],text=True)
def mkfade(site):
 @Fade
 def wrapped(d,s,start,end,cur,last,ping,w,ch,en,mode):
  if trace:
   dj,dz=find(d);sj,sz=find(s)
   events.append(dict(site=hex(site),dest=dz,source_out=tags[dj][dz],source_in=tags[sj][sz],start=start,end=end,cur=cur,last=last,mode=mode,enabled=en,ping=ping))
  fade(d,s,start,end,cur,last,ping,w,ch,en,mode)
 return wrapped
for site,target in re.findall(r'^\s*([0-9a-f]+):.*callq\s+0x([0-9a-f]+)',dis,re.M):
 site,target=int(site,16),int(target,16)
 if target in (0x3f2f0,0x49db0):
  if target==0x3f2f0: cb=mkfade(site);callbacks.append(cb);dest=0x2e0000+len(callbacks)*16;jump(dest,C.cast(cb,C.c_void_p).value)
  else: dest=0x2f0020;jump(dest,C.cast(reverse,C.c_void_p).value)
  put(mem,site+1,'i',dest-site-5)
def bounds(center,length,bank=None):
 for j in ([bank] if bank is not None else range(2)):
  for off,val in [(0,0),(0x80,center/199999),(0x84,center/199999),(0x100,length/199999),(0x180,1),(0x200,0)]: put(ep,j*0x280+off,'f',val)
def init(mode,rev,L,p,cf=255,q=100,ping=0,center=60025):
 C.memset(rp,0,0x200);C.memset(C.addressof(ep),0,0x500)
 put(file,0x18,'Q',800000);put(file,0x20,'Q',sp)
 for off,fmt,val in [(0x88,'Q',C.addressof(file)),(0xa0,'i',200000),(0x9c,'i',2),(0xa8,'H',2),(0xb8,'Q',bp[0]),(0xc0,'Q',bp[1]),(0x1a8,'Q',C.addressof(ep)),(0x24,'i',-1),(0xcc,'i',p),(0x94,'i',-1),(0x28,'i',1),(0x2c,'i',ping),(0x30,'i',rev),(0x38,'i',mode),(0x3c,'f',q),(0x40,'i',1),(0x44,'i',1),(0x48,'i',int(24000*(cf/255)**2)),(0x50,'i',0),(0x98,'B',1),(0x1a4,'B',1),(0x198,'f',1),(0x19c,'f',1)]:put(reader,off,fmt,val)
 bounds(center,L)
def render(n,used=None):
 events.clear(); ready=C.c_ubyte();assert read(rp,n,1,None,C.byref(ready))==0 and ready.value
 y=list((C.c_int16*(n*2)).from_address(bp[0]))[::2];ev=list(events); tg=tags[0][:2*n:2] if trace else []
 if used is not None: assert update(rp,used)==0
 return y,ev,tg
def waveform(kind):
 for j in range(200000):
  if kind=='periodic':v=12000*math.sin(2*math.pi*j/100)
  else:v=8000*math.sin(2*math.pi*j/137.3)+4000*math.sin(2*math.pi*j/401.7)+2000*math.sin(2*math.pi*j/61.1)
  sample[2*j]=sample[2*j+1]=int(v)
 slopes=[abs(sample[2*j+2]-sample[2*j]) for j in range(199999)]
 return dict(max=max(slopes),rms=math.sqrt(sum(x*x for x in slopes)/len(slopes)),p99=sorted(slopes)[int(.99*len(slopes))])
def trial(mode,rev,L,p,delta,cf=255,q=100,ping=0,pre_render=1,post=128,control=False):
 init(mode,rev,L,p,cf,q,ping)
 before,be,bt=render(pre_render,1);prior=before[0];active=reader[8][0];cursor=gi(0xcc)
 # Both producer banks updated equally: stationary Center edit with no interpolation ramp.
 bounds(60025+(delta if rev else -delta),L)
 after,ev,tg=render(post,post)
 step=after[0]-prior
 return dict(p=p,cursor=cursor,active=active,step=step,first=after[0],previous=prior,max_step=max(abs(b-a) for a,b in zip([prior]+after,after)),events=ev,tags=tg,before_events=be),after
if __name__=='__main__':
 trace=True
 waveform('periodic')
 for mode in range(2):
  for rev in range(2):
   for offset in [-3200,-3000,-2800,-2400,-100,100]:
    p=66025+offset if not rev else 54025-offset
    r,y=trial(mode,rev,12050,p,800,post=8)
    print(mode,rev,offset,json.dumps(r),flush=True)
