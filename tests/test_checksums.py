# SPDX-License-Identifier: GPL-2.0-or-later
"""Prevent routine guide edits from causing checksum CI failures."""
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from check_checksums import verify_inventory

class InventoryTests(unittest.TestCase):
    def test_guides_excluded_but_code_and_research_still_checked(self):
        import hashlib
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'nested').mkdir();code=root/'tool.py';code.write_text('code');research=root/'notes.md';research.write_text('evidence')
            names=['nested/README.md','nested/RECOVERY.md','contributing.md','FIRMWARE_MAP.md','BUILD_VERSION_HISTORY.md']
            inventory=root/'SHA256SUMS';lines=['0'*64+'  '+name for name in names]
            lines.extend(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.name for p in (code,research));inventory.write_text('\n'.join(lines)+'\n')
            self.assertEqual(verify_inventory(inventory),2)
            research.write_text('changed')
            with self.assertRaisesRegex(ValueError,'notes.md'):verify_inventory(inventory)
            research.write_text('evidence');code.write_text('changed')
            with self.assertRaisesRegex(ValueError,'tool.py'):verify_inventory(inventory)

    def test_unsafe_path_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            inventory=Path(directory)/'SHA256SUMS';inventory.write_text('0'*64+'  ../escape.py\n')
            with self.assertRaisesRegex(ValueError,'invalid inventory'):verify_inventory(inventory)
