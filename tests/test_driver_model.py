import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from driver_model import (  # noqa: E402
    begin_graphics,
    encode_columns,
    encode_pair,
    end_for_text,
    graphics_band_feed,
    reverse7,
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
        self.assertTrue(all(b & 0x80 for b in encoded))
        self.assertNotIn(0x03, encoded)

    def test_old_etx_collision_becomes_83(self):
        self.assertEqual(reverse7(0x60), 0x03)
        self.assertEqual(encode_pair(0x60, 0x00), 0x83)

    def test_r5_first_sendgc_enters_graphics(self):
        stream, state = begin_graphics(False)
        self.assertEqual(stream, b"\x03")
        self.assertTrue(state)

    def test_r5_next_sendgc_stays_in_graphics(self):
        stream, state = begin_graphics(True)
        self.assertEqual(stream, b"")
        self.assertTrue(state)

    def test_r5_normal_band_feed_stays_in_graphics(self):
        stream, state = graphics_band_feed(True, 0, 1)
        self.assertEqual(stream, b"\x03\x0e")
        self.assertTrue(state)

    def test_r5_multiple_native_band_feeds(self):
        stream, state = graphics_band_feed(True, 0, 2)
        self.assertEqual(stream, b"\x03\x0e\x03\x0e")
        self.assertTrue(state)

    def test_r5_boundary_change_exits_then_crlf(self):
        stream, state = graphics_band_feed(True, 12, 1)
        self.assertEqual(stream, b"\x03\x02\x0d\x0a")
        self.assertFalse(state)

    def test_r5_cr_only_exits_then_returns_carriage(self):
        stream, state = graphics_band_feed(True, 0, 0)
        self.assertEqual(stream, b"\x03\x02\x0d")
        self.assertFalse(state)

    def test_r5_text_output_auto_exits(self):
        stream, state = end_for_text(True)
        self.assertEqual(stream, b"\x03\x02")
        self.assertFalse(state)


if __name__ == "__main__":
    unittest.main()
