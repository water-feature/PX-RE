"""Audit reuse of now-unreachable acceleration instructions, not spare padding."""
import hashlib
from pathlib import Path
import struct,json
ROOT=Path(__file__).resolve().parent.parent;OUT=Path(__file__).resolve().parent
b=(ROOT/'b9_250_candidate_work/pic_2.2.2.1.2.bin').read_bytes()
n=(OUT/'pic_B14_global_no_acceleration_unpackaged.bin').read_bytes()
lo,hi=0x9D07A468,0x9D07A56C
aliases=[lo,lo-0x40000000,lo-0x80000000]
inside=lambda t:any(a<=t<a+hi-lo for a in aliases)
literals=[];control=[];constructed=[]
for i in range(len(b)-3):
    w=struct.unpack_from('<I',b,i)[0]
    if inside(w):literals.append([hex(0x9D000000+i),hex(w)])
    if i%4:continue
    pc=0x9D000000+i;op=w>>26;target=None
    if op in (2,3):target=((pc+4)&0xF0000000)|((w&0x3FFFFFF)<<2)
    if op in (1,4,5,6,7,20,21,22,23):
        im=w&65535;target=pc+4+(im if im<32768 else im-65536)*4
    if target is not None and inside(target):control.append([hex(pc),hex(target)])
    if op==15:
        reg=w>>16&31;upper=(w&65535)<<16
        for j in range(i+4,min(i+68,len(b)-3),4):
            v=struct.unpack_from('<I',b,j)[0];o=v>>26
            if v>>21&31==reg and o in (9,13):
                im=v&65535
                t=(upper+(im if im<32768 else im-65536))&0xFFFFFFFF if o==9 else upper|im
                if inside(t):constructed.append([hex(pc),hex(0x9D000000+j),hex(t)])
assert not literals and not constructed
assert control==[['0x9d0768c4','0x9d07a500'],['0x9d07a34c','0x9d07a468'],['0x9d07a428','0x9d07a4ac'],['0x9d07a484','0x9d07a50c']]
# First is monotonic byte lookup data, not instructions (Ghidra no function/xref).
assert b[0x768C4:0x768C8]==bytes([14,15,17,18])
# Second removed. Third originates in negative acceleration block whose only
# canonical ingress is removed at 3c8. Fourth originates in reused dead block.
assert hashlib.sha256(struct.pack('<I',struct.unpack_from('<I',n,0x7A34C)[0])).hexdigest()=='df3f619804a92fdb4057192dc43dd748ea778adc52bc498ce80524c014b81119'
assert hashlib.sha256(struct.pack('<I',struct.unpack_from('<I',n,0x7A3C8)[0])).hexdigest()=='df3f619804a92fdb4057192dc43dd748ea778adc52bc498ce80524c014b81119'
# Existing anchor-rejection shared return block at 450..468 must survive.
assert n[0x7A450:0x7A468]==b[0x7A450:0x7A468]
# Both service entry references and decoder callers, direct target scans.
calls={t:[] for t in (0x9D07A208,0x9D07A258,0x9D07DB44,0x9D07A298)}
for i in range(0,len(b)-3,4):
    w=struct.unpack_from('<I',b,i)[0]
    if w>>26 not in (2,3):continue
    t=((0x9D000000+i+4)&0xF0000000)|((w&0x3FFFFFF)<<2)
    if t in calls:calls[t].append(hex(0x9D000000+i))
assert calls[0x9D07A208]==['0x9d07a274']
assert calls[0x9D07A258]==['0x9d0538c8']
assert calls[0x9D07DB44]==['0x9d07a23c']
assert calls[0x9D07A298]==['0x9d07a590','0x9d07a6b8']
assert all(struct.pack('<I',t) not in b for t in (0x9D07A208,0x9D07A258,0x9D07DB44))
report={'status':'PASS','dead_code_reserved':['0x9d07a468','0x9d07a56c'],
        'helper_used':['0x9d07a468','0x9d07a4f8'],'literal_refs':literals,
        'nearby_constructed_refs':constructed,'raw_control_hits':control,
        'lookup_data_false_positive':'9d0768c4 = 0e 0f 11 12 in monotonic byte table',
        'shared_anchor_exit_preserved':True,'baseline_direct_calls':{hex(t):v for t,v in calls.items()},
        'scope':'Direct references, nearby constructions and exhaustive decoder execution; arbitrary computed code pointers not exhaustively excluded.',
        'reentrancy':'Recovered service caller is main loop only; no direct ISR encoder-event/service recursion or literal callback registration. Each synchronous dispatch returns before next event.'}
(OUT/'placement_results.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
