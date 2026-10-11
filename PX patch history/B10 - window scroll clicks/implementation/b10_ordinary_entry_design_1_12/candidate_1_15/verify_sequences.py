# SPDX-License-Identifier: GPL-2.0-or-later
from pathlib import Path
namespace={}
exec((Path(__file__).parent/'run_lifecycle.py').read_text().split('# Whole vs fragmented')[0],namespace)
s=namespace['s'];stream=namespace['stream'];geo=namespace['geo'];metrics=namespace['metrics'];p=namespace['p'];count=0
for wave in ['periodic','rich']:
 s.waveform(wave)
 for L in [12050,24050]:
  for mode in range(2):
   for rev in range(2):
    for ping in range(2):
     start,end=geo(mode,rev,L,60025,ping);sgn=1 if end>start else -1;at=start-sgn*100
     a=stream(mode,rev,L,at,800,True,ping,chunks=(4096,),horizon=7000)
     b=stream(mode,rev,L,at,800,True,ping,chunks=(1,7,31,64,257,13),oversample=True,horizon=7000)
     N=metrics(a)['N'];inc=sgn if not ping else -sgn
     assert all(v-u==inc for u,v in zip(a['incoming'][:N-1],a['incoming'][1:N]))
     assert a['incoming'][N-1]==a['tags'][N]-inc
     assert a['incoming']==b['incoming'] and a['tags']==b['tags']
     assert metrics(a)['handoff']==metrics(b)['handoff']
     count+=1
print('continuous outgoing/incoming sequences and handoff:',count,'cases')
