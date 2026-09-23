import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from build_runtime_disk import _vtoc_bitmap_offset  # noqa: E402
from patch_printshop_source import patch_bdraw  # noqa: E402


class RuntimeDiskR29Tests(unittest.TestCase):
    def test_dos33_vtoc_sector_bit_order(self):
        base = (17 * 16 * 256) + 0x38

        off, mask = _vtoc_bitmap_offset(0, 15)
        self.assertEqual(off, base)
        self.assertEqual(mask, 0x80)

        off, mask = _vtoc_bitmap_offset(0, 8)
        self.assertEqual(off, base)
        self.assertEqual(mask, 0x01)

        off, mask = _vtoc_bitmap_offset(0, 7)
        self.assertEqual(off, base + 1)
        self.assertEqual(mask, 0x80)

        off, mask = _vtoc_bitmap_offset(0, 0)
        self.assertEqual(off, base + 1)
        self.assertEqual(mask, 0x01)

    def test_bdraw_patch_is_banner_only_and_inserts_helpers(self):
        source = """ ORG $7800
BSTR6 LDX #00
 LDY #01
 JSR CRLF
 NOP
BICON2 LDA #01
 TAY
 AND XCUR
 ORA #06
 TAX
 JSR CRLF
 END
"""
        patched = patch_bdraw(source)

        self.assertIn("BSTR6 JSR R29BTXT", patched)
        self.assertIn("BICON2 JSR R29BICO", patched)
        self.assertIn("R29BTXT LDA $95F1", patched)
        self.assertIn("R29BICO LDA $95F1", patched)
        self.assertIn("R29TPH HEX 00", patched)
        self.assertNotIn("BSTR6 LDX #00", patched)
        self.assertLess(patched.index("R29BTXT"), patched.rindex("END"))

    def test_bdraw_patch_rejects_missing_banner_sites(self):
        with self.assertRaises(RuntimeError):
            patch_bdraw(" END\n")


if __name__ == "__main__":
    unittest.main()
