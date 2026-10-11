from pathlib import Path
import hashlib,json
source=Path(__file__).with_name('baseline.bin');b=source.read_bytes()
assert hashlib.sha256(b).hexdigest()=='d2775bd0e017e4442ce7d5bbc7d089022a1cf8c02714d89427462938e934d166'
c=bytearray(b)
for off,old,new in [(7,1,3),(13+0x250ef,1,3),(13+0x1f4e3,0,3)]:
 assert c[off]==old;c[off]=new
assert b[13+0x1f4dd:13+0x1f4e7]==bytes.fromhex('c78540f9ffff00921340')
assert b[13+0x250e9:13+0x250f0]==bytes.fromhex('80bd74faffff01')
checksum=sum(int.from_bytes(c[i:i+2],'little') for i in range(13,13+986520,2))&65535
assert checksum==0xf64b;c[0xf0da5:0xf0da7]=checksum.to_bytes(2,'little')
changes=[i for i,(x,y) in enumerate(zip(b,c)) if x!=y]
assert changes==[7,13+0x1f4e3,13+0x250ef,0xf0da6]
assert c[0xf0da7:]==b[0xf0da7:] and len(c)==len(b)
Path(__file__).with_name('voice_sysex_2.2.2.0.3.bin').write_bytes(c)
manifest={'file_name':'voice_sysex_2.2.2.0.3.bin','sha256':hashlib.sha256(c).hexdigest(),'file_bytes':len(c),'baseline_sha256':hashlib.sha256(b).hexdigest(),'application_header_and_comparison':[2,2,2,0,3],'screen_DSP_version':[2,2,2,0,3],'screen_message':'0x40139203','pic_version':[2,2,2,1,0],'app_checksum':hex(checksum),'changes':[{ 'offset':hex(i),'old':b[i],'new':c[i]} for i in changes],'hardware_tested':False}
Path(__file__).with_name('manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');print(json.dumps(manifest,indent=2))
