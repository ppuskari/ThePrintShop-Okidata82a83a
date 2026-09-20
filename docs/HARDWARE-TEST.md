# Hardware validation plan

## Target

- Apple II / IIe-class Print Shop v2 environment
- Okidata MICROLINE 82A with physically validated OkiGraph I ROM set
- Okidata MICROLINE 83A with physically validated OkiGraph I ROM set
- whichever Apple II printer interface is actually connected; the v0.1
  driver does not alter Print Shop's interface-card layer

## Prepare the runnable disk

From the repository root:

```powershell
.\scripts\Build-RuntimeDisk.ps1
```

Use this image for emulator and physical-machine testing:

```
build-runtime\PrintShop-Okidata82a83a-OkiGraphI.dsk
```

The current validated build is 143,360 bytes with SHA-256:

```
947e0929d894d6cc47aad760098c4b92e49b5796d939795b2a29f8a58e49d2f8
```

The build performs an untouched control assembly before constructing the
runtime. It verifies that the base disk's `PRCOMS` and `MENUS7` are exact
matches for those control binaries, then installs the OkiGraph versions at
their original load addresses (`$1800` and `$6300`) without reallocating
their DOS files.

The older source-only workflow remains available through
`scripts\Build-DriverSource.ps1`, but those source disks are development
inputs rather than the executable hardware-test artifact.

## Gate 1 - direct line-spacing behavior

Before spending time on a full Print Shop print, verify the retained Okidata
type-5 spacing command on the 82A/83A OkiGraph I ROM:

```
ESC % 9 $0E
LF
```

`$0E = 14/144 inch = 7/72 inch`, which is a common Print Shop seven-row
advance request.

Confirm that the paper advance is repeatable and that the command does not
print visible garbage or disturb graphics state.

Also exercise at least:

- `n=$04` (2/72 inch)
- `n=$0E` (7/72 inch)
- `n=$18` (12/72 inch)

If this gate fails, stop there; the raster conversion can remain unchanged
and the next build will replace only the type-5 CR/LF implementation.

## Gate 2 - command/data collision pattern

Print a pattern that deliberately generates the old raw graphics value
`$03`.

The model test uses a source pair whose merged seven-bit value is `$60`.
After Print Shop's seven-bit reversal, the legacy driver would have produced
`$03`.  v0.1 must place `$83` on the wire instead.

Expected result:

- no unexpected exit from graphics mode;
- no command execution in the middle of a row;
- no missing or shifted columns.

## Gate 3 - simple graphics

Use a simple Print Shop item with:

- a solid vertical edge;
- alternating one-column detail;
- blank areas;
- a diagonal; and
- a filled region.

Check for:

- correct top-to-bottom pin orientation;
- no seven-bit inversion;
- no doubled/missing horizontal columns;
- clean return to text/control mode after each graphics row.

## Gate 4 - dimensional check

OkiGraph I is a 60-column/inch graphics path.

For the 82A, the reconstructed native line capacity is 480 graphics columns
(8.0 inches).  For the 83A it is 792 columns (13.2 inches).

Print Shop itself may choose a narrower design area, so this gate is about
scale rather than forcing the application to consume the entire carriage.

Measure a known-width graphic.  Two Print Shop 120-cpi source columns should
collapse into one 60-cpi Oki column.

## Gate 5 - application coverage

After a basic card/sign succeeds, exercise at least one output from each
major path:

- Sign
- Greeting Card
- Letterhead
- Banner

The original source routes these through the same `SENDGC`, `GCOUT1`,
and `CRLF` abstraction, but this catches assumptions in individual drawing
modules.

## What to capture from the first run

For each printer:

- 82A or 83A
- OkiGraph I ROM set/revision
- Apple II model
- printer interface card and slot
- Print Shop build/source snapshot
- pass/fail for spacing gate
- photograph or scan of the test pattern
- measured horizontal width
- measured vertical band spacing
- any point where graphics unexpectedly returns to text mode

Those observations will decide whether v0.2 is simply the separate type-10
UI integration or whether CR/LF needs an 82A/83A-specific implementation.
