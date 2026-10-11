import proposal as p
s=p.s
import csv,json,collections,math
wave=None;rows=[];counts=collections.Counter();worst=[]
for old in csv.DictReader(open(p.O/'phase.csv')):
 if not int(old['corrected']):continue
 if wave!=old['wave']:wave=old['wave'];s.waveform(wave)
 mode,rev,L,at,delta,cf,N=[int(old[k]) for k in ['mode','reverse','L','p','delta','cf','remaining']]
 outputs=[];sources=[]
 for enabled in [False,True]:
  p.enabled=enabled;s.init(mode,rev,L,at,cf);before,be,bt=s.render(256,1);prior=before[0];s.bounds(60025+(delta if rev else -delta),L)
  y=[];tags=[]
  while len(y)<N+2:
   used=min(4096,N+2-len(y));z,e,t=s.render(used,used);y+=z;tags+=t
  outputs.append([prior]+y);sources.append(tags)
 assert sources[0]==sources[1]
 a,b=outputs;natural=s.sample[2*sources[1][N]]-s.sample[2*(sources[1][N]-(1 if not rev else -1))]
 entry=b[1]-b[0];handoff=b[N+1]-b[N]
 assert entry==int(old['control_step'])
 assert handoff==natural
 ds0=[abs(v-u) for u,v in zip(a,a[1:])];ds1=[abs(v-u) for u,v in zip(b,b[1:])]
 row=dict(wave=wave,L=L,mode=mode,reverse=rev,delta=delta,cf=cf,p=at,N=N,old_entry=a[1]-a[0],new_entry=entry,old_handoff=a[N+1]-a[N],new_handoff=handoff,natural_handoff=natural,old_max_step=max(ds0),new_max_step=max(ds1),source_max=int(old['source_max']),source_frames_equal=True)
 rows.append(row);counts['cases']+=1
 if counts['cases']%1000==0:print(dict(counts),flush=True)
with open(p.O/'handoff_sweep.csv','w') as f:
 w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
groups=collections.defaultdict(list)
for r in rows:groups[tuple(r[k] for k in ['wave','L','mode','reverse','delta','cf'])].append(r)
summary=[]
for key,a in groups.items():
 z=dict(zip(['wave','L','mode','reverse','delta','cf'],key));z.update(n=len(a),min_N=min(r['N'] for r in a),max_N=max(r['N'] for r in a),old_entry_max=max(abs(r['old_entry']) for r in a),new_entry_max=max(abs(r['new_entry']) for r in a),old_handoff_max=max(abs(r['old_handoff']) for r in a),new_handoff_max=max(abs(r['new_handoff']) for r in a),old_transition_max=max(r['old_max_step'] for r in a),new_transition_max=max(r['new_max_step'] for r in a),handoff_excess_max=max(abs(r['new_handoff']-r['natural_handoff']) for r in a));summary.append(z)
(p.O/'handoff_summary.json').write_text(json.dumps(summary,indent=2))
assert s.P.read_bytes()==s.raw
print('completed',dict(counts),flush=True)
