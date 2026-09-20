import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from driver_model import (  # noqa: E402
    CONT_PRIME,
    FIRST_PRIME,
    GRAPHICS,
    TEXT,
    crlf_r8,
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

    def test_r8_x7_at_job_start_marks_first_prime(self):
        stream, state = crlf_r8(state=TEXT, x_72=7, y_count=0)
        self.assertEqual(stream, b"\x0d")
        self.assertEqual(state, FIRST_PRIME)

    def test_r8_first_row_enters_graphics_without_vertical_feed(self):
        stream, state = crlf_r8(state=FIRST_PRIME, x_72=0, y_count=1)
        self.assertEqual(stream, b"\x0d\x03")
        self.assertEqual(state, GRAPHICS)
        self.assertNotIn(0x0A, stream)
        self.assertNotIn(0x0E, stream)

    def test_r8_active_band_uses_native_feed(self):
        stream, state = crlf_r8(state=GRAPHICS, x_72=0, y_count=1)
        self.assertEqual(stream, b"\x03\x0e")
        self.assertEqual(state, GRAPHICS)

    def test_r8_piece_setup_exits_and_marks_continuation(self):
        stream, state = crlf_r8(state=GRAPHICS, x_72=7, y_count=0)
        self.assertEqual(stream, b"\x03\x02\x0d")
        self.assertEqual(state, CONT_PRIME)

    def test_r8_next_piece_gets_exactly_one_native_feed(self):
        stream, state = crlf_r8(state=CONT_PRIME, x_72=0, y_count=1)
        self.assertEqual(stream, b"\x0d\x03\x03\x0e")
        self.assertEqual(state, GRAPHICS)
        self.assertNotIn(0x0A, stream)

    def test_r8_lf36_is_suppressed(self):
        stream, state = crlf_r8(state=GRAPHICS, x_72=2, y_count=1)
        self.assertEqual(stream, b"\x03\x02\x0d")
        self.assertEqual(state, TEXT)
        self.assertNotIn(0x0A, stream)

    def test_r8_never_emits_legacy_spacing_sequence(self):
        cases = [
            (TEXT, 7, 0),
            (FIRST_PRIME, 0, 1),
            (GRAPHICS, 0, 1),
            (GRAPHICS, 7, 0),
            (CONT_PRIME, 0, 1),
            (GRAPHICS, 2, 1),
        ]
        for state, x, y in cases:
            stream, _ = crlf_r8(state=state, x_72=x, y_count=y)
            self.assertNotIn(b"%9", stream)


if __name__ == "__main__":
    unittest.main()
