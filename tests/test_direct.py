# SPDX-License-Identifier: GPL-2.0-or-later
"""Synthetic direct-builder failures; no manufacturer firmware or toolchain."""
import hashlib
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch

DIRECT=Path(__file__).resolve().parents[1]/'firmware_builder/direct'
sys.path.insert(0,str(DIRECT))
from core import Component,Write,sha
from build import write_new
from elf_objects import Object,link
from mips import encode
from objects import Objects
import px_container

class DirectContainerTests(unittest.TestCase):
    def test_direct_parser_round_trip_truncation_and_checksum(self):
        from test_container import fixture
        data=fixture();self.assertEqual(px_container.serialize(px_container.parse(data)),data)
        for size in range(len(data)):
            with self.subTest(size=size),self.assertRaises(ValueError):px_container.parse(data[:size])
        corrupt=bytearray(data);corrupt[13]^=1
        with self.assertRaisesRegex(ValueError,'checksum mismatch'):px_container.parse(bytes(corrupt))

class OwnershipTests(unittest.TestCase):
    def test_one_pass_and_conflict_rejection(self):
        c=Component('fixture',b'abc',5)
        c.add(Write(1,b'X',sha(b'b'),'hook','synthetic source'))
        c.add(Write(3,b'yz',sha(b''),'extension','synthetic source'))
        self.assertEqual(c.render(),b'aXcyz')
        with self.assertRaisesRegex(ValueError,'overlapping'):c.add(Write(1,b'Y',sha(b'b'),'conflict','source'))

    def test_guard_bounds_and_unowned_extension_rejected(self):
        c=Component('fixture',b'abc',5)
        with self.assertRaisesRegex(ValueError,'guard failed'):c.add(Write(0,b'X',sha(b'z'),'hook','source'))
        with self.assertRaisesRegex(ValueError,'bounds'):c.add(Write(5,b'X',sha(b''),'hook','source'))
        c.add(Write(4,b'X',sha(b''),'extension','source'))
        with self.assertRaisesRegex(ValueError,'unowned extension'):c.render()

class ObjectTests(unittest.TestCase):
    def test_bad_elf_rejected(self):
        for data in (b'',bytes(64),b'\x7fELF\x02\x01'):
            with self.subTest(size=len(data)),self.assertRaises(ValueError):Object('bad',data)

    def test_mips_targets_and_immediates_rejected(self):
        for row in [('j',0x80000000),('j',0x9d000003),('beq','v0','zero',0x9d100000),('addiu','v0','zero',32768)]:
            with self.subTest(row=row),self.assertRaises(ValueError):encode(0x9d000000,row)

    def test_unresolved_and_unsupported_relocation(self):
        # Hand-authored minimal relocatable object: no compiler output or firmware.
        names=b'\0.text\0.symtab\0.strtab\0.rela.text\0.shstrtab\0'
        sections=[bytes(64)]
        data=bytearray(64)
        data[:6]=b'\x7fELF\x02\x01';struct.pack_into('<HH',data,16,1,62)
        def section(name,kind,flags,payload,link=0,info=0,alignment=1,entsize=0):
            offset=len(data);data.extend(payload)
            sections.append(struct.pack('<IIQQQQIIQQ',names.index(name.encode()+b'\0'),kind,flags,0,offset,len(payload),link,info,alignment,entsize))
        section('.text',1,6,bytes(4))
        section('.symtab',2,0,bytes(24)+struct.pack('<IBBHQQ',1,0x10,0,0,0,0),3,0,8,24)
        section('.strtab',3,0,b'\0missing\0')
        section('.rela.text',4,0,struct.pack('<QQq',0,(1<<32)|2,0),2,1,8,24)
        section('.shstrtab',3,0,names)
        shoff=len(data);data.extend(b''.join(sections));struct.pack_into('<Q',data,40,shoff);struct.pack_into('<HHH',data,58,64,len(sections),5)
        with self.assertRaisesRegex(ValueError,'Unresolved'):link([Object('fixture',bytes(data))],0x1000,0x2000,{})
        relocation=struct.unpack_from('<Q',data,shoff+4*64+24)[0]
        struct.pack_into('<Q',data,relocation+8,(1<<32)|255)
        with self.assertRaisesRegex(ValueError,'Unsupported'):link([Object('fixture',bytes(data))],0x1000,0x2000,{'missing':0x3000})

class CacheTests(unittest.TestCase):
    def test_restoration_and_tampering_rejected(self):
        factory=b'ab';source=b'authored';blob=b'\0b';ident=sha(blob)
        manifest={'entries':{'fixture':{'kind':'object','returncode':0,'inputs':[{'name':'source.c','sha256':sha(source)}],
            'outputs':[{'sha256':ident,'size':2,'restored_sha256':sha(factory),
                        'firmware_spans':[{'offset':0,'source_offset':0,'size':1,'sha256':sha(b'a')}]}]}}}
        raw=json.dumps(manifest).encode()
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'blobs').mkdir();(root/'manifest.json').write_bytes(raw);path=root/'blobs'/ident;path.write_bytes(blob)
            with patch('objects.FACTORY_SHA256',sha(factory)),patch('objects.MANIFEST_SHA256',sha(raw)):
                cache=Objects(root,factory)
                self.assertEqual(cache.restore('fixture',{'source.c':source}),[factory])
                with self.assertRaisesRegex(ValueError,'hash mismatch'):cache.restore('fixture',{'source.c':b'changed'})
                with self.assertRaisesRegex(ValueError,'source/include set'):cache.restore('fixture',{})
                path.write_bytes(b'xb')
                with self.assertRaisesRegex(ValueError,'Cached object identity'):cache.restore('fixture',{'source.c':source})
                (root/'manifest.json').write_bytes(raw+b'\n')
                with self.assertRaisesRegex(ValueError,'manifest identity'):Objects(root,factory)
                with self.assertRaisesRegex(ValueError,'Factory identity'):Objects(root,b'wrong')

class OutputTests(unittest.TestCase):
    def test_atomic_no_replace_and_failure_cleanup(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);output=root/'final.bin';write_new(output,b'validated')
            with self.assertRaises(FileExistsError):write_new(output,b'replacement')
            self.assertEqual(output.read_bytes(),b'validated')
            with patch('build.os.link',side_effect=OSError('publish failure')):
                with self.assertRaises(OSError):write_new(root/'failed.bin',b'data')
            self.assertEqual([p.name for p in root.iterdir()],['final.bin'])

if __name__=='__main__':unittest.main()
