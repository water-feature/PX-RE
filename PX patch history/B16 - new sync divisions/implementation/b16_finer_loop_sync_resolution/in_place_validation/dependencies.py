from pathlib import Path
import json,struct
D=Path(__file__).resolve().parent
ns={'__file__':str(D/'preflight.py')};s=(D/'preflight.py').read_text();exec(s[:s.index('# Combined display execution')],ns)
CPU=ns['CPU'];fresh=ns['fresh'];image=ns['image'];BASE=ns['BASE'];words=ns['words'];data=ns['data']
# Execute exact preset range-validation loop, including both branch-likely slots.
recall=0
for raw in range(256):
 c=fresh()
 for ident in (0x1d,0x5e):
  for bank in (0,1):c.write(0x8000046c+2*(ident+bank*0x6b7),2,raw)
 c.run(BASE+0x4d6d4,BASE+0x4d72c)
 for ident in (0x1d,0x5e):
  for bank in (0,1):assert c.read(0x8000046c+2*(ident+bank*0x6b7),2)==(raw if raw<=17 else 0)
 recall+=1
# Execute actual transport packer; intercept unchanged I/O boundary, not hardware.
transport=0
for ident in (0x1d,0x5e):
 for raw in range(18):
  for layer in (0,1,2):
   c=fresh();ret=c.reg[31];sp=c.reg[29];saved=c.reg[16];c.reg[4:6]=[layer,ident];sent=[]
   for bank in (0,1):c.write(0x8000046c+2*(ident+bank*0x6b7),2,raw)
   def hook(c,pc):
    if pc==BASE+0x75c1c:sent.append(c.reg[4]);return True
    return False
   c.run(BASE+0x4d324,ret,hook=hook)
   want=([ident<<16|raw] if layer in (0,2) else [])+([(ident+0x800)<<16|raw] if layer in (1,2) else [])
   assert sent==want and c.reg[29]==sp and c.reg[16]==saved
   transport+=1
# Targeted incoming direct branch/jump references and literal pointers (all byte alignments).
spans=[(BASE+0x4fa74,BASE+0x4fb10),(BASE+0x60278,BASE+0x60298),(BASE+0x62074,BASE+0x620b4)]
def inside(a):return any(lo<=a<hi for lo,hi in spans)
external=[];internal=[]
for off in range(0,len(image)-3,4):
 w=struct.unpack_from('<I',image,off)[0];op=w>>26;pc=BASE+off;target=None
 if op in (2,3):target=((pc+4)&0xf0000000)|((w&0x3ffffff)<<2)
 elif op in (1,4,5,6,7,20,21,22,23):
  imm=w&65535;target=pc+4+4*(imm if imm<32768 else imm-65536)
 if target is not None and inside(target):(internal if inside(pc) else external).append([hex(pc),hex(target),hex(w)])
pointers=[]
for off in range(len(image)-3):
 v=struct.unpack_from('<I',image,off)[0]
 if inside(v):pointers.append([hex(BASE+off),hex(v)])
print('external instruction candidates',external);print('literal candidates',pointers)
assert external==[['0x9d0006d0','0x9d04fa74','0xb413e9d']]
assert pointers==[['0x9d05f8b8','0x9d060278'],['0x9d05f9bc','0x9d060278']]
# Direct LUI+low-address constructions, including alias physical/kseg1 targets.
constructed=[]
for off in range(0,len(image)-4,4):
 w=struct.unpack_from('<I',image,off)[0]
 if w>>26!=15:continue
 reg=w>>16&31;upper=(w&65535)<<16
 for dist in range(4,36,4):
  if off+dist+4>len(image):break
  z=struct.unpack_from('<I',image,off+dist)[0];op=z>>26;rs=z>>21&31;rt=z>>16&31;imm=z&65535
  if rs==reg and op in (9,13):
   addr=((upper+(imm if imm<32768 else imm-65536)) if op==9 else upper|imm)&0xffffffff
   canonical=(addr&0x1fffffff)|0x80000000
   if inside(canonical):constructed.append([hex(BASE+off),hex(BASE+off+dist),hex(addr)])
  # Stop on instructions writing tracked register (usual instruction forms).
  writes=(rt if op in (8,9,10,11,12,13,14,15,32,33,35,36,37) else (z>>11&31 if op==0 and z&63 not in (8,9) else -1))
  if writes==reg:break
assert constructed==[['0x9d06027c','0x9d060280','0x9d062074']],constructed
result={'status':'PASS','preset_actual_validator_u8_cases':recall,'transport_actual_packer_cases':transport,'external_direct_entries':external,'literal_references_all_alignments':pointers,'constructed_addresses_bounded_lookahead':constructed,'limits':['Computed/external consumers cannot be exhaustively excluded by application-image references','Transport I/O boundary mocked; preset physical save/read and external MIDI hardware not executed','Display lookup requires validated raw 0..17; corrupt RAM or unchecked external writer remains out of contract','Recovery independence NOT VERIFIED']}
(D/'dependency_results.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
