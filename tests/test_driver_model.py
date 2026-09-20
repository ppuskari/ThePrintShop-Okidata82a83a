import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from driver_model import crlf_r7, encode_columns, encode_pair, reverse7  # noqa: E402


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

    def test_odd_source_count_is_rejected(self):
        with self.assertRaises(ValueError):
            encode_columns(b"\x01")

    def test_r7_active_graphics_band_stays_open(self):
        stream, state = crlf_r7(in_graphics=True, x_72=0, y_count=1)
        self.assertEqual(stream, b"\x03\x0e")
        self.assertTrue(state)

    def test_r7_one_sixth_boundary_exits_then_plain_lf(self):
        stream, state = crlf_r7(in_graphics=True, x_72=12, y_count=1)
        self.assertEqual(stream, b"\x03\x02\x0d\x0a")
        self.assertFalse(state)
        self.assertNotIn(b"%9", stream)

    def test_r7_lf36_is_suppressed(self):
        stream, state = crlf_r7(in_graphics=True, x_72=2, y_count=1)
        self.assertEqual(stream, b"\x03\x02\x0d")
        self.assertFalse(state)
        self.assertNotIn(0x0A, stream)
        self.assertNotIn(b"%9", stream)

    def test_r7_text_first_row_uses_plain_lf(self):
        stream, state = crlf_r7(in_graphics=False, x_72=0, y_count=1)
        self.assertEqual(stream, b"\x0d\x0a")
        self.assertFalse(state)

    def test_r7_never_emits_legacy_spacing_sequence(self):
        for state, x, y in [
            (False, 7, 0),
            (False, 0, 1),
            (True, 0, 1),
            (True, 12, 1),
            (True, 2, 1),
        ]:
            stream, _ = crlf_r7(in_graphics=state, x_72=x, y_count=y)
            self.assertNotIn(b"%9", stream)


if __name__ == "__main__":
    unittest.main()
