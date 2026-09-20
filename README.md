# The Print Shop – Okidata MICROLINE 82A/83A OkiGraph I Driver

Apple II printer-driver work for **Brøderbund The Print Shop v2**, targeting
the **Okidata MICROLINE 82A and 83A with OkiGraph I firmware**.

## Current status

**R8 executable disk build: implemented and CI-validated; physical printer validation is next.**

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

## Driver evolution

The initial v0.1 patch was deliberately layout-preserving and proved the
graphics-data path on real hardware.  R3 keeps the fixed `PRCOMS` jump table
at `$1800`, leaves Print Shop's printer-interface-card code untouched, and
retains the proven high-bit-safe raster conversion.  The type-5 CR/LF control
path is now OkiGraph-specific because hardware testing disproved reuse of the
legacy ML92/93 spacing sequence.

The assembly/control notes are in [`src/OKI8283.S`](src/OKI8283.S).

## Runnable disk build

The historical sources now assemble into real executable overlays with
Merlin32. An untouched control build was compared against the archived
`ColorPrintShop.DSK` runtime:

- `PRCOMS`: 1,962 bytes, exact byte-for-byte match, load address `$1800`
- `MENUS7`: 3,014 bytes, exact byte-for-byte match, load address `$6300`
- `DRAW1`: 2,737 bytes, exact byte-for-byte match to historical
  `GCDRAW.S`, load address `$7800`

That establishes a compatible runtime base and proves the source-to-runtime
alias `GCDRAW.S -> DRAW1`.

To build the actual runnable disk on Windows:

```powershell
.\scripts\Build-RuntimeDisk.ps1
```

It creates:

```
build-runtime\PrintShop-Okidata82a83a-OkiGraphI.dsk
```

Current R8 validated image:

```
size   143360 bytes
SHA256 fc0c54c0d457845e27cc259429e36ce1604684df6bb22eabbe63f270669de92b
```

R7 physical testing established that the remaining repeatable micro-feed
occurs at the greeting-card piece boundary correlated with the on-screen
`THINKING -> PRINTING` transition. Source tracing showed that the screen
routines themselves do not touch the printer. The cause is inside `DUMP`:
each piece performs an `X=7,Y=0` setup and then an `X=0,Y=1` first-row
advance.

R8 keeps the proven R7 continuous-graphics PRCOMS path and patches the actual
greeting-card/sign runtime overlay. The historical `GCDRAW.S` control build
was proven byte-for-byte identical to runtime `DRAW1`
(`$7800`, 2737 bytes), so the disk builder now verifies and patches that
third executable overlay as well.

R8 enters OkiGraph graphics immediately after each DUMP setup. On the first
outside-card DUMP it skips the historical first-row vertical feed so raster
output begins at the physical print-head position. On later pieces the first
row receives one native `$03 $0E` feed, matching normal in-piece bands rather
than the ordinary text LF that caused the visible boundary jump.

Validated R8 overlays:

```
PRCOMS.OKI
length 2034
SHA256 a960e7c6a92003f4a7cc42dda5db75b433d75abb4adfb30d40bc30c156f68124

MENUS7.OKI
length 3018
SHA256 1562e1ad72c5660ade0ccda7ef9cfa439805ee35e96fc3a5a923096c7d37d485

GCDRAW.OKI -> runtime DRAW1
length 2762
SHA256 c9d6a4f1242dbcae8f1bb6a3fe5b0445313521d1781baffbe6211b9abee324f8
```

The original runtime DRAW1 control is 2737 bytes with SHA256
`cfa548eb4f950156c14639372f2681edbaa810e86f0945d73c24e0304e436353`.
The expanded R8 overlay still fits its existing DOS allocation and remains
below the application data beginning at `$8300`.

A separate dimensional issue remains intentionally exposed: Print Shop's
nominal seven-row pitch is 14/144 inch while the firmware-backed native
OkiGraph feed is 15/144 inch. That predicts roughly 7.1% vertical stretch and
matches the remaining 1/2-3/4 inch hardware observation. R8 isolates the
piece-boundary error first; source-row resampling can address the scale after
this build is measured.

The script uses an installed Merlin32 if available; otherwise it downloads
the pinned v1.1.10 Windows build. It verifies the original runtime overlays
against the control build before changing the disk, then rewrites only `PRCOMS`, `MENUS7`, and verified runtime `DRAW1/GCDRAW` through their existing DOS T/S chains and verifies all three files after read-back.

See [`docs/EXECUTABLE-BUILD.md`](docs/EXECUTABLE-BUILD.md) for the complete
reproducibility and validation record.

## Build / validate on Windows

From the repository root:

```powershell
.\scripts\Build-DriverSource.ps1
```

That performs the wire-model unit tests, checks the patch against the actual
1987 Print Shop v2 source snapshot, and produces decoded patched source plus
a complete three-disk local source set:

```
build\PRCOMS.OKI.S
build\MENUS7.OKI.S
build\PrintShop-V2-OkiGraph-source-1.dsk
build\PrintShop-V2-OkiGraph-source-2.dsk
build\PrintShop-V2-OkiGraph-source-3.dsk
```

Equivalent individual commands:

```powershell
py -3 -m unittest discover -s tests -v
py -3 tools\patch_printshop_source.py --check
py -3 tools\patch_printshop_source.py --output-dir build --output-disks build
```

Source disks 1 and 2 contain the rewritten files; source disk 3 is copied
unchanged so the build directory contains a complete set. The historical
Brøderbund source and generated disk images are **not committed to this repository**.

## Validation status

GitHub Actions currently verifies:

- seven-bit reversal;
- 120-to-60 column conversion;
- bit 7 set on every graphics-data byte;
- the legacy raw-`$03` collision becomes `$83`;
- OkiGraph transaction framing;
- R3 text and graphics CR/LF framing, including the mandatory Y=0 carriage return; and
- exact applicability of the source patch to the 1987-01-26 source disks;
- DOS source-disk rewrite/read-back through the original T/S chains;
- untouched Merlin32 control overlays against the shipped runtime;
- patched executable overlay sizes and hashes;
- in-place runtime-disk replacement with preserved load addresses; and
- the complete Windows build producing a deterministic 143,360-byte `.dsk`.

## Repository map

- `src/OKI8283.S` — 6502 assembly integration fragment
- `src/driver_model.py` — executable wire-level model
- `tools/patch_printshop_source.py` — source transformation
- `tools/prepare_merlin32_build.py` — Big Mac-to-Merlin32 build preparation
- `tools/validate_overlay_build.py` — control/patched executable verification
- `tools/build_runtime_disk.py` — verified executable disk construction, including GCDRAW -> DRAW1
- `tools/inspect_printshop_source.py` — reproducible historical-source scanner
- `tests/test_driver_model.py` — regression tests
- `docs/DESIGN.md` — source/driver architecture and design decisions
- `docs/EXECUTABLE-BUILD.md` — executable overlay/runtime-disk build record
- `docs/HARDWARE-TEST.md` — staged 82A/83A physical validation plan
- `scripts/Build-DriverSource.ps1` — source-disk build helper
- `scripts/Build-RuntimeDisk.ps1` — one-command executable `.dsk` build

## Source basis

Print Shop v2 interface discovery uses the three-disk source snapshot dated
**1987-01-26** from the Asimov Apple II archive.

OkiGraph I protocol behavior is based on the independent ROM reconstruction
and hardware work in:

https://github.com/ppuskari/Okidata-Microline-82A-83A

## Next milestone

Validate R8 on the physical 82A/83A with the head aligned to the intended
top-of-page raster baseline. Confirm that the first graphics row no longer
advances the paper and that the repeatable THINKING -> PRINTING piece-boundary
micro-step is gone. Then measure the remaining vertical scale error and inspect
whether the persistent right-edge motif/raster corruption changed.

After the boundary behavior is isolated, the next likely vertical-scale step
is source-row resampling to compensate for the proven 15/144-inch native
OkiGraph feed versus Print Shop's nominal 14/144-inch band pitch.
