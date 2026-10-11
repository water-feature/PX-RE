"""Compare components extracted independently from baseline and packaged updates.
The JSON mapping is supplied by the verified container extractor, not invented here.
"""
import argparse,json,hashlib
from pathlib import Path
ap=argparse.ArgumentParser();ap.add_argument('manifest',type=Path);ap.add_argument('--expected-qnx',type=Path,required=True);args=ap.parse_args()
m=json.loads(args.manifest.read_text());old=m['baseline'];new=m['candidate'];qnx=m['qnx_component_name']
assert set(old)==set(new),'Component inventory changed'
assert qnx in old and len(old)>1,'Missing application or preserved components'
def read(p):
 p=Path(p);return (p if p.is_absolute() else args.manifest.parent/p).read_bytes()
result=[]
for name in sorted(old):
 a=read(old[name]);b=read(new[name])
 if name==qnx:assert b==args.expected_qnx.read_bytes(),'Packaged QNX does not equal validated candidate'
 else:assert a==b,'Preserved component changed: '+name
 result.append({'component':name,'baseline_sha256':hashlib.sha256(a).hexdigest(),'candidate_sha256':hashlib.sha256(b).hexdigest(),'status':'validated application' if name==qnx else 'byte-identical'})
print(json.dumps({'components':result,'scope':'Extracted payload byte equality only. Container metadata/checksums and extractor completeness must also be verified by the audited packaging workflow.'},indent=2))
