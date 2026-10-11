import sweep as s
import csv,json,hashlib,math,collections
s.trace=True
summaries=[]; examples={}
fields=['wave','length_input','mode','reverse','delta','crossfade','p','cursor','active','branch','step','control_step','edit_excess','max_step','source_local_slope','source_max_slope','ratio_source_max','first_site','first_progress','source_out','source_in']
f=open(s.O/'sweep.csv','w');w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
for wave in ['periodic','rich']:
 slope=s.waveform(wave)
 for L in [12050,24050]:
  for mode in range(2):
   for rev in range(2):
    for delta,cf,stride in [(800,255,4),(-800,255,16),(128,255,16),(2000,255,16),(800,50,16),(800,128,16)]:
     groups=collections.defaultdict(list)
     # Sweep the full unquantized window; Pitched computes its own period-rounded boundaries.
     A=60025-L//2;B=A+L
     for p in range(A+1,B,stride):
      r,y=s.trial(mode,rev,L,p,delta,cf,post=8)
      c,cy=s.trial(mode,rev,L,p,0,cf,post=8)
      ev=r['events']; first=next((e for e in ev if e['dest']==0),None)
      if r['active']:branch='retained_splice'
      elif first and first['site'] in ['0x41060','0x41237','0x406f6','0x41584']:branch='forced'
      elif first:branch='ordinary_entry'
      else:branch='direct'
      local=abs(s.sample[2*(r['cursor']-(1 if rev else 0))]-s.sample[2*(r['cursor']-(0 if rev else 1))])
      row=dict(wave=wave,length_input=L,mode=mode,reverse=rev,delta=delta,crossfade=cf,p=p,cursor=r['cursor'],active=r['active'],branch=branch,step=r['step'],control_step=c['step'],edit_excess=r['step']-c['step'],max_step=r['max_step'],source_local_slope=local,source_max_slope=slope['max'],ratio_source_max=abs(r['step'])/slope['max'],first_site=first['site'] if first else '',first_progress=(first['cur']-first['start'])/(first['end']-first['start']) if first and first['end']!=first['start'] else 0,source_out=first['source_out'] if first else r['tags'][0],source_in=first['source_in'] if first else -1)
      w.writerow(row);groups[branch].append(row)
      key=(wave,L,mode,rev,delta,cf,branch)
      if key not in examples or abs(row['edit_excess'])>abs(examples[key]['row']['edit_excess']):examples[key]=dict(row=row,edited=r,control=c,after=y,control_after=cy)
     n=sum(map(len,groups.values()))
     for branch,rows in groups.items():
      z=[abs(r['step']) for r in rows];ex=[abs(r['edit_excess']) for r in rows]
      summaries.append(dict(wave=wave,L=L,mode=mode,reverse=rev,delta=delta,cf=cf,stride=stride,branch=branch,n=len(rows),total=n,branch_fraction=len(rows)/n,max_step=max(z),max_edit_excess=max(ex),rms_edit_excess=math.sqrt(sum(v*v for v in ex)/len(ex)),steps_over_4x_source_max=sum(v>4*slope['max'] for v in z),excess_over_4x_source_max=sum(v>4*slope['max'] for v in ex),source_slope=slope,pmin=min(r['p'] for r in rows),pmax=max(r['p'] for r in rows)))
     print('done',wave,L,mode,rev,delta,cf,n,flush=True)
f.close()
(s.O/'summary.json').write_text(json.dumps(summaries,indent=2))
(s.O/'examples.json').write_text(json.dumps(list(examples.values()),indent=2))
(s.O/'identity.json').write_text(json.dumps(dict(input=str(s.P),sha256=hashlib.sha256(s.raw).hexdigest(),unchanged=s.raw==s.P.read_bytes(),reextracted_identical=s.raw==(s.P.parent/'reextracted_qnx.elf').read_bytes(),execution='unmodified emitted .12 routines via x86_64 Python ctypes under Rosetta; host-only memory bindings/instrumentation, no compilation',displacement='synthetic source-frame translation',q=100,rate=48000,stereo=True,post_frames=8,pre_consumed=1),indent=2))
