"""Opcode-nibble LZ decoder and its AOT pipeline method."""
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import aot_overlay_pipeline as pipeline  # noqa: E402
from opcode_nibble_lz import StreamError, decode, decode_exact  # noqa: E402


class FakeDisc:
    def __init__(self, files):
        self.data = {name.upper(): body for name, body in files.items()}
        self.files = {name: (10, len(body)) for name, body in self.data.items()}

    def read(self, name):
        return self.data[name.upper()]


class DecodeTest(unittest.TestCase):
    def test_every_op(self):
        stream = bytes([
            0x04, 1, 2, 3, 4,      # literals            -> 01 02 03 04
            0x40,                  # byte step +1 x3      -> 05 06 07
            0x60,                  # repeat 07 x3         -> 07 07 07
            0x70,                  # repeat pair 07 07 x2 -> 07 07 07 07
            0x02, 0x10, 0x00,      # literals            -> 10 00
            0x02, 0x20, 0x00,      # literals            -> 20 00
            0x50,                  # halfword step 0x10 x2 -> 30 00 40 00
            0x80 | 2,              # 3 bytes from offset 2 (pos-5)
            0xC0 | (1 << 2), 1,    # 5 bytes from offset 1 (pos-4)
            0xE0, 0, 0,            # 5 bytes from offset 0 (pos-3), overlapping
            0x00,
        ])
        out = decode_exact(stream)
        # Back-references copy byte by byte, so overlapping copies repeat.
        ref = bytearray([1, 2, 3, 4, 5, 6, 7, 7, 7, 7, 7, 7, 7, 7,
                         0x10, 0, 0x20, 0, 0x30, 0, 0x40, 0])
        for offset, count in ((2, 3), (1, 5), (0, 5)):
            start = len(ref) - offset - 3
            for k in range(count):
                ref.append(ref[start + k])
        self.assertEqual(out, bytes(ref))

    def test_steps_wrap(self):
        self.assertEqual(decode_exact(bytes([0x02, 0xFE, 0xFF, 0x40, 0x00])),
                         bytes([0xFE, 0xFF, 0x00, 0x01, 0x02]))
        self.assertEqual(decode_exact(bytes([0x04, 0xFF, 0xFF, 0xFF, 0x7F, 0x50, 0x00]))[-4:],
                         bytes([0xFF, 0xFF, 0xFF, 0x7F]))

    def test_consumed_and_exactness(self):
        self.assertEqual(decode(bytes([0x01, 9, 0x00, 0xAA])), (b'\x09', 3))
        with self.assertRaises(StreamError):
            decode_exact(bytes([0x01, 9, 0x00, 0xAA]))

    def test_invalid_streams_fail_closed(self):
        for stream in (b'', bytes([0x05, 1, 2]), bytes([0x40, 0x00]), bytes([0x50, 0x00]),
                       bytes([0x60, 0x00]), bytes([0x70, 0x00]), bytes([0x01, 1, 0x80, 0x00]),
                       bytes([0xC0]), bytes([0xE0, 0x00])):
            with self.assertRaises(StreamError, msg=stream.hex()):
                decode_exact(stream)


class PipelineMethodTest(unittest.TestCase):
    def setUp(self):
        self.image = bytes([0x08, 0x00, 0xE0, 0x03, 0x21, 0x10, 0x00, 0x00, 0x00])
        stream = bytes([0x08]) + self.image[:8] + bytes([0x00])
        self.disc = FakeDisc({'MOD/CODE.BIN': stream, 'MOD/TAIL.BIN': stream + b'\x01'})
        self.spec = dict(method='opcode_nibble_lz_files', files=[dict(
            file='MOD/CODE.BIN', load_addr='0x80100000', entries=['0x80100000'],
            decoded_sha256=hashlib.sha256(self.image[:8]).hexdigest())])

    def test_decoded_image_becomes_a_fixed_source(self):
        (source,) = pipeline.spec_sources(self.disc, self.spec)
        self.assertEqual((source['name'], source['base'], source['body']),
                         ('MOD/CODE.BIN', 0x80100000, self.image[:8]))

    def test_changed_image_or_trailing_bytes_fail(self):
        changed = json.loads(json.dumps(self.spec))
        changed['files'][0]['decoded_sha256'] = '00' * 32
        with self.assertRaises(pipeline.ProfileError):
            pipeline.spec_sources(self.disc, changed)
        tail = json.loads(json.dumps(self.spec))
        tail['files'][0]['file'] = 'MOD/TAIL.BIN'
        with self.assertRaises(pipeline.ProfileError):
            pipeline.spec_sources(self.disc, tail)

    def test_unaligned_or_duplicate_files_fail(self):
        unaligned = json.loads(json.dumps(self.spec))
        unaligned['files'][0]['load_addr'] = '0x80100002'
        with self.assertRaises(pipeline.ProfileError):
            pipeline.spec_sources(self.disc, unaligned)
        duplicate = json.loads(json.dumps(self.spec))
        duplicate['files'] *= 2
        with self.assertRaises(pipeline.ProfileError):
            pipeline.spec_sources(self.disc, duplicate)

    def test_prepare_builds_one_recipe(self):
        with tempfile.TemporaryDirectory() as directory:
            self.disc.binary = Path(directory) / 'source.bin'
            self.disc.binary.write_bytes(b'track')
            inventory = pipeline.prepare(dict(game_id='TEST', images=[self.spec],
                                              expected_records=1, strict_bounds=True),
                                         self.disc, [], Path(directory))
        self.assertEqual(inventory['required_images'], ['MOD/CODE.BIN'])
        self.assertEqual(inventory['recipe_count'], 1)


if __name__ == '__main__':
    unittest.main(verbosity=2)
