import proposal as p
s=p.s
import csv,json,math,collections,hashlib
results=[];counts=collections.Counter();examples={};wave=None
f=open(p.O/'phase.csv','w');fields=['wave','L','mode','reverse','delta','cf','p','branch','old_step','new_step','control_step','old_excess','new_excess','source_max','corrected','remaining','first_out','first_in']
w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
for old in csv.DictReader(open(s.O/'sweep.csv')):
 if wave!=old['wave']:wave=old['wave'];s.waveform(wave)
 mode,rev,L,at,delta,cf=[int(old[k]) for k in ['mode','reverse','length_input','p','delta','crossfade']]
 p.enabled=True
 r,y=s.trial(mode,rev,L,at,delta,cf,post=8)
 ev=r['events'];first=next((e for e in ev if e['dest']==0),None)
 corrected=bool(first and first['corrected'])
 assert r['cursor']==int(old['cursor'])
 if first:
  assert first['source_out']==int(old['source_out']) and first['source_in']==int(old['source_in'])
 row=dict(wave=wave,L=L,mode=mode,reverse=rev,delta=delta,cf=cf,p=at,branch=old['branch'],old_step=int(old['step']),new_step=r['step'],control_step=int(old['control_step']),old_excess=int(old['edit_excess']),new_excess=r['step']-int(old['control_step']),source_max=int(old['source_max_slope']),corrected=int(corrected),remaining=first.get('remaining',0) if first else 0,first_out=first['source_out'] if first else r['tags'][0],first_in=first['source_in'] if first else -1)
 if not corrected:assert row['new_step']==row['old_step']
 else:assert row['new_excess']==0 # exact outgoing-only entry, including both modes/directions
 w.writerow(row);results.append(row);counts['trials']+=1;counts['corrected']+=corrected
 key=(wave,L,mode,rev,delta,cf,old['branch'])
 if key not in examples or abs(row['old_excess'])>abs(examples[key]['row']['old_excess']):examples[key]=dict(row=row,trace=r,after=y)
 if counts['trials']%10000==0:print(dict(counts),flush=True)
f.close()
summary=[]
groups=collections.defaultdict(list)
for r in results:groups[tuple(r[k] for k in ['wave','L','mode','reverse','delta','cf','branch'])].append(r)
for key,rows in groups.items():
 d=dict(zip(['wave','L','mode','reverse','delta','cf','branch'],key));d.update(n=len(rows),corrected=sum(r['corrected'] for r in rows),old_max_step=max(abs(r['old_step']) for r in rows),new_max_step=max(abs(r['new_step']) for r in rows),old_max_excess=max(abs(r['old_excess']) for r in rows),new_max_excess=max(abs(r['new_excess']) for r in rows));summary.append(d)
(p.O/'phase_summary.json').write_text(json.dumps(summary,indent=2));(p.O/'phase_examples.json').write_text(json.dumps(list(examples.values()),indent=2));(p.O/'phase_counts.json').write_text(json.dumps(dict(counts),indent=2))
assert s.P.read_bytes()==s.raw
