#!/usr/bin/env python3
"""Package only the pinned B5 ELF into the pinned tested voice container.
Established pass-34 framing and voice naming; header-only test identity because
an embedded revision change would violate the required candidate SHA-256.
"""
import hashlib,json,struct
from pathlib import Path
ROOT=Path(__file__).resolve().parent
WORKSPACE=ROOT.parent
BASE_SHA='2ad5392eb842cbcd5c2e85e65ab42c16f1fac12d16b09c417a61761a8348bcbf'
BASE_ELF_SHA='651f0ac3339f4f41a4c0bc562cdf4c72df821d85aad3f689e700612b8c8b05e7'
CANDIDATE_SHA='07ff1fd635505114945fc4dcab11a212f4bc9164b1a7ab8beb681482cb7c2b35'
VERSION=(2,2,2,0,5)
OUTPUT='voice_b5_2.2.2.0.5.bin'
def sha(b):return hashlib.sha256(b).hexdigest()
def checksum(b):
    if len(b)%2:raise ValueError('established word checksum requires an even payload')
    return sum(x[0] for x in struct.iter_unpack('<H',b))&0xffff

def records(data):
    if data[:1]!=b'\xf0' or data[-1:]!=b'\xf7':raise ValueError('bad update framing')
    cursor=1;result=[]
    for kind in (1,2,3):
        header=data[cursor:cursor+12]
        if len(header)!=12 or header[0]!=kind or header[1]!=0x7b or header[7]!=0x7a:raise ValueError('unexpected record header')
        size=int.from_bytes(header[8:12],'big');end=cursor+12+size
        if end+2>len(data)-1:raise ValueError('record length exceeds container')
        payload=data[cursor+12:end];trailer=data[end:end+2]
        result.append({'type':kind,'start':cursor,'end':end+2,'header':header,'payload':payload,'trailer':trailer})
        cursor=end+2
    if cursor!=len(data)-1:raise ValueError('extra or missing records')
    return result

def compose(base,candidate):
    if sha(base)!=BASE_SHA:raise ValueError('tested voice container identity mismatch')
    if sha(candidate)!=CANDIDATE_SHA:raise ValueError('required B5 candidate identity mismatch')
    parsed=records(base);application=parsed[0]
    if sha(application['payload'])!=BASE_ELF_SHA:raise ValueError('tested voice QNX payload identity mismatch')
    roundtrip=b'\xf0'+b''.join(r['header']+r['payload']+r['trailer'] for r in parsed)+b'\xf7'
    if roundtrip!=base:raise ValueError('base parse/repack round-trip failed')
    if len(candidate)>0xffffffff:raise ValueError('candidate exceeds established 32-bit length field')
    header=bytearray(application['header']);header[2:7]=bytes(VERSION);header[8:12]=len(candidate).to_bytes(4,'big')
    output=b'\xf0'+header+candidate+checksum(candidate).to_bytes(2,'little')+base[application['end']:]
    return bytes(output)

def main():
    base_path=WORKSPACE/'voice_2.2.2.0.2.bin'
    candidate_path=WORKSPACE/'b5_candidate_work/voice_2.2.2.0.2_qnx_B5_candidate.elf'
    destination=ROOT/OUTPUT;manifest_path=ROOT/'b5_packaging_manifest.json'
    extraction=ROOT/'b5_packaged_qnx.elf';validation_path=ROOT/'b5_packaging_validation.json'
    for path in [destination,manifest_path,extraction,validation_path]:
        if path.exists():raise FileExistsError('refuse to overwrite existing output '+str(path))
    base=base_path.read_bytes();candidate=candidate_path.read_bytes();output=compose(base,candidate)
    # Independent verifier imports none of this packager's code.
    from verify_b5_test import verify
    verification=verify(base,output,candidate)
    with destination.open('xb') as f:f.write(output)
    saved=destination.read_bytes()
    completed=verify(base,saved,candidate)
    assert saved==output and sha(saved)==verification['container_sha256']
    with extraction.open('xb') as f:f.write(saved[completed['records'][0]['payload_offset']:completed['records'][0]['payload_offset']+len(candidate)])
    if sha(extraction.read_bytes())!=CANDIDATE_SHA:raise ValueError('saved extracted QNX hash mismatch')
    validation_path.write_text(json.dumps(completed,indent=2)+'\n')
    # Packaging-only rejection cases; no unchanged candidate/DSP tests rerun.
    negative=[]
    for label,bb,cc in [('modified base',base[:-1]+b'\x00',candidate),('truncated base',base[:-1],candidate),('modified candidate',base,candidate[:-1]+bytes([candidate[-1]^1])),('truncated candidate',base,candidate[:-1])]:
        try:compose(bb,cc)
        except ValueError:negative.append({'case':label,'rejected':True})
        else:raise ValueError('input guard unexpectedly accepted '+label)
    tampered=bytearray(saved);tampered[7]=2
    try:verify(base,bytes(tampered),candidate)
    except (ValueError,AssertionError):negative.append({'case':'wrong packaged B5 revision','rejected':True})
    else:raise ValueError('verifier accepted wrong B5 revision')
    for label,offset in [('QNX checksum corruption',completed['records'][0]['trailer_offset']),('PIC byte corruption',completed['records'][2]['payload_offset'])]:
        tampered=bytearray(saved);tampered[offset]^=1
        try:verify(base,bytes(tampered),candidate)
        except (ValueError,AssertionError):negative.append({'case':label,'rejected':True})
        else:raise ValueError('verifier accepted '+label)
    manifest={'status':'packaged_and_offline_verified','test_file':destination.name,'test_sha256':sha(saved),'test_bytes':len(saved),
              'base_file':base_path.name,'base_sha256':sha(base),'base_bytes':len(base),'required_candidate_file':str(candidate_path.relative_to(WORKSPACE)),'required_candidate_sha256':sha(candidate),'candidate_bytes':len(candidate),
              'package_revision':list(VERSION),'identity_scope':'container header and descriptive filename only; exact ELF retains voice DSP revision 2.2.2.0.2',
              'format':'F0 + three records (type,7B,5 version bytes,7A,u32be length,payload,u16le trailer) + F7',
              'application_checksum':completed['records'][0]['stored_checksum'],'qnx_size_growth':len(candidate)-len(records(base)[0]['payload']),
              'change_whitelist':[{'region':'application header version','offset':3,'bytes':5,'old':'0202020002','new':'0202020005'},
                                  {'region':'application length','offset':9,'bytes':4,'old':base[9:13].hex(),'new':saved[9:13].hex()},
                                  {'region':'QNX application payload','old_offset':13,'old_bytes':986520,'new_offset':13,'new_bytes':len(candidate)},
                                  {'region':'application checksum trailer','old_offset':13+986520,'new_offset':13+len(candidate),'bytes':2,'old':base[13+986520:15+986520].hex(),'new':saved[13+len(candidate):15+len(candidate)].hex()}],
              'all_other_records_byte_identical':True,'records':completed['records'],'verification_summary':{k:v for k,v in completed.items() if k!='records'},'negative_cases':negative,
              'rollback':{'known_good_tested_voice_file':base_path.name,'known_good_tested_voice_sha256':sha(base),'same_version_gate_caveat':'Exact candidate retains compiled .2 gate; incoming tested voice .2 is skipped. Established running-updater rollback requires official stock .0 first, then tested voice .2; use a pretest SSD recovery image if the updater cannot run.',
                          'official_stock_intermediate_file':'PxUpdate_V2.2.2.0.0.bin','official_stock_intermediate_sha256':'a4b304b3bb48ca933ae63c99c0098698c497ebfc7c38ab2a823b5e0df4919fa9'},
              'deterministic_rebuild_matches':compose(base,candidate)==saved,'saved_extraction_sha256':sha(extraction.read_bytes()),'usb_filename_if_standard_prefix_is_required':'PxUpdate_V2.2.2.0.5.bin',
              'source_sha256':{n:sha((ROOT/n).read_bytes()) for n in ['package_b5_test.py','verify_b5_test.py']},
              'pending':['hardware updater/QNX acceptance','target performance','listening tests'],'flashed':False}
    if base_path.read_bytes()!=base or candidate_path.read_bytes()!=candidate:raise ValueError('input changed during packaging')
    manifest_path.write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps({k:manifest[k] for k in ['status','test_file','test_sha256','test_bytes','application_checksum','qnx_size_growth']},indent=2))
if __name__=='__main__':main()
