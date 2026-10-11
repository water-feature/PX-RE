# SPDX-License-Identifier: GPL-2.0-or-later
import proposal as p
s=p.s
import json,hashlib
p.capture_streams=True
out=[]
# Existing emitted-code test inputs only; report documents are not read.
for kind in ['periodic','rich']:
 s.waveform(kind)
 for mode in range(2):
  for rev in range(2):
   for ping in range(2):
    for L in [12050,24050]:
     for region in ['already_active','forced','normal']:
      arrays=[];traces=[];states=[]
      for enabled in [False,True]:
       p.enabled=enabled;s.init(mode,rev,L,60025+(L//2-1000)*(1 if not rev else -1),ping=ping);s.put(s.reader,0x1b4,'B',1-rev)
       if region!='already_active':s.put(s.reader,0xcc,'i',60025)
       y,e,t=s.render(256,17)
       s.bounds(60025+((25000 if region=='already_active' else 20000 if region=='forced' else 0)*(1 if rev else -1)),L)
       z=[];src=[];events=[]
       for n in [1,31,256,4096,256]:
        yy,ee,tt=s.render(n,n);z+=yy;src+=tt;events+=ee
       arrays.append(z);traces.append((src,[(e['site'],e['source_out'],e['source_in'],e['cur'],e['last'],e.get('in_sources')) for e in events]));states.append(bytes(s.reader))
      assert arrays[0]==arrays[1] and traces[0]==traces[1] and states[0]==states[1], (kind,mode,rev,ping,L,region, arrays[0]==arrays[1],traces[0]==traces[1],states[0]==states[1])
      out.append(dict(wave=kind,mode=mode,reverse=rev,ping=ping,L=L,region=region,identical_pcm_sources_state=True))
# Center-follow direction states: preserve effective direction while changing Center geometry.
follow=[]
for wave in ['periodic','rich']:
 s.waveform(wave)
 for mode in range(2):
  for rev in range(2):
   for ping in range(2):
    for setting in [0,1,2]:
     streams=[]
     for enabled in [False,True]:
      p.enabled=enabled
      # Ordinary entry approximately 100 frames before old fade start.
      st=(63038 if not rev else 57012) if mode==0 else (63050 if not rev else 57000)
      s.init(mode,rev,12050,st+(-100 if not rev else 100),ping=ping)
      s.put(s.reader,0x1b4,'B',1-rev);s.put(s.reader,0x50,'i',setting)
      def direction_banks(center):
       s.bounds(center,12050)
       # These endpoint values only select effective direction here; displacement remains synthetic.
       if rev:
        for bank in range(2):s.put(s.ep,bank*0x280+0x84,'f',(center-1)/199999)
      direction_banks(60025)
      y,e,t=s.render(256,1);direction_banks(60025+(800 if rev else -800))
      z=[];ins=[];tags=[];ev=[]
      for n in [256]*12:
       zz,ee,tt=s.render(n,n);z+=zz;tags+=tt
       for e in ee:
        if e.get('corrected'):ev.append(e)
       ins+=ee
      streams.append(dict(prior=y[0],y=z,tags=tags,events=ins,corrected=ev))
     a,b=streams
     assert b['corrected'] and a['tags']==b['tags']
     ev=b['corrected'][0];N=abs(ev['end']-ev['origin']);sgn=-1 if rev else 1;inc=sgn if not ping else -sgn
     assert b['y'][0]==s.sample[2*b['tags'][0]]
     src=b['tags'][N];handoff=b['y'][N]-b['y'][N-1];natural=s.sample[2*src]-s.sample[2*(src-inc)]
     assert handoff==natural
     follow.append(dict(wave=wave,mode=mode,reverse=rev,ping=ping,reader_center_follow_value=setting,old_entry=a['y'][0]-a['prior'],new_entry=b['y'][0]-b['prior'],handoff=handoff,natural_handoff=natural,outgoing_sources_unchanged=True))
(p.O/'preservation.json').write_text(json.dumps(out,indent=2));(p.O/'center_follow.json').write_text(json.dumps(follow,indent=2))
print('preservation',len(out),'center-follow',len(follow))
assert s.P.read_bytes()==s.raw
