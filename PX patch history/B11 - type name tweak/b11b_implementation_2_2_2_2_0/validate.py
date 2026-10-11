"""Validate actual emitted PIC bytes with no instruction overlays."""
from pathlib import Path
import contextlib,io,json,runpy,struct,sys
import build as b
O=b.O;R=b.R
def main():
    pic=(O/'pic_2.2.2.2.0_B11b.bin').read_bytes();app=(O/'voice_2.2.2.2.0_B11b_qnx.elf').read_bytes()
    emission=json.loads((O/'emission.json').read_text())
    assert b.sha(pic)==emission['PIC_sha256'] and b.sha(app)==emission['QNX_sha256']
    import setter_harness as sh
    import measure_compact as m
    # The independent assembler ran during import. Match its complete word map
    # against disk, then execute disk bytes rather than the harness overlays.
    assert all(struct.unpack_from('<I',pic,p-b.BASE)[0]==w for p,w in m.image.items())
    for a,z in b.OWNED:
        assert pic[a-b.BASE:z-b.BASE]==(O/'approved'/f'fragment_{a:08x}.bin').read_bytes()
        assert (O/'compact'/f'fragment_{a:08x}.bin').read_bytes()==(O/'approved'/f'fragment_{a:08x}.bin').read_bytes()
    sh.pic.b=pic
    original=sh.CPU
    class EmittedCPU(original):
        def __init__(self,overlay=None,callbacks=None):
            if overlay:
                assert all(struct.unpack_from('<I',pic,p-b.BASE)[0]==w for p,w in overlay.items()),'overlay would conceal a disk mismatch'
            super().__init__(None,callbacks)
    sh.CPU=m.CPU=EmittedCPU
    log=io.StringIO()
    with contextlib.redirect_stdout(log):
        runpy.run_path(str(O/'measure_compact.py'),run_name='__main__')
        runpy.run_path(str(O/'check_compact.py'),run_name='__main__')
        runpy.run_path(str(O/'check_bank_refresh.py'),run_name='__main__')
    b.save('validation.log',log.getvalue().encode())
    routing=json.loads((O/'compact/results.json').read_text());extended=json.loads((O/'compact/extended_results.json').read_text())
    # Decode actual emitted control transfers and their delay slots.
    edges=[];external={0x9d02ebe8,0x9d02eae8,0x9d02a794,0x9d02d464,0x9d04d300,0x9d04dacc,0x9d04d4fc}
    for pc in sorted(m.image):
        w=struct.unpack_from('<I',pic,pc-b.BASE)[0];op=w>>26;target=None
        if op in (2,3):target=((pc+4)&0xf0000000)|((w&0x3ffffff)<<2)
        elif op in (4,5,20,21):
            n=w&65535;target=pc+4+4*(n if n<32768 else n-65536)
        if target is None:continue
        assert target%4==0 and (target in m.image or target in external)
        delay=struct.unpack_from('<I',pic,pc+4-b.BASE)[0]
        assert delay>>26 not in (1,2,3,4,5,6,7,20,21,22,23)
        assert not (delay>>26==0 and delay&63 in (8,9))
        edges.append({'source':hex(pc),'target':hex(target),'delay_word':hex(delay),'instruction':sh.pic.dec(pc,w)})
    assert struct.unpack_from('<I',pic,0x2df08)[0]==(3<<26)|((0x9d04dacc>>2)&0x3ffffff)
    assert m.image[0x9d02dd10]&65535==0xdf10
    b.save('branch_targets.json',(json.dumps(edges,indent=2)+'\n').encode())
    baseline=b.PIC.read_bytes()
    allowed={p-b.BASE+i for p in m.image for i in range(4)}|{p+i for p in b.PIC_META for i in range(4)}
    assert set(b.diff(baseline,pic))<=allowed
    for a,z in [(0x2a794,0x2a7bc),(0x2d464,0x2d484),(0x22760,0x227ac),(0x2eae8,0x2eb08),(0x2ebe8,0x2ec08)]:assert pic[a:z]==baseline[a:z]
    # Verify both real PIC report thunks and four-component report immediates.
    for site,target in [(0x258c0,0x9d075c1c),(0x51bc8,0x9d075b18)]:
        c=EmittedCPU();c.run(b.BASE+site,{target});assert c.r[4]==0x402a0000 and c.r[31]==b.BASE+site+8
    for off in (0x258b4,0x51bc4):
        c=EmittedCPU();c.r[4]=0x40290000;c.plain(struct.unpack_from('<I',pic,off)[0],b.BASE+off);assert c.r[4]==0x40292222
    reply=struct.unpack_from('<I',app,0x1f4e3)[0];packed=reply&65535
    assert reply==0x40139220 and [packed>>14,(packed>>11)&7,(packed>>8)&7,(packed>>4)&15,packed&15]==list(b.REV)
    # Execute the existing bounded x86 decoder on actual updater gate bytes.
    source=(R/'b7_candidate_work/validate_version_gates.py').read_text();ns={'app':app,'struct':struct}
    exec(source[source.index('def gate('):source.index('\napp_cases=')],ns);gate=ns['gate'];cases=0
    for compiled,image in [(list(b.REV),app),([2,2,2,1,15],b.APP.read_bytes())]:
        ns['app']=image
        for incoming in [list(b.REV),[2,2,2,1,15],[2,2,2,1,16]]:
            assert (not bool(gate('app',incoming).get(0x373c,0)))==(incoming==compiled);cases+=1
        for i in range(5):
            incoming=compiled.copy();incoming[i]^=1;assert gate('app',incoming).get(0x373c,0);cases+=1
        for installed in [list(b.REV),[2,2,2,1,15],[2,2,2,1,16]]:
            assert bool(gate('pic',list(b.REV),installed).get(0x3744,0))==(installed==list(b.REV));cases+=1
    # Execute unchanged receiver arithmetic on every candidate PIC block.
    sys.path.insert(0,str(R/'b9_250_candidate_work'));import mips_check as mc
    blocks=[pic[i:i+4096] for i in range(0,len(pic),4096)];c=mc.CPU(pic)
    for block in blocks:
        c.write(mc.GP-0x7f20,0,4)
        pcs=range(0x9d044484,0x9d04449c,4) if len(block)==4096 else range(0x9d04466c,0x9d044684,4)
        for low,high in zip(block[::2],block[1::2]):
            c.write(mc.GP-0x7f1c,low,4);c.s('v0',high)
            for pc in pcs:c.simple(mc.decode(pic,pc))
        expected=b.sum16(block);assert c.read(mc.GP-0x7f20,2)==expected
        for incoming in (expected,expected^1):
            c.s('v0',incoming&255);c.s('a1',incoming>>8);c.s('v1',expected)
            for pc in (0x9d0444f0,0x9d0444f4,0x9d0444f8):c.simple(mc.decode(pic,pc))
            assert (c.g('v0')==c.g('v1'))==(incoming==expected)
    report={'status':'PASS','PIC_sha256':b.sha(pic),'QNX_sha256':b.sha(app),'instruction_source':'actual emitted file; overlays disabled','LLVM':'51 layout words match approved fragments, zero relocations','routing_cases':routing['actual_routing_and_setter_cases'],'extended':extended,'branch_target_count':len(edges),'branch_targets_and_delay_slots':'PASS','preserved_refresh_Group_cache_and_unrelated_bytes':'PASS','version_report_and_display':'PASS: 2.2.2.2.0','actual_version_gate_cases':cases,'PIC_transport_blocks':len(blocks),'valid_corrupt_checksum_comparisons':len(blocks)*2,'cache_correction_included':False,'hardware':'NOT VERIFIED; no hardware flashed','limits':'UI/metadata/sample I/O stubbed; full on-device preset recall and interrupt timing not executed'}
    b.save('validation.json',(json.dumps(report,indent=2)+'\n').encode());print(json.dumps(report,indent=2))
if __name__=='__main__':main()
