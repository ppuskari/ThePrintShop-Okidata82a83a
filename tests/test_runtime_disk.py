import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from build_runtime_disk import (  # noqa: E402
    BANNER_ICON_CALL,
    BANNER_TEXT_CALL,
    EXPECTED_ORIGINAL,
    R29_HELPER_BYTES,
    patch_banner_draw4_payload,
)


class RuntimeDiskR29Tests(unittest.TestCase):
    def test_expected_overlay_load_address_is_optional(self):
        self.assertIn("load", EXPECTED_ORIGINAL["PRCOMS"])
        self.assertNotIn("load", EXPECTED_ORIGINAL["MENUS7"])

    def test_r29_runtime_draw4_exact_layout(self):
        payload = bytearray([0xEA] * 1012)
        text_off = 0x0085
        icon_off = 0x02BE
        payload[text_off:text_off + len(BANNER_TEXT_CALL)] = BANNER_TEXT_CALL
        payload[icon_off:icon_off + len(BANNER_ICON_CALL)] = BANNER_ICON_CALL

        patched, info = patch_banner_draw4_payload(bytes(payload), 0x7800)

        self.assertEqual(info["text_site"], text_off)
        self.assertEqual(info["icon_site"], icon_off)
        self.assertEqual(info["helper"], 0x7BF4)
        self.assertEqual(info["common"], 0x7BF8)

        self.assertEqual(len(patched), 1020)
        self.assertEqual(patched[1012:], R29_HELPER_BYTES)
        self.assertEqual(0x7800 + len(patched) - 1, 0x7BFB)

    def test_r29_text_site_uses_bitcnt_and_shared_dex(self):
        payload = bytearray([0xEA] * 1012)
        text_off = 0x0085
        icon_off = 0x02BE
        payload[text_off:text_off + len(BANNER_TEXT_CALL)] = BANNER_TEXT_CALL
        payload[icon_off:icon_off + len(BANNER_ICON_CALL)] = BANNER_ICON_CALL

        patched, _ = patch_banner_draw4_payload(bytes(payload), 0x7800)

        expected = bytes.fromhex("A6 58 A0 01 20 F8 7B")
        self.assertEqual(
            patched[text_off:text_off + len(expected)],
            expected,
        )

    def test_r29_icon_site_uses_xcur_mod8_and_shared_helper(self):
        payload = bytearray([0xEA] * 1012)
        text_off = 0x0085
        icon_off = 0x02BE
        payload[text_off:text_off + len(BANNER_TEXT_CALL)] = BANNER_TEXT_CALL
        payload[icon_off:icon_off + len(BANNER_ICON_CALL)] = BANNER_ICON_CALL

        patched, _ = patch_banner_draw4_payload(bytes(payload), 0x7800)

        expected = bytes.fromhex(
            "A2 03 A0 01 A5 54 29 07 20 F4 7B"
        )
        self.assertEqual(
            patched[icon_off:icon_off + len(expected)],
            expected,
        )

    def test_r29_helper_is_exact_eight_byte_state_mapper(self):
        self.assertEqual(
            R29_HELPER_BYTES,
            bytes.fromhex("F0 02 A2 01 CA 4C 03 18"),
        )
        self.assertEqual(len(R29_HELPER_BYTES), 8)

    def test_r29_patch_changes_only_two_sites_before_eof(self):
        payload = bytearray([0xEA] * 1012)
        text_off = 0x0085
        icon_off = 0x02BE
        payload[text_off:text_off + len(BANNER_TEXT_CALL)] = BANNER_TEXT_CALL
        payload[icon_off:icon_off + len(BANNER_ICON_CALL)] = BANNER_ICON_CALL
        original = bytes(payload)

        patched, _ = patch_banner_draw4_payload(original, 0x7800)

        changed = {
            i
            for i, (old, new) in enumerate(
                zip(original, patched[:len(original)])
            )
            if old != new
        }
        allowed = set(range(text_off, text_off + len(BANNER_TEXT_CALL)))
        allowed.update(range(icon_off, icon_off + len(BANNER_ICON_CALL)))
        self.assertTrue(changed)
        self.assertTrue(changed.issubset(allowed))

    def test_r29_patch_requires_unique_banner_sites(self):
        with self.assertRaises(RuntimeError):
            patch_banner_draw4_payload(bytes([0xEA]) * 1012)


if __name__ == "__main__":
    unittest.main()
