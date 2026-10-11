"""Package only validated exact bytes; exclusively publish a new candidate."""
from pathlib import Path
import json,struct
import build as b
O=b.O;R=b.R
NAME='PxUpdate_V2.2.2.2.0_B11b_real_instrument_on_Type_candidate.bin'
def extract(data):
    # Independent extraction uses a cursor and unpacked big-endian lengths,
    # without the build module's parser or serializer.
    assert data[:1]==b'\xf0' and data[-1:]==b'\xf7'
    cursor=1;rows=[]
    while cursor<len(data)-1:
        typ,marker,*version=data[cursor:cursor+7]
        assert typ==len(rows)+1 and marker==123 and data[cursor+7]==122
        size=struct.unpack_from('>I',data,cursor+8)[0]
        start=cursor+12;end=start+size
        assert end+2<=len(data)-1
        rows.append({'header':data[cursor:start],'payload':data[start:end],'trailer':data[end:end+2],'offset':cursor,'start':start,'end':end,'version':version})
        cursor=end+2
    assert cursor==len(data)-1 and len(rows)==3
    return rows
def main():
    target=R/NAME;assert not target.exists(),'Never overwrite an existing candidate'
    validation=json.loads((O/'validation.json').read_text());assert validation['status']=='PASS'
    old=b.PKG.read_bytes();assert b.sha(old)=='ebb2aebbd0decdadce92ed40d257e0cb03ebbf7aecf3e05749d9533fd5603450'
    base=b.parse(old);app=(O/'voice_2.2.2.2.0_B11b_qnx.elf').read_bytes();pic=(O/'pic_2.2.2.2.0_B11b.bin').read_bytes()
    assert b.sha(app)==validation['QNX_sha256'] and b.sha(pic)==validation['PIC_sha256']
    rows=[]
    for i,payload in enumerate((app,base[1][1],pic)):
        h,_,t,off=base[i]
        if i in (0,2):h=h[:2]+b.REV+h[7:]
        if i==0:t=struct.pack('<H',b.sum16(payload))
        rows.append((h,payload,t,off))
    data=b.serialize(rows);assert len(data)==len(old)==3187784
    b.save('package_pending_validation.bin',data)
    saved=(O/'package_pending_validation.bin').read_bytes();ex=extract(saved);prior=extract(old)
    assert saved==data and ex[0]['payload']==app and ex[2]['payload']==pic
    assert ex[1]==prior[1]
    assert ex[2]['trailer']==prior[2]['trailer']==b'00'
    for i in (0,1):
        payload=ex[i]['payload']
        checksum=sum(int.from_bytes(payload[j:j+2],'little') for j in range(0,len(payload),2))&65535
        assert ex[i]['trailer']==checksum.to_bytes(2,'little')
    assert all(ex[i]['version']==list(b.REV) for i in (0,2))
    assert all(ex[i]['offset']==prior[i]['offset'] and ex[i]['end']==prior[i]['end'] for i in range(3))
    # Every difference is accounted for, including revision metadata separately
    # from functional ownership. No QNX audio code or FPGA byte may change.
    pic_allowed={a-b.BASE+i for lo,hi in b.OWNED for a in range(lo,hi,4) for i in range(4)}
    pic_allowed|={a-b.BASE+i for a in b.SITES for i in range(4)}|{a+i for a in b.PIC_META for i in range(4)}
    allowed={ex[2]['start']+i for i in pic_allowed}|{ex[0]['start']+i for i in b.APP_META}
    allowed|={ex[i]['offset']+j for i in (0,2) for j in range(2,7)}|{ex[0]['end'],ex[0]['end']+1}
    changed=b.diff(old,saved);assert set(changed)<=allowed
    for name,i in [('reextracted_qnx.elf',0),('reextracted_fpga.bin',1),('reextracted_pic.bin',2)]:b.save(name,ex[i]['payload'])
    assert (O/'reextracted_qnx.elf').read_bytes()==app and (O/'reextracted_pic.bin').read_bytes()==pic
    b.diff_file('package_diff.tsv',old,saved)
    # Publication is the final step after validation. xb refuses even an
    # identically named package created by another process during validation.
    with target.open('xb') as f:f.write(saved)
    assert target.read_bytes()==saved
    published=extract(target.read_bytes());assert published==ex
    report={'status':'PASS','revision':'2.2.2.2.0','baseline':'exact 2.2.2.1.15','baseline_package_sha256':b.sha(old),'package':str(target),'package_bytes':len(saved),'package_sha256':b.sha(saved),'PIC_sha256':b.sha(pic),'QNX_sha256':b.sha(app),'FPGA_sha256':b.sha(ex[1]['payload']),'application_checksum':ex[0]['trailer'].hex(),'FPGA_checksum':ex[1]['trailer'].hex(),'PIC_legacy_container_trailer':ex[2]['trailer'].hex(),'PIC_block_checksum_validation':validation['PIC_transport_blocks'],'package_differing_bytes':len(changed),'all_package_differences_accounted':True,'independent_reextraction_matches_validated_components':True,'FPGA_entire_record_unchanged':True,'PIC_and_QNX_outside_B11b_and_version_metadata_unchanged':True,'cache_correction_included':False,'no_existing_candidate_overwritten':True,'flashable_candidate':True,'hardware':'NOT VERIFIED','flashed':False}
    b.save('package_results.json',(json.dumps(report,indent=2)+'\n').encode());print(json.dumps(report,indent=2))
if __name__=='__main__':main()
