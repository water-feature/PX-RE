# SPDX-License-Identifier: GPL-2.0-or-later
"""Restore pinned helper objects directly, without subprocesses or temporary files."""
import json
from pathlib import Path
from core import FACTORY_SHA256, sha

MANIFEST_SHA256 = 'b30faf7b0d64e3eb5cda6a7d49b8d0d41596e0f8b75356136419d3a0dea741cc'

class Objects:
    def __init__(self, cache, factory):
        if sha(factory) != FACTORY_SHA256:
            raise ValueError('Factory identity mismatch')
        self.cache, self.factory = Path(cache).resolve(), factory
        raw = (self.cache/'manifest.json').read_bytes()
        if sha(raw) != MANIFEST_SHA256:
            raise ValueError('Published object manifest identity mismatch')
        self.manifest = json.loads(raw)

    def restore(self, key, inputs):
        entry = self.manifest['entries'].get(key)
        if not entry or entry['kind'] != 'object' or entry['returncode'] != 0:
            raise ValueError('Unknown or unsuccessful object recipe')
        required = {item['name']:item['sha256'] for item in entry['inputs']}
        if set(inputs) != set(required):
            raise ValueError('Object source/include set differs from recorded recipe')
        for name, expected in required.items():
            if sha(inputs[name]) != expected:
                raise ValueError('Object source/include hash mismatch: '+name)
        result = []
        for output in entry['outputs']:
            ident = output['sha256']
            if len(ident) != 64 or any(c not in '0123456789abcdef' for c in ident):
                raise ValueError('Invalid cache blob identifier')
            path = (self.cache/'blobs'/ident).resolve()
            if not path.is_relative_to(self.cache):
                raise ValueError('Cache blob escapes cache directory')
            blob = path.read_bytes()
            if len(blob) != output['size'] or sha(blob) != ident:
                raise ValueError('Cached object identity mismatch')
            restored = bytearray(blob)
            end = 0
            for span in output['firmware_spans']:
                offset, source, size = span['offset'],span['source_offset'],span['size']
                if (size <= 0 or offset < end or offset+size > len(blob)
                        or source < 0 or source+size > len(self.factory)):
                    raise ValueError('Redaction bounds or overlap invalid')
                if any(blob[offset:offset+size]):
                    raise ValueError('Redaction placeholder changed')
                data = self.factory[source:source+size]
                if sha(data) != span['sha256']:
                    raise ValueError('Factory restoration span mismatch')
                restored[offset:offset+size] = data
                end = offset+size
            if sha(restored) != output['restored_sha256']:
                raise ValueError('Restored object identity mismatch')
            result.append(bytes(restored))
        return result
