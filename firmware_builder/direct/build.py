# SPDX-License-Identifier: GPL-2.0-or-later
"""Build one final update directly from the exact factory update, in memory."""
import argparse
import json
import os
from pathlib import Path
import struct
import sys
import tempfile
import time
sys.dont_write_bytecode=True
from core import FACTORY_SHA256,FINAL_SHA256,sha
from objects import Objects
import pic
import qnx
from px_container import Record,parse,serialize,sum16,elf_layout

HERE=Path(__file__).resolve().parent
def validate(factory,output,receipts):
    old,new=parse(factory),parse(output)
    if old[1].encode()!=new[1].encode():raise ValueError('FPGA record changed')
    for i,name in [(0,'QNX'),(2,'PIC')]:
        before,after=old[i].payload,new[i].payload
        owned=bytearray(len(after))
        for row in receipts[name]:
            lo,hi=row['offset'],row['offset']+row['size']
            if hi>len(after) or any(owned[lo:hi]):raise ValueError('Invalid final ownership receipt')
            if sha(before[lo:hi])!=row['factory_sha256'] or sha(after[lo:hi])!=row['generated_sha256']:raise ValueError('Ownership receipt hash mismatch')
            owned[lo:hi]=b'\x01'*(hi-lo)
        if any(not owned[i] for i in range(len(after)) if i>=len(before) or after[i]!=before[i]):raise ValueError('Unowned changed byte')
        if new[i].header[2:7]!=bytes((2,2,2,2,2)):raise ValueError('Wrong final revision header')
    app=new[0].payload;layout=elf_layout(app)
    for p in layout['programs']:
        if p['type']==1 and p['file_size']>p['memory_size']:raise ValueError('ELF load size exceeds memory size')
    allocated=[]
    for name,s in layout['sections'].items():
        if s['type']==8:continue
        if name in ('.b5.text','.b5.eh_frame','.b8.text','.b8.eh_frame','.b15_text','.b15_eh_frame'):
            lo,hi=s['address'],s['address']+s['size']
            if any(lo<b and a<hi for a,b in allocated):raise ValueError('Added ELF sections overlap')
            allocated.append((lo,hi))
            if not any(p['type']==1 and p['flags']&4 and p['address']<=lo and hi<=p['address']+p['file_size'] for p in layout['programs']):raise ValueError('Added ELF section is not readable')
    h=layout['sections']['.eh_frame_hdr'];frame,pairs=qnx.decode(app[h['offset']:h['offset']+h['size']],h['address'])
    if len(pairs)!=910 or pairs!=sorted(pairs):raise ValueError('Final unwind index mismatch')
    for pc,fde in pairs:
        if fde+16>len(app):raise ValueError('FDE exceeds application')
        length,cie,delta,extent=struct.unpack_from('<IIiI',app,fde)
        if not cie or length<12 or fde+4+length>len(app) or fde+8+delta!=pc:raise ValueError('Indexed FDE target or extent mismatch')
        if not any(p['type']==1 and p['flags']&1 and p['address']<=pc and pc+extent<=p['address']+p['file_size'] for p in layout['programs']):raise ValueError('FDE code is outside executable mapping')
    if struct.unpack_from('<I',app,0x1f4e3)[0]!=0x40139222 or app[0x250e2]!=2 or app[0x250ef]!=2:raise ValueError('DSP/updater revision mismatch')
    if len(output)!=3187784 or sha(output)!=FINAL_SHA256:raise ValueError('Final update identity mismatch')
    return {'factory_identity':'PASS','record_checksums':'PASS','final_identity':'PASS','FPGA_unchanged':'PASS',
            'changed_byte_ownership':'PASS','ELF_added_sections_and_loads':'PASS','indexed_FDEs':len(pairs),
            'revision_headers_and_gates':'PASS'}

def build(factory,cache_path,progress=lambda stage,seconds:None):
    start=time.perf_counter();times={}
    def stage(name):
        nonlocal start
        now=time.perf_counter();times[name]=now-start;start=now;progress(name,times[name])
    if sha(factory)!=FACTORY_SHA256:raise ValueError('Factory identity mismatch')
    old=parse(factory)
    if serialize(old)!=factory:raise ValueError('Factory container round trip mismatch')
    cache=Objects(cache_path,factory);stage('input and cache verification')
    app,ar=qnx.build(old[0].payload,cache);stage('direct QNX generation')
    dsp,dr=pic.build(old[2].payload,cache);stage('direct PIC generation')
    def record(original,payload):
        header=bytearray(original.header);header[2:7]=bytes((2,2,2,2,2));header[8:12]=len(payload).to_bytes(4,'big')
        return Record(original.kind,0,bytes(header),payload,sum16(payload).to_bytes(2,'little') if original.kind==1 else original.trailer)
    result=serialize((record(old[0],app),old[1],record(old[2],dsp)))
    receipts={'QNX':ar,'PIC':dr};checks=validate(factory,result,receipts);stage('final container validation')
    return result,{'status':'PASS','sha256':sha(result),'size':len(result),'checks':checks,'stage_seconds':times,
                   'platform':sys.platform,'python':sys.version,'intermediate_firmware_files':0,
                   'historical_builders_executed':0,'compiler_processes':0,'object_identities_used':15,
                   'ownership':receipts,'hardware':'NOT VERIFIED','native_platform_scope':'This execution only'}

def write_new(path,data):
    """Publish a fully written file atomically, without replacing an existing path."""
    path=Path(path)
    if os.path.lexists(path):raise FileExistsError('Output already exists: '+str(path))
    temporary=None
    try:
        with tempfile.NamedTemporaryFile(prefix='.'+path.name+'.',suffix='.tmp',dir=path.parent,delete=False) as stream:
            temporary=Path(stream.name);stream.write(data);stream.flush();os.fsync(stream.fileno())
        os.link(temporary,path) # Atomic exclusive creation on Windows, macOS and Linux.
    finally:
        if temporary is not None:temporary.unlink(missing_ok=True)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('factory',type=Path)
    parser.add_argument('-o','--output',type=Path,required=True)
    args=parser.parse_args();report_path=args.output.with_suffix(args.output.suffix+'.report.json')
    if args.factory.resolve()==args.output.resolve():raise ValueError('Output must differ from factory input')
    if args.output.resolve().is_relative_to(HERE.parents[1]):raise ValueError('Output must be outside the repository')
    if any(os.path.lexists(p) for p in (args.output,report_path)):raise FileExistsError('Output or report already exists')
    result,report=build(args.factory.read_bytes(),HERE/'cache',lambda name,seconds:print(f'PASS: {name} ({seconds:.3f}s)',flush=True))
    write_new(args.output,result)
    write_new(report_path,(json.dumps(report,indent=2)+'\n').encode())
    print('PASS: final firmware '+str(args.output),flush=True)
    print('Bytes: '+str(len(result)),flush=True)
    print('SHA-256: '+report['sha256'],flush=True)

if __name__=='__main__':
    try:main()
    except (ValueError,OSError,struct.error) as error:
        print('FAIL: '+str(error),file=sys.stderr,flush=True);sys.exit(1)
