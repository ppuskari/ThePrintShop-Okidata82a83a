# Hardware validation plan

## R9 target

- Apple II / IIe-class Print Shop v2 environment
- Okidata MICROLINE 82A or 83A with validated OkiGraph I ROMs
- current repository R9 runtime disk
- normal Apple II printer interface path; R8 does not change the interface-card
  layer

Build:

```powershell
.\scripts\Build-RuntimeDisk.ps1
```

Expected image:

```
build-runtime\PrintShop-Okidata82a83a-OkiGraphI.dsk
143360 bytes
SHA256 29d2eae0d4f0eb3c221be125fc705b2cbcbcbef104fabefb990b3525a642d08d
```

## Gate 1 - top-of-page first raster

Physically place the desired top graphics pin at the intended top raster
baseline before starting the Print Shop output.

R8/R9 are specifically designed so the first outside-card DUMP does **not**
advance the paper before its first raster row.

Confirm:

- no startup LF before the first graphics row;
- no visible `%9` or other control-string garbage;
- the first border/raster begins at the physical baseline selected by the
  operator.

## Gate 2 - THINKING -> PRINTING piece boundary

Use the same Season's Greetings card used for R7.

R7 showed a repeatable small vertical discontinuity when the application
changed from THINKING back to PRINTING. The screen routines themselves do not
touch the printer; source tracing located the boundary inside GCDRAW/DRAW1.

R9 should produce one native graphics feed at later DUMP starts, exactly like
ordinary in-piece band stepping.

Confirm whether the repeated micro-gap:

- disappears;
- remains but changes size; or
- moves to a different boundary.

A photograph that includes the whole sheet plus a close-up of the discontinuity
is useful.

## Gate 3 - vertical scale

Do not use or test `ESC % 9 n`: physical R6 testing already showed that this
legacy ML92/93 sequence is not valid on the 82A/83A OkiGraph-I path and can
print literal command bytes.

Measure from the first raster baseline to the corresponding expected endpoint.

Known pitch mismatch:

```
Print Shop nominal band = 14/144 inch
OkiGraph native feed    = 15/144 inch
ratio                   = 15/14 = 1.071428...
```

Therefore about 7.1% vertical stretch is expected even when all accidental
extra feeds are gone. Record the actual measured error; that measurement will
drive a later source-row resampling build.

## Gate 4 - persistent raster/motif defect

Inspect the known problem areas from R7:

- the right end of the upper border where several lower motif halves disappear;
- the corresponding lower/right border region;
- the localized line/column corruption in the card quadrants.

GCDRAW source tracing has already ruled out two simple causes for this card:

- SENDGC counts are fixed and even (`$0200`/`$0400`);
- the defect is not caused by trailing-blank trimming.

If R8 changes these defects, the cause was tied to the DUMP graphics-state
boundary. If they remain identical, the next investigation should focus on
the forward/reverse raster loops, RHALF blank insertion, and exact wire bytes
around the affected columns.

## Gate 5 - application coverage

After greeting-card output is stable, exercise:

- Sign
- Letterhead
- Banner

Those paths share PRCOMS but do not all use the newly patched greeting-card
DRAW1/GCDRAW boundary logic, so they are useful controls.

## Capture with each run

Record:

- exact disk SHA256;
- 82A or 83A;
- OkiGraph ROM revision/set;
- Apple II model and printer interface;
- physical top-of-page alignment;
- first-raster startup movement;
- location/size of any THINKING -> PRINTING micro-gap;
- total measured vertical size/error;
- close-up of the missing motif region; and
- any carriage-position or graphics-state anomaly.


## R9 vertical resampling gate

For the monochrome type-5 greeting-card path, R9 changes each historical
28-band piece into 26 output bands. Fourteen individual source rows are
skipped in a distributed pattern; no complete seven-row source band is
discarded.

Check:

- total card height compared with the R8 sheet;
- top and bottom border alignment on 8.5 x 11 paper;
- whether the fold-over gap remains correct;
- whether any new horizontal discontinuity appears at the distributed
  single-row resample points;
- whether the existing right-edge missing-motif and localized raster defects
  change or remain identical.

The expected geometric change from R8 is approximately 14/15 in the
card-piece vertical dimension. The first and final source rows are preserved.
