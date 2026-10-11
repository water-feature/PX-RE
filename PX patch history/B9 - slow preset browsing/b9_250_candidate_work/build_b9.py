"""Build only authorized minimal B9 on exact hardware-tested B6 .9.
Publication is separate and requires independent instruction/package validation.
"""
from pathlib import Path
import struct,hashlib,json
ROOT=Path(__file__).resolve().parent.parent;OUT=Path(__file__).resolve().parent
BASE=0x9d000000;REV=(2,2,2,1,2);NAME='PxUpdate_V2.2.2.1.2.bin'
PANEL=(0x9d02a3d0,0x9d02a808,0x9d02aabc,0x9d02bcc8,0x9d02dcf0,0x9d02e0c0)
sha=lambda b:hashlib.sha256(b).hexdigest()
REGS='zero at v0 v1 a0 a1 a2 a3 t0 t1 t2 t3 t4 t5 t6 t7 s0 s1 s2 s3 s4 s5 s6 s7 t8 t9 k0 k1 gp sp fp ra'.split();R=dict(zip(REGS,range(32)))
def records(b):
 assert b[0]==240 and b[-1]==247
 p=1;out=[]
 for typ in (1,2,3):
  h=b[p:p+12];assert h[:2]==bytes((typ,123)) and h[7]==122
  n=int.from_bytes(h[8:12],'big');out.append((p,p+12,p+12+n,h,b[p+12:p+12+n],b[p+12+n:p+14+n]));p+=n+14
 assert p==len(b)-1
 return out
# Small explicit assembler, independent decoder used by validate_instructions.py.
def asm(pc,row):
 op,*a=row
 if op=='nop':return 0
 if op=='lui':assert 0<=a[1]<=65535;return 15<<26|R[a[0]]<<16|a[1]
 if op in ('addu',):return R[a[1]]<<21|R[a[2]]<<16|R[a[0]]<<11|33
 if op in ('ori','addiu','lw'):
  if op=='lw':dst,im,src=a
  else:dst,src,im=a
  assert (0<=im<=65535) if op=='ori' else (-32768<=im<=32767)
  return {'ori':13,'addiu':9,'lw':35}[op]<<26|R[src]<<21|R[dst]<<16|(im&65535)
 if op=='beq':
  disp=(a[2]-pc-4)//4;assert a[2]%4==0 and -32768<=disp<=32767
  return 4<<26|R[a[0]]<<21|R[a[1]]<<16|(disp&65535)
 if op=='j':assert a[0]%4==0 and a[0]>>28==(pc+4)>>28;return 2<<26|((a[0]>>2)&0x3ffffff)
 raise AssertionError(row)

def build():
 assert not (ROOT/NAME).exists(),'Refuse to overwrite published revision'
 base=(ROOT/'PxUpdate_V2.2.2.0.9.bin').read_bytes()
 assert sha(base)=='438da40fee68dee6062f169e3ca9ed461bf31547f0c1f0a77279a3bc264e6e5d'
 rr=records(base);pic0=rr[2][4];app0=rr[0][4]
 assert pic0==(ROOT/'b6_candidate_work/pic_2.2.2.0.9.bin').read_bytes()
 assert app0==(ROOT/'b6_candidate_work/voice_2.2.2.0.9_qnx.elf').read_bytes()
 # Exact allowlist proof: caller JAL + a3=0 delay; all six supply both-layer mode.
 for ret in PANEL:
  assert struct.unpack_from('<II',pic0,ret-BASE-8)==(3<<26|((0x9d0234cc>>2)&0x3ffffff),0x00003821)
  assert 0x24030002 in struct.unpack_from('<6I',pic0,ret-BASE-24)
 assert struct.unpack_from('<I',pic0,0x234d0)[0]==0xafbf0044
 assert struct.unpack_from('<II',pic0,0x23550)==(0x02708021,0x240201f4)
 assert pic0[0xd84:0xe00]==b'\xff'*124
 helper=0x9d000d84
 rows=[('addu','s0','s3','s0'),('j',helper+20),('addiu','t3','zero',0),('addiu','t3','zero',1),('addiu','v0','zero',500),('lw','t1',0x44,'sp'),('lui','t0',0x9d02)]
 skip=helper+(7+13+2)*4
 for ret in PANEL:rows += [('ori','t2','t0',ret&65535),('beq','t1','t2',skip)]
 rows += [('nop',),('j',0x9d023558),('nop',),('beq','t3','zero',helper+26*4),('nop',),('j',0x9d023558),('addiu','v0','zero',250),('j',0x9d02355c),('nop',)]
 assert len(rows)==28 and helper+len(rows)*4==0x9d000df4
 words={helper+i*4:asm(helper+i*4,row) for i,row in enumerate(rows)}
 pic=bytearray(pic0);manifest={}
 def put(addr,word,reason):
  off=addr-BASE;old=struct.unpack_from('<I',pic0,off)[0];struct.pack_into('<I',pic,off,word)
  manifest[f'{addr:08x}']={'old_word':f'{old:08x}','new_word':f'{word:08x}','old_bytes':struct.pack('<I',old).hex(),'new_bytes':struct.pack('<I',word).hex(),'reason':reason}
 for addr,word in words.items():put(addr,word,'B9 positive panel countdown no-reset helper')
 put(0x9d023550,asm(0x9d023550,('j',helper)),'B9 positive path hook; existing 500 delay slot preserved')
 assert struct.unpack_from('<II',pic0,0x235e4)==(0x0b408d55,0x02708021)
 put(0x9d0235e4,asm(0x9d0235e4,('j',helper+12)),'Immediate reload classification; pointer delay preserved')
 for addr in (0x9d0258b4,0x9d051bc4):
  assert struct.unpack_from('<I',pic0,addr-BASE)[0]==0x24842220
  put(addr,0x24842221,'revision first four fields 2.2.2.1')
 for addr in (0x9d001394,0x9d0013a0):
  assert struct.unpack_from('<I',pic0,addr-BASE)[0]==0x24840009
  put(addr,0x24840002,'revision fifth field 1; existing B6 report thunk retained')
 # Existing M formatter exposes first three fields only: retain M:2.2.2.
 assert struct.unpack_from('<I',pic,0x52fec)[0]==0x24020002
 app=bytearray(app0);qchanges=[]
 for off,old,new in [(0x1f4e3,9,0x12),(0x250e2,0,1),(0x250ef,9,2)]:
  assert app0[off]==old;app[off]=new;qchanges.append({'offset':hex(off),'old':old,'new':new,'reason':'version report/updater equality'})
 package=bytearray(base)
 for i,payload in [(0,app),(2,pic)]:
  h,a,z,*_=rr[i];package[h+2:h+7]=bytes(REV);package[a:z]=payload
  if i==0:package[z:z+2]=struct.pack('<H',sum(struct.unpack('<'+'H'*(len(app)//2),app))&65535)
 assert len(pic)==len(pic0)==530784 and len(app)==len(app0)==1039304 and len(package)==len(base)==3151848
 assert package[rr[1][0]:rr[1][2]+2]==base[rr[1][0]:rr[1][2]+2]
 (OUT/'pic_2.2.2.1.2.bin').write_bytes(pic);(OUT/'voice_2.2.2.1.2_qnx.elf').write_bytes(app)
 (OUT/'package_pending_validation.bin').write_bytes(package)
 (OUT/'helper_assembly_input.json').write_text(json.dumps({'base':hex(helper),'rows':rows,'allowlist':list(map(hex,PANEL))},indent=2)+'\n')
 report={'baseline_package_sha256':sha(base),'baseline_PIC_sha256':sha(pic0),'baseline_QNX_sha256':sha(app0),'candidate_package_sha256':sha(package),'candidate_PIC_sha256':sha(pic),'candidate_QNX_sha256':sha(app),'revision':REV,'filename':NAME,'helper':[hex(helper),hex(helper+len(rows)*4)],'helper_instructions':28,'helper_bytes':112,'hook':'0x9d023550','behavior_code_bytes':120,'PIC':manifest,'QNX':qchanges,'FPGA_complete_record_unchanged':True,'M_formatter_unchanged':'M:2.2.2','publication':'pending independent validation'}
 (OUT/'b9_patch_manifest.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k not in ('PIC','QNX')},indent=2))
if __name__=='__main__':build()
