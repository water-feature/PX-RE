#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Independent container verifier; no packager imports or QNX execution."""
import hashlib,struct,json
from pathlib import Path
VOICE_SHA='2ad5392eb842cbcd5c2e85e65ab42c16f1fac12d16b09c417a61761a8348bcbf'
QNX_SHA='07ff1fd635505114945fc4dcab11a212f4bc9164b1a7ab8beb681482cb7c2b35'
FPGA_SHA='54c70b9969c7bc6004c7ceb257a15ff1581ef82b1c3c1ad1eba185eacf15ad2b'
PIC_SHA='14e9c9b9dc562b0384fc43b3c5e0eb7fea84a5792d1a19b9b3ea8276ef7646f5'
def digest(data):return hashlib.sha256(data).hexdigest()
def walk(data):
    if data[0]!=240:raise ValueError('missing F0')
    result=[];p=1
    while p<len(data) and data[p]!=247:
        if p+12>len(data):raise ValueError('truncated header')
        kind,marker=data[p:p+2];revision=tuple(data[p+2:p+7]);marker2=data[p+7]
        if marker!=123 or marker2!=122:raise ValueError('bad record markers')
        length=struct.unpack_from('>I',data,p+8)[0];payload_offset=p+12;trailer_offset=payload_offset+length
        if length%2 or trailer_offset+2>=len(data):raise ValueError('invalid payload length')
        payload=data[payload_offset:trailer_offset];stored=struct.unpack_from('<H',data,trailer_offset)[0]
        # Explicit byte-pair implementation independent of struct.iter_unpack.
        calculated=sum(payload[i]+256*payload[i+1] for i in range(0,length,2))%65536
        result.append({'type':kind,'header_offset':p,'payload_offset':payload_offset,'trailer_offset':trailer_offset,'end_offset':trailer_offset+2,'length':length,'revision':list(revision),
                       'stored_checksum':f'0x{stored:04x}','calculated_word_checksum':f'0x{calculated:04x}','word_checksum_matches':stored==calculated,'payload_sha256':digest(payload),
                       'record_sha256':digest(data[p:trailer_offset+2])})
        p=trailer_offset+2
    if p!=len(data)-1 or data[p]!=247:raise ValueError('trailing bytes or missing F7')
    if [r['type'] for r in result]!=[1,2,3]:raise ValueError('unexpected record chain')
    return result

def verify(base,test,candidate):
    checks=[]
    def require(label,condition):
        if not condition:raise ValueError(label)
        checks.append(label)
    require('exact tested voice container',digest(base)==VOICE_SHA)
    require('required candidate identity',digest(candidate)==QNX_SHA)
    baseline=walk(base);packed=walk(test)
    require('three records and F0/F7 framing',len(packed)==len(baseline)==3)
    require('B5 header revision 2.2.2.0.5',packed[0]['revision']==[2,2,2,0,5])
    require('application length matches exact candidate',packed[0]['length']==len(candidate)==1014576)
    q=packed[0];payload=test[q['payload_offset']:q['trailer_offset']]
    require('extracted QNX bytes and pinned hash',payload==candidate and digest(payload)==QNX_SHA)
    require('application word checksum',q['word_checksum_matches'])
    require('base application checksum',baseline[0]['word_checksum_matches'] and baseline[0]['stored_checksum']=='0xf44b')
    require('application header changes confined to version/length',test[:3]==base[:3] and test[3:7]==base[3:7] and test[7]==5 and test[8]==base[8])
    require('complete later-record suffix unchanged',test[q['end_offset']:]==base[baseline[0]['end_offset']:])
    shift=len(candidate)-baseline[0]['length']
    require('total file length equals payload growth',len(test)==len(base)+shift)
    for old,new,pin in zip(baseline[1:],packed[1:],[FPGA_SHA,PIC_SHA]):
        kind=old['type'];name='FPGA' if kind==2 else 'PIC'
        require(name+' complete record bytes unchanged',base[old['header_offset']:old['end_offset']]==test[new['header_offset']:new['end_offset']])
        require(name+' payload bytes/hash unchanged',base[old['payload_offset']:old['trailer_offset']]==test[new['payload_offset']:new['trailer_offset']] and old['payload_sha256']==new['payload_sha256']==pin)
        require(name+' length/revision/trailer preserved',old['length']==new['length'] and old['revision']==new['revision'] and old['stored_checksum']==new['stored_checksum'])
        require(name+' offset shift matches QNX growth',new['header_offset']==old['header_offset']+shift)
    require('FPGA checksum matches established word sum',packed[1]['word_checksum_matches'] and baseline[1]['word_checksum_matches'])
    require('known PIC checksum discrepancy preserved exactly',packed[2]['stored_checksum']==baseline[2]['stored_checksum']=='0x3030' and packed[2]['calculated_word_checksum']==baseline[2]['calculated_word_checksum']=='0x4658')
    return {'status':'offline_container_verified','container_sha256':digest(test),'container_bytes':len(test),'candidate_sha256':digest(payload),'passed':len(checks),'checks':checks,'records':packed,
            'known_base_checksum_exception':'PIC stored 0x3030 differs from simple word sum 0x4658 in the exact tested base; its entire record/trailer is preserved, not repaired.',
            'hardware_acceptance_tested':False,'target_performance_tested':False,'listening_tested':False}

if __name__=='__main__':
    root=Path(__file__).resolve().parent;workspace=root.parent
    result=verify((workspace/'voice_2.2.2.0.2.bin').read_bytes(),(root/'voice_b5_2.2.2.0.5.bin').read_bytes(),(workspace/'b5_candidate_work/voice_2.2.2.0.2_qnx_B5_candidate.elf').read_bytes())
    print(json.dumps(result,indent=2))
