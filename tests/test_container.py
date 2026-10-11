"""Synthetic format fixtures only; no manufacturer firmware is required."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'firmware_builder'))
from container import parse, serialize, sum16


def fixture():
    records = []
    for kind, payload in [(1, b'\x01\x02\x03\x04'), (2, b'\x05\x06'), (3, b'PIC')]:
        header = bytes([kind, 0x7b, 2, 2, 2, 0, 0, 0x7a]) + len(payload).to_bytes(4, 'big')
        trailer = b'00' if kind == 3 else sum16(payload).to_bytes(2, 'little')
        records.append(header + payload + trailer)
    return b'\xf0' + b''.join(records) + b'\xf7'


class ContainerTests(unittest.TestCase):
    def test_round_trip_and_record_boundaries(self):
        data = fixture()
        rows = parse(data)
        self.assertEqual([r.kind for r in rows], [1, 2, 3])
        self.assertEqual([r.payload for r in rows], [b'\x01\x02\x03\x04', b'\x05\x06', b'PIC'])
        self.assertEqual(serialize(rows), data)
        for row in rows:
            self.assertEqual(data[row.payload_offset:row.trailer_offset], row.payload)

    def test_every_truncation_rejected(self):
        data = fixture()
        for size in range(len(data)):
            with self.subTest(size=size), self.assertRaises(ValueError):
                parse(data[:size])

    def test_corruption_rejected(self):
        data = fixture()
        rows = parse(data)
        positions = [0, len(data)-1]
        for row in rows:
            positions += [row.offset, row.offset+1, row.offset+7, row.offset+11, row.trailer_offset]
            if row.kind in (1, 2):
                positions.append(row.payload_offset)
        for position in positions:
            changed = bytearray(data)
            changed[position] ^= 1
            with self.subTest(position=position), self.assertRaises(ValueError):
                parse(bytes(changed))

    def test_trailing_data_rejected(self):
        with self.assertRaises(ValueError):
            parse(fixture()[:-1] + b'extra\xf7')

    def test_odd_checksum_payload_rejected(self):
        with self.assertRaises(ValueError):
            sum16(b'x')


if __name__ == '__main__':
    unittest.main()
