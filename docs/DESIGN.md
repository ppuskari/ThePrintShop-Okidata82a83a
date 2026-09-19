# Driver design: Print Shop v2 + OkiGraph I

## Goal

Add native Apple II **The Print Shop v2** output for the Okidata
MICROLINE 82A and 83A equipped with the **OkiGraph I** ROM option.

The first implementation deliberately minimizes risk by repurposing the
existing Print Shop **printer type 5**, which is the original
"OKIDATA MICROLINE 92,93" driver.

## Source provenance

The historical source used for interface discovery is the three-disk
Brøderbund Print Shop v2 source snapshot dated 1987-01-26 on the Asimov
Apple II archive:

- The Print Shop V2.0 source code 1987-01-26 disk 1 of 3
- The Print Shop V2.0 source code 1987-01-26 disk 2 of 3
- The Print Shop V2.0 source code 1987-01-26 disk 3 of 3

The source itself is not redistributed by this repository.  The inspection
and patch tools download it when requested.

OkiGraph I protocol behavior is taken from the independently reconstructed
firmware work in:

https://github.com/ppuskari/Okidata-Microline-82A-83A

## What Print Shop already gives us

The original v2 source has a clean printer abstraction in `PRCOMS.S`.
The fixed entry table begins at `$1800` and includes:

- character output
- carriage-return/line-feed handling
- graphics-mode setup
- graphics-byte output
- printer-ready handling

All major Print Shop drawing paths call those entry points rather than
talking directly to a particular printer.

The drawing code also builds graphics in seven-scanline batches.  That is a
natural match for OkiGraph I's seven host-addressable print pins.

Printer type 5 is especially useful:

1. its menu entry is the MICROLINE 92/93;
2. its graphics setup enters Okidata graphics with ETX (`$03`);
3. its graphics output merges pairs of source columns, reducing the
   Print Shop 120-column/inch stream to a 60-column/inch Oki stream;
4. it reverses the lower seven bits before output, matching the Okidata
   top-pin bit convention;
5. it ends graphics with `$03 $02`; and
6. its line-spacing path expresses Print Shop's X/72-inch request as
   Okidata `ESC % 9 n`, with `n = 2*X` (1/144-inch units).

That is close enough to the 82A/83A OkiGraph I protocol that a first driver
does not need a new rasterizer.

## OkiGraph I wire conversion

For each pair of Print Shop source columns `a,b`:

```
merged = (a | b) & $7F
wire   = $80 | reverse7(merged)
```

The high bit is intentionally forced on every graphics-data byte.

The reconstructed 82A/83A OkiGraph I behavior uses only bits 0..6 for the
seven pins.  Keeping bit 7 set therefore leaves dot data unchanged while
ensuring a graphics byte can never equal ETX (`$03`) and be mistaken for a
command prefix.

A graphics transaction remains:

```
$03
<data bytes, all $80..$FF>
$03 $02
```

## v0.1 patch strategy

v0.1 **repurposes printer type 5** rather than adding a tenth printer.

This is intentional.  It proves the physical printer path with the smallest
possible change before expanding the UI and dispatch tables.

Two source changes are made:

### MENUS7.S

The 23-character original type-5 label is replaced with another
23-character label:

```
OKI 82A/83A OKIGRAPH I<space>
```

Keeping the same length avoids moving subsequent menu data.

### PRCOMS.S / GC5

The legacy 92/93 path handled a possible raw graphics value of `$03` by
special-casing it.  The OkiGraph I variant instead sets bit 7 before output.

The replacement is designed to assemble to the **same 20 bytes** as the
original affected block.  Five NOPs occupy the bytes freed by removing the
legacy ETX-data escape.  As a result, labels and code following the block do
not move.

This is a deliberate safety property, not an optimization target.

## Line spacing

v0.1 retains Print Shop's original type-5 line-spacing path:

```
ESC % 9 n
n = 2 * X
```

where Print Shop supplies `X` in 1/72-inch units.

This is the first hardware-validation gate.  If the reconstructed OkiGraph I
ROMs accept the same Okidata programmable-spacing command, Print Shop's
existing vertical-layout calculations remain untouched.

If hardware testing shows that this command is not accepted by the 82A/83A
OkiGraph I ROM, v0.2 will add a type-5-specific CR/LF adapter instead of
changing any drawing code.

## Why not add printer type 10 immediately?

A separate selector is the desired end state because it preserves original
MICROLINE 92/93 support.  It also requires touching:

- printer-menu bounds and storage,
- SENDGC dispatch,
- GCOUT1 dispatch,
- SETLF dispatch, and
- the printer-name list.

None of that is necessary to answer the first and most important question:
does the existing Okidata raster path drive the physically validated
82A/83A OkiGraph I ROMs correctly with high-bit-safe graphics data?

Once v0.1 passes on hardware, restoring 92/93 as type 5 and adding
82A/83A OkiGraph I as a distinct type 10 is straightforward.

## Validation in this repository

`src/driver_model.py` is an executable wire-level model.

`tests/test_driver_model.py` verifies:

- seven-bit reversal;
- 120-to-60 column collapse;
- bit 7 is always set on graphics data;
- the old raw-`$03` collision becomes `$83`;
- graphics transaction framing; and
- the retained type-5 line-spacing encoding.

`tools/patch_printshop_source.py --check` validates that the patch applies
exactly once to the historical source snapshot and that both
layout-preserving invariants remain true.
