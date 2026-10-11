import proposal as p
import ctypes as C,json
s=p.s;s.waveform('periodic');p.capture_streams=True
seek_cases=0
for mode in [0,1]:
 for rev in [0,1]:
  for ping in [0,1]:
   for active in [False,True]:
    results=[]
    for enabled in [False,True]:
     p.enabled=enabled;s.init(mode,rev,12050,60025+(5025 if not rev else -5025) if active else 60025,ping=ping)
     s.put(s.reader,0x1b4,'B',1-rev);s.render(256,17)
     s.put(s.reader,0x24,'i',s.gi(0xcc)+(200 if not rev else -200))
     y,e,t=s.render(256,17)
     assert not any(v['corrected'] for v in e)
     results.append((y,t,bytes(s.reader)))
    assert results[0]==results[1];seek_cases+=1
# A seek suppresses a new envelope but does not erase a retained corrected one.
for rev in [0,1]:
 p.enabled=True;s.init(0,rev,12050,62925 if not rev else 57112)
 s.render(256,1);s.bounds(59225 if not rev else 60825,12050);s.render(256,17)
 assert p.flags()&2
 origin=s.gi(0x10);s.put(s.reader,0x24,'i',s.gi(0xcc));y,e,t=s.render(256,1)
 assert not p.flags()&4
 for v in e:
  if v['corrected']:assert v['site'] in ['0x3fd79','0x41390'] and v['origin']==origin

def make(rev):
 f=dict(reader=C.create_string_buffer(0x200),ep=C.create_string_buffer(0x510),bufs=[C.create_string_buffer(16384) for _ in range(2)])
 f['rp']=C.addressof(f['reader']);f['bp']=[C.addressof(b) for b in f['bufs']]
 select(f);p.enabled=True;s.init(0,rev,12050,62925 if not rev else 57112)
 s.render(256,1);s.bounds(59225 if not rev else 60825,12050)
 return f
def select(f):
 for k,v in f.items():setattr(s,k,v)
chunks=[17,1,7,31,64,257,13]*20
expected=[]
for rev in [0,1]:
 f=make(rev);y=[]
 for n in chunks:y+=s.render(max(256,n),n)[0][:n]
 expected.append(y)
fixtures=[make(0),make(1)];actual=[[],[]]
for n in chunks:
 for j,f in enumerate(fixtures):select(f);actual[j]+=s.render(max(256,n),n)[0][:n]
assert actual==expected
report=dict(status='PASS',unowned_seek_equivalence=seek_cases,owned_seek_preservation=2,interleaved_independent_reader_streams=2)
(p.O/'transport.json').write_text(json.dumps(report,indent=2));print(report)
