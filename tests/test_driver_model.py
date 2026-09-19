import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from driver_model import (  # noqa: E402
    encode_columns,
    encode_pair,
    graphics_crlf,
    graphics_record,
    reverse7,
    text_crlf,
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

    def test_r2_text_crlf_has_no_legacy_escape_spacing(self):
        self.assertEqual(text_crlf(0), b"\x0d")
        self.assertEqual(text_crlf(2), b"\x0d\x0a\x0a")
        self.assertNotIn(0x1B, text_crlf(2))

    def test_r2_graphics_crlf_native_feed_and_exit(self):
        self.assertEqual(graphics_crlf(0), b"")
        self.assertEqual(graphics_crlf(1), b"\x03\x0e\x03\x02")
        self.assertEqual(
            graphics_crlf(2),
            b"\x03\x0e\x03\x02\x03\x0e\x03\x02",
        )


if __name__ == "__main__":
    unittest.main()
