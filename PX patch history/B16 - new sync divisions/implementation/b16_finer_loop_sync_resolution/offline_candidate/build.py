"""B16 offline emission from pinned .2.0 B11b sources; packaging is separate."""
from pathlib import Path
import struct,hashlib,json,subprocess
from mips_tools import listing
D=Path(__file__).resolve().parent;R=D.parents[1];BASE=0x9d000000
sha=lambda b:hashlib.sha256(b).hexdigest()
PIC=R/'b11b_implementation_2_2_2_2_0/pic_2.2.2.2.0_B11b.bin'
QNX=R/'b11b_implementation_2_2_2_2_0/voice_2.2.2.2.0_B11b_qnx.elf'
PKG=R/'PxUpdate_V2.2.2.2.0_B11b_real_instrument_on_Type_candidate.bin'
PICHASH='caa2a19d9a246aaeded2debd6b373490fee06f035d101373c24ec188456f6612'
QNXHASH='dcc77bdaff17f99288182ffb4927e85dcb76de597f8c5906a4078df8f5b14d16'
def put(name,b):
 with (D/name).open('xb') as f:f.write(b)
def elf(b):
 assert b[:6]==b'\x7fELF\x02\x01'
 so=struct.unpack_from('<Q',b,40)[0];ss,n,si=struct.unpack_from('<HHH',b,58)
 sec=[list(struct.unpack_from('<IIQQQQIIQQ',b,so+i*ss)) for i in range(n)]
 st=sec[si];names=b[st[4]:st[4]+st[5]]
 named={names[x[0]:].split(b'\0')[0].decode():(i,x) for i,x in enumerate(sec)}
 po=struct.unpack_from('<Q',b,32)[0];ps,pn=struct.unpack_from('<HH',b,54)
 ph=[list(struct.unpack_from('<IIQQQQQQ',b,po+i*ps)) for i in range(pn)]
 return named,sec,ph,so,ss,po,ps
class MIPS:
 def __init__(self):self.words=[];self.labels={};self.fix=[]
 def emit(self,w):self.words.append(w)
 def label(self,s):self.labels[s]=len(self.words)
 def li(self,t,n):self.emit(9<<26|t<<16|n&65535)
 def branch(self,op,s,t,label):self.fix.append((len(self.words),label));self.emit(op<<26|s<<21|t<<16)
 def j(self,op,target):self.emit(op<<26|target>>2&0x3ffffff)
 def addu(self,d,s,t=0):self.emit(s<<21|t<<16|d<<11|33)
 def subu(self,d,s,t):self.emit(s<<21|t<<16|d<<11|35)
 def addiu(self,t,s,n):self.emit(9<<26|s<<21|t<<16|n&65535)
 def sltiu(self,t,s,n):self.emit(11<<26|s<<21|t<<16|n&65535)
 def jr(self,s):self.emit(s<<21|8)
 def done(self):
  for i,l in self.fix:self.words[i]|=(self.labels[l]-i-1)&65535
  return b''.join(struct.pack('<I',w) for w in self.words)
def parsepkg(b):
 assert b[0]==240 and b[-1]==247;cur=1;out=[]
 for typ in (1,2,3):
  h=b[cur:cur+12];assert h[0]==typ and h[1]==123 and h[7]==122
  n=int.from_bytes(h[8:12],'big');start=cur+12;end=start+n
  out.append((h,b[start:end],b[end:end+2],cur,start,end));cur=end+2
 assert cur==len(b)-1
 return out
def changes(a,b):
 assert len(a)==len(b);return [i for i,(x,y) in enumerate(zip(a,b)) if x!=y]
def diff(name,a,b,base=0):
 z=changes(a,b);put(name,('offset\taddress\told\tnew\n'+''.join(f'{i:#x}\t{base+i:#x}\t{a[i]:02x}\t{b[i]:02x}\n' for i in z)).encode());return z

def main():
 pic=PIC.read_bytes();qnx=QNX.read_bytes();pkg=PKG.read_bytes()
 assert sha(pic)==PICHASH and sha(qnx)==QNXHASH
 rows=parsepkg(pkg);assert rows[0][1]==qnx and rows[2][1]==pic
 assert all(rows[i][0][2:7]==bytes([2,2,2,2,0]) for i in (0,2))
 # Risk-assessed 192-byte allocation, never represented as proven owned.
 assert pic[0xe00:0xec0]==b'\xff'*192
 m=MIPS();m.li(8,0x1d);m.branch(4,16,8,'sync');m.li(8,0x5e)
 m.branch(5,16,8,'old');m.emit(0)
 m.label('sync');m.sltiu(8,4,16);m.branch(5,8,0,'ranked');m.addiu(4,4,2)
 m.li(8,19);m.subu(4,8,4)
 m.label('ranked');m.addu(25,31);m.j(3,0x9d0816e0);m.emit(0)
 m.sltiu(3,2,2);m.branch(4,3,0,'done');m.addiu(2,2,-2)
 m.li(3,15);m.subu(2,3,2)
 m.label('done');m.jr(25);m.addu(31,25)
 m.label('old');m.j(2,0x9d0816e0);m.emit(0)
 code=m.done();assert len(code)==88
 out=bytearray(pic);out[0xe00:0xe64]=code+b'\0'*12
 out[0xe64:0xeac]=pic[0x62074:0x620b4]+struct.pack('<II',BASE+0xeac,BASE+0xeb6)
 out[0xeac:0xec0]=b'1/32 Step\0' + b'1/64 Step\0'
 writes={0x4fab4:(0x0f4205b8,(3<<26)|((BASE+0xe00)>>2&0x3ffffff)),0x6027c:(0x3c059d06,0x3c059d00),0x60280:(0x24a52074,0x24a50e64)}
 for o,(old,new) in writes.items():assert struct.unpack_from('<I',pic,o)[0]==old;struct.pack_into('<I',out,o,new)
 assert pic[0x4fab8:0x4fabc]==b'\0'*4
 for o in (0x475f4,0x47900):assert struct.unpack_from('<H',pic,o)[0]==15;struct.pack_into('<H',out,o,17)
 pa=set(range(0xe00,0xec0))|{p+j for p in writes for j in range(4)}|{0x475f4,0x47900}
 assert set(changes(pic,out))<=pa
 put('pic_2.2.2.2.0_B16_offline.bin',out);put('PIC_emission.txt',(listing(out,BASE+0xe00,BASE+0xe64)+'\n'+listing(out,BASE+0x4fab4,BASE+0x4fabc)+'\n').encode())
 # Assemble x86_64 ELF object, then resolve its actual PC-relative relocations.
 subprocess.run(['clang','-target','x86_64-unknown-linux-gnu','-c',str(D/'qnx_helper.s'),'-o',str(D/'qnx_helper.o')],check=True)
 obj=(D/'qnx_helper.o').read_bytes();ns,secs,_,_,_,_,_=elf(obj)
 tx=ns['.text'][1];helper=bytearray(obj[tx[4]:tx[4]+tx[5]])
 sy=ns['.symtab'][1];st=secs[sy[6]];strings=obj[st[4]:st[4]+st[5]];symbols=[]
 for p in range(sy[4],sy[4]+sy[5],sy[9]):
  n,info,other,si,val,size=struct.unpack_from('<IBBHQQ',obj,p);symbols.append((strings[n:].split(b'\0')[0].decode(),si,val))
 ends={n:v for n,si,v in symbols};assert ends['b16_code_end']==136 and len(helper)==156
 ext={'resume_old':0x1ae5c,'resume_positive':0x1ae64,'resume_duration':0x1aea6,'runtime_s0':0x2a5140};rels=[]
 re=ns['.rela.text'][1]
 for p in range(re[4],re[4]+re[5],re[9]):
  off,info,add=struct.unpack_from('<QQq',obj,p);idx=info>>32;typ=info&0xffffffff;name,si,val=symbols[idx]
  assert typ in (2,4)
  target=ext[name] if si==0 else 0x101700+val
  displacement=target+add-(0x101700+off);assert -2**31<=displacement<2**31
  struct.pack_into('<i',helper,off,displacement);rels.append({'offset':hex(off),'symbol':name,'type':typ,'target':hex(target),'addend':add})
 assert len(rels)==4 and {r['symbol'] for r in rels}==set(ext)
 qo=bytearray(qnx);assert qnx[0x101700:0x10179c]==b'\0'*156;qo[0x101700:0x10179c]=helper
 assert qnx[0x1ae55:0x1ae5c]==bytes.fromhex('f3410f2a4c2418')
 qo[0x1ae55:0x1ae5c]=b'\xe9'+struct.pack('<i',0x101700-(0x1ae55+5))+b'\x90\x90'
 # Append FDE contiguously, before the existing zero padding terminator.
 fde=0x10277c;cie=0x92fd8
 cfi=bytes.fromhex('0f03765806 1006027600 100f027678 100e027670 100d027668 100c027660 1003027650')
 body=struct.pack('<IiI',fde+4-cie,0x101700-(fde+8),136)+b'\0'+cfi
 body+=b'\0'*((-len(body)-4)%8);frame=struct.pack('<I',len(body))+body;assert len(frame)==56
 assert qnx[fde:fde+56]==b'\0'*56;qo[fde:fde+56]=frame
 assert struct.unpack_from('<I',qnx,0x103008)[0]==909
 struct.pack_into('<I',qo,0x103008,910)
 assert qnx[0x104c74:0x104c7c]==b'\0'*8
 struct.pack_into('<ii',qo,0x104c74,0x101700-0x103000,fde-0x103000)
 ns,secs,ph,so,ss,po,ps=elf(qnx);section_changes=[];qallowed=set(range(0x1ae55,0x1ae5c))|set(range(0x101700,0x10179c))|set(range(fde,fde+56))|set(range(0x103008,0x10300c))|set(range(0x104c74,0x104c7c))
 for name,newsize in (('.b15_text',0x179c),('.b15_eh_frame',0x7b4),('.eh_frame_hdr',0x1c7c)):
  i,s=ns[name];pos=so+i*ss+32;section_changes.append({'section':name,'old_size':s[5],'new_size':newsize,'size_field':hex(pos)});struct.pack_into('<Q',qo,pos,newsize);qallowed.update(range(pos,pos+8))
 ehph=[]
 for i,p in enumerate(ph):
  if p[0]==0x6474e550:
   assert p[2]==0x103000 and p[5]==p[6]==0x1c74
   for off in (32,40):struct.pack_into('<Q',qo,po+i*ps+off,0x1c7c);qallowed.update(range(po+i*ps+off,po+i*ps+off+8))
   ehph.append(i)
 assert len(ehph)==1
 assert set(changes(qnx,qo))<=qallowed
 put('voice_2.2.2.2.0_B16_offline_qnx.elf',qo);put('qnx_helper_linked.bin',helper)
 pd=diff('PIC_diff.tsv',pic,out,BASE);qd=diff('QNX_diff.tsv',qnx,qo,0x100000)
 report={'status':'EMITTED, REQUIRES VALIDATION','baseline_revision':'2.2.2.2.0','baseline_PIC_sha256':sha(pic),'baseline_QNX_sha256':sha(qnx),'baseline_package_sha256':sha(pkg),'PIC_sha256':sha(out),'QNX_sha256':sha(qo),'PIC_changed_bytes':len(pd),'QNX_changed_bytes':len(qd),'PIC_adapter_code_bytes':88,'PIC_adapter_reserved_bytes':100,'PIC_display_bytes':92,'PIC_allocation_bytes':192,'PIC_allocation_status':'risk-assessed, NOT formally proven owned','QNX_helper_code_bytes':136,'QNX_helper_constant_bytes':20,'QNX_FDE_bytes':56,'QNX_FDE_file':hex(fde),'QNX_added_index_bytes':8,'section_changes':section_changes,'relocations':rels,'PT_LOAD_unchanged':True,'outside_allowed_bytes_unchanged':True,'versions_unchanged':True,'hardware':'NOT VERIFIED','flashed':False}
 put('build_results.json',(json.dumps(report,indent=2)+'\n').encode());print(json.dumps(report,indent=2))
if __name__=='__main__':main()
