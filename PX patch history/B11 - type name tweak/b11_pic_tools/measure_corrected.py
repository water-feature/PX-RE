# SPDX-License-Identifier: GPL-2.0-or-later
"""Emit four standalone instruction fragments. Never opens a firmware image.

Sizing sketch only: valid stock group IDs, initialized cache, one parameter bank.
Not a deployable B11 patch; linked-layer semantics remain unresolved.
"""
import struct
from pathlib import Path

R = dict(zip(('zero','at','v0','v1','a0','a1','a2','a3','t0','t1','t2','t3','t4','t5','t6','t7','s0','s1','s2','s3','s4','s5','s6','s7','t8','t9','k0','k1','gp','sp','fp','ra'),range(32)))
sections = [(2634196812, 2634196924, 'entry:\nlhu v0,6,a0\nbne v0,zero,inst2\nlhu v1,0x20,a0\naddiu v0,zero,1\nsh v0,0x74,a0\nbeql v1,v0,0x9d02ebe8\nlhu a0,0x44,a0\naddiu a2,zero,0x24\naddiu s3,zero,0\ncommon:\nlhu a0,0x44,s0\njal 0x9d04d300\naddu a1,a2,zero\nlhu t0,-4,a1\naddu t2,v0,zero\nlw t3,8,s1\nslt t3,zero,t3\nbeq zero,zero,direction\nsll t3,t3,1\nrefresh1:\njal 0x9d03ec34\naddu a0,zero,zero\njal 0x9d03ec34\naddiu a0,zero,1\njal 0x9d03ec34\naddiu a0,zero,2\nui:\nlbu a1,0x1b8,s0\naddiu a0,s0,0x1b4\njal 0x9d036a28\naddu a2,zero,zero\n'), (2634208296, 2634208388, 'inst2:\naddiu v0,zero,1\nsh v0,0x76,a0\nbeql v1,v0,0x9d02eae8\nlhu a0,0x44,a0\naddiu a2,zero,0x65\nbeq zero,zero,common\naddiu s3,zero,3\ndirection:\naddiu a3,t3,-1\naddiu v0,zero,16\nsw v0,0x10,sp\nbeq t0,zero,invoke\naddu t3,t2,zero\nadvance:\naddu t3,t3,a3\nbeq zero,zero,scan\nsltiu t4,t3,17\nrefresh2:\njal 0x9d03ec34\naddiu a0,zero,3\njal 0x9d03ec34\naddiu a0,zero,4\njal 0x9d03ec34\naddiu a0,zero,5\nbeq zero,zero,0x9d02a7b0\nlbu a1,0x1b8,s0\n'), (2634210568, 2634210604, 'scan:\nbeq t4,zero,refresh_select\naddu a0,t0,zero\njal 0x9d0792e0\naddu a1,t3,zero\nsltiu v0,v0,2\nbne v0,zero,advance\nnop\nbeq zero,zero,invoke\nsubu a3,t3,t2\n'), (2634211064, 2634211100, 'invoke:\nlhu a1,0x44,s0\njal 0x9d04fa6c\naddu a0,zero,zero\nrefresh_select:\nbeq s3,zero,refresh1\nnop\nbeq zero,zero,refresh2\nnop\nnop\nnop\n')]
labels = {}; instructions=[]
for start,end,src in sections:
    pc=start
    for line in src.strip().splitlines():
        if line.endswith(':'): labels[line[:-1]]=pc
        else:
            instructions.append((pc,line)); pc+=4
    assert pc==end, (hex(start),hex(pc),hex(end))

def target(s): return labels[s] if s in labels else int(s,0)
def encode(pc,line):
    if line=='nop': return 0
    op,args=line.split(' ',1); a=args.split(',')
    if op in ('addu','subu','slt','movn'):
        d,s,t=map(R.__getitem__,a)
        return (s<<21)|(t<<16)|(d<<11)|dict(addu=33,subu=35,slt=42,movn=11)[op]
    if op=='sll':
        d,t,n=a; return (R[t]<<16)|(R[d]<<11)|(int(n,0)<<6)
    if op=='lui': return (15<<26)|(R[a[0]]<<16)|(int(a[1],0)&65535)
    if op in ('addiu','sltiu','andi'):
        t,s,n=a
        return (dict(addiu=9,sltiu=11,andi=12)[op]<<26)|(R[s]<<21)|(R[t]<<16)|(int(n,0)&65535)
    if op in ('lhu','lbu','lw','sh','sw'):
        t,n,s=a
        return (dict(lhu=37,lbu=36,lw=35,sh=41,sw=43)[op]<<26)|(R[s]<<21)|(R[t]<<16)|(int(n,0)&65535)
    if op in ('beq','bne','beql'):
        s,t,d=a; off=(target(d)-(pc+4))//4
        assert -32768<=off<=32767
        return (dict(beq=4,bne=5,beql=20)[op]<<26)|(R[s]<<21)|(R[t]<<16)|(off&65535)
    if op=='jal':
        dest=target(a[0]); assert dest>>28==(pc+4)>>28
        return (3<<26)|((dest>>2)&0x3ffffff)
    raise ValueError(line)

out=Path(__file__).parent/'corrected';out.mkdir(exist_ok=True)
listing=[]; total=0
for start,end,src in sections:
    fragment=[(pc,line) for pc,line in instructions if start<=pc<end]
    words=[encode(pc,line) for pc,line in fragment]
    data=b''.join(struct.pack('<I',w) for w in words)
    assert len(data)==end-start
    (out/f'scratch_{start:08x}.bin').write_bytes(data)
    listing.extend(f'{pc:08x}: {word:08x}  {line}' for (pc,line),word in zip(fragment,words))
    total+=len(data)
    print(f'[{start:08x},{end:08x}): {len(data)} bytes')
(out/'in_place_listing.txt').write_text('\n'.join(listing)+'\n')
assert labels['ui']==0x9d02a7ac
print(f'Total: {total} bytes; {len(instructions)} instructions; extra firmware storage: 0 bytes.')
print('Explicit subset encoder; no independent toolchain verification or firmware installation.')

# Execute the emitted words in a minimal decoder, including delay slots and
# annulled branch-likely slots. Setter/refresh/UI are explicit mocked calls.
# This checks the sizing sketch; it cannot validate firmware cache lifecycles.
image={pc:encode(pc,line) for pc,line in instructions}
def signed(x): return x-0x100000000 if x&0x80000000 else x
def run(instrument,layer,current,direction,populated,factory=False,group_mode=False):
    rr=[0]*32; mem={}; obj=0x80060000; event=0x80061000
    rr[R['a0']]=rr[R['s0']]=obj
    rr[R['a1']]=rr[R['s1']]=event
    mem.update({obj+6:instrument,obj+0x20:int(group_mode),obj+0x44:layer,event+8:direction&0xffffffff})
    param=(0x24,0x65)[instrument]
    ptr=0x8000046c+2*param+(0xd6e if layer&0xfffd else 0)
    group=0 if factory else 9
    mem[ptr-4]=group; mem[ptr]=current
    for category in range(17): mem[0x80037e90+8*(17*group+category)]=3 if category in populated else 1
    calls=[]; flags=[]; reads=[]; pc=labels['entry']; steps=0
    def plain(word):
        op=word>>26; s=(word>>21)&31; t=(word>>16)&31; d=(word>>11)&31
        immediate=word&65535; si=immediate if immediate<32768 else immediate-65536
        if op==0:
            fn=word&63
            if fn==0: rr[d]=(rr[t]<<((word>>6)&31))&0xffffffff
            elif fn==33: rr[d]=(rr[s]+rr[t])&0xffffffff
            elif fn==35: rr[d]=(rr[s]-rr[t])&0xffffffff
            elif fn==42: rr[d]=int(signed(rr[s])<signed(rr[t]))
            elif fn==11:
                if rr[t]: rr[d]=rr[s]
            else: raise AssertionError(hex(word))
        elif op==15: rr[t]=immediate<<16
        elif op==9: rr[t]=(rr[s]+si)&0xffffffff
        elif op==11: rr[t]=int(rr[s]<(si&0xffffffff))
        elif op==12: rr[t]=rr[s]&immediate
        elif op in (35,36,37):
            address=(rr[s]+si)&0xffffffff
            rr[t]=mem.get(address,0)&({35:0xffffffff,36:255,37:65535}[op])
            if 0x80037e90<=address<0x8003a118: reads.append(address)
        elif op in (41,43): mem[(rr[s]+si)&0xffffffff]=rr[t]&({41:65535,43:0xffffffff}[op])
        else: raise AssertionError(hex(word))
        rr[0]=0
    while True:
        steps+=1; assert steps<1000
        w=image[pc]; op=w>>26
        if op in (4,5,20):
            s=(w>>21)&31; t=(w>>16)&31
            taken=(rr[s]==rr[t]) if op in (4,20) else (rr[s]!=rr[t])
            off=w&65535; off=off if off<32768 else off-65536
            dest=pc+4+off*4
            if taken or op!=20: plain(image[pc+4])
            if taken and dest in (0x9d02ebe8,0x9d02eae8):
                assert group_mode and rr[R['a0']]==layer
                return
            pc=dest if taken else pc+8
        elif op==3:
            dest=((pc+4)&0xf0000000)|((w&0x3ffffff)<<2)
            rr[31]=pc+8; plain(image[pc+4])
            if dest==0x9d04d300:
                bank=(0xd6e if rr[4]&0xfffd else 0)
                rr[4]&=0xfffd
                rr[5]=0x8000046c+bank+2*rr[5]
                rr[2]=mem[rr[5]]
            elif dest==0x9d0792e0:
                address=0x80037e90+8*(17*rr[4]+rr[5])
                reads.append(address)
                rr[2]=mem[address]
                rr[3]=0x80037e90
                rr[4]*=17
                rr[5]+=rr[4]
            elif dest==0x9d04fa6c:
                assert rr[4]==0 and rr[5]==layer and rr[6]==param and mem[rr[29]+0x10]==16
                calls.append(signed(rr[7]))
            elif dest==0x9d03ec34: flags.append(rr[4])
            elif dest==0x9d036a28: break
            else: raise AssertionError(hex(dest))
            pc+=8
        else: plain(w); pc+=4
    expected=next((c-current for c in range(current+direction,17 if direction>0 else -1,direction) if c in populated),0)
    assert calls==([direction] if factory else [expected] if expected else []), (instrument,layer,current,direction,populated,calls,expected)
    assert flags==([0,1,2] if instrument==0 else [3,4,5])
    assert len(reads)<=16
    assert mem[obj+(0x74 if instrument==0 else 0x76)]==1

patterns=[set(),set(range(17)),{0},{16},{2,7,15},{1,4,8,12}]
cases=0
for instrument in (0,1):
    for layer in (0,1,2):
        for current in range(17):
            for direction in (-1,1):
                for populated in patterns:
                    run(instrument,layer,current,direction,populated); cases+=1
                run(instrument,layer,current,direction,set(),factory=True); cases+=1
                run(instrument,layer,current,direction,set(),group_mode=True); cases+=1
print(f'Minimal emitted-word interpreter: {cases} bank-selection/Factory/Group cases passed (including edit value 2).')
