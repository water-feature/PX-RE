"""Build an offline ProphetX application candidate; never writes an update.

Usage: python build_application_patch.py --input /path/ProphetX.elf --output /path/candidate.elf
The accompanying specification contains SHA-256 guards from the audited
original application. The entire source hash and every edited span must match.
"""
from pathlib import Path
import argparse, hashlib, json, struct
from io import BytesIO
from elftools.elf.elffile import ELFFile

ORIGINAL_SHA='7db8a8276f0bda34d22fdd2e8744b304dc7d62f80f9189836b107a4d7b178cff'
P=Path(__file__).resolve().parent
def build(source, spec):
    if hashlib.sha256(source).hexdigest()!=ORIGINAL_SHA:raise ValueError('Original application SHA-256 mismatch; refusing patch')
    if spec['format']!=2 or spec['input_sha256']!=ORIGINAL_SHA or spec['input_size']!=len(source):raise ValueError('Specification/source identity mismatch')
    candidate=bytearray(source);occupied=set()
    for s in spec['spans']:
        off=int(s['offset'],16);after=bytes.fromhex(s['replacement_hex']);n=s['size']
        if n!=s['expected_size'] or n!=len(after) or off<0 or off+n>len(source):raise ValueError('Invalid span length/range')
        if hashlib.sha256(source[off:off+n]).hexdigest()!=s['expected_sha256']:raise ValueError(f'Expected bytes mismatch at {off:#x}')
        positions=set(range(off,off+n))
        if occupied&positions:raise ValueError('Overlapping edits')
        occupied|=positions;candidate[off:off+n]=after
    result=bytes(candidate)
    if len(result)!=len(source):raise ValueError('Application size changed')
    changed={i for i,(a,b) in enumerate(zip(source,result)) if a!=b}
    if not changed<=occupied:raise ValueError('Change outside allowed spans')
    old,new=ELFFile(BytesIO(source)),ELFFile(BytesIO(result))
    for key in ['e_type','e_machine','e_entry','e_phoff','e_phnum','e_shoff','e_shnum']:
        if old[key]!=new[key]:raise ValueError('Unexpected ELF header change')
    for a,b in zip(old.iter_segments(),new.iter_segments()):
        if a['p_type']=='PT_LOAD' and a.header!=b.header:raise ValueError('Load segment layout/permissions changed')
    for h in spec['integration_hooks']:
        a=int(h['site'],16);b=result[a:a+h['size']]
        if h['kind']=='nop':
            if b!=b'\x90'*h['size']:raise ValueError('Old coordinator lock remains')
        else:
            opcode=0xe8 if h['kind']=='call' else 0xe9
            target=a+5+struct.unpack('<i',b[1:5])[0]
            if b[0]!=opcode or target!=int(h['target'],16) or b[5:]!=b'\x90'*(h['size']-5):raise ValueError('Invalid installed hook')
    return result,{'input_sha256':ORIGINAL_SHA,'output_sha256':hashlib.sha256(result).hexdigest(),'application_size':len(result),'edited_spans':len(spec['spans']),'bytes_in_edit_spans':len(occupied),'bytes_actually_changed':len(changed),'integration_sites':len(spec['integration_hooks']),'load_segments_unchanged':True,'status':'offline application candidate, not an installable update','limits':['Thread/DSP behavior mocked in emulation; no hardware click test','No general external cancellation support','New unwind records use indexed lookup','Application version/checksum update packaging not performed']}

if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--input',type=Path,required=True);ap.add_argument('--output',type=Path,required=True)
    args=ap.parse_args()
    if args.input.resolve()==args.output.resolve():ap.error('Input and output must differ')
    if args.output.exists():ap.error('Output already exists; refusing overwrite')
    spec=json.loads((P/'patch_spec.json').read_text())
    try:result,report=build(args.input.read_bytes(),spec)
    except ValueError as exc:ap.error(str(exc))
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('xb') as f:f.write(result)
    report_path=args.output.with_suffix('.manifest.json')
    report_path.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
