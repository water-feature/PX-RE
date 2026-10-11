# SPDX-License-Identifier: GPL-2.0-or-later
"""Apply the frozen approved B11b layout to the exact .1.15 components."""
from pathlib import Path
import hashlib,json,struct
O=Path(__file__).resolve().parent; R=O.parent
BASE=0x9d000000; REV=bytes([2,2,2,2,0])
PKG=R/'PxUpdate_V2.2.2.1.15_B10_ordinary_entry_candidate.bin'
PIC=R/'b10_ordinary_entry_design_1_12/candidate_1_15/reextracted_pic.bin'
APP=R/'b10_ordinary_entry_design_1_12/candidate_1_15/reextracted_qnx.elf'
OWNED=[(0x9d02a74c,0x9d02a794),(0x9d02d428,0x9d02d464),(0x9d02dd08,0x9d02dd2c),(0x9d02def8,0x9d02df1c)]
SITES=[0x9d04debc,0x9d04e010,0x9d04e54c,0x9d04e624]
PIC_META={0x1394:(0x2484000f,0x24840000),0x13a0:(0x2484000f,0x24840000),0x258b4:(0x24842221,0x24842222),0x51bc4:(0x24842221,0x24842222)}
APP_META={0x1f4e3:(0x1f,0x20),0x250e2:(1,2),0x250ef:(15,0)}
sha=lambda b:hashlib.sha256(b).hexdigest()
def save(name,data):
    with (O/name).open('xb') as f:f.write(data)
def parse(b):
    assert b[0]==240 and b[-1]==247
    off=1;rows=[]
    for typ in (1,2,3):
        h=b[off:off+12];assert len(h)==12 and h[0]==typ and h[1]==123 and h[7]==122
        n=int.from_bytes(h[8:12],'big');end=off+12+n
        assert end+2<len(b)
        rows.append((h,b[off+12:end],b[end:end+2],off));off=end+2
    assert off==len(b)-1
    return rows
def serialize(rows):return b'\xf0'+b''.join(h+p+t for h,p,t,_ in rows)+b'\xf7'
def sum16(b):
    assert len(b)%2==0
    return sum(struct.unpack('<'+'H'*(len(b)//2),b))&65535
def diff(old,new):
    assert len(old)==len(new)
    return [i for i,(a,b) in enumerate(zip(old,new)) if a!=b]
def diff_file(name,old,new,base=0):
    changed=diff(old,new);rows=['offset\taddress\tbaseline\tcandidate']
    rows += [f'0x{i:x}\t0x{base+i:x}\t{old[i]:02x}\t{new[i]:02x}' for i in changed]
    save(name,('\n'.join(rows)+'\n').encode());return changed
def main():
    manifest=json.loads((O/'input_manifest.json').read_text())
    for name,digest in manifest.items():assert sha((R/name).read_bytes())==digest,name
    old=PKG.read_bytes();pic=PIC.read_bytes();app=APP.read_bytes()
    assert sha(old)=='ebb2aebbd0decdadce92ed40d257e0cb03ebbf7aecf3e05749d9533fd5603450'
    assert sha(pic)=='be8eb8ac823a639f3024b97e01b017ef0cef5f33d086eaa71dfe55d4b0e34622'
    assert sha(app)=='dd9efbcd2804e02cc4599e72d2ee90f996facce1fa06f1815a0078270566a2fa'
    records=parse(old);assert serialize(records)==old
    assert records[0][1]==app and records[2][1]==pic
    assert all(records[i][0][2:7]==bytes([2,2,2,1,15]) for i in (0,2))
    for h,p,t,_ in records[:2]:assert int.from_bytes(t,'little')==sum16(p)
    assert records[2][2]==b'00'
    out=bytearray(pic);words={}
    for lo,hi in OWNED:
        fragment=(O/'approved'/f'fragment_{lo:08x}.bin').read_bytes()
        assert len(fragment)==hi-lo
        for pos in range(lo,hi,4):words[pos]=struct.unpack_from('<I',fragment,pos-lo)[0]
        out[lo-BASE:hi-BASE]=fragment
    listing={int(line.split()[0],16):int(line.split()[1],16) for line in (O/'approved/listing.txt').read_text().splitlines()}
    assert words==listing and len(words)==51 and words[0x9d02df18]==0
    for pos in SITES:
        assert struct.unpack_from('<I',pic,pos-BASE)[0]==(3<<26)|((0x9d04d4fc>>2)&0x3ffffff)
        words[pos]=(3<<26)|((0x9d02dd08>>2)&0x3ffffff)
        struct.pack_into('<I',out,pos-BASE,words[pos])
    behavior=bytes(out)
    code_allowed={p-BASE+i for p in words for i in range(4)}
    assert set(diff(pic,behavior))<=code_allowed and len(code_allowed)==220
    for off,(before,after) in PIC_META.items():
        assert struct.unpack_from('<I',out,off)[0]==before
        struct.pack_into('<I',out,off,after)
    qnx=bytearray(app)
    for off,(before,after) in APP_META.items():assert qnx[off]==before;qnx[off]=after
    assert set(diff(app,qnx))==set(APP_META)
    assert set(diff(pic,out))<=code_allowed|{off+i for off in PIC_META for i in range(4)}
    # All outside ownership/version metadata is byte-identical, including the
    # stock cache route, shared refresh paths, Group entries and inherited fixes.
    save('pic_2.2.2.2.0_B11b.bin',out);save('voice_2.2.2.2.0_B11b_qnx.elf',qnx)
    pd=diff_file('PIC_diff.tsv',pic,out,BASE);qd=diff_file('QNX_diff.tsv',app,qnx)
    save('emission_listing.txt',('\n'.join(f'{pos:08x} {struct.unpack_from("<I",pic,pos-BASE)[0]:08x} -> {w:08x}' for pos,w in sorted(words.items()))+'\n').encode())
    report={'status':'EMITTED_REQUIRES_VALIDATION','revision':list(REV),'baseline':'exact 2.2.2.1.15','baseline_package_sha256':sha(old),'baseline_PIC_sha256':sha(pic),'baseline_QNX_sha256':sha(app),'PIC_sha256':sha(out),'QNX_sha256':sha(qnx),'owned_ranges':[[hex(a),hex(z)] for a,z in OWNED],'active_layout_bytes':200,'allocated_layout_bytes':204,'clamp_call_sites':[hex(a) for a in SITES],'PIC_changed_bytes':len(pd),'QNX_changed_bytes':len(qd),'PIC_revision_word_offsets':[hex(a) for a in PIC_META],'QNX_revision_byte_offsets':[hex(a) for a in APP_META],'behavior_matches_frozen_approved_layout':True,'outside_ownership_and_metadata_unchanged':True,'cache_correction_included':False,'flashed':False}
    save('emission.json',(json.dumps(report,indent=2)+'\n').encode());print(json.dumps(report,indent=2))
if __name__=='__main__':main()
