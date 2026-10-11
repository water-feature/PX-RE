# SPDX-License-Identifier: GPL-2.0-or-later
"""Package the retained B15 images; no flashing or source rebuilds.
Format authority: b14_stable_frame_packaging_work/package_stable.py.
"""
from pathlib import Path
import hashlib, json, struct, sys

O = Path(__file__).resolve().parent
R = O.parent
REV = bytes([2, 2, 2, 1, 8])
sha = lambda b: hashlib.sha256(b).hexdigest()

def parse(b):
    assert b[0] == 0xf0 and b[-1] == 0xf7
    pos, rows = 1, []
    for kind in (1, 2, 3):
        header = b[pos:pos+12]
        assert header[0] == kind and header[1] == 0x7b and header[7] == 0x7a
        end = pos + 12 + int.from_bytes(header[8:12], 'big')
        rows.append((header, b[pos+12:end], b[end:end+2], pos+12))
        pos = end + 2
    assert pos == len(b)-1
    return rows

def serialize(rows):
    return b'\xf0' + b''.join(h+p+t for h,p,t,_ in rows) + b'\xf7'

def sum16(b):
    assert len(b) % 2 == 0
    return sum(x[0] for x in struct.iter_unpack('<H', b)) & 65535

def ranges(old, new):
    start = None
    for i in range(max(len(old), len(new))):
        different = i >= len(old) or i >= len(new) or old[i] != new[i]
        if different and start is None:
            start = i
        elif not different and start is not None:
            yield start, i
            start = None
    if start is not None:
        yield start, max(len(old), len(new))

def write_ranges(path, old, new, component, payload_offset=None, virtual_base=None, ph=None):
    count = total = 0
    with path.open('w') as out:
        out.write('component\tfile_start\tfile_end_exclusive\tlength\tpackage_start\tpackage_end_exclusive\tvirtual_start\tvirtual_end_exclusive\n')
        bounded=[]
        for lo,hi in ranges(old,new):
            cuts={lo,hi}
            if ph:
                for kind,flags,f,v,pa,fs,ms,al in ph:
                    if kind==1:
                        cuts.update(x for x in (f,f+fs) if lo<x<hi)
            cuts=sorted(cuts)
            bounded.extend(zip(cuts,cuts[1:]))
        for lo, hi in bounded:
            va = hex(virtual_base+lo) if virtual_base is not None else '-'
            vaend = hex(virtual_base+hi) if virtual_base is not None else '-'
            if ph:
                mapped = [v+(lo-f) for kind,flags,f,v,pa,fs,ms,al in ph if kind==1 and f<=lo<f+fs]
                va = ','.join(hex(x) for x in mapped) or 'nonloaded'
                vaend = ','.join(hex(x+hi-lo) for x in mapped) or 'nonloaded'
            pkg = (hex(payload_offset+lo), hex(payload_offset+hi)) if payload_offset is not None else ('-', '-')
            out.write(f'{component}\t{lo:#x}\t{hi:#x}\t{hi-lo}\t{pkg[0]}\t{pkg[1]}\t{va}\t{vaend}\n')
            count += 1
            total += hi-lo
    return {'ranges':count, 'different_or_added_bytes':total, 'file':path.name}

def main():
    stock_package = (R/'PxUpdate_V2.2.2.1.7.bin').read_bytes()
    original = parse(stock_package)
    assert serialize(original) == stock_package
    for h,p,t,_ in original[:2]:
        assert int.from_bytes(t,'little') == sum16(p)
    assert original[2][2] == b'00'
    assert original[0][1] == (R/'b14_stable_frame_packaging_work/voice_2.2.2.1.7_qnx.elf').read_bytes()
    assert original[2][1] == (R/'b14_stable_frame_packaging_work/pic_2.2.2.1.7.bin').read_bytes()
    fitted = (O/'pic_B15_absolute_INCOMPLETE.bin').read_bytes()
    qnx = (O/'voice_B15_absolute_QNX_UNPLACED.elf').read_bytes()
    assert sha(fitted) == 'bbaeda4fd2d32602088747caa81d4031fb4607c0073344e3e92fb6bdf00efbfe'
    assert sha(qnx) == json.loads((O/'absolute_qnx_integration_results.json').read_text())['candidate_sha256']
    pic, app = bytearray(fitted), bytearray(qnx)
    for off in (0x1394,0x13a0):
        assert hashlib.sha256(struct.pack('<I',struct.unpack_from('<I',pic,off)[0])).hexdigest()=='af1ad5f7ab9d96ce85f26b3de2e6a0b6dcc66054c2c06e0ef734156379b76468'
        struct.pack_into('<I',pic,off,0x24840008)
    assert app[0x1f4e3] == 0x17 and app[0x250ef] == 7
    app[0x1f4e3], app[0x250ef] = 0x18, 8
    assert [i for i,(a,b) in enumerate(zip(pic,fitted)) if a!=b] == [0x1394,0x13a0]
    assert [i for i,(a,b) in enumerate(zip(app,qnx)) if a!=b] == [0x1f4e3,0x250ef]
    rows=[]
    for index,payload in ((0,bytes(app)),(1,original[1][1]),(2,bytes(pic))):
        h,_,t,_ = original[index]
        if index!=1:
            h=h[:2]+REV+h[7:8]+len(payload).to_bytes(4,'big')
        if index==0:
            t=struct.pack('<H',sum16(payload))
        rows.append((h,payload,t,0))
    package=serialize(rows)
    target=O/'PxUpdate_V2.2.2.1.8_B15_candidate.bin'
    if target.exists():
        assert target.read_bytes()==package, 'refuse to overwrite different package'
    else:
        with target.open('xb') as out: out.write(package)
    extracted=parse(target.read_bytes())
    assert extracted[0][1]==app and extracted[2][1]==pic
    assert extracted[1][:3]==original[1][:3]
    assert all(int.from_bytes(t,'little')==sum16(p) for h,p,t,_ in extracted[:2])
    assert extracted[2][2]==b'00' and len(pic)==len(fitted)==len(original[2][1])
    words={hex(pc):hex(struct.unpack_from('<I',pic,pc)[0]) for pc in (0x81868,0x7fb40,0x7a3c8,0x7a3cc)}
    assert list(words.values())==['0x24633fc0','0x24843fc0','0x0','0x0']
    integration=json.loads((O/'absolute_pic_integration.json').read_text())
    regions=[(0x7a210,0x7a258),(0x7a4f8,0x7a56c),(0x7a408,0x7a450)]
    placements=[]
    for lo,hi in regions:
        assert pic[lo:hi]==fitted[lo:hi]
        pieces=[x for x in integration['pieces'] if lo<=int(x['pc'],16)-0x9d000000<hi]
        placements.append({'start':hex(0x9d000000+lo),'end':hex(0x9d000000+hi),'sha256':sha(pic[lo:hi]),'pieces':pieces})
    # Real retained version-thunk and checksum instructions in the bounded interpreter.
    sys.path.insert(0,str(O))
    import validate_pic_emission as v
    m=v.m
    for site,target_pc in ((0x258c0,0x9d075c1c),(0x51bc8,0x9d075b18)):
        c=m.CPU(pic);c.run(m.BASE+site,{target_pc})
        assert c.g('a0')==0x402a0008 and c.g('ra')==m.BASE+site+8
    for off in (0x258b4,0x51bc4):
        c=m.CPU(pic);c.s('a0',0x40290000);c.fetch_simple(m.BASE+off)
        assert c.g('a0')==0x40292221
    assert hashlib.sha256(struct.pack('<I',struct.unpack_from('<I',app,0x1f4e3)[0])).hexdigest()=='8c17100e1576a73618b83d9b06a4f40fa59805a9fab3f9b6bbeb88a2543d06e8'
    source=(R/'b7_candidate_work/validate_version_gates.py').read_text()
    ns={'app':app,'pic':pic,'struct':struct}
    exec(source[source.index('def gate('):source.index('\napp_cases=')],ns)
    gate=ns['gate'];cases=0
    for incoming in (list(REV),[2,2,2,1,7],[2,2,2,0,9]):
        assert (not bool(gate('app',incoming).get(0x373c,0)))==(incoming==list(REV));cases+=1
        assert bool(gate('pic',list(REV),incoming).get(0x3744,0))==(incoming==list(REV));cases+=1
    for i in range(5):
        incoming=list(REV);incoming[i]^=1
        assert gate('app',incoming).get(0x373c,0)
        assert not gate('pic',incoming,list(REV)).get(0x3744,0);cases+=2
    blocks=[pic[i:i+4096] for i in range(0,len(pic),4096)]
    c=m.CPU(pic)
    for block in blocks:
        c.write(m.GP-0x7f20,0,4)
        pcs=range(0x9d044484,0x9d04449c,4) if len(block)==4096 else range(0x9d04466c,0x9d044684,4)
        for low,high in zip(block[::2],block[1::2]):
            c.write(m.GP-0x7f1c,low,4);c.s('v0',high)
            for pc in pcs:c.simple(m.decode(pic,pc))
        expected=sum16(block);assert c.read(m.GP-0x7f20,2)==expected
        for incoming in (expected,expected^1):
            c.s('v0',incoming&255);c.s('a1',incoming>>8);c.s('v1',expected)
            for pc in (0x9d0444f0,0x9d0444f4,0x9d0444f8):c.simple(m.decode(pic,pc))
            assert (c.g('v0')==c.g('v1'))==(incoming==expected)
    for name,payload in (('pic_2.2.2.1.8_B15_candidate.bin',pic),('voice_2.2.2.1.8_B15_candidate_qnx.elf',app)):
        (O/name).write_bytes(payload)
    phoff=struct.unpack_from('<Q',app,32)[0];phents,phnum=struct.unpack_from('<HH',app,54)
    ph=[struct.unpack_from('<IIQQQQQQ',app,phoff+i*phents) for i in range(phnum)]
    diffs={
        'PIC':write_ranges(O/'candidate_1_8_pic_diff.tsv',original[2][1],pic,'PIC',extracted[2][3],0x9d000000),
        'QNX':write_ranges(O/'candidate_1_8_qnx_diff.tsv',original[0][1],app,'QNX',extracted[0][3],ph=ph),
        'package_positional':write_ranges(O/'candidate_1_8_package_diff.tsv',stock_package,package,'container'),
    }
    report={'status':'PASS_PACKAGE_BYTES_MODELED_UPDATER_CHECKS','version':list(REV),'package':target.name,
            'hashes':{'stock_package':sha(stock_package),'package':sha(package),'input_fitted_PIC':sha(fitted),'PIC':sha(pic),'input_QNX':sha(qnx),'QNX':sha(app),'FPGA':sha(extracted[1][1])},
            'package_bytes':len(package),'stock_package_bytes':len(stock_package),'PIC_bytes':len(pic),'QNX_bytes':len(app),
            'sections':[{'type':i+1,'payload_offset':hex(r[3]),'length':len(r[1]),'header':r[0].hex(),'trailer':r[2].hex()} for i,r in enumerate(extracted)],
            'required_words':words,'placements':placements,'diffs':diffs,'FPGA_record_unchanged':True,
            'metadata_only_delta_from_retained_inputs':{'PIC':['0x1394','0x13a0'],'QNX':['0x1f4e3','0x250ef']},
            'version_gate_cases':cases,'PIC_transport_checksum_blocks':len(blocks),'checksum_accept_reject_cases':2*len(blocks),
            'stack':{'startup_SP':'0x8007fff0','state_start':'0x80057aa0','state_end':'0x80057ae0','growth':'down','gap_to_state_end':0x28510,'gap_to_state_start':0x28550,'runtime_high_water':'NOT VERIFIED'},
            'hardware':'NOT VERIFIED','flashed':False,'limits':'Package framing/checksums and bounded updater interpretation only. Open ownership, ABI, interrupt and hardware checks remain; QNX runtime not executed. PIC length unchanged; QNX/package grow by existing retained QNX artifact size delta. Positional package diff includes shifts of unchanged later records.'}
    (O/'candidate_1_8_results.json').write_text(json.dumps(report,indent=2)+'\n')
    (O/'candidate_1_8_SHA256SUMS').write_text(''.join(f'{sha((O/n).read_bytes())}  {n}\n' for n in (target.name,'pic_2.2.2.1.8_B15_candidate.bin','voice_2.2.2.1.8_B15_candidate_qnx.elf')))
    print(json.dumps(report,indent=2))

if __name__=='__main__': main()
