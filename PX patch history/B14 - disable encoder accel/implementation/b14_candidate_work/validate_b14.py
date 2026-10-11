# SPDX-License-Identifier: GPL-2.0-or-later
"""Execute candidate words, with adversarial dispatch/ISR contracts.
This is a bounded host interpreter, not a silicon timing test.
"""
from pathlib import Path
import sys, json, struct, hashlib
ROOT=Path(__file__).resolve().parent.parent; OUT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'b9_250_candidate_work'))
import mips_check as m
original_decode=m.decode
def decode(image,pc):
    w=struct.unpack_from('<I',image,pc-m.BASE)[0]
    if w==0xC0:return ('ehb',)
    if w&0xFFE0FFFF==0x41606000:return ('di',m.REGS[w>>16&31])
    if w&0xFFE0FFFF==0x40806000:return ('mtc0_status',m.REGS[w>>16&31])
    if w>>26==31 and w&63==10 and w>>6&31==6:
        return ('lbux',m.REGS[w>>11&31],m.REGS[w>>16&31],m.REGS[w>>21&31])
    return original_decode(image,pc)
m.decode=decode
class CPU(m.CPU):
    def __init__(self,image,status=0x1000FF01):
        super().__init__(image);self.status=status;self.events=[];self.dispatch_inject=None
    def simple(self,row):
        op,*a=row
        if op=='ehb':return
        if op=='di':self.s(a[0],self.status);self.status&=~1;return
        if op=='mtc0_status':self.status=self.g(a[0]);return
        if op=='lbux':self.s(a[0],self.read(self.g(a[1])+self.g(a[2]),1));return
        super().simple(row)
    def external(self,pc):
        if pc!=0x9D07DB44:return False
        encoder,delta=self.g('a0'),m.signed(self.g('a1'))
        assert 0<=encoder<21 and delta in (-1,1)
        self.events.append((encoder,delta))
        if self.dispatch_inject:self.dispatch_inject(self)
        ra=self.g('ra');sp=self.g('sp')
        for i in list(range(1,16))+[24,25]:self.r[i]=0xBAD00000+i
        for off in range(0,16,4):self.write(sp+off,0xDECAFBAD,4)
        self.s('ra',ra);return True

base=(ROOT/'b9_250_candidate_work/pic_2.2.2.1.2.bin').read_bytes()
new=(OUT/'pic_B14_global_no_acceleration_unpackaged.bin').read_bytes()
record=lambda i:0x80010BF0+12*i
stop=0x9D081950
def service(i,n,status=0x1000FF01,inject=None,dispatch=None):
    c=CPU(new,status);c.s('a0',i);c.s('ra',stop);c.write(record(i)+8,n,4)
    c.write(record(i)-4,0x1234ABCD,4);c.write(record(i)+12,0x87654321,4)
    before=c.r.copy();c.inject=inject;c.dispatch_inject=dispatch
    c.run(0x9D07A208,{stop},maxsteps=200000)
    for reg in [*m.REGS[16:24],'gp','sp','fp','ra']:
        assert c.g(reg)==before[m.R[reg]],reg
    assert c.read(record(i)-4,4)==0x1234ABCD and c.read(record(i)+12,4)==0x87654321
    assert c.status==status
    return c

counts={}
for i in range(21):
    for n in [0,1,-1,3,-3,4,-4,32,-32,256,-256]:
        for status in [0x1000FF01,0x1000FF00]:
            c=service(i,n,status)
            assert c.events==[(i,1 if n>0 else -1)]*abs(n)
            assert c.read(record(i)+8,4)==0
counts['service_cases']=21*11*2

# New ISR movement while each synchronous callback runs must remain pending.
for n in [4,-3]:
    def producer(c):
        assert c.status&1
        addr=record(17)+8;c.write(addr,c.read(addr,4)+1,4)
    c=service(17,n,dispatch=producer)
    assert len(c.events)==abs(n) and c.read(record(17)+8,4)==abs(n)
    pending=c.read(record(17)+8,4)
    assert service(17,pending).events==[(17,1)]*pending
counts['during_dispatch_races']=2

# Interrupt attempt at every helper/hook boundary; masked attempts stay pending
# until IE is restored. Include the shared call address and both hook words.
pcs=[0x9D07A208,0x9D07A20C,*range(0x9D07A468,0x9D07A4F8,4),0x9D07DB44]
for pc in pcs:
    state={'requested':False,'done':False,'snapshot':None}
    def inject(c,at):
        if at==pc:state['requested']=True
        if state['requested'] and not state['done'] and c.status&1:
            addr=record(16)+8;c.write(addr,c.read(addr,4)+5,4);state['done']=True
            state['snapshot']=at<=0x9D07A4A0 and at!=0x9D07DB44
    c=service(16,4,inject=inject)
    assert state['done'],hex(pc)
    assert len(c.events)+c.read(record(16)+8,4)==9,hex(pc)
    assert len(c.events) in (4,9),hex(pc)
counts['instruction_boundary_races']=len(pcs)

# Exhaustively compare the patched decoder against factory slow timing for all
# countdown values, transition families, direction, warm-up and anchor cases.
cases=0
for q in range(16):
    for direction in (0,1):
        for warm in range(4):
            for anchor in (q,255):
                ref=CPU(base);ref.s('a0',0);ref.s('ra',stop)
                fields={0:q>>2,1:q&3,2:warm,4:direction,5:0,6:anchor}
                for off,val in fields.items():ref.write(record(0)+off,val,1)
                ref.run(0x9D07A298,{stop})
                expected=m.signed(ref.g('v0'))
                assert expected in (-1,0,1)
                for timer in range(256):
                    c=CPU(new);c.s('a0',0);c.s('ra',stop)
                    for off,val in fields.items():c.write(record(0)+off,timer if off==5 else val,1)
                    c.run(0x9D07A298,{stop})
                    assert m.signed(c.g('v0'))==expected,(q,direction,warm,anchor,timer)
                    for off in (0,1,2,4,5,6):assert c.read(record(0)+off,1)==ref.read(record(0)+off,1)
                    assert not any(0x9D07A408<=a<0x9D07A450 or 0x9D07A468<=a<0x9D07A56C for a,_ in c.trace)
                    cases+=1
counts['decoder_cases']=cases

for i in range(21):
    for states,sign in [([3,2,0,1,3],1),([3,1,0,2,3],-1)]:
        c=CPU(new);c.write(record(i)+6,255,1);total=0
        for _ in range(50):
            for prev,cur in zip(states,states[1:]):
                c.s('a0',i);c.s('ra',stop);c.write(record(i),cur,1);c.write(record(i)+1,prev,1)
                c.run(0x9D07A298,{stop});total+=m.signed(c.g('v0'))
        assert total==50*sign
counts['ideal_quadrature_sweeps']=42

# B9 and all unrelated bytes preserved, stronger than selected-span checks.
manifest=json.loads((OUT/'patch_manifest.json').read_text())
allowed=manifest['allowed_ranges']
diff=[i for i,(a,b) in enumerate(zip(base,new)) if a!=b]
assert len(diff)==manifest['changed_bytes']==146
assert all(any(a<=i<z for a,z in allowed) for i in diff)
assert base[0x234CC:0x235EC]==new[0x234CC:0x235EC]
assert base[0xD84:0xDF4]==new[0xD84:0xDF4]
report={'status':'PASS','candidate_sha256':hashlib.sha256(new).hexdigest(),
        **counts,'B9_helper_and_hooks_preserved':True,'outside_allowlist_identical':True,
        'limits':'Mock synchronous event consumer; bounded instruction model, no silicon timing or mechanical detent calibration. Signed reversal cancellation retained.'}
(OUT/'validation_results.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
