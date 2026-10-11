#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Independent verification using raw offsets and byte literals."""
from pathlib import Path
import hashlib,json,sys
base,output=map(Path,sys.argv[1:]);a=base.read_bytes();b=output.read_bytes()
assert hashlib.sha256(a).hexdigest()=='f6b5205fc40e635305445bb19dd1a41d12f2ee4c64b7284ccd432868ef0c5898'
assert len(a)==len(b)==3099064
expected=bytearray(a)
# Byte literals intentionally independent of the builder's word assembly.
expected[0x29c605:0x29c609]=bytes.fromhex('80 04 40 0b')
expected[0x274255:0x274275]=bytes.fromhex('05 00 a3 90 f0 00 63 38 03 00 60 10 21 10 00 00 93 7b 41 0f 04 00 a4 90 6e a5 40 0b 00 00 00 00')
expected[0x298909]=0x21 # 0x273055 + 0x258B4: low version-immediate byte
expected[0x2c4c19]=0x21 # 0x273055 + 0x51BC4
expected[0x27304e]=1
assert b==expected
assert b[:0x273049]==a[:0x273049]
assert hashlib.sha256(b[0x29c609:0x29c60d]).hexdigest()=='7aab477050ea5f44b8635ade6db046d97c08e90267a2b24d189c783e35fdce93'
assert b[0x27304b:0x273050]==bytes([2,2,2,1,0])
assert b[3:8]==bytes([2,2,2,0,1]) and b[-3:]==b'00\xf7'
for lo,n,trailer in [(13,986520,0xf0da5),(0xf0db3,1581716,0x273047)]:
 assert b[lo:lo+n]==a[lo:lo+n]
 value=sum(int.from_bytes(b[x:x+2],'little') for x in range(lo,lo+n,2))&65535
 assert value==int.from_bytes(b[trailer:trailer+2],'little')
pic_sha=hashlib.sha256(b[0x273055:0x2f49b5]).hexdigest()
transfer=json.loads(Path('next_evidence/pic_transfer_result.json').read_text())
assert pic_sha==transfer['candidate_pic_sha256']
result={'combined_sha256':hashlib.sha256(b).hexdigest(),'exact_expected_bytes':True,'changed_bytes':sum(x!=y for x,y in zip(a,b)),
 'qnx_and_fpga_identical':True,'pic_equals_transfer_tested_candidate':True,'all_record_sizes_and_trailers_preserved':True}
output.with_name('independent_verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
