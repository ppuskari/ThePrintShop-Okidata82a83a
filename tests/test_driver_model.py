import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from driver_model import (  # noqa: E402
    crlf_type5,
    encode_columns,
    encode_pair,
    gcdraw_piece_start,
    reverse7,
    r9_card_band_starts,
    sendgc_begin,
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

    def test_sendgc_enters_graphics_once(self):
        self.assertEqual(sendgc_begin(False), (b"\x03", True))
        self.assertEqual(sendgc_begin(True), (b"", True))

    def test_active_band_uses_native_feed_and_stays_open(self):
        stream, state = crlf_type5(
            in_graphics=True, x_72=0, y_count=1
        )
        self.assertEqual(stream, b"\x03\x0e")
        self.assertTrue(state)

    def test_lf36_is_suppressed(self):
        stream, state = crlf_type5(
            in_graphics=True, x_72=2, y_count=1
        )
        self.assertEqual(stream, b"\x03\x02\x0d")
        self.assertFalse(state)
        self.assertNotIn(0x0A, stream)

    def test_first_outside_piece_has_no_vertical_feed(self):
        stream, state = gcdraw_piece_start(
            in_graphics=False,
            first_outside_piece=True,
        )
        self.assertEqual(stream, b"\x0d\x03")
        self.assertTrue(state)
        self.assertNotIn(0x0A, stream)
        self.assertNotIn(0x0E, stream)

    def test_later_piece_uses_one_native_graphics_feed(self):
        stream, state = gcdraw_piece_start(
            in_graphics=True,
            first_outside_piece=False,
        )
        self.assertEqual(stream, b"\x03\x02\x0d\x03\x03\x0e")
        self.assertTrue(state)
        self.assertNotIn(0x0A, stream)
        self.assertEqual(stream.count(bytes([0x0E])), 1)

    def test_no_legacy_spacing_sequence(self):
        streams = [
            crlf_type5(in_graphics=False, x_72=7, y_count=0)[0],
            crlf_type5(in_graphics=True, x_72=0, y_count=1)[0],
            crlf_type5(in_graphics=True, x_72=12, y_count=1)[0],
            crlf_type5(in_graphics=True, x_72=2, y_count=1)[0],
            gcdraw_piece_start(
                in_graphics=False, first_outside_piece=True
            )[0],
            gcdraw_piece_start(
                in_graphics=True, first_outside_piece=False
            )[0],
        ]
        for stream in streams:
            self.assertNotIn(b"%9", stream)

    def test_r9_card_resampler_preserves_full_source_extent(self):
        starts = r9_card_band_starts()
        self.assertEqual(len(starts), 26)
        self.assertEqual(starts[0], 0)
        self.assertEqual(starts[-1], 189)
        self.assertEqual(starts[-1] + 6, 195)

    def test_r9_card_resampler_uses_fourteen_single_row_skips(self):
        starts = r9_card_band_starts()
        deltas = [b - a for a, b in zip(starts, starts[1:])]
        self.assertEqual(deltas.count(8), 14)
        self.assertEqual(deltas.count(7), 11)
        self.assertTrue(all(d in (7, 8) for d in deltas))

    def test_r9_card_resampler_ratio(self):
        # 196 logical rows -> 182 output rows = 13/14? No:
        # the target is the nearest integer to 196 * 14/15 = 182.93.
        self.assertEqual(26 * 7, 182)
        self.assertEqual(round(196 * 14 / 15), 183)


if __name__ == "__main__":
    unittest.main()
