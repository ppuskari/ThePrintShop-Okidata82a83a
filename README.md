# The Print Shop – Okidata MICROLINE 82A/83A OkiGraph I Driver

Apple II printer-driver work for **Brøderbund The Print Shop v2**, targeting
the **Okidata MICROLINE 82A and 83A with OkiGraph I firmware**.

## Current status

**R21 greeting cards, R26 signs, and R27 stationery are hardware-golden; R29 isolates banner text/icon geometry fixes inside DRAW4.**

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

## R30 banner text: true native-row densification

R30 keeps the hardware-good R29 banner-icon geometry byte-for-byte and
replaces only the banner-text spacing approximation with real raster-row
replay.

The source audit proved that BSTR builds each current font row into `IBUF`,
then STRSUB/BSTR9..BSTR12 transmits that row, and only after STRSUB returns do
BSTR13/BSTR15 advance `BITCNT` and `SADDR`. R30 therefore reuses the
already-built `IBUF` row instead of reconstructing or rewinding font data.

The exact shipped DRAW4 remains the address basis:

```text
load              $7800
original payload  1012 bytes
BSTR6              +$0085
STRSEND            +$00B7, 37 bytes
STRSUB             +$00FF
BICON2             +$02BE
```

R30 makes three fixed-size changes:

1. **BSTR6 stays historical.** `LDX #0 / LDY #1 / JSR CRLF` is left
   untouched. Once type-5 graphics is active this is the proven native
   OkiGraph `$03,$0E` 15/144-inch feed.
2. **STRSUB is monomorphized for the monochrome Oki path.** The historical
   `COLOR=0` calculation yields `RBTEMP=$FE`; R30 sets that value directly
   and jumps to BSTR9. The five now-unreachable bytes at `$7906` become a
   private row-feed entry: `LDX #0 / JMP CRLF`.
3. **STRSEND's 37-byte color wrapper is replaced in place.** Every nonblank
   source row is sent once. Selected rows are then advanced by one native
   feed and the exact same `IBUF` raster is sent a second time.

Duplicate selection uses existing immutable source position, not a private
phase variable:

```text
BITCNT 8  -> duplicate
BITCNT 5  -> duplicate
BITCNT 2  -> duplicate except when (SADDR & 3) == 2
```

Across four complete eight-row source groups this produces:

```text
32 source rows
11 duplicate rows
43 physical rows

43 * 15/144 = 645/144 inch
historical target:
32 * 20/144 = 640/144 inch

geometry error = +0.78125%
```

A selected all-blank source row never enters STRSEND and is therefore not
replayed. That deliberately keeps blank regions tighter; it does not alter the
future schedule because selection derives directly from `BITCNT/SADDR`.

The R29 icon patch and its EOF helper at `$7BF4-$7BFB` are unchanged. No
existing address moves, no DOS sector is allocated, the VTOC/T/S lists remain
untouched, and resident SYSLIB remains 4773 bytes.

Validated R30 runtime:

```text
DRAW4
length  1020
RAM     $7800-$7BFB
packed  1024/1024
SHA256  4360a87c4663b50aad99c6a5f7fca75f997d3b23ff8e73bd3f783619f9d03235

runtime disk
size    143360
SHA256  2e5ab070988b3b36df0072577c2ebf57c61cf616551a0ef10c88f3cac0db387f
```

R30 remains an Oki/type-5 banner hardware-test branch. Cards, signs, and
stationery continue to use the frozen R21/R26/R27 paths.

## R29 banner: in-place DRAW4 geometry correction

R29 rebases directly from the hardware-good R27 runtime and deliberately
avoids every memory/allocation mechanism that destabilized the rejected R28
experiments.

The runtime basis is the exact shipped DRAW4 binary:

```text
load    $7800
length  1012
SHA256  787a97a6b6441724da019edf6ec586df3cf56acc61047db0b402553ac03699e4
```

DRAW4 already owns four 256-byte DOS data sectors. Its four-byte DOS binary
header plus 1012-byte payload consumes 1016 of those 1024 bytes, leaving
exactly eight bytes after EOF in the existing allocation. R29 makes those
eight bytes loadable and uses them as one shared helper:

```text
$7BF4  F0 02       BEQ icon_merge
$7BF6  A2 01       LDX #1
$7BF8  CA          DEX
$7BF9  4C 03 18    JMP $1803       ; original PRCOMS CRLF
```

The final DRAW4 payload is exactly 1020 bytes:

```text
DOS header  4
payload  1020
total    1024 bytes = original four-sector allocation exactly
RAM      $7800-$7BFB
```

No existing DRAW4 address moves. No sector is allocated. The VTOC and T/S
list are untouched. Resident SYSLIB remains at its historical 4773-byte
length with only the already-proven R14 TEST PAPER POSITION patch.

### Banner text state

The historical BSTR6 seven-byte sequence is replaced in-place, length for
length:

```asm
LDX BITCNT          ; $58, Print Shop state 8..1
LDY #1
JSR $7BF8           ; DEX / JMP CRLF
```

This maps BITCNT 8..1 to X=7..0. Under the frozen R27 type-5 CRLF behavior,
an eight-slice group advances:

```text
6 ordinary one-line feeds  = 6 x 24/144
X=2 zero-feed merge        = 0
X=0 native OkiGraph feed   = 15/144
total                      = 159/144

historical target          = 8 x 20/144 = 160/144
error                      = -0.625%
```

There is no new phase variable; Print Shop's existing BITCNT is the state.

### Banner icon state

The historical eleven-byte BICON2 sequence is also replaced in-place,
length for length:

```asm
LDX #3
LDY #1
LDA XCUR            ; $54
AND #7
JSR $7BF4
```

JSR preserves the Z flag from AND #7. At the helper, every XCUR multiple of
eight keeps X=3 and the shared DEX maps it to X=2, producing a zero-feed
overstrike. All other slices first become X=1 and DEX maps them to X=0,
producing one native 15/144-inch OkiGraph feed.

Across the 88-slice icon:

```text
11 zero-feed merges
77 native feeds
77 x 15/144 = 1155/144 inch

historical target = 88 x 13/144 = 1144/144 inch
error             = +11/144 inch = +1.94 mm (+0.96%)
```

The two hook locations are verified uniquely against the exact shipped
DRAW4 byte patterns before patching, and the builder proves no pre-existing
byte outside those two fixed ranges changes.

R29 is intentionally an **Oki/type-5 banner hardware-test branch**. The
fixed-size DRAW4 hook sites are shared by banner mode, so non-type-5 banner
spacing is not preserved by this no-growth experiment. Do not use R29 for the
planned ImageWriter/DMP comparison. Cards, signs, and stationery remain on
the frozen R21/R26/R27 paths. After the Oki banner geometry is hardware-good,
the final separate printer-type integration must isolate this behavior before
merge/release.

## R27 stationery: restore the collapsed full-page advance

R26 hardware validation finished sign mode at approximately 9.9 mm from both
form edges, with the paper-position dots about one dot from ideal.  R27 leaves
the R21 greeting-card and R26 sign geometry unchanged.

The first stationery hardware test exposed a different problem.  The artwork
itself starts correctly and the final registration position is about 10.2 mm
from the desired page boundary, but the long inter-section/page movement is
short by about **121 mm**.

Source archaeology found the reason in the historical `LHDRAW.S` (runtime
DRAW3) stationery path.  For `SIDE != 0`, Print Shop deliberately calls a
movement documented as 575/72 inch:

```asm
MOV575 LDX #40
 LDY #14
 JSR MOVCRLF
 LDX #08
 LDY #01
 JSR MOVCRLF
*
MOV7 LDX #07
 LDY #01
```

With the original Okidata 92/93 type-5 driver, `SETLF5` programmed each
linefeed to X/72 inch.  Therefore the intended movement was:

```text
14 x 40/72 + 1 x 8/72 + 1 x 7/72
= 575/72 inch
= 202.85 mm
```

Our OkiGraph I driver intentionally keeps `SETLF5` disabled because the
historical `ESC % 9 n` sequence caused hardware corruption and runaway
feeding in R17-R19.  As a result, the X=40 and X=8 spacing requests had
collapsed into ordinary text linefeeds.

R27 fixes only the type-5 `X=40,Y=14` stationery call while graphics mode is
active.  Instead of exiting graphics and emitting 14 ordinary linefeeds, it
emits **68 proven native OkiGraph graphics feeds**:

```text
68 x 15/144 inch
= 7.08333 inch
= 179.917 mm
```

At the printer's normal 6-LPI text advance, the 14 ordinary linefeeds that
this replaces account for about 59.267 mm.  Therefore the net added movement
is approximately:

```text
179.917 - 59.267 = 120.650 mm
```

which is within about 0.35 mm of the hardware-measured 121 mm deficit.  The
following X=8 and X=7 one-linefeed calls remain unchanged.

This is implemented in PRCOMS rather than by enlarging DRAW3.  Runtime DRAW3
is 2811 bytes; its first 1791 bytes match the assembled historical LHDRAW
source exactly, followed by a 1020-byte nonzero data tail.  Keeping DRAW3
byte-for-byte unchanged avoids moving or overwriting that tail.

R27 also keeps the compact graphics-exit behavior equivalent by routing the
active type-5 exit through `COUT1`; this recovers enough bytes for the new
stationery case while keeping PRCOMS inside its existing DOS allocation.

Validated R27 overlays:

```text
PRCOMS.OKI
length 2043
SHA256 f0763857572ee113b2806fd0262d2f38b83d9f58571fa721a83867aad00d46a5

MENUS7.OKI
length 3018
SHA256 1562e1ad72c5660ade0ccda7ef9cfa439805ee35e96fc3a5a923096c7d37d485

GCDRAW.OKI -> runtime DRAW1
length 2810
SHA256 4bd76c9d9fbe1a32870b00edc3ca54061037dc6cd4491eb8202b5e7f26c9db4a
```

Validated R27 runtime image:

```text
size   143360 bytes
SHA256 904720bf9c72bcc99b4255f23c44cb601621a2715adf8e2360335bd655d8f6f0
```

## R26 sign height: balanced six-band reduction

R25 attempted to move the sign down by adding a first-raster native feed.
Hardware measurement remained essentially unchanged at about 8.5 mm top and
12.2 mm bottom.  Source tracing explains why: the `CREDBUF-1` sentinel used
by that first-raster decision is initialized only on the SIDE=0 outside-card
path, so it is not a reliable first-sign-piece discriminator.

Rather than add another special top-feed state machine, R26 uses the proven
sign raster machinery itself.  It starts from R24 and restores one additional
duplicate band in the **first** 196-line half.  The sign therefore changes from
seven omitted duplicate bands to six, evenly distributed:

```text
first 196-line half:   3 duplicate bands omitted
second 196-line half:  3 duplicate bands omitted
total:                 6 bands omitted
```

This keeps the top border at the R24/R25 position, but adds one native band
inside the first half.  Everything below that restored band shifts downward by:

```text
15/144 inch = 2.646 mm
```

Hardware validation landed at approximately **9.9 mm top / 9.9 mm bottom**,
with the paper-position registration only about one dot from ideal.  R26 is
therefore the frozen sign baseline.  The two 196-line halves now also use identical
3-band compression, which is cleaner than R24's 4+3 distribution.

All 28 source batches in each half still render.  Only redundant second copies
from the sign's 2x vertical enlargement are omitted.  No source artwork is
cropped.

Greeting-card SIDE=0/1 geometry remains on the frozen R21 path.  PRCOMS,
MENUS7, SETLF5-disabled behavior, and the R14 CR-only TEST PAPER POSITION
patch are unchanged.

Validated R26 overlays:

```text
PRCOMS.OKI
length 2039
SHA256 7c6072a2186d09fb911eaf16abccc0cf3238ef8aa2e9f2575f167050f4a61137

MENUS7.OKI
length 3018
SHA256 1562e1ad72c5660ade0ccda7ef9cfa439805ee35e96fc3a5a923096c7d37d485

GCDRAW.OKI -> runtime DRAW1
length 2810
SHA256 4bd76c9d9fbe1a32870b00edc3ca54061037dc6cd4491eb8202b5e7f26c9db4a
```

Validated R26 runtime image:

```text
size   143360 bytes
SHA256 51a095f9f13d58fe519bf5e0713b79ec9ea3fcc16ed03c7a4dc84c06fa9b9210
```

## R24 sign height: restore one lower duplicate band

R23 proved that the eight-band reduction was almost exactly the right physical
height, but hardware testing showed the final lower border band was visually
too aggressive: the inner line printed while the outer line was effectively
lost.  One additional native seven-pin graphics band should complete that
bottom border and still retain the excellent vertical fit.

R24 therefore changes only the sign duplicate-removal cadence.  It removes
**seven** redundant duplicate OkiGraph bands over the full sign instead of
eight:

```text
R23 reduction: 8 x 15/144 inch = 21.167 mm
R24 reduction: 7 x 15/144 inch = 18.521 mm
difference:                         +2.646 mm height restored
```

The first 196-line sign half still omits four duplicate bands.  The second
196-line half omits only three.  The omitted copies remain distributed through
the raster, and the final portion of the second half is no longer one of the
skip locations.  This preserves complete source coverage and restores one
native output band near the lower end rather than changing the top margin.

Greeting-card SIDE=0/1 geometry remains byte-for-byte on the frozen R21 path.
`SETLF5` remains disabled; R24 uses only the proven native OkiGraph
`$03 $0E` vertical feed.

Validated R24 overlays:

```text
PRCOMS.OKI
length 2039
SHA256 7c6072a2186d09fb911eaf16abccc0cf3238ef8aa2e9f2575f167050f4a61137

GCDRAW.OKI -> runtime DRAW1
length 2812
SHA256 9f74176a45823ee9544ce3a7aae2970e90252786f706960e309af481ace4524d

MENUS7.OKI
length 3018
SHA256 1562e1ad72c5660ade0ccda7ef9cfa439805ee35e96fc3a5a923096c7d37d485
```

Validated R24 runtime image:

```text
size   143360 bytes
SHA256 98e23b7191047fe7d427f645e5847e57ca738974723cbe9d0b647b655168cd04
```

## R23 sign height: superseded eight-band experiment

R22 used a smaller five-band sign reduction.  R23 supersedes that experiment
and applies the same total physical vertical reduction that made the R21
greeting-card page fit so well.

The greeting-card path reduces each of its four 196-line pieces from 28 native
output bands to 26, for a total reduction of eight native OkiGraph bands over
the full sheet:

```text
4 pieces x (28 - 26) = 8 bands removed
8 x 15/144 inch      = 120/144 inch
                     = 0.833333 inch
                     = 21.167 mm
```

R23 removes exactly eight redundant duplicate bands from the full sign:
four from each 196-line sign half.  Sign mode normally prints every seven-line
source band twice vertically, so dropping one of the two copies does not crop
source artwork.  All 28 source batches in each half are still rendered.

The four duplicate omissions in each half are distributed through the raster
at regular intervals rather than taken from the beginning or end.  Therefore:

- the R21/R22 sign top margin is unchanged;
- all source graphics, text, and border rows remain represented;
- the full sign is shortened by the same 21.167 mm as the total greeting-card
  page reduction;
- greeting-card SIDE=0/1 geometry and the R21 double-native fold remain
  untouched.

In source-line-equivalent terms, eight omitted duplicate seven-line bands at
2x sign enlargement correspond to 28 source lines, but the important match is
the physical output reduction: **eight native bands**, exactly the same total
band reduction as the greeting-card sheet.

R23 remains native-only.  `SETLF5` stays disabled and no `ESC % 9 n`
fine-spacing commands are used.

Validated R23 overlays:

```text
PRCOMS.OKI
length 2039
SHA256 7c6072a2186d09fb911eaf16abccc0cf3238ef8aa2e9f2575f167050f4a61137

GCDRAW.OKI -> runtime DRAW1
length 2810
SHA256 00fb0aed8c2a80b145e3316e67b8db1727948808a07dd58ce42999e1729801b0

MENUS7.OKI
length 3018
SHA256 1562e1ad72c5660ade0ccda7ef9cfa439805ee35e96fc3a5a923096c7d37d485
```

Validated R23 runtime image:

```text
size   143360 bytes
SHA256 e937060c3c945a679a65f6e080fee14ea7099937fc2ac5660061b2a9c2ace287
```

## R22 sign height: superseded five-band experiment

R21 is retained unchanged for greeting cards.  The sign path was still using
the original Print Shop SIDE=2 expansion: each 196-line half is decoded as 28
seven-line source batches and each source batch is printed twice, producing
56 native OkiGraph bands per half (112 bands for the full sign).

That means the sign had *not* received the vertical compression applied while
tuning the card path.

R22 keeps the sign's existing top position but removes five redundant
second copies of already-rendered sign bands across the full 392-line source:

```text
first 196-line half:   omit 2 duplicate bands
second 196-line half:  omit 3 duplicate bands
total:                 omit 5 duplicate bands
```

Because a sign source band represents seven source lines and is normally
doubled vertically, five removed duplicate bands are equivalent to:

```text
5 * 7 / 2 = 17.5 source lines
```

which is effectively the requested 18-line reduction.

No source graphics are cropped.  The code advances to the next seven-line
source batch whenever one duplicate is omitted, so all 28 source batches in
each half are still rendered.  The omitted duplicates are distributed through
the sign rather than removed from the top or bottom.

The physical height reduction is exactly five already-proven native OkiGraph
feeds:

```text
5 * 15/144 inch = 75/144 inch
                 = 0.520833 inch
                 = 13.229 mm
```

The top margin is therefore unchanged from R21.  Greeting-card SIDE=0/1
geometry, the R21 fold spacing, PRCOMS, and the R14 CR-only TEST PAPER POSITION
patch are unchanged.

Validated R22 overlays:

```text
PRCOMS.OKI
length 2039
SHA256 7c6072a2186d09fb911eaf16abccc0cf3238ef8aa2e9f2575f167050f4a61137

GCDRAW.OKI -> runtime DRAW1
length 2812
SHA256 194fcdecd03dd9589e3c722c707e1ba007da1f3763a01cd090243ca32cc0cf61

MENUS7.OKI
length 3018
SHA256 1562e1ad72c5660ade0ccda7ef9cfa439805ee35e96fc3a5a923096c7d37d485
```

Validated R22 runtime image:

```text
size   143360 bytes
SHA256 1f7b71bdbcecf6269db92e7050c68da53ee49b64f7d5b4c2188c1dc88bae60b4
```

R22 DRAW1 is exactly 2812 bytes, the maximum payload that still fits its
existing 2816-byte DOS binary allocation including the four-byte header.

## R21 double-native fold

R20 hardware measurements put the first border at about 6.0 mm from the top
perforation and the final border at about 9.0 mm from the next perforation.
The central complete-panel gap was also about 9 mm.

R21 leaves the R20 top position completely unchanged and adds one additional
native OkiGraph graphics feed at the true fold between the two complete card
panels:

```text
R20 fold:  1 x 15/144 inch = 2.646 mm
R21 fold:  2 x 15/144 inch = 5.292 mm
difference                  = +2.646 mm
```

That shifts only the second complete panel downward by 2.646 mm.  If the R20
9.0 mm bottom measurement repeats, the predicted R21 bottom margin is:

```text
9.0 - 2.646 = 6.354 mm
```

which closely matches the measured ~6.0 mm top margin.

R21 remains native-only: `SETLF5` is still disabled and no `ESC % 9 n`
fine-spacing commands are emitted.  Half-panel joins, raster spacing, and the
R14 TEST PAPER POSITION CR-only patch are unchanged.

Validated R21 overlays:

```text
PRCOMS.OKI
length 2039
SHA256 7c6072a2186d09fb911eaf16abccc0cf3238ef8aa2e9f2575f167050f4a61137

GCDRAW.OKI -> runtime DRAW1
length 2808
SHA256 dff91a6893a862160e9f2e0452f3c4941e3a2110caea055240de135c1ff99b5f

MENUS7.OKI
length 3018
SHA256 1562e1ad72c5660ade0ccda7ef9cfa439805ee35e96fc3a5a923096c7d37d485
```

Validated R21 runtime image:

```text
size   143360 bytes
SHA256 42042644cfe7071e11f6cd8acde45bc51526d4ddeca6e90a3d25c4b2925b27b4
```

## R20 native-only top and fold adjustment

R17-R19 demonstrated on hardware that re-enabling the historical type-5
`ESC % 9 n` spacing path is not safe for this OkiGraph I driver.  The
hardware symptoms included stray dot output, internal panel gaps, and a
runaway feed sequence.  R20 therefore rebases directly from R16 and keeps
`SETLF5` disabled exactly as in the hardware-good R11-R16 path.

R20 uses only the native OkiGraph graphics feed already proven on hardware:

```text
$03 $0E = 15/144 inch = 2.646 mm
```

The first physical card raster now takes one native graphics feed rather than
R16's two.  That moves the first printed border upward by exactly 15/144 inch
(2.646 mm).

At the true complete-panel transition, the existing `LF36` helper is changed
only for `SIDE=1`: while graphics mode is still active it calls CRLF with
X=0,Y=1, producing exactly one native `$03 $0E` feed.  The subsequent
DOALL9 logic then exits graphics normally.  `SIDE=0` retains the R16
zero-feed behavior, and `SIDE=2` (signs) retains its original path.

This deliberately gives up the attempted 1.8-1.9 mm fine adjustment in favor
of the smallest vertical quantum that is already proven safe on OkiGraph I.
Because the same 15/144-inch amount is removed from the top and inserted at
the fold, the lower complete panel should remain at essentially the same
absolute page position as R16.

Validated R20 overlays:

```text
PRCOMS.OKI
length 2039
SHA256 7c6072a2186d09fb911eaf16abccc0cf3238ef8aa2e9f2575f167050f4a61137

GCDRAW.OKI -> runtime DRAW1
length 2807
SHA256 aa1cd6a98049d447c179f18405a8de74ff4b587a56d4cbc9dfd210d651953aa9

MENUS7.OKI
length 3018
SHA256 1562e1ad72c5660ade0ccda7ef9cfa439805ee35e96fc3a5a923096c7d37d485
```

Validated R20 runtime image:

```text
size   143360 bytes
SHA256 c9486cc9494317471a3f5cc2c73daaa6c93b6202d1ed56e293ee4ce0dc8c1e13
```

The R14 TEST PAPER POSITION CR-only patch remains unchanged.

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
