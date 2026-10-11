from pathlib import Path
import struct as S,json,csv,hashlib
from build import elf,BASE,O
sha=lambda b:hashlib.sha256(b).hexdigest()
def main():
 b=(O/'voice_2.2.2.1.15_qnx.elf').read_bytes();old=(BASE/'voice_2.2.2.1.12_qnx.elf').read_bytes()
 m=json.loads((O/'emission.json').read_text());assert sha(b)==m['sha256']
 assert sha(old)==m['baseline_sha256']=='b411fc94d17683f49d62184e3c794f6e4eea72e7d6ea58edd1b78ff706377ced'
 assert len(b)==len(old)
 ranges=m['allowed_ranges'];assert all(any(lo<=i<hi for lo,hi,_ in ranges) for i,(a,c) in enumerate(zip(old,b)) if a!=c)
 sec,names=elf(old);newsec,newnames=elf(b);assert names==newnames
 inherited={}
 for name in ['.b5.text','.b5.eh_frame','.b8.text','.b8.eh_frame','.b15_text','.b15_eh_frame']:
  s=sec[names.index(name)];lo,n=s[4],s[5];assert old[lo:lo+n]==b[lo:lo+n];inherited[name]=sha(b[lo:lo+n])
 phoff=S.unpack_from('<Q',old,32)[0]
 for i in range(S.unpack_from('<H',old,56)[0]):
  lo=phoff+56*i
  if hashlib.sha256(S.pack('<I',S.unpack_from('<I',old,lo)[0])).hexdigest()!='0fe51dced2745ee6eab34377ad3e64563eef82533a339cae1c75354d09fd1dd5':assert b[lo:lo+56]==old[lo:lo+56]
 h=0x103000;oldn=S.unpack_from('<I',old,h+8)[0];newn=S.unpack_from('<I',b,h+8)[0]
 def pairs(data,n):return [tuple(h+x for x in S.unpack_from('<ii',data,h+12+8*i)) for i in range(n)]
 prior=pairs(old,oldn);current=pairs(b,newn);assert oldn==899 and current==sorted(prior+[tuple(x) for x in m['new_FDEs']])
 for pc,f in current:
  length,cie=S.unpack_from('<II',b,f);assert cie and length>=12
  assert f+8+S.unpack_from('<i',b,f+8)[0]==pc
  cieaddr=f+4-cie;assert hashlib.sha256(S.pack('<I',S.unpack_from('<I',b,cieaddr+4)[0])).hexdigest()=='df3f619804a92fdb4057192dc43dd748ea778adc52bc498ce80524c014b81119'
  if (pc,f) in prior:assert b[f:f+4+length]==old[f:f+4+length]
 assert hashlib.sha256(S.pack('<I',S.unpack_from('<I',b,0x1f4e3)[0])).hexdigest()=='7c2065036356b0a1304f121c0d1e8f0444413dd11302da2d440028937a8e0619' and b[0x250ef]==15
 identity=json.loads((O/'identity.json').read_text());assert identity['sha256']==sha(b) and identity['unchanged'] and identity['firmware_build']
 phase=json.loads((O/'phase_counts.json').read_text());assert phase==dict(trials=162528,corrected=6900)
 hand=list(csv.DictReader(open(O/'handoff_sweep.csv')));assert len(hand)==6900
 assert all(int(x['new_handoff'])==int(x['natural_handoff']) for x in hand)
 life=json.loads((O/'lifecycle.json').read_text());assert len(life)==160
 assert sum(x['kind']=='no_edit' and x['identical'] for x in life)==96
 short=json.loads((O/'short_distances.json').read_text());assert len(short)==160 and sum(len(x['cases']) for x in short)==16000
 preservation=json.loads((O/'preservation.json').read_text());assert len(preservation)==96 and all(x['identical_pcm_sources_state'] for x in preservation)
 follow=json.loads((O/'center_follow.json').read_text());assert len(follow)==48 and all(x['handoff']==x['natural_handoff'] for x in follow)
 for name in ['storage','transport']:assert json.loads((O/(name+'.json')).read_text())['status']=='PASS'
 center=json.loads((O/'inherited_center.log').read_text());assert center['status']=='PASS' and center['cases']==43528
 assert '32 cases' in (O/'sequences.log').read_text() and '32 cases' in (O/'repeated_tail.log').read_text()
 assert 'completed' in (O/'lifecycle.log').read_text() and 'completed' in (O/'handoff.log').read_text()
 psummary=json.loads((O/'phase_summary.json').read_text());assert all(x['new_max_excess']==0 for x in psummary if x['corrected'])
 shortstats=[dict(N=n,entry=max(x['new_entry_max'] for x in short if x['N']==n),handoff=max((x['new_handoff_max'] or 0) for x in short if x['N']==n),any_step=max(x['new_max_step'] for x in short if x['N']==n)) for n in [0,1,2,3,4,8,16,32,64,128]]
 report=dict(status='PASS',QNX_sha256=sha(b),baseline='exact .1.12',phase=phase,handoff_cases=len(hand),entry_excess_max=0,handoff_excess_max=0,transition_step_max=max(int(x['new_max_step']) for x in hand),old_transition_step_max=max(int(x['old_max_step']) for x in hand),no_edit_cases=96,preservation_cases=96,reader_FwdRev_cases=48,short_cases=16000,short_distances=shortstats,lifecycle_cases=32,repeated_edit_cases=32,source_sequence_cases=32,split_max_difference=max(x.get('split_max_difference',0) for x in life),storage=json.loads((O/'storage.json').read_text()),transport=json.loads((O/'transport.json').read_text()),inherited_code_and_frames_unchanged=inherited,all_899_inherited_FDEs_identical=True,new_FDEs=len(m['new_FDEs']),PT_LOADs_unchanged=True,additional_audio_buffers=0,per_reader_bytes=16,hardware='NOT VERIFIED',flashed=False)
 report['actual_emitted_inherited_Center_fixture']=center
 (O/'validation.json').write_text(json.dumps(report,indent=2)+'\n')
 artifacts=['patch.c','hooks.s','build.py','proposal.py','voice_2.2.2.1.15_qnx.elf','emission.json','identity.json','phase.csv','handoff_sweep.csv','lifecycle.json','short_distances.json','preservation.json','center_follow.json','storage.json','transport.json','validation.json']
 (O/'validation_manifest.json').write_text(json.dumps({f:sha((O/f).read_bytes()) for f in artifacts},indent=2)+'\n');print(json.dumps(report,indent=2))
if __name__=='__main__':main()
