# The Print Shop – Okidata MICROLINE 82A/83A OkiGraph I Driver

Apple II printer-driver work for **Brøderbund The Print Shop v2**, targeting
the **Okidata MICROLINE 82A and 83A with OkiGraph I firmware**.

## Current status

**R6 executable disk build: implemented and CI-validated; physical printer validation is next.**

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

That establishes a compatible runtime base for this source snapshot.

To build the actual runnable disk on Windows:

```powershell
.\scripts\Build-RuntimeDisk.ps1
```

It creates:

```
build-runtime\PrintShop-Okidata82a83a-OkiGraphI.dsk
```

Current R6 validated image:

```
size   143360 bytes
SHA256 09122e40e8baead48a86d35f348532e6298efa0a1f573f68eb5f4b89b62913e0
```

R5 was the closest hardware result yet: continuous OkiGraph state across normal
seven-dot bands made most border motifs contiguous and stopped the runaway
carriage behavior. The remaining sheet showed stale control bytes before the
welcome text, incomplete right-edge motifs/corruption, and excessive spacing
at the card/page-half reposition.

R6 keeps the R5 continuous-graphics band path but adds deterministic state
initialization when printer type 5 is selected. It also caches Print Shop's
requested X spacing in 1/144-inch units and uses `ESC % 9 n` as the direct
vertical movement for text/boundary reposition calls, with no extra LF.
Normal in-graphics row advances remain native `$03 $0E`.

Validated R6 overlays:

```
PRCOMS.OKI
length 2042
SHA256 d1cd460b9d8a6660395ed868e72c830437c3fe8e4a4a96ed63977e394ec07c90

MENUS7.OKI
length 3022
SHA256 6c35e2f9b1771c35a41f5686e1079d32f08d70bd75470f7f565c96c5fddb8bf8
```

PRCOMS remains entirely below the Apple II $2000 boundary.

The script uses an installed Merlin32 if available; otherwise it downloads
the pinned v1.1.10 Windows build. It verifies the original runtime overlays
against the control build before changing the disk, then rewrites only
`PRCOMS` and `MENUS7` through their existing DOS T/S chains and verifies
both files after read-back.

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
- `tools/build_runtime_disk.py` — verified executable disk construction
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

Validate the R6 disk on the physical 82A/83A. The specific targets are removal
of the stray control/text output at graphics transitions, elimination of the
extra vertical gap between seven-dot bands, and restoration of one-page layout.

If R3 validates the corrected carriage-return and native graphics-feed path,
the next source build can preserve the original 92/93 driver as type 5 and add
**82A/83A OkiGraph I as a distinct printer type 10**.
