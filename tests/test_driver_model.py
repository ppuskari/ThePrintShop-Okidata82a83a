import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from driver_model import (  # noqa: E402
    crlf_r6,
    direct_feed,
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

    def test_r6_spacing_setup_caches_14_144_and_only_returns_carriage(self):
        stream, state, spacing = crlf_r6(
            in_graphics=False,
            cached_spacing_144=0,
            x_72=7,
            y_count=0,
        )
        self.assertEqual(stream, b"\x0d")
        self.assertFalse(state)
        self.assertEqual(spacing, 14)

    def test_r6_normal_graphics_band_stays_open(self):
        stream, state, spacing = crlf_r6(
            in_graphics=True,
            cached_spacing_144=14,
            x_72=0,
            y_count=1,
        )
        self.assertEqual(stream, b"\x03\x0e")
        self.assertTrue(state)
        self.assertEqual(spacing, 14)

    def test_r6_boundary_exits_and_uses_direct_motion_without_lf(self):
        stream, state, spacing = crlf_r6(
            in_graphics=True,
            cached_spacing_144=14,
            x_72=12,
            y_count=1,
        )
        self.assertEqual(
            stream,
            b"\x03\x02\x0d\x1b%9\x18",
        )
        self.assertFalse(state)
        self.assertEqual(spacing, 24)
        self.assertNotIn(0x0A, stream)

    def test_r6_half_page_reposition_uses_36_144_direct_steps(self):
        stream, state, spacing = crlf_r6(
            in_graphics=False,
            cached_spacing_144=24,
            x_72=18,
            y_count=22,
        )
        self.assertFalse(state)
        self.assertEqual(spacing, 36)
        self.assertEqual(stream[:1], b"\x0d")
        self.assertEqual(stream[1:], direct_feed(36) * 22)
        self.assertNotIn(0x0A, stream)

    def test_r6_zero_spacing_fallback(self):
        stream, state, spacing = crlf_r6(
            in_graphics=False,
            cached_spacing_144=0,
            x_72=0,
            y_count=2,
        )
        self.assertEqual(stream, b"\x0d\x0a\x0a")
        self.assertFalse(state)
        self.assertEqual(spacing, 0)


if __name__ == "__main__":
    unittest.main()
