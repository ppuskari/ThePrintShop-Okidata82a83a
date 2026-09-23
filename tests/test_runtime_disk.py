import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from build_runtime_disk import (  # noqa: E402
    BANNER_ICON_CALL,
    BANNER_TEXT_CALL,
    _build_banner_icon_helper,
    _build_banner_text_helper,
    _vtoc_bitmap_offset,
    EXPECTED_ORIGINAL,
    patch_banner_draw4_payload,
)


class RuntimeDiskR29Tests(unittest.TestCase):
    def test_expected_overlay_load_address_is_optional(self):
        self.assertIn("load", EXPECTED_ORIGINAL["PRCOMS"])
        self.assertNotIn("load", EXPECTED_ORIGINAL["MENUS7"])

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

    def test_r29_runtime_draw4_patch_changes_only_jsr_operands(self):
        prefix = bytes([0xEA]) * 17
        middle = bytes([0xEA]) * 23
        suffix = bytes([0xEA]) * 19
        original = (
            prefix
            + BANNER_TEXT_CALL
            + middle
            + BANNER_ICON_CALL
            + suffix
        )

        patched, info = patch_banner_draw4_payload(original, 0x7800)

        self.assertEqual(info["text_site"], len(prefix))
        self.assertEqual(
            info["icon_site"],
            len(prefix) + len(BANNER_TEXT_CALL) + len(middle),
        )

        text_helper = _build_banner_text_helper(info["text_helper"])
        icon_helper = _build_banner_icon_helper(info["icon_helper"])
        self.assertEqual(
            patched[len(original):],
            text_helper + icon_helper,
        )

        expected_base = bytearray(original)
        text_jsr = info["text_site"] + 4
        expected_base[text_jsr + 1] = info["text_helper"] & 0xFF
        expected_base[text_jsr + 2] = (info["text_helper"] >> 8) & 0xFF

        icon_jsr = info["icon_site"] + 8
        expected_base[icon_jsr + 1] = info["icon_helper"] & 0xFF
        expected_base[icon_jsr + 2] = (info["icon_helper"] >> 8) & 0xFF

        self.assertEqual(
            patched[:len(original)],
            bytes(expected_base),
        )

    def test_r29_helpers_tail_jump_to_original_crlf(self):
        text = _build_banner_text_helper(0x7BF4)
        icon = _build_banner_icon_helper(0x7C20)
        self.assertIn(bytes.fromhex("4C 03 18"), text)
        self.assertIn(bytes.fromhex("4C 03 18"), icon)

    def test_r29_patch_requires_unique_banner_sites(self):
        with self.assertRaises(RuntimeError):
            patch_banner_draw4_payload(bytes([0xEA]) * 128)


if __name__ == "__main__":
    unittest.main()
