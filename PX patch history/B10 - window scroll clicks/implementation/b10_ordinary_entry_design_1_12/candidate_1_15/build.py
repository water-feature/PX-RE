from pathlib import Path
import struct as S,hashlib,json,subprocess
O=Path(__file__).resolve().parent
BASE=O.parents[1]/'b7_lfo_center_investigation/implementation_1_12'
def sha(b):return hashlib.sha256(b).hexdigest()
def elf(b):
 shoff=S.unpack_from('<Q',b,40)[0];n,strings=S.unpack_from('<HH',b,60)
 sec=[S.unpack_from('<II4QII2Q',b,shoff+64*i) for i in range(n)]
 st=sec[strings];names=b[st[4]:st[4]+st[5]]
 return sec,[names[x[0]:].split(b'\0')[0].decode() for x in sec]
def main():
 old=(BASE/'voice_2.2.2.1.12_qnx.elf').read_bytes()
 assert sha(old)=='b411fc94d17683f49d62184e3c794f6e4eea72e7d6ea58edd1b78ff706377ced'
 for src in ['patch.c','hooks.s']:
  subprocess.run(['clang','-target','x86_64-unknown-linux-gnu','-Oz','-ffreestanding','-fPIC','-fno-stack-protector','-fno-strict-aliasing','-ffp-contract=off','-fasynchronous-unwind-tables','-c',str(O/src),'-o',str(O/(src.split('.')[0]+'.o'))],check=True)
 objects=[];text=0x1012c0;frame=0x1025a4
 symbols=dict(image_anchor=text,read_resume=0x3f848,update_resume=0x41876,close_resume=0x42518,open_resume=0x42cd6,original_fade=0x3f2f0,local_read=0x3f080,allocate=0x46100)
 for filename in ['patch.o','hooks.o']:
  b=(O/filename).read_bytes();sec,names=elf(b);locations={}
  for i,n in enumerate(names):
   if n=='.text':text=(text+15)&~15;locations[i]=text;text+=sec[i][5]
   elif n=='.eh_frame':frame=(frame+3)&~3;locations[i]=frame;frame+=sec[i][5]
  symsec=sec[names.index('.symtab')];st=sec[symsec[6]];strings=b[st[4]:st[4]+st[5]];syms=[]
  for j in range(0,symsec[5],24):
   no,info,other,idx,value,size=S.unpack_from('<IBBHQQ',b,symsec[4]+j);name=strings[no:].split(b'\0')[0].decode();syms.append((name,idx,value))
   if idx in locations and name:symbols[name]=locations[idx]+value
  objects.append((b,sec,names,locations,syms))
 assert text<=0x102000 and frame<=0x103000
 out=bytearray(old);ranges=[]
 def put(off,value,why):
  assert off+len(value)<=len(out);out[off:off+len(value)]=value;ranges.append([off,off+len(value),why])
 newfdes=[]
 for b,sec,names,loc,syms in objects:
  data={i:bytearray(b[sec[i][4]:sec[i][4]+sec[i][5]]) for i in loc}
  for rs in sec:
   if rs[1]!=4 or rs[7] not in loc:continue
   target=rs[7]
   for j in range(0,rs[5],24):
    off,info,add=S.unpack_from('<QQq',b,rs[4]+j);typ=info&0xffffffff;name,idx,val=syms[info>>32]
    address=loc[idx]+val if idx in loc else symbols[name]
    assert typ in (2,4),(name,typ)
    S.pack_into('<i',data[target],off,address+add-(loc[target]+off))
  for i,payload in data.items():
   assert old[loc[i]:loc[i]+len(payload)]==bytes(len(payload));put(loc[i],payload,names[i])
   if names[i]=='.eh_frame':
    off=0
    while off<len(payload):
     length,cie=S.unpack_from('<II',payload,off)
     if not length:break
     if cie:
      pc=loc[i]+off+8+S.unpack_from('<i',payload,off+8)[0];newfdes.append((pc,loc[i]+off))
     off+=length+4
 def hook(off,size,name,expected):
  assert old[off:off+size].hex()==expected
  put(off,b'\xe9'+S.pack('<i',symbols[name]-off-5)+b'\x90'*(size-5),name)
 hook(0x3f840,8,'entry_read','4157415641554154')
 hook(0x41870,6,'entry_update','81fe00100000')
 hook(0x42510,8,'close_hook','4883bf8800000000')
 hook(0x42cd1,5,'open_hook','41c6470800')
 calls={0x3f01d:'entry_allocate',0x40bc7:'reverse_read_hook',**{p:'fade_hook' for p in [0x4056f,0x40849,0x40e5d,0x40f79,0x40ad0,0x40c27,0x3fd79,0x41390]}}
 for off,name in calls.items():
  target=0x46100 if name=='entry_allocate' else 0x3f080 if name=='reverse_read_hook' else 0x3f2f0
  assert old[off:off+5]==b'\xe8'+S.pack('<i',target-off-5)
  put(off,b'\xe8'+S.pack('<i',symbols[name]-off-5),name)
 h=0x103000;assert old[h:h+4]==bytes([1,0x1b,3,0x3b])
 count=S.unpack_from('<I',old,h+8)[0];assert count==899
 inherited=[tuple(h+v for v in S.unpack_from('<ii',old,h+12+j*8)) for j in range(count)]
 pairs=sorted(inherited+newfdes);header=old[h:h+8]+S.pack('<I',len(pairs))+b''.join(S.pack('<ii',pc-h,f-h) for pc,f in pairs)
 put(h,header,'unwind index')
 phoff=S.unpack_from('<Q',old,32)[0]
 for i in range(S.unpack_from('<H',old,56)[0]):
  off=phoff+i*56
  if hashlib.sha256(S.pack('<I',S.unpack_from('<I',old,off)[0])).hexdigest()=='0fe51dced2745ee6eab34377ad3e64563eef82533a339cae1c75354d09fd1dd5':put(off+32,S.pack('<QQ',len(header),len(header)),'unwind sizes')
 sec,names=elf(old);shoff=S.unpack_from('<Q',old,40)[0]
 for name,end in [('.b15_text',text),('.b15_eh_frame',frame),('.eh_frame_hdr',h+len(header))]:
  i=names.index(name);put(shoff+64*i+32,S.pack('<Q',end-sec[i][3]),name+' size')
 assert old[0x1f4e3:0x1f4e7]==S.pack('<I',0x4013921c) and old[0x250ef]==12
 put(0x1f4e3,b'\x1f','revision .15');put(0x250ef,b'\x0f','updater .15')
 changed=[i for i,(a,b) in enumerate(zip(old,out)) if a!=b]
 assert all(any(lo<=i<hi for lo,hi,_ in ranges) for i in changed)
 target=O/'voice_2.2.2.1.15_qnx.elf';target.write_bytes(out)
 report=dict(status='EMITTED_NOT_YET_VALIDATED',baseline_sha256=sha(old),sha256=sha(out),symbols=symbols,text_end=text,frame_end=frame,new_FDEs=newfdes,inherited_FDEs=count,allowed_ranges=ranges,changed_bytes=len(changed),per_reader_bytes=16,additional_audio_buffers=0)
 (O/'emission.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
if __name__=='__main__':main()
