# SPDX-License-Identifier: GPL-2.0-or-later
"""Verify source/evidence inventories with CI's routine-guide exclusions."""
import hashlib
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
GUIDES={'readme.md','contributing.md','firmware_map.md','recovery.md'}

def verify_inventory(path):
    seen=set();checked=0
    for number,line in enumerate(path.read_text().splitlines(),1):
        if not line.strip():continue
        digest,separator,name=line.partition('  ')
        relative=Path(name);target=(path.parent/relative).resolve()
        if (not separator or len(digest)!=64 or any(c not in '0123456789abcdef' for c in digest)
                or not name or name in seen or relative.is_absolute() or '..' in relative.parts
                or not target.is_relative_to(path.parent.resolve())):
            raise ValueError(f'{path}:{number}: invalid inventory entry')
        seen.add(name)
        if relative.name.lower() in GUIDES:continue
        if not target.is_file() or hashlib.sha256(target.read_bytes()).hexdigest()!=digest:
            raise ValueError(f'{path}: checksum failed: {name}')
        checked+=1
    if not checked:raise ValueError(f'{path}: empty source/evidence inventory')
    return checked

def main():
    inventories=[ROOT/'SHA256SUMS']
    for directory in ('PX patch history','SSD expansion'):
        inventories.extend(sorted((ROOT/directory).rglob('SHA256SUMS')))
    count=sum(verify_inventory(path) for path in inventories)
    print(f'PASS: {len(inventories)} inventories, {count} source/evidence checks (routine guides excluded)')

if __name__=='__main__':
    try:main()
    except (ValueError,OSError) as error:
        print(str(error),file=sys.stderr);sys.exit(1)
