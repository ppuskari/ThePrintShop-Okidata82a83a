# The Print Shop – Okidata MICROLINE 82A/83A OkiGraph I Driver

Apple II printer-driver work for **Brøderbund The Print Shop v2**, targeting
the **Okidata MICROLINE 82A and 83A with OkiGraph I firmware**.

## Current status

**R19 single-fold-gap correction: CI-validated; hardware caliper validation is next.**

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

The hardware-good R11 graphics-byte conversion is:

```
logical = reverse7(source0 | source1)

normal logical byte -> send once
logical $03         -> send $03,$03
```

The doubled-ETX rule restores the historical Okidata type-5 literal-data
escape and eliminated the progressive horizontal column loss seen in earlier
builds.

## R19 single fold gap

The R18 hardware photo exposed the remaining interpretation error: the
`DUMP2` boundary is not the fold between the two complete printed card
panels.  In monochrome greeting-card output, each complete panel is rendered
by two 196-line pieces, so `DUMP2` occurs at the midpoint of the panel as
well as at its beginning.  Applying fine spacing there therefore created the
two visible horizontal seams in the printed artwork.

R19 keeps the R18 fine-spacing transport but moves the adjustments to the
actual geometry boundaries.

For the top-of-page correction, only the absolute first monochrome piece is
special-cased:

```text
SIDE = 1
PIECE = $C4 (196)
```

That first piece gets 4/144 inch of text-mode fine feed followed by the normal
single 15/144-inch native graphics feed, for 19/144 inch total.  Relative to
R16's two native graphics feeds (30/144 inch), the first printed border moves
up by exactly:

```text
11/144 inch = 1.940 mm
```

Every other `DUMP2` join remains zero-feed, so there is no inserted white
space in the middle of either complete card panel.

The true fold is the boundary between the two `DOALL` passes.  The first
complete panel is `SIDE=1`; the second is `SIDE=0`.  R19 changes the
existing `LF36` end-of-panel helper so that:

- end of `SIDE=1`: one 10/144-inch (1.764 mm) fine feed;
- end of `SIDE=0`: no extra feed.

The existing `DOALL9` X=12,Y=0 call immediately restores normal
24/144-inch text spacing after the fold feed.  Thus there is exactly one
added vertical gap per card, and it occurs only at the real fold between the
two complete panels.

Validated R19 overlays:

```text
PRCOMS.OKI
length 2043
SHA256 74ec82b69ed2ccce454a4db9e8c70eef46bb0dcbacba84227156025501967118

GCDRAW.OKI -> runtime DRAW1
length 2811
SHA256 eb2548a7b4cd55dd0456da6ab9bc7ebbc600a0c33d37ec5787dd00ed3fc93645

MENUS7.OKI
length 3018
SHA256 1562e1ad72c5660ade0ccda7ef9cfa439805ee35e96fc3a5a923096c7d37d485
```

The R14 TEST PAPER POSITION CR-only patch and all horizontal/raster behavior
remain unchanged.

## R18 card vertical spacing: rebase from R16

R17 is intentionally abandoned.  It changed the `X=12` boundaries inside
each rendered card panel, which inserted white space in the middle of both
panels and caused the output to run off the page.

R18 is rebased directly from the hardware-tested R16 branch and targets only
the two measurements requested for the next card test:

```text
top margin:       R16 - 11/144 inch
                  = R16 - 1.940 mm

between the two complete card panels:
                  +10/144 inch
                  = +1.764 mm
```

The 10/144-inch value is the nearest native `ESC % 9 n` spacing reachable
through Print Shop's X/72-inch interface to the requested 1.8-1.9 mm.

The important distinction is where the extra spacing is applied.  GCDRAW's
`DUMP2` entry occurs once at the beginning of each complete card panel.
R18 selects the first versus second complete panel from `SIDE` and `PIECE`
and changes that DUMP2 positioning only:

- first complete panel: `X=1,Y=2` -> two 2/144-inch fine feeds = 4/144 inch;
- second complete panel: `X=5,Y=1` -> one 10/144-inch fine feed.

The first physical raster that used two native 15/144-inch feeds in the R16
special case is reduced to the normal single 15/144-inch feed.  Therefore the
first-panel start changes from 30/144 inch to:

```text
4/144 fine positioning
+ 15/144 native OkiGraph raster feed
= 19/144 inch

30/144 - 19/144 = 11/144 inch = 1.940 mm upward
```

No R17-style substitution is made at the `X=12` boundaries within a panel.
Those boundaries retain their R16 physical distance.  Fine spacing is emitted
only after graphics mode has been exited; the next `SENDGC` re-enters
OkiGraph graphics mode.

The R14 TEST PAPER POSITION CR-only patch remains unchanged.

R18 is deliberately a greeting-card calibration build.  Signs and stationery
remain a later validation step after the card geometry is frozen.

Validated R18 overlays:

```text
PRCOMS.OKI
length 2043
SHA256 74ec82b69ed2ccce454a4db9e8c70eef46bb0dcbacba84227156025501967118

GCDRAW.OKI -> runtime DRAW1
length 2811
SHA256 309f7182240d896eefca1b0d1aeb3d6161eed77deba8b571e0595052d2045a13

MENUS7.OKI
length 3018
SHA256 1562e1ad72c5660ade0ccda7ef9cfa439805ee35e96fc3a5a923096c7d37d485
```

Validated R18 runtime image:

```text
size   143360 bytes
SHA256 7ea6fb104e2e5153f2ea7755e1fdadac65bb4c34150bde4ffcf8c9dccbd71048
```

## R16 first-card raster: two native OkiGraph feeds

With R15 aligned from the perforation-defined paper-position test, hardware
measurement put the top border dots at about 5.4 mm and the bottom border dots
at about 11.2-11.4 mm.  Centering that image requires roughly another 2.9-3.0
mm downward shift.  One native OkiGraph graphics feed is about 15/144 inch,
or 2.65 mm, so R16 tests exactly one additional native feed.

The first physical card raster now takes `CRLF X=0,Y=2` while graphics mode
is already active.  On the OkiGraph-specific PRCOMS path that produces two
native graphics advances before the first raster:

```text
$03 $0E
$03 $0E
```

Normal later rows still use `Y=1`, so their spacing is unchanged.  No text
line feed is restored.

To fit this without crossing the Print Shop application-data boundary at
`$8300`, the first-raster decision is written as a four-byte extension only:

```asm
R13FIRST LDA PIECE
 CLC
 ADC YMAX
 CMP #$88
 BNE ROW
 LDY #02
 BNE R16ROW
*
ROW LDX #00
 LDY #01
R16ROW JSR CRLF
ROW0 LDA COLORPR
```

On the first-pane condition, X is already zero from `LDX CREDBUF-1 / BEQ`,
so the special path can skip `LDX #00`.  `LDY #02` clears Z, making the
`BNE R16ROW` unconditional.  Other cases fall through the normal
`LDX #00 / LDY #01` row path.

The runtime DRAW1 DOS file has an existing 2816-byte on-disk allocation,
but four of those bytes are the DOS binary load/length header, so the maximum
payload that can be rewritten in place is 2812 bytes.  R16 therefore recovers
four bytes elsewhere instead of growing the file:

- the three R12 padding NOPs that replaced the removed startup `JSR LF36`
  are now omitted entirely; all labels are reassembled, so they are not needed
  for layout preservation;
- immediately after `INC CREDBUF-1`, `JMP ROW0` becomes `BNE ROW0`.
  That branch is guaranteed taken on this path because the preceding logic
  reaches it only when `CREDBUF-1` was 1, so the increment produces 2.

Those four bytes exactly pay for the R16 two-feed first-raster logic.  The
assembled GCDRAW/DRAW1 payload remains 2812 bytes and still fits the existing
DOS allocation without reallocating sectors.  PRCOMS, MENUS7, source-row
resampling, fold and inter-piece geometry, graphics escaping, and the R14
CR-only paper-position patch are unchanged.

## R15 first-card raster: one native OkiGraph feed

The perforation-aligned R14 paper-position test removed the remaining setup
ambiguity.  Hardware comparison showed that the current zero-feed first raster
starts slightly too high, while one manual normal line feed starts clearly too
low.

R15 changes only the R13 first-physical-card-raster branch.  When the
`PIECE + YMAX = $88` first-pane condition is true, execution now goes through
the existing `ROW` path instead of skipping directly to `ROW0`:

```asm
; R13
CMP #$88
BEQ ROW0

; R15
CMP #$88
BEQ ROW
```

For printer type 5, graphics mode has already been entered by `SENDGC`.
The existing `ROW` call uses `CRLF X=0,Y=1`, which the OkiGraph-specific
PRCOMS path implements as exactly one native graphics feed:

```text
$03 $0E
```

That is the roughly 15/144-inch startup shift we want to test.  No normal
text LF is restored.  PRCOMS, graphics escaping, source-row resampling, later
raster feeds, fold spacing, inter-piece positioning, and the R14 CR-only paper
alignment patch are unchanged.

The source edit is length-preserving: the assembled GCDRAW/DRAW1 overlay
remains 2812 bytes and only the relative branch target changes.

## R14 TEST PAPER POSITION: carriage return only

The original Print Shop `TEST PAPER POSITION` path prints its horizontal
alignment dots and then advances the paper.  Source/runtime tracing shows that
DRAW5 menu option 2 calls SYSLIB through `$8803`.  SYSLIB's routine at
`$88CC` ends at `$88FA` with:

```asm
INX
LDY #$01
JMP $1803       ; PRCOMS CRLF
```

That final jump is the unwanted carriage-return/line-feed operation.  R14
changes only that six-byte epilogue, leaving the dot pattern, printer driver,
and every normal print-path CR/LF untouched:

```asm
LDA #$0D
JMP $1800       ; raw printer character output: CR only
NOP             ; length-preserving runtime patch
```

Runtime bytes at `SYSLIB $88FA`:

```text
original  E8 A0 01 4C 03 18
R14       A9 0D 4C 00 18 EA
```

The runtime builder refuses to apply the patch unless SYSLIB loads at
`$8800` and the exact six historical bytes are present.  It then rereads
SYSLIB through the DOS T/S chain and verifies the complete patched payload.
This makes repeated paper-position tests return the carriage to column zero
without changing the paper's vertical position, so the operator can
micro-adjust the fanfold paper and run the test again.

## R13 first-pane top alignment

R13 keeps the hardware-good R11 OkiGraph driver and the R12 common startup
`LF36` removal unchanged.  Hardware testing of R12 showed one remaining
full first-row feed before the physically first greeting-card pane when the
paper top is aligned with the top print-head pin.

The first inside-card pass satisfies `PIECE + YMAX = 392` for both
monochrome and color, so R13 uses that geometry to suppress only that first
`ROW` CRLF while `CREDBUF-1` is still in its initial state.  The existing
outside-card first-row suppression, all later raster-row feeds, fold spacing,
and inter-piece positioning remain unchanged.

Validated R13 runtime image:

```
size   143360 bytes
SHA256 3eef3ef4660483bce6681f939fc3f1409ac533319efc9d332407e0c57c152bc1
```

Validated R13 overlays:

```
PRCOMS.OKI
length 2039
SHA256 7c6072a2186d09fb911eaf16abccc0cf3238ef8aa2e9f2575f167050f4a61137

MENUS7.OKI
length 3018
SHA256 1562e1ad72c5660ade0ccda7ef9cfa439805ee35e96fc3a5a923096c7d37d485

GCDRAW.OKI -> runtime DRAW1
length 2812
SHA256 2c37296b3e8d4bdad9170c0b56be91cc29925a9089e975d406efb2e9643e8bf9
```

## R12 common startup-feed cleanup

R12 keeps the hardware-good R11 OkiGraph driver unchanged and modifies only
the common greeting-card/sign drawing overlay.

Historical `GCDRAW` begins the print job with:

```
JSR LF36
```

before the drawing path performs its own first-row positioning.  That produces
two stacked startup vertical motions and affects every printer type using the
same base program path, including Epson, DMP/ImageWriter, ImageWriter II, and
Okidata.

R12 replaces only that initial three-byte `JSR LF36` with three `NOP`
instructions.  End-of-job, fold, and inter-piece positioning remain unchanged.

Validated R12 runtime image:

```
size   143360 bytes
SHA256 4259a5e98464f32e1aec691ae3365d21e471ceb585a12ee5ec54be4b8175ac0d
```

Validated R12 overlays:

```
PRCOMS.OKI
length 2039
SHA256 7c6072a2186d09fb911eaf16abccc0cf3238ef8aa2e9f2575f167050f4a61137

MENUS7.OKI
length 3018
SHA256 1562e1ad72c5660ade0ccda7ef9cfa439805ee35e96fc3a5a923096c7d37d485

GCDRAW.OKI -> runtime DRAW1
length 2807
SHA256 46a9e2c6777a4da7d96cceabdbb5c7246421067bf2b529410a99bb9b0e406011
```

## R11 horizontal-stream test

R11 keeps the R10/R9A geometry and changes only the type-5 graphics-data
escaping. The historical Oki type-5 path emits seven-bit graphics bytes
directly and doubles a literal ETX (`$03`) as `$03,$03`. Earlier OkiGraph
builds forced bit 7 instead (`$83`), which is now under hardware test as a
possible source of mid-row column loss if the printer parser treats graphics
data as seven-bit.

Validated R11 runtime image:

```
size   143360 bytes
SHA256 1a40ea0430d472635279ff1bc9a3125e64def52ef0973f02ad1d19532884f830
```

Validated R11 PRCOMS overlay:

```
length 2039
SHA256 7c6072a2186d09fb911eaf16abccc0cf3238ef8aa2e9f2575f167050f4a61137
```

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

Current R13 validated image:

```
size   143360 bytes
SHA256 3eef3ef4660483bce6681f939fc3f1409ac533319efc9d332407e0c57c152bc1
```

R6 was physically validated and was the closest result yet: the total vertical
size was within roughly half an inch, but literal control-sequence fragments
still appeared at the start/midpoint/end, several border motifs lost their
lower portion near the right edge, and two card quadrants showed localized
raster corruption.

The R6 sheet proved that the inherited ML92/93 `ESC % 9 n` sequence must not
be used on this OkiGraph-I path. R7 removes it completely and returns to the
hardware-proven R5 continuous-graphics core. Type-5 state is initialized when
the printer is selected. Normal in-graphics rows remain `$03 $0E`; X=12
boundary motion uses ordinary 1/6-inch LF; and Print Shop's X=2 LF36 helper is
suppressed rather than being incorrectly expanded to a full LF.

Greeting-card source tracing also confirmed that GCDRAW uses fixed even
`SENDGC` sizes (`$0200`/`$0400`), so the observed right-edge card defect
is not caused by variable blank trimming or an odd transaction count.

Validated R7 overlays:

```
PRCOMS.OKI
length 2034
SHA256 a960e7c6a92003f4a7cc42dda5db75b433d75abb4adfb30d40bc30c156f68124

MENUS7.OKI
length 3018
SHA256 1562e1ad72c5660ade0ccda7ef9cfa439805ee35e96fc3a5a923096c7d37d485
```

PRCOMS remains entirely below the Apple II `$2000` boundary.

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

Validate the R7 disk on the physical 82A/83A. The specific targets are removal
of the stray control/text output at graphics transitions, elimination of the
extra vertical gap between seven-dot bands, and restoration of one-page layout.

If R3 validates the corrected carriage-return and native graphics-feed path,
the next source build can preserve the original 92/93 driver as type 5 and add
**82A/83A OkiGraph I as a distinct printer type 10**.
