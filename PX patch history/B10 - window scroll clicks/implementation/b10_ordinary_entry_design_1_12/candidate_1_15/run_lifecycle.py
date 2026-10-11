# SPDX-License-Identifier: GPL-2.0-or-later
import proposal as p
s=p.s
import json,math,random,collections,hashlib
summaries=[];streams={};fail=[]
p.capture_streams=True
def setup(mode,rev,L,at,delta,enabled,ping=0,pre=256,used=1,center=60025):
 p.enabled=enabled;s.init(mode,rev,L,at,ping=ping,center=center);s.put(s.reader,0x1b4,'B',1-rev)
 y,e,t=s.render(pre,used);prior=y[used-1]
 s.bounds(center+(delta if rev else -delta),L)
 return prior

def stream(mode,rev,L,at,delta,enabled,ping=0,chunks=(256,),oversample=False,horizon=7000,edits=(),center=60025):
 prior=setup(mode,rev,L,at,delta,enabled,ping,center=center)
 ys=[];tags=[];ins=[];events=[];states=[];pos=0;ci=0
 editmap=dict(edits)
 while pos<horizon:
  if pos in editmap:s.bounds(editmap[pos],L)
  used=min(chunks[ci%len(chunks)],horizon-pos);ci+=1
  nxt=min((k for k in editmap if k>pos),default=horizon);used=min(used,nxt-pos)
  render=min(4096,max(used,256)) if oversample else used
  y,e,t=s.render(render,used)
  # Source events restricted to committed prefix; rendered but unused spans do not count.
  incoming=[None]*used
  for v in e:
   for k,source in enumerate(v.get('in_sources',[])):
    if v['offset']+k<used:incoming[v['offset']+k]=source
   if v['offset']<used:
    v=dict(v);v['position']=pos+v['offset'];v['count']=min(abs(v['last']-v['cur']),used-v['offset']);events.append(v)
  ys+=y[:used];tags+=t[:used];ins+=incoming
  states.append(dict(at=pos+used,cursor=s.gi(0xcc),active=s.reader[8][0],out=s.gi(0xc),out_start=s.gi(0x10),out_end=s.gi(0x14),in_cursor=s.gi(0x18),in_start=s.gi(0x1c),in_end=s.gi(0x20),corrected=p.state['corrected']))
  pos+=used
 return dict(prior=prior,y=ys,tags=tags,incoming=ins,events=events,states=states)
def metrics(z):
 ev=next((e for e in z['events'] if e.get('corrected')),None)
 N=abs(ev['end']-ev['origin']) if ev else None
 y=z['y'];d=[b-a for a,b in zip([z['prior']]+y,y)]
 return dict(entry=d[0],N=N,handoff=d[N] if N is not None and N<len(d) else None,last_fade_step=d[N-1] if N is not None and N>0 else None,max_step=max(map(abs,d)),corrected_events=sum(e.get('corrected',False) for e in z['events']))

def geo(mode,rev,L,center,ping=0):
 s.init(mode,rev,L,int(center+(L*.45)*(1 if not rev else -1)),ping=ping,center=center);s.put(s.reader,0x1b4,'B',1-rev)
 y,e,t=s.render(1,1);assert e
 return e[0]['start'],e[0]['end']
# Whole vs fragmented and repeated edits, both reader direction states, both modes and loop lengths.
for wave in ['periodic','rich']:
 s.waveform(wave)
 for L in [12050,24050]:
  for mode in range(2):
   for rev in range(2):
    for ping in range(2):
     st,en=geo(mode,rev,L,60025,ping);sgn=1 if en>st else -1;at=st-sgn*100
     a=stream(mode,rev,L,at,800,False,ping,horizon=7000)
     b=stream(mode,rev,L,at,800,True,ping,horizon=7000)
     c=stream(mode,rev,L,at,800,True,ping,chunks=(1,7,31,64,257,13),oversample=True,horizon=7000)
     assert a['tags']==b['tags']==c['tags']
     assert b['incoming']==c['incoming']
     # Modified envelope start may differ, every consumed cursor and source handoff must agree.
     assert a['states'][-1]['cursor']==b['states'][-1]['cursor']==c['states'][-1]['cursor']
     long=stream(mode,rev,L,at,800,True,ping,chunks=(4096,),horizon=7000)
     assert b['tags']==long['tags'] and b['incoming']==long['incoming']
     diffs=[abs(x-y) for x,y in zip(b['y'],c['y'])]
     m=metrics(b);mc=metrics(c)
     # Handoff is incoming's normal next sample; evaluate against source tags from original emitted output after fade.
     N=m['N'];incoming_handoff_source=b['tags'][N] if N is not None else None
     natural=(s.sample[2*incoming_handoff_source]-s.sample[2*(incoming_handoff_source-(sgn if not ping else -sgn))]) if N is not None else None
     assert m['entry']==a['y'][0]-a['prior'] or m['entry']==s.sample[2*b['tags'][0]]-b['prior']
     assert N is not None and m['handoff']==natural
     assert abs(mc['handoff']-natural)==0
     incoming_direction=sgn if not ping else -sgn
     assert b['incoming'][N-1]==incoming_handoff_source-incoming_direction
     assert all(v-u==incoming_direction for u,v in zip(b['incoming'][:N-1],b['incoming'][1:N]))
     summary=dict(wave=wave,L=L,mode=mode,reverse=rev,ping=ping,kind='lifecycle',baseline=metrics(a),corrected=m,fragmented=mc,split_max_difference=max(diffs),split_different_frames=sum(v!=0 for v in diffs),source_tags_equal=True,incoming_sources_partition_equal=True,long_render_max_difference=max(abs(x-y) for x,y in zip(b['y'],long['y'])),long_render_metrics=metrics(long),incoming_handoff_source=incoming_handoff_source,natural_handoff_slope=natural)
     summaries.append(summary)
     if wave=='periodic' and mode==0 and rev==0 and ping==0:streams[str(L)]=dict(old=a,new=b,fragmented=c)
     # Second edit after 17 consumed frames: excludes original fade completely, retained transition must survive.
     newcenter=60025+(25000 if rev else -25000)
     edited=stream(mode,rev,L,at,800,True,ping,chunks=(64,17,255),oversample=True,horizon=7000,edits=((17,newcenter),))
     # Also edit before any corrected sample has been consumed by discarding a render.
     prior=setup(mode,rev,L,at,800,True,ping)
     s.render(256,None);assert not p.state['corrected']
     s.bounds(60025+(1000 if rev else -1000),L)
     y,e,t=s.render(256,1)
     assert e[0]['corrected'] and e[0]['origin']==e[0]['cur']
     # Repeated identical renders consume nothing and produce identical outputs.
     setup(mode,rev,L,at,800,True,ping)
     y1,e1,t1=s.render(256,None);y2,e2,t2=s.render(256,None)
     assert y1==y2 and t1==t2 and not p.state['corrected']
     n=metrics(b)['N']
     same_partition=stream(mode,rev,L,at,800,True,ping,chunks=(64,17,255),oversample=True,horizon=7000,edits=((17,60025+(800 if rev else -800)),))
     assert edited['y'][:n]==same_partition['y'][:n]
     assert edited['tags'][:n+1]==b['tags'][:n+1]
     assert edited['incoming'][:n]==b['incoming'][:n]
     summaries.append(dict(wave=wave,L=L,mode=mode,reverse=rev,ping=ping,kind='second_edit',preserved_frames=n,unconsumed_render_restarted_at_outgoing=True,metrics=metrics(edited)))
# No-edit equivalence with actual PCM slopes, including an initially in-fade playhead (no history).
for wave in ['periodic','rich']:
 s.waveform(wave)
 for mode in range(2):
  for rev in range(2):
   for ping in range(2):
    for L in [12050,24050]:
     st,en=geo(mode,rev,L,60025,ping);sgn=1 if en>st else -1
     for at in [60025,st-sgn*100,st+sgn*100]:
      a=stream(mode,rev,L,at,0,False,ping,horizon=7000)
      b=stream(mode,rev,L,at,0,True,ping,horizon=7000)
      assert a['y']==b['y'] and a['tags']==b['tags'] and a['states']==b['states']
      summaries.append(dict(wave=wave,L=L,mode=mode,reverse=rev,ping=ping,kind='no_edit',initial_cursor=at,identical=True,max_step=metrics(b)['max_step']))
# Exhaust short-distance conditions over 100 source phases using large synthetic edits.
short=[]
for wave in ['periodic','rich']:
 s.waveform(wave)
 for mode in range(2):
  for rev in range(2):
   for ping in range(2):
    for N in [0,1,2,3,4,8,16,32,64,128]:
     agg=[]
     for phase in range(100):
      center=60025+phase;st,en=geo(mode,rev,12050,center+(8000 if rev else -8000),ping);sgn=1 if en>st else -1
      origin=en-sgn*N;at=origin-sgn
      a=stream(mode,rev,12050,at,8000,False,ping,horizon=max(N+4,16),center=center)
      b=stream(mode,rev,12050,at,8000,True,ping,horizon=max(N+4,16),center=center)
      assert a['tags']==b['tags']
      mb=metrics(b)
      if N>0:
       assert mb['N']==N
       assert mb['entry']==s.sample[2*b['tags'][0]]-b['prior']
      if N>=2:
       src=b['tags'][N]
       assert mb['handoff']==s.sample[2*src]-s.sample[2*(src-(sgn if not ping else -sgn))]
      agg.append(dict(phase=phase,old=metrics(a),new=mb))
     short.append(dict(wave=wave,mode=mode,reverse=rev,ping=ping,N=N,old_entry_max=max(abs(x['old']['entry']) for x in agg),new_entry_max=max(abs(x['new']['entry']) for x in agg),old_max_step=max(x['old']['max_step'] for x in agg),new_max_step=max(x['new']['max_step'] for x in agg),new_handoff_max=max(abs(x['new']['handoff']) for x in agg if x['new']['handoff'] is not None) if N else None,cases=agg))
     print('short',wave,mode,rev,ping,N,short[-1]['new_entry_max'],short[-1]['new_max_step'],flush=True)
(p.O/'lifecycle.json').write_text(json.dumps(summaries,indent=2));(p.O/'streams.json').write_text(json.dumps(streams));(p.O/'short_distances.json').write_text(json.dumps(short,indent=2));(p.O/'identity.json').write_text(json.dumps(dict(input=str(p.O/'voice_2.2.2.1.15_qnx.elf'),sha256=hashlib.sha256(p.patch).hexdigest(),unchanged=(p.O/'voice_2.2.2.1.15_qnx.elf').read_bytes()==p.patch,host_execution=True,firmware_build=True,stats=p.stats),indent=2))
print('completed',len(summaries),len(short),p.stats,flush=True)
