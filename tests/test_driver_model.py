import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from driver_model import (  # noqa: E402
    direct_feed_144,
    encode_columns,
    encode_pair,
    graphics_record,
    reverse7,
    type5_crlf,
    update_spacing_72,
)


class DriverModelTests(unittest.TestCase):
    def test_reverse7_endpoints(self):
        self.assertEqual(reverse7(0x01), 0x40)
        self.assertEqual(reverse7(0x40), 0x01)
        self.assertEqual(reverse7(0x7F), 0x7F)

    def test_pair_collapses_120_to_60_cpi(self):
        self.assertEqual(encode_pair(0x01, 0x00), 0xC0)
        self.assertEqual(encode_pair(0x00, 0x40), 0x81)
        self.assertEqual(encode_pair(0x01, 0x40), 0xC1)

    def test_wire_data_always_has_bit7_set(self):
        source = bytes(range(128)) * 2
        encoded = encode_columns(source)
        self.assertTrue(encoded)
        self.assertTrue(all(b & 0x80 for b in encoded))
        self.assertNotIn(0x03, encoded)

    def test_old_etx_collision_becomes_83(self):
        self.assertEqual(reverse7(0x60), 0x03)
        self.assertEqual(encode_pair(0x60, 0x00), 0x83)

    def test_graphics_framing(self):
        record = graphics_record(bytes([0x60, 0x00, 0x01, 0x00]))
        self.assertEqual(record, bytes([0x03, 0x83, 0xC0, 0x03, 0x02]))

    def test_odd_source_count_is_rejected(self):
        with self.assertRaises(ValueError):
            encode_columns(b"\x01")

    def test_r4_x7_y0_caches_exact_14_144_without_feed(self):
        stream, spacing = type5_crlf(24, 7, 0)
        self.assertEqual(spacing, 14)
        self.assertEqual(stream, b"\x0d")

    def test_r4_x0_y1_uses_cached_14_144_direct_feed(self):
        stream, spacing = type5_crlf(14, 0, 1)
        self.assertEqual(spacing, 14)
        self.assertEqual(stream, b"\x0d\x1b%9\x0e")
        self.assertNotIn(0x0A, stream)

    def test_r4_spacing_update_and_multiple_feeds(self):
        stream, spacing = type5_crlf(14, 12, 2)
        self.assertEqual(spacing, 24)
        self.assertEqual(
            stream,
            b"\x0d\x1b%9\x18\x1b%9\x18",
        )

    def test_direct_feed_encoding(self):
        self.assertEqual(direct_feed_144(14), b"\x1b%9\x0e")
        self.assertEqual(update_spacing_72(14, 0), 14)
        self.assertEqual(update_spacing_72(14, 3), 6)


if __name__ == "__main__":
    unittest.main()
