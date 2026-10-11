from pathlib import Path
import hashlib,struct,json,sys
sha=lambda d:hashlib.sha256(d).hexdigest()
def parse(d):
 assert d[0]==0xf0 and d[-1]==0xf7
 o=1;r=[]
 for t in (1,2,3):
  assert d[o]==t and d[o+1]==0x7b and d[o+7]==0x7a
  n=int.from_bytes(d[o+8:o+12],'big');end=o+14+n
  assert end<len(d)
  r.append((o,o+12,n,end));o=end
 assert o==len(d)-1
 return r
q=Path(sys.argv[1]).read_bytes();s=Path(sys.argv[2]).read_bytes();out=Path(sys.argv[3])
assert sha(q)=='2cd57a89d0873ad7e81c410748e3725de6a336494f4c6af1e0110aba85b15c95'
assert sha(s)=='bbc3c2ad26bef7310fc15cac8edee22a1792d8ced3788f7080acccc047304857'
qr=parse(q);sr=parse(s);c=bytearray(q);ph,pp,pn,pe=qr[2];sh,sp,sn,se=sr[2]
assert pn==sn==530784
assert sha(s[sp:sp+sn])=='2f746346fa1e592795fd243a9866a8019e69c2d97ab3d674204bb7f5022ef0cc'
c[ph:pe]=s[sh:se]
c[7]=7
for off,old in [(13+0x1f4e3,2),(13+0x250ef,2)]:
 assert c[off]==old;c[off]=7
# PIC update revision 2.2.3.0.0, both actual report paths, and M display.
c[ph+2:ph+7]=bytes([2,2,3,0,0])
for off in [0x258b4,0x51bc4]:
 assert hashlib.sha256(struct.pack('<I',struct.unpack_from('<I',c,pp+off)[0])).hexdigest()=='99d4d638528ade1cc25fc4c47a71456f6271bafd05cfcc9871ac2258b0f65d8d'
 struct.pack_into('<I',c,pp+off,0x24842230)
assert hashlib.sha256(struct.pack('<I',struct.unpack_from('<I',c,pp+0x52fec)[0])).hexdigest()=='1f72b3d3bc7d3086c957c55ac17ec67f1328fb167c06edde5e436698631746de'
struct.pack_into('<I',c,pp+0x52fec,0x24020003)
a,ap,an,ae=qr[0];cs=(sum(c[ap:ap+an:2])+256*sum(c[ap+1:ap+an:2]))&65535
c[ap+an:ae]=cs.to_bytes(2,'little')
assert not out.exists();out.write_bytes(c)
# Independently reconstruct exact permitted delta from latest QNX input.
allowed={7,13+0x1f4e3,13+0x250ef,ap+an,ap+an+1}|set(range(ph,pe))
assert all(i in allowed for i,(x,y) in enumerate(zip(q,c)) if x!=y)
assert len(c)==len(q) and parse(c)==qr
elfold=q[ap:ap+an];elf=c[ap:ap+an]
assert [i for i,(x,y) in enumerate(zip(elfold,elf)) if x!=y]==[0x1f4e3,0x250ef]
assert sha(elfold)=='85b76594924f1a8b7deffec1d81f79feb848edf6c631d0eb2b6c24f49aa393f1'
assert c[qr[1][0]:qr[1][3]]==q[qr[1][0]:qr[1][3]]
picold=s[sp:sp+sn];pic=c[pp:pp+pn]
assert [i for i,(x,y) in enumerate(zip(picold,pic)) if x!=y]==[0x258b4,0x51bc4,0x52fec]
assert c[pe-2:pe]==b'00'
assert cs==int.from_bytes(c[ae-2:ae],'little')
m={'sha256':sha(c),'size':len(c),'app_checksum':hex(cs),'qnx_source':sha(q),'pic_source':sha(s),'pic_sha256':sha(pic),'qnx_payload_sha256':sha(elf),'application_revision':[2,2,2,0,7],'pic_revision':[2,2,3,0,0],'screen':'M: 2.2.3, DSP: 2.2.2.0.7','qnx_record':qr[0],'fpga_record':qr[1],'pic_record':qr[2],'structural_validation':'PASS','combined_hardware_tested':False}
out.with_suffix('.json').write_text(json.dumps(m,indent=2)+'\n');print(json.dumps(m,indent=2))
