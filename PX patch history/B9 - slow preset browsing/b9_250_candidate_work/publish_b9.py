"""Publish the exact independently validated candidate without overwriting files."""
from pathlib import Path
import json,hashlib
ROOT=Path(__file__).resolve().parent.parent;OUT=Path(__file__).resolve().parent
reports=[json.loads((OUT/n).read_text()) for n in ('b9_instruction_validation.json','b9_placement_validation.json','b9_packaged_validation.json')]
assert all(r['status']=='PASS' for r in reports)
b=(OUT/'package_pending_validation.bin').read_bytes();sha=hashlib.sha256(b).hexdigest();assert sha==reports[2]['package_sha256']
p=ROOT/'PxUpdate_V2.2.2.1.2.bin'
with p.open('xb') as f:f.write(b)
assert p.read_bytes()==b
(OUT/'revision_reservation.md').write_text('B9 panel-250 candidate reserves 2.2.2.1.2. Workspace artifacts and handovers contained no prior reservation for this revision. B7 retains 2.2.2.1.0; B9 500-tick candidate retains 2.2.2.1.1. Regenerated from verified B6 .9 with only reviewed B9 behavior and metadata changes; instruction-differential checks against hardware-tested B9 .1.1 pass.\n')
print(p.name,sha,len(b))
