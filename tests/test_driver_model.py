import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from driver_model import (  # noqa: E402
    GRAPHICS,
    PRIMED,
    TEXT,
    crlf_r7,
    encode_columns,
    encode_pair,
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

    def test_odd_source_count_is_rejected(self):
        with self.assertRaises(ValueError):
            encode_columns(b"\x01")

    def test_r7_x7_setup_primes_without_feeding(self):
        stream, state = crlf_r7(state=TEXT, x_72=7, y_count=0)
        self.assertEqual(stream, b"\x0d")
        self.assertEqual(state, PRIMED)

    def test_r7_first_band_enters_graphics_and_native_feeds(self):
        stream, state = crlf_r7(state=PRIMED, x_72=0, y_count=1)
        self.assertEqual(stream, b"\x0d\x03\x03\x0e")
        self.assertEqual(state, GRAPHICS)

    def test_r7_normal_band_stays_in_graphics(self):
        stream, state = crlf_r7(state=GRAPHICS, x_72=0, y_count=1)
        self.assertEqual(stream, b"\x03\x0e")
        self.assertEqual(state, GRAPHICS)

    def test_r7_one_sixth_boundary_exits_then_plain_lf(self):
        stream, state = crlf_r7(state=GRAPHICS, x_72=12, y_count=1)
        self.assertEqual(stream, b"\x03\x02\x0d\x0a")
        self.assertEqual(state, TEXT)
        self.assertNotIn(b"%9", stream)

    def test_r7_lf36_is_suppressed(self):
        stream, state = crlf_r7(state=GRAPHICS, x_72=2, y_count=1)
        self.assertEqual(stream, b"\x03\x02\x0d")
        self.assertEqual(state, TEXT)
        self.assertNotIn(0x0A, stream)
        self.assertNotIn(b"%9", stream)

    def test_r7_stale_state_is_treated_as_text(self):
        stream, state = crlf_r7(state=99, x_72=12, y_count=1)
        self.assertEqual(stream, b"\x0d\x0a")
        self.assertEqual(state, TEXT)

    def test_r7_never_emits_legacy_spacing_sequence(self):
        for state, x, y in [
            (TEXT, 7, 0),
            (PRIMED, 0, 1),
            (GRAPHICS, 0, 1),
            (GRAPHICS, 12, 1),
            (GRAPHICS, 2, 1),
        ]:
            stream, _ = crlf_r7(state=state, x_72=x, y_count=y)
            self.assertNotIn(b"%9", stream)


if __name__ == "__main__":
    unittest.main()
