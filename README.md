# The Print Shop – Okidata MICROLINE 82A/83A OkiGraph I Driver

Apple II printer-driver work for **Brøderbund The Print Shop v2**, targeting
the **Okidata MICROLINE 82A and 83A with OkiGraph I firmware**.

## Current status

**v0.1 source patch: implemented and CI-validated; physical printer validation is next.**

The original Print Shop v2 source already contains a dedicated
`OKIDATA MICROLINE 92,93` printer type. That path is an unusually good
starting point for the 82A/83A OkiGraph I driver because it already:

- converts the application's 120-column/inch graphics stream to a
  60-column/inch Okidata stream by merging source-column pairs;
- reverses the lower seven graphics bits for Okidata pin order;
- enters graphics with `$03`;
- leaves graphics with `$03 $02`; and
- uses Okidata `ESC % 9 n` programmable line spacing.

The v0.1 driver deliberately repurposes that printer type instead of adding
a tenth selector immediately.

The graphics-byte conversion becomes:

```
wire = $80 | reverse7(source0 | source1)
```

Forcing bit 7 high preserves the seven dot bits while preventing graphics
data from ever colliding with OkiGraph's ETX (`$03`) command prefix.

## Low-risk first build

The initial patch is intentionally layout-preserving:

- the new printer-menu label is the same 23 characters as the original;
- the modified `GC5` machine-code region remains exactly 20 bytes;
- the fixed `PRCOMS` jump table at `$1800` is unchanged;
- Print Shop's printer-interface-card code is untouched; and
- the existing type-5 line-spacing path is retained for hardware validation.

The assembly core is in [`src/OKI8283.S`](src/OKI8283.S).

## Build / validate on Windows

From the repository root:

```powershell
.\scripts\Build-DriverSource.ps1
```

That performs the wire-model unit tests, checks the patch against the actual
1987 Print Shop v2 source snapshot, and produces:

```
build\PRCOMS.OKI.S
build\MENUS7.OKI.S
```

Equivalent individual commands:

```powershell
py -3 -m unittest discover -s tests -v
py -3 tools\patch_printshop_source.py --check
py -3 tools\patch_printshop_source.py --output-dir build
```

The historical Brøderbund source is downloaded for the transformation but is
**not committed to this repository**.

## Validation status

GitHub Actions currently verifies:

- seven-bit reversal;
- 120-to-60 column conversion;
- bit 7 set on every graphics-data byte;
- the legacy raw-`$03` collision becomes `$83`;
- OkiGraph transaction framing;
- existing type-5 line-spacing encoding; and
- exact applicability of the source patch to the 1987-01-26 source disks.

## Repository map

- `src/OKI8283.S` — 6502 assembly integration fragment
- `src/driver_model.py` — executable wire-level model
- `tools/patch_printshop_source.py` — source transformation
- `tools/inspect_printshop_source.py` — reproducible historical-source scanner
- `tests/test_driver_model.py` — regression tests
- `docs/DESIGN.md` — source/driver architecture and design decisions
- `docs/HARDWARE-TEST.md` — staged 82A/83A physical validation plan
- `scripts/Build-DriverSource.ps1` — Windows validation/build helper

## Source basis

Print Shop v2 interface discovery uses the three-disk source snapshot dated
**1987-01-26** from the Asimov Apple II archive.

OkiGraph I protocol behavior is based on the independent ROM reconstruction
and hardware work in:

https://github.com/ppuskari/Okidata-Microline-82A-83A

## Next milestone

Run v0.1 on a physical 82A and 83A with the reconstructed OkiGraph I ROMs.

The first gate is the retained `ESC % 9 n` line-spacing command. If that
works as expected, the next source build can preserve the original 92/93
driver as type 5 and add **82A/83A OkiGraph I as a distinct printer type 10**.
