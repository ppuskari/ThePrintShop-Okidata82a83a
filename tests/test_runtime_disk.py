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
    R30_STRSUB_OLD,
    _build_r30_strsend,
    _find_r30_strsend,
    patch_banner_draw4_payload,
)


def historical_strsend(strsub_addr: int) -> bytes:
    """Synthetic exact-shape historical STRSEND with absolute FCOLOR."""
    return bytes([
        0x84, 0x5B,                   # STY FNZY
        0xA9, 0x01,                   # LDA #1
        0x85, 0x5D,                   # STA CTEMP
        0xAD, 0xF8, 0x95,             # LDA COLORPR
        0xF0, 0x0A,                   # BEQ STRSEND2
        0xAE, 0x34, 0x12,             # LDX FCOLOR (synthetic abs)
        0xBD, 0x78, 0x56,             # LDA COLORTBL-1,X
        0x85, 0x5D,                   # STA CTEMP
        0xA9, 0x03,                   # LDA #3
        0x85, 0x5F,                   # STRSEND2 STA COLOR
        0xF0, 0x05,                   # BEQ STRSEND4
        0xA6, 0x5F,                   # STRSEND3 LDX COLOR
        0x20, 0x99, 0x99,             # JSR COLORCHG
        0x20,                          # STRSEND4 JSR STRSUB
        strsub_addr & 0xFF,
        (strsub_addr >> 8) & 0xFF,
        0xC6, 0x5F,                   # DEC COLOR
        0x10, 0xF4,                   # BPL STRSEND3
    ])


def synthetic_draw4() -> tuple[bytes, dict[str, int]]:
    load = 0x7800
    text_off = 0x0085
    strsend_off = 0x0120
    strsub_off = 0x0170
    icon_off = 0x02BE

    payload = bytearray([0xEA] * 1012)
    payload[
        text_off:text_off + len(BANNER_TEXT_CALL)
    ] = BANNER_TEXT_CALL
    payload[
        icon_off:icon_off + len(BANNER_ICON_CALL)
    ] = BANNER_ICON_CALL
    payload[
        strsub_off:strsub_off + len(R30_STRSUB_OLD)
    ] = R30_STRSUB_OLD

    strsub_addr = load + strsub_off
    block = historical_strsend(strsub_addr)
    payload[strsend_off:strsend_off + len(block)] = block

    return bytes(payload), {
        "load": load,
        "text_off": text_off,
        "strsend_off": strsend_off,
        "strsub_off": strsub_off,
        "strsub_addr": strsub_addr,
        "icon_off": icon_off,
    }


class RuntimeDiskR30Tests(unittest.TestCase):
    def test_expected_overlay_load_address_is_optional(self):
        self.assertIn("load", EXPECTED_ORIGINAL["PRCOMS"])
        self.assertNotIn("load", EXPECTED_ORIGINAL["MENUS7"])

    def test_strsend_parser_validates_historical_control_flow(self):
        payload, meta = synthetic_draw4()
        start, end, strsub = _find_r30_strsend(payload)
        self.assertEqual(start, meta["strsend_off"])
        self.assertEqual(end - start, 37)
        self.assertEqual(strsub, meta["strsub_addr"])

    def test_r30_scheduler_is_exactly_historical_block_size(self):
        payload, meta = synthetic_draw4()
        start, end, strsub = _find_r30_strsend(payload)
        feed = meta["strsub_addr"] + 7
        code = _build_r30_strsend(
            strsub_addr=strsub,
            feed_helper_addr=feed,
            block_len=end - start,
        )
        self.assertEqual(len(code), 37)
        self.assertEqual(code[-2:], b"\xEA\xEA")

        # STY FNZY / JSR STRSUB then deterministic BITCNT/SADDR scheduler.
        self.assertEqual(
            code[:7],
            bytes([
                0x84, 0x5B,
                0x20,
                strsub & 0xFF,
                (strsub >> 8) & 0xFF,
                0xA5, 0x58,
            ]),
        )

    def test_r30_full_draw4_layout_and_frozen_icon_helper(self):
        original, meta = synthetic_draw4()
        patched, info = patch_banner_draw4_payload(
            original,
            meta["load"],
        )

        self.assertEqual(info["text_site"], meta["text_off"])
        self.assertEqual(info["icon_site"], meta["icon_off"])
        self.assertEqual(info["strsend_site"], meta["strsend_off"])
        self.assertEqual(info["strsend_len"], 37)
        self.assertEqual(info["strsub_site"], meta["strsub_off"])
        self.assertEqual(info["feed_helper"], meta["strsub_addr"] + 7)
        self.assertEqual(info["icon_helper"], 0x7BF4)

        self.assertEqual(len(patched), 1020)
        self.assertEqual(patched[1012:], R29_HELPER_BYTES)
        self.assertEqual(0x7800 + len(patched) - 1, 0x7BFB)

        # R30 restores/leaves the historical native BSTR6 sequence unchanged.
        self.assertEqual(
            patched[
                meta["text_off"]:
                meta["text_off"] + len(BANNER_TEXT_CALL)
            ],
            BANNER_TEXT_CALL,
        )

        # R29 icon hook remains byte-for-byte the proven mapping.
        expected_icon = bytes.fromhex(
            "A2 03 A0 01 A5 54 29 07 20 F4 7B"
        )
        self.assertEqual(
            patched[
                meta["icon_off"]:
                meta["icon_off"] + len(expected_icon)
            ],
            expected_icon,
        )

    def test_r30_strsub_has_normal_entry_and_hidden_feed_entry(self):
        original, meta = synthetic_draw4()
        patched, _ = patch_banner_draw4_payload(
            original,
            meta["load"],
        )
        off = meta["strsub_off"]
        bstr9 = meta["strsub_addr"] + len(R30_STRSUB_OLD)
        expected = bytes([
            0xA9, 0xFE,
            0x85, 0x5E,
            0x4C, bstr9 & 0xFF, (bstr9 >> 8) & 0xFF,
            0xA2, 0x00,
            0x4C, 0x03, 0x18,
        ])
        self.assertEqual(
            patched[off:off + len(expected)],
            expected,
        )

    def test_r30_changes_only_text_sender_and_r29_icon_ranges(self):
        original, meta = synthetic_draw4()
        patched, info = patch_banner_draw4_payload(
            original,
            meta["load"],
        )

        changed = {
            i
            for i, (old, new) in enumerate(
                zip(original, patched[:len(original)])
            )
            if old != new
        }
        allowed = set(
            range(
                info["strsend_site"],
                info["strsend_site"] + info["strsend_len"],
            )
        )
        allowed.update(
            range(
                info["strsub_site"],
                info["strsub_site"] + len(R30_STRSUB_OLD),
            )
        )
        allowed.update(
            range(
                info["icon_site"],
                info["icon_site"] + len(BANNER_ICON_CALL),
            )
        )
        self.assertTrue(changed)
        self.assertTrue(changed.issubset(allowed))
        self.assertFalse(
            any(
                i in changed
                for i in range(
                    meta["text_off"],
                    meta["text_off"] + len(BANNER_TEXT_CALL),
                )
            )
        )

    def test_r30_patch_rejects_missing_runtime_sites(self):
        with self.assertRaises(RuntimeError):
            patch_banner_draw4_payload(bytes([0xEA]) * 1012)


if __name__ == "__main__":
    unittest.main()
