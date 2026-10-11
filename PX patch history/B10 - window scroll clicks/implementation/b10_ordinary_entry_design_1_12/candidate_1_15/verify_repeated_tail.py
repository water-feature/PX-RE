from pathlib import Path
namespace={};exec((Path(__file__).parent/'run_lifecycle.py').read_text().split('# Whole vs fragmented')[0],namespace)
s=namespace['s'];p=namespace['p'];stream=namespace['stream'];geo=namespace['geo'];metrics=namespace['metrics']
import json
rows=[]
for wave in ['periodic','rich']:
 s.waveform(wave)
 for L in [12050,24050]:
  for mode in range(2):
   for rev in range(2):
    for ping in range(2):
     start,end=geo(mode,rev,L,60025,ping);sgn=1 if end>start else -1;at=start-sgn*100
     edits=((17,60025+(25000 if rev else -25000)),(43,60025+(27000 if rev else -27000)))
     old=stream(mode,rev,L,at,800,False,ping,chunks=(1,31,257,13,4096),oversample=True,horizon=20000,edits=edits)
     new=stream(mode,rev,L,at,800,True,ping,chunks=(1,31,257,13,4096),oversample=True,horizon=20000,edits=edits)
     N=metrics(new)['N'];assert old['tags']==new['tags']
     # After the corrected fade hands off, inherited incoming tail, following forced fade and subsequent playback agree exactly.
     assert old['y'][N:]==new['y'][N:]
     forced=[e for e in new['events'] if int(e['site'],16) in p.FORCED]
     # Bounce states may first reverse at a retained endpoint; all forced calls that occur remain unmodified.
     assert all(not e['corrected'] for e in forced)
     rows.append(dict(wave=wave,L=L,mode=mode,reverse=rev,ping=ping,N=N,following_frames_equal=20000-N,forced_calls=len(forced),forced_unmodified=True,final_corrected_flag=new['states'][-1]['corrected']))
(p.O/'repeated_tail.json').write_text(json.dumps(rows,indent=2));print('repeated excluding edits, retained tail and subsequent playback:',len(rows),'cases')
