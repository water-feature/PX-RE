#!/usr/bin/env python3
"""Check browser recipe integrity and Python-source drift without firmware."""
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def main():
    script = (ROOT / 'website/recipe.js').read_text()
    assignment = script.split('globalThis.PX_RECIPE_JSON = ', 1)[1].strip().removesuffix(';')
    payload = json.loads(assignment)
    digest = hashlib.sha256(payload.encode()).hexdigest()
    pin = re.search(r'"([0-9a-f]{64})"', (ROOT / 'website/recipe-pin.js').read_text())[1]
    if digest != pin:
        raise SystemExit('Browser recipe integrity mismatch')
    recipe = json.loads(payload)
    expected_paths = {str(p.relative_to(ROOT)) for p in (ROOT / 'firmware_builder/direct').rglob('*')
                      if p.is_file() and '__pycache__' not in p.parts}
    if set(recipe['sources']) != expected_paths:
        raise SystemExit('Direct builder source inventory changed; regenerate browser recipe')
    for name, expected in recipe['sources'].items():
        path = ROOT / name
        if not path.is_relative_to(ROOT / 'firmware_builder/direct') or '..' in Path(name).parts:
            raise SystemExit('Unsafe recipe source path')
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise SystemExit('Direct builder changed; regenerate browser recipe: ' + name)
    for component in recipe['components']:
        cursor = component['factory_size']
        previous_end = 0
        for w in component['writes']:
            end = w['offset'] + w['size']
            if w['offset'] < previous_end or end > component['final_size'] or w['size'] <= 0:
                raise SystemExit('Invalid recipe ownership')
            if end > cursor:
                if w['offset'] > cursor:
                    raise SystemExit('Unowned recipe extension')
                cursor = end
            previous_end = end
        if cursor != component['final_size']:
            raise SystemExit('Incomplete recipe extension')
    print('PASS: browser recipe integrity, source pins and ownership extents')


if __name__ == '__main__':
    main()
