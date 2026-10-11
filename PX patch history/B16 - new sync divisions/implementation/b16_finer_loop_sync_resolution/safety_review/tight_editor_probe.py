"""Isolated instruction overlay: reads baseline, never writes a firmware image.

No build/package driver imports. Outputs are text/JSON only. Explicit MIPS32
encoding and a scoped interpreter, not an independent assembler or PIC emulator.
"""
from pathlib import Path
import hashlib
import json
import struct

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
BASE = 0x9D000000
START, END = 0x9D04FA74, 0x9D04FB10
HELPER, SETTER = 0x9D0816E0, 0x9D04DACC
PIN = 'caa2a19d9a246aaeded2debd6b373490fee06f035d101373c24ec188456f6612'
NAMES = 'zero at v0 v1 a0 a1 a2 a3 t0 t1 t2 t3 t4 t5 t6 t7 s0 s1 s2 s3 s4 s5 s6 s7 t8 t9 k0 k1 gp sp fp ra'.split()
REG = {n:i for i,n in enumerate(NAMES)}
def r(n): return REG[n]
def signed(v): return v - 0x100000000 if v & 0x80000000 else v

def program():
    words, source, labels, fix = [], [], {}, []
    def emit(word, text): words.append(word); source.append(text)
    def rr(op, d, s, t):
        emit(r(s)<<21 | r(t)<<16 | r(d)<<11 | {'addu':33,'movn':11,'movz':10}[op], f'{op} {d},{s},{t}')
    def imm(op, t, s, v):
        text=f'{op} {t},{v:#x}({s})' if op in ('lw','lhu') else f'{op} {t},{s},{v:#x}'
        emit({'addiu':9,'andi':12,'xori':14,'sltiu':11,'lw':35,'lhu':37}[op]<<26 | r(s)<<21 | r(t)<<16 | (v&65535), text)
    def move(d,s): rr('addu',d,s,'zero')
    def lui(t,v): emit(15<<26 | r(t)<<16 | v, f'lui {t},{v:#x}')
    def jump(op,target): emit(op<<26 | (target>>2 & 0x3ffffff), f'{"jal" if op==3 else "j"} {target:#x}')
    move('t3','a0'); move('t4','a1'); move('t5','a2')
    move('a1','a3'); imm('lw','a2','sp',0x30)
    emit(r('t5')<<16 | r('v0')<<11 | 1<<6, 'sll v0,t5,1')
    imm('addiu','v1','v0',0xd6e); imm('andi','t0','t4',0xfffd)
    rr('movn','v0','v1','t0'); lui('v1',0x8000)
    rr('addu','v0','v0','v1'); imm('lhu','a0','v0',0x46c)
    imm('xori','t0','t5',0x1d); imm('xori','t1','t5',0x5e)
    rr('movz','t0','zero','t1')
    imm('sltiu','v1','a0',16); imm('addiu','t1','a0',2)
    imm('xori','t2','t1',19); rr('movz','t1','t2','v1')
    jump(3,HELPER); rr('movz','a0','t1','t0')
    imm('sltiu','v1','v0',2); imm('xori','t1','v0',17)
    imm('addiu','t2','v0',-2); rr('movn','t2','t1','v1')
    imm('andi','a3','v0',65535); rr('movz','a3','t2','t0')
    imm('addiu','v0','zero',0x182)
    fix.append((len(words),'setter')); emit(5<<26 | r('t5')<<21 | r('v0')<<16,'bne t5,v0,setter')
    move('a0','t3')
    imm('sltiu','v1','a3',30); imm('addiu','v0','zero',30)
    rr('movn','a3','v0','v1')
    labels['setter'] = START + 4*len(words)
    move('a1','t4'); move('a2','t5'); imm('lw','ra','sp',0x1c)
    jump(2,SETTER); imm('addiu','sp','sp',32)
    for index, label in fix:
        displacement=(labels[label]-(START+4*index+4))//4
        assert -32768<=displacement<=32767
        words[index] |= displacement&65535
    assert len(words)==38 and START+4*len(words)==END-4
    words.append(0); source.append('nop ; remaining original-body word, unreachable by normal tail')
    return {START+4*i:w for i,w in enumerate(words)}, source

class CPU:
    def __init__(self, image, overlay=None):
        self.image=image; self.overlay=overlay or {}; self.reg=[0]*32
        self.mem={}; self.trace=[]; self.writes=[]
    def read(self,a,n):
        if BASE<=a and a+n<=BASE+len(self.image):
            return int.from_bytes(self.image[a-BASE:a-BASE+n],'little')
        return sum(self.mem.get(a+i,0)<<(8*i) for i in range(n))
    def word(self,pc): return self.overlay.get(pc, self.read(pc,4))
    def write(self,a,n,v):
        self.writes.append((a,n))
        for i in range(n): self.mem[a+i]=(v>>(8*i))&255
    def plain(self,w):
        op=w>>26; s=w>>21&31; t=w>>16&31; d=w>>11&31
        fn=w&63; u=w&65535; k=u if u<32768 else u-65536
        q=self.reg
        if op==0:
            if fn==0:q[d]=q[t]<<(w>>6&31)
            elif fn==33:q[d]=q[s]+q[t]
            elif fn==35:q[d]=q[s]-q[t]
            elif fn==37:q[d]=q[s]|q[t]
            elif fn==38:q[d]=q[s]^q[t]
            elif fn==42:q[d]=int(signed(q[s])<signed(q[t]))
            elif fn==43:q[d]=int(q[s]<q[t])
            elif fn==10:
                if q[t]==0:q[d]=q[s]
            elif fn==11:
                if q[t]!=0:q[d]=q[s]
            else:raise AssertionError(('R instruction',hex(w)))
        elif op==9:q[t]=q[s]+k
        elif op==11:q[t]=int(q[s]<(k&0xffffffff))
        elif op==12:q[t]=q[s]&u
        elif op==14:q[t]=q[s]^u
        elif op==15:q[t]=u<<16
        elif op in (35,37):q[t]=self.read((q[s]+k)&0xffffffff,4 if op==35 else 2)
        elif op in (41,43):self.write((q[s]+k)&0xffffffff,2 if op==41 else 4,q[t])
        else:raise AssertionError(('instruction',hex(w)))
        self.reg=[v&0xffffffff for v in q]; self.reg[0]=0
    def run(self,pc,stop):
        for _ in range(240):
            if pc==stop:return
            self.trace.append(pc); w=self.word(pc); op=w>>26
            s=w>>21&31; t=w>>16&31; u=w&65535; k=u if u<32768 else u-65536
            target=None
            if op in (2,3):
                target=((pc+4)&0xf0000000)|((w&0x3ffffff)<<2)
                if op==3:self.reg[31]=pc+8
            elif op in (4,5):target=pc+4+4*k if ((self.reg[s]==self.reg[t])==(op==4)) else pc+8
            elif op==1 and t==0:target=pc+4+4*k if signed(self.reg[s])<0 else pc+8
            elif op==0 and w&63==8:target=self.reg[s]
            if target is None:self.plain(w); pc+=4
            else:
                self.trace.append(pc+4); self.plain(self.word(pc+4)); pc=target
        raise AssertionError('instruction limit')

def edit(image,overlay,ident,layer,a,b,delta,flag,maxv,stop=SETTER,wrapper=True):
    c=CPU(image,overlay); c.reg=[(0x5a010000+i*0x101)&0xffffffff for i in range(32)];c.reg[0]=0
    sp=0x80070000; ret=0x9d077770; c.reg[29]=sp;c.reg[31]=ret;c.reg[28]=0x80007ff0
    saved={i:c.reg[i] for i in range(16,24)};saved[30]=c.reg[30]
    c.reg[4:8]=[flag,layer,ident,delta&0xffffffff];c.write(sp+16,4,maxv)
    for bank,value in enumerate((a,b)):c.write(0x8000046c+2*(ident+bank*0x6b7),2,value)
    c.writes=[]
    c.run(0x9d04fa6c if wrapper else 0x9d0006cc,stop)
    if stop==SETTER:
        assert c.reg[29]==sp and c.reg[31]==ret
        assert all(c.reg[i]==v for i,v in saved.items())
        assert c.reg[4:7]==[flag,layer,ident]
        assert all(sp-32<=addr and addr+n<=sp for addr,n in c.writes)
    return c.reg[7],c

def main():
    image=(ROOT/'b11b_implementation_2_2_2_2_0/pic_2.2.2.2.0_B11b.bin').read_bytes()
    assert hashlib.sha256(image).hexdigest()==PIN
    overlay,source=program()
    assert len(overlay)*4==156 and min(overlay)==START and max(overlay)==END-4
    assert image[HELPER-BASE:HELPER-BASE+28].hex()=='2110a400030040042a18c2000800e0030b10c3000800e00321100000'
    gate=sum(((0 if i^0x5e==0 else i^0x1d)==0)==(i in (0x1d,0x5e)) for i in range(65536))
    assert gate==65536
    sync=non=bpm=chain=0
    deltas=list(range(-128,129))+[-32768,32767,-2147483648,2147483647,0x7ffffffe,-2147483647]
    layers=(0,1,2,3,4,65535,65536,65538)
    for ident in (0x1d,0x5e):
        for layer in layers:
            for flag in (0,1):
                for raw in range(18):
                    for delta in deltas:
                        aa,bb=raw,(raw+7)%18
                        selected=aa if layer&0xfffd==0 else bb
                        rank=selected+2 if selected<16 else 17-selected
                        k=max(0,min(17,signed((rank+delta)&0xffffffff)))
                        want=k-2 if k>=2 else 17-k
                        result,c=edit(image,overlay,ident,layer,aa,bb,delta,flag,17)
                        assert result==want,(ident,layer,raw,delta,result,want)
                        assert HELPER in c.trace and all(START<=p<END or p in range(0x9d04fa6c,START) or 0x9d0005d8<=p<0x9d0006d8 or HELPER<=p<HELPER+28 for p in c.trace)
                        sync+=1
    # Every baseline parameter-array ID, with all three ordinary layer selectors.
    # Special B11 IDs are tested at unchanged wrapper continuation to isolate editor.
    for ident in range(0x6b7):
        if ident in (0x1d,0x5e):continue
        for layer in (0,1,2):
            for delta in (-2147483648,-128,-1,0,1,128,2147483647):
                for maximum in (15,65535):
                    old,_=edit(image,None,ident,layer,63,127,delta,1,maximum)
                    new,_=edit(image,overlay,ident,layer,63,127,delta,1,maximum)
                    assert old==new,(ident,layer,delta,maximum,old,new)
                    non+=1
    for layer in layers:
        for raw in (0,1,29,30,31,65535):
            for delta in deltas:
                old,_=edit(image,None,0x182,layer,raw,raw,delta,0,65535)
                new,_=edit(image,overlay,0x182,layer,raw,raw,delta,0,65535)
                assert old==new and new>=30;bpm+=1
    # Verify the unchanged setter/B11/B6 prologue chain establishes identical
    # arguments and callee-saved context before original setter dispatch.
    for ident in (0x1d,0x5e,0x182,0x24,0x65):
        for layer in (0,1,2):
            for flag in (0,1):
                _,new=edit(image,overlay,ident,layer,0,0,0,flag,17 if ident in (0x1d,0x5e) else 127,stop=0x9d04dafc,wrapper=False)
                _,old=edit(image,None,ident,layer,0,0,0,flag,17 if ident in (0x1d,0x5e) else 127,stop=0x9d04dafc,wrapper=False)
                assert new.reg[4:8]==old.reg[4:8]
                assert new.reg[16:24]==old.reg[16:24] and new.reg[28:32]==old.reg[28:32];chain+=1
    listing='\n'.join(f'{pc:08x}: {overlay[pc]:08x}  {text}' for pc,text in zip(sorted(overlay),source))+'\n'
    (OUT/'TIGHT_EDITOR_LAYOUT.txt').write_text(listing)
    result={'status':'PASS: isolated explicit-word/scoped-interpreter checks only','baseline_sha256':PIN,
            'body_start':hex(START),'body_end_exclusive':hex(END),'active_words':38,'active_bytes':152,'body_bytes':156,'remaining_bytes':4,
            'gate_u16_cases':gate,'sync_instruction_cases':sync,'nonSync_baseline_comparisons':non,'BPM_baseline_comparisons':bpm,'setter_chain_context_comparisons':chain,
            'context':'t3=flag,t4=layer,t5=ID across exact helper; s0/s1/s2 untouched; original 32-byte frame/RA slot retained',
            'display_spare_bytes_used':0,'firmware_images_written':False,'package_generated':False,'hardware_actions':False,
            'limits':['No independent MIPS assembler/disassembler available; explicit ISA word encoding','Scoped interpreter does not model pipeline/cache/interrupts','Existing special B11 wrapper CP0 paths not executed; unchanged bytes retained','Full setter/event routes and hardware not executed','Recovery independence not established; user accepted general uncertainty for investigation only']}
    (OUT/'tight_editor_results.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
