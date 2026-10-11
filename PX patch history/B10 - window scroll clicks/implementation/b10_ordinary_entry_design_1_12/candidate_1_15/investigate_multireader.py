"""Read-only emitted .15 timing experiment; no firmware build or semantic patch."""
import proposal as p
import ctypes as C,csv,json,hashlib,collections
s=p.s;p.enabled=True
Ns=[0,1,2,3,4,8,16,32,64,128,512,2048]
rates=[.5,1.,2.]
def select(f):
 for k in ['reader','ep','bufs','rp','bp','tags']:setattr(s,k,f[k])
def fresh():
 f=dict(reader=C.create_string_buffer(0x200),ep=C.create_string_buffer(0x510),bufs=[C.create_string_buffer(16384) for _ in range(2)],tags=[[-1]*8192 for _ in range(2)])
 f['rp']=C.addressof(f['reader']);f['bp']=[C.addressof(b) for b in f['bufs']];return f
def render(n,rate):
 s.events.clear();ready=C.c_ubyte();assert s.read(s.rp,n,rate,None,C.byref(ready))==0 and ready.value
 y=list((C.c_int16*(n*2)).from_address(s.bp[0]))[::2];ev=list(s.events);tags=s.tags[0][:2*n:2]
 assert s.update(s.rp,n)==0
 return y,ev,tags
rows=[];isolation=0;rate_signatures=collections.defaultdict(dict)
for wave in ['periodic','rich']:
 s.waveform(wave)
 for mode in [0,1]:
  for rev in [0,1]:
   for ping in [0,1]:
    for phase in range(100):
     center=60025+phase;edited=center+(8000 if rev else -8000)
     for rate in rates:
      select(fresh());s.init(mode,rev,12050,int(edited+12050*.45*(1 if not rev else -1)),ping=ping,center=edited);s.put(s.reader,0x1b4,'B',1-rev)
      _,ev,_=render(1,rate);st,en=ev[0]['start'],ev[0]['end'];direction=1 if en>st else -1
      for batch in range(3):
       fs=[]
       for j,N in enumerate(Ns[batch*4:batch*4+4]):
        f=fresh();select(f);at=en-direction*(N+1);s.init(mode,rev,12050,at,ping=ping,center=center);s.put(s.reader,0x1b4,'B',1-rev)
        y,_,_=render(1,rate);s.bounds(edited,12050)
        f.update(N=N,y=[],t=[],events=[],prior=y[0],j=j,at=at);fs.append(f)
       # Serial reference from snapshots, followed by independently partitioned interleaving.
       refs=[]
       for f in fs:
        select(f);saved=bytes(s.reader),bytes(s.ep)
        y,e,t=render(f['N']+2,rate);refs.append((y,t))
        C.memmove(s.rp,saved[0],len(saved[0]));C.memmove(C.addressof(s.ep),saved[1],len(saved[1]))
       turn=0
       while any(len(f['y'])<f['N']+2 for f in fs):
        for f in fs:
         left=f['N']+2-len(f['y'])
         if not left:continue
         select(f);n=min(left,[1,7,31,64,257][(turn+f['j'])%5]);y,e,t=render(n,rate)
         f['y']+=y;f['t']+=t;f['events']+=e
        turn+=1
       for f,(ref,tags) in zip(fs,refs):
        assert f['t']==tags
        diff=max(abs(a-b) for a,b in zip(f['y'],ref));assert diff<=1;isolation+=1
        N=f['N'];y=f['y'];ds=[abs(b-a) for a,b in zip([f['prior']]+y,y)]
        corrected=next((v for v in f['events'] if v['corrected']),None)
        if N:assert corrected and abs(corrected['end']-corrected['origin'])==N
        incoming_dir=direction if not ping else -direction
        src=f['t'][N];natural=int(s.sample[2*src])-int(s.sample[2*(src-incoming_dir)])
        if N>=2:assert y[N]-y[N-1]==natural
        rows.append(dict(wave=wave,mode=mode,reverse=rev,ping=ping,phase=phase,rate=rate,reader=f['j'],initial_playhead=f['at'],N=N,corrected=bool(corrected),entry=ds[0],interior=max(ds[1:N],default=0),handoff=ds[N],max_step=max(ds[:N+1]),max_index=max(range(N+1),key=lambda k:ds[k]),natural_handoff=abs(natural),partition_difference=diff))
        rate_signatures[(wave,mode,rev,ping,phase,N)][rate]=(ref,tags)
    print('completed',wave,mode,rev,ping,len(rows),flush=True)
with open(p.O/'multireader_timing.csv','w') as out:
 w=csv.DictWriter(out,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
groups=[]
for rate in rates:
 for N in Ns:
  a=[r for r in rows if r['rate']==rate and r['N']==N]
  groups.append(dict(rate=rate,N=N,cases=len(a),max_step=max(r['max_step'] for r in a),interior_max=max(r['interior'] for r in a),entry_max=max(r['entry'] for r in a),handoff_max=max(r['handoff'] for r in a),interior_worst_cases=sum(r['max_index'] not in [0,N] for r in a)))
report=dict(status='PASS',scope='Host execution of saved emitted reader code; no resampler or mixer',cases=len(rows),independent_readers=4,isolation_comparisons=isolation,rate_identical_groups=sum(all(v==a[1.] for v in a.values()) for a in rate_signatures.values()),rate_groups=len(rate_signatures),firmware_sha256=hashlib.sha256(p.patch).hexdigest(),groups=groups)
assert (p.O/'voice_2.2.2.1.15_qnx.elf').read_bytes()==p.patch
(p.O/'multireader_timing.json').write_text(json.dumps(report,indent=2));print(json.dumps(report),flush=True)
