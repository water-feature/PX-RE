# SPDX-License-Identifier: GPL-2.0-or-later
"""Pure byte operations for a direct factory-based build; no filesystem effects."""
from dataclasses import dataclass
import hashlib

FACTORY_SHA256 = 'a4b304b3bb48ca933ae63c99c0098698c497ebfc7c38ab2a823b5e0df4919fa9'
FINAL_SHA256 = '488444589607a1b4e793a8d8f79a67c5bd50773b722c302e6d80bc1db77b4b7c'

def sha(data):
    return hashlib.sha256(data).hexdigest()

@dataclass(frozen=True)
class Write:
    offset: int
    data: bytes
    expected_factory_sha256: str
    owner: str
    source: str

class Component:
    """All guards address the original factory component, never a prior write."""
    def __init__(self, name, factory, final_size):
        if not isinstance(factory, bytes) or final_size < len(factory):
            raise ValueError('Component requires immutable factory bytes and nonshrinking extent')
        self.name, self.factory, self.final_size = name, factory, final_size
        self.writes = []

    def add(self, write):
        if not isinstance(write.data, bytes) or not write.data:
            raise ValueError('Write requires nonempty immutable bytes')
        end = write.offset + len(write.data)
        if write.offset < 0 or end > self.final_size or not write.owner or not write.source:
            raise ValueError('Write bounds or source ownership invalid')
        original = self.factory[write.offset:min(end, len(self.factory))]
        if sha(original) != write.expected_factory_sha256:
            raise ValueError(f'{self.name}: factory guard failed for {write.owner}')
        for prior in self.writes:
            if write.offset < prior.offset + len(prior.data) and prior.offset < end:
                raise ValueError(f'{self.name}: overlapping final owners: {prior.owner}, {write.owner}')
        self.writes.append(write)

    def render(self):
        writes = sorted(self.writes, key=lambda w:w.offset)
        # Every added byte, including padding, needs explicit ownership.
        covered = len(self.factory)
        for write in writes:
            end = write.offset + len(write.data)
            if end > covered:
                if write.offset > covered:
                    raise ValueError(f'{self.name}: unowned extension at {covered:#x}')
                covered = end
        if covered != self.final_size:
            raise ValueError(f'{self.name}: unowned extension at {covered:#x}')
        result = bytearray(self.factory)
        result.extend(bytes(self.final_size-len(result)))
        for write in writes:
            result[write.offset:write.offset+len(write.data)] = write.data
        return bytes(result)

    def receipt(self):
        return [{'offset':w.offset,'size':len(w.data),'owner':w.owner,'source':w.source,
                 'factory_sha256':w.expected_factory_sha256,'generated_sha256':sha(w.data)}
                for w in sorted(self.writes,key=lambda w:w.offset)]
