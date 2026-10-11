"""Execute actual candidate x86 gate bytes using a bounded instruction decoder.
No symbolic gate overlays. Version formatter arguments verified from PIC words.
"""
import hashlib
from pathlib import Path
import struct,json
P=Path(__file__).resolve().parent
app=(P/'voice_2.2.2.0.8_qnx.elf').read_bytes();pic=(P/'pic_2.2.2.0.8.bin').read_bytes()
def gate(kind,incoming,installed=None):
 pc=0x24F21 if kind=='app' else 0x24A3F
 regs={'eax':0,'ecx':0,'edx':0};zf=False;writes={}
 for step in range(100):
  if pc==(0x24F39 if kind=='app' else 0x24A5D): return writes
  b=app[pc:pc+12]
  if b[:2]==b'\x80\xbd':
   off=struct.unpack_from('<i',b,2)[0]+0x590;zf=incoming[off]==b[6];pc+=7
  elif b[:2] in (b'\x0f\x84',b'\x0f\x85'):
   take=zf if b[1]==0x84 else not zf
   pc=pc+6+(struct.unpack_from('<i',b,2)[0] if take else 0)
  elif b[0]==0xe9: pc+=5+struct.unpack_from('<i',b,1)[0]
  elif b[:3]==b'\x41\xc7\x87':
   off,val=struct.unpack_from('<II',b,3);writes[off]=val;pc+=11
  elif b[:3]==b'\x41\x8b\x87':
   off=struct.unpack_from('<I',b,3)[0]
   assert off in (0x374C,0x3750)
   regs['eax']=sum(installed[i]<<(12-4*i) for i in range(4)) if off==0x374C else installed[4];pc+=7
  elif b[:3] in (b'\x0f\xb6\x8d',b'\x0f\xb6\x95'):
   off=struct.unpack_from('<i',b,3)[0]+0x590
   regs['ecx' if b[2]==0x8D else 'edx']=incoming[off];pc+=7
  elif b[:2]==b'\x89\xc2': regs['edx']=regs['eax'];pc+=2
  elif b[:2]==b'\xc1\xea': regs['edx']>>=b[2];pc+=3
  elif b[:2] in (b'\x83\xe2',b'\x83\xe0'):
   regs['edx' if b[1]==0xe2 else 'eax']&=b[2];pc+=3
  elif b[:2] in (b'\x39\xd1',b'\x39\xc2'):
   zf=regs['ecx']==regs['edx'] if b[1]==0xd1 else regs['edx']==regs['eax'];pc+=2
  else: raise AssertionError((hex(pc),b.hex()))
 raise AssertionError('gate did not terminate')
app_cases=[]
for incoming in ([2,2,2,0,x] for x in (0,1,2,7,8)):
 writes=gate('app',incoming);skip=not bool(writes.get(0x373C,0));assert skip==(incoming==[2,2,2,0,8])
 app_cases.append({'incoming':incoming,'skip':skip})
pic_cases=[]
for installed in ([2,2,2,0,0],[2,2,3,0,0],[2,2,4,0,0]):
 writes=gate('pic',[2,2,4,0,0],installed);skip=bool(writes.get(0x3744,0));assert skip==(installed==[2,2,4,0,0])
 pic_cases.append({'installed':installed,'incoming':[2,2,4,0,0],'skip':skip})
# Individually mutate every component: gate must compare all five.
for i in range(5):
 incoming=[2,2,4,0,0];incoming[i]^=1
 assert not gate('pic',incoming,[2,2,4,0,0]).get(0x3744,0)
assert hashlib.sha256(app[0x1F4DD:0x1F4E3]).hexdigest()=='6818940f9775e42f5d7406aac6317f88908778a6c59027cb66420fbf6ddcd3bd'
reply=struct.unpack_from('<I',app,0x1F4E3)[0];assert reply==0x40139208
# Verify actual formatter sources/argument layout, retaining exact .7 code
# everywhere except M minor argument. DSP fields are packed in the reply.
words=lambda off,n:struct.unpack_from('<'+'I'*n,pic,off)
assert words(0x52FE4,5)==(0x24060002,0x24070002,0x24020004,0x0F42049F,0xAFA20010)
packed=reply&65535
dsp=[packed>>14,(packed>>11)&7,(packed>>8)&7,(packed>>4)&15,packed&15]
assert dsp==[2,2,2,0,8]
result={'status':'PASS','application_gate_decoded_cases':app_cases,'PIC_gate_decoded_cases':pic_cases,'all_five_PIC_components_compared':True,'DSP_actual_reply':hex(reply),'screen_arguments':'M: 2.2.4, DSP: 2.2.2.0.8','historical_dot7':'Exact .7 display/report/header encode M 2.2.3. Historical hardware M 2.2.2 indicates this PIC was not running; precise installation cause requires target readback.'}
(P/'b7_version_validation_results.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
