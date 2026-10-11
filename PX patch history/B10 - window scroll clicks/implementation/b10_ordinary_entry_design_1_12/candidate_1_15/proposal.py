# SPDX-License-Identifier: GPL-2.0-or-later
"""Harness adapter: executes the saved emitted .15 hooks; no semantic correction."""
from pathlib import Path
import ctypes as C,struct,re,json,types,sys
O=Path(__file__).resolve().parent
R=O.parents[1]
loader=R/'b10_center_sweep_1_12/sweep.py'
s=types.ModuleType('emitted_sweep');s.__file__=str(loader);sys.modules[s.__name__]=s
source=loader.read_text().replace("sum([tags[j][z+2*k:z+2*k+2] for k in range(n-1,-1,-1)],[])","[v for k in range(n-1,-1,-1) for v in tags[j][z+2*k:z+2*k+2]]")
exec(compile(source,str(loader),'exec'),s.__dict__)
s.ep=C.create_string_buffer(0x510)
rawread=s.read;rawupdate=s.update
orig_init=s.init
state={'corrected':False};enabled=True;capture_streams=False;pending=None
stats=dict(starts=0,commits=0,retained_calls=0,one_frame=0)
ORD={0x4056f,0x40849,0x40e5d,0x40f79,0x40ad0,0x40c27};RET={0x3fd79,0x41390}
FORCED={0x406f6,0x41060,0x41237,0x41584}
meta=json.loads((O/'emission.json').read_text());sym=meta['symbols']
def flags():return struct.unpack_from('<I',s.ep,0x500)[0]
def init(*a,**k):
 C.memset(C.addressof(s.ep),0,0x510);state['corrected']=False
 orig_init(*a,**k)
s.init=init
Entry=C.CFUNCTYPE(None,C.c_void_p,C.c_void_p,*([C.c_int]*9),C.c_void_p,C.c_ulong)
actual=Entry(s.base+sym['entry_fade'])
def event(d,src,start,end,cur,last,ping,w,ch,en,mode,site,run):
 dj,dz=s.find(d);sj,sz=s.find(src);width=w*ch;offset=(d-s.bp[0])//width
 ev=dict(site=hex(site),dest=dz,offset=offset,source_out=s.tags[dj][dz],source_in=s.tags[sj][sz],start=start,end=end,cur=cur,last=last,mode=mode,enabled=en,ping=ping,corrected=False)
 run()
 f=flags();fresh=site in ORD and bool(f&4) and offset==0 and struct.unpack_from('<i',s.ep,0x504)[0]==cur
 corrected=enabled and (fresh or (site in RET and bool(f&2)))
 if corrected:
  origin=cur if fresh else start;ev.update(corrected=True,origin=origin,remaining=abs(end-origin)-abs(cur-origin),source_in=s.tags[sj][sz])
  stats['starts' if fresh else 'retained_calls']+=1
  stats['one_frame']+=abs(end-origin)==1
 if capture_streams:
  n=abs(last-cur);ev['out_sources']=s.tags[dj][dz:dz+n*ch:ch];ev['in_sources']=s.tags[sj][sz:sz+n*ch:ch]
 if s.trace:s.events.append(ev)
@Entry
def observed(d,src,start,end,cur,last,ping,w,ch,en,mode,r,site):
 event(d,src,start,end,cur,last,ping,w,ch,en,mode,site,lambda:actual(d,src,start,end,cur,last,ping,w,ch,en,mode,r,site))
s.callbacks.append(observed)
# Baseline trace adapters retain original emitted FadeBuffer behavior.
for site,target in re.findall(r'^\s*([0-9a-f]+):.*callq\s+0x([0-9a-f]+)',s.dis,re.M):
 site,target=int(site,16),int(target,16)
 if target!=0x3f2f0:continue
 def make(site):
  @s.Fade
  def cb(d,src,st,en,cur,last,ping,w,ch,on,mode):
   event(d,src,st,en,cur,last,ping,w,ch,on,mode,site,lambda:s.fade(d,src,st,en,cur,last,ping,w,ch,on,mode))
  return cb
 cb=make(site);s.callbacks.append(cb);dest=0x2d0000+len(s.callbacks)*16;s.jump(dest,C.cast(cb,C.c_void_p).value);s.put(s.mem,site+1,'i',dest-site-5)
baseline=bytes(s.mem)
patch=(O/'voice_2.2.2.1.15_qnx.elf').read_bytes()
for k in range(struct.unpack_from('<H',patch,56)[0]):
 off=struct.unpack_from('<Q',patch,32)[0]+56*k;typ,fl,fo,va,pa,sz,ms,al=struct.unpack_from('<II6Q',patch,off)
 if typ==1:s.mem[va:va+sz]=patch[fo:fo+sz]
s.put(s.mem,0x29ffa8,'Q',C.addressof(s.guard))
s.jump(0x7b20,C.cast(s.copy,C.c_void_p).value);s.jump(0x73f0,C.cast(s.zero,C.c_void_p).value)
for site,target in re.findall(r'^\s*([0-9a-f]+):.*callq\s+0x([0-9a-f]+)',s.dis,re.M):
 if int(target,16)==0x49db0:s.put(s.mem,int(site,16)+1,'i',0x2f0020-int(site,16)-5)
s.jump(0x2f0020,C.cast(s.reverse,C.c_void_p).value)
for site in FORCED:s.mem[site:site+5]=baseline[site:site+5]
dis=s.subprocess.check_output(['objdump','-d','--start-address='+str(sym['fade_hook']),'--stop-address='+str(sym['close_hook']),str(O/'voice_2.2.2.1.15_qnx.elf')],text=True)
sites=[int(a,16) for a,b in re.findall(r'^\s*([0-9a-f]+):.*callq\s+0x([0-9a-f]+)',dis,re.M) if int(b,16)==sym['entry_fade']];assert len(sites)==1
s.jump(0x2c0000,C.cast(observed,C.c_void_p).value);s.put(s.mem,sites[0]+1,'i',0x2c0000-sites[0]-5)
patched=bytes(s.mem);current=True
def read(*args):
 global current,pending
 if current!=enabled:s.mem[:]=patched if enabled else baseline;current=enabled
 pending={};return rawread(*args)
def update(*args):
 before=bool(flags()&2);result=rawupdate(*args);state['corrected']=bool(flags()&2)
 stats['commits']+=state['corrected'] and not before
 return result
s.read=read;s.update=update;s.trace=True
