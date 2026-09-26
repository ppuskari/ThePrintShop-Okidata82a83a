# R31 Final Hardware Validation

R31 separates the two Okidata families that shared printer type 5 during
development and is the basis of the v1.0.0 final release.

The complete type-10 OkiGraph regression passed on physical 82A/83A hardware,
and the restored type-5 `OKIDATA MICROLINE 92,93` path was subsequently
validated on a real MICROLINE 92. R31 is therefore hardware-golden.

## Printer selections

```text
type 5   OKIDATA MICROLINE 92,93
type 10  OKI 82A/83A OKIGRAPH I
```

Type 5 regains the historical Print Shop PRCOMS behavior, including the
original Okidata 92/93 graphics entry/exit and `ESC % 9 n` spacing path.

Type 10 carries the proven OkiGraph behavior developed through R30.

## Runtime split

### PRCOMS / selector

```text
PRCOMS R31
length  2044
packed  2048/2048
SHA256  e5d235ac23ecfc5b593bd9b46c74bf1669265a1db0b73f9e280df811b31dfa95

MENUS7 R31
length  3041
SHA256  f6177227faff75262e4cac378488e5ec244a956663ed3173d01fb4e72c13fd85
```

The type-10 PRCOMS path uses the OkiGraph native-feed state. Type 5 remains on
the historical path.

### Cards and signs

Historical `DRAW1` stays on disk for stock printer behavior. Its entry is
wrapped in existing EOF slack:

```text
DRAW1 R31 dispatcher
load       $7800
length     2765
capacity   2812
old entry  $7830
stub       $82B1
SHA256     62e825739a525d25bc59aa3295a44a9919e15b2cadebece15f4f14fdba1de460
```

For printer type 10 the dispatcher loads `DRAW6`, which is the exact
hardware-good OkiGraph card/sign overlay:

```text
DRAW6
load    $7800
length  2810
SHA256  be8bbee04098717019870a60b5f16f002427412e7399cadbcc179d7c0f7d34a7
```

For every other printer, including type 5, the dispatcher jumps to the
historical DRAW1 entry.

### Stationery

Historical `DRAW3` remains byte-for-byte unchanged on disk.

A 25-byte wrapper is appended to existing MENUS3 slack. It loads DRAW3
normally and, only for type 10, patches the two R27 stationery immediates in
RAM:

```text
$7EE5  40 -> 0
$7EE7  14 -> 68
```

Patched MENUS3:

```text
length  2609
SHA256  e2e2b3bb88ed326403cdac1a3a87b032199e3ee542229e07ab6f4f5377484e8b
```

Type 5 therefore executes the untouched historical DRAW3.

### Banners

Historical `DRAW4` remains byte-for-byte unchanged for stock printers.

Type 10 is routed to `DRAW8`, which is the exact R30 hardware-golden banner
overlay:

```text
DRAW8
load    $7800
length  1020
SHA256  4360a87c4663b50aad99c6a5f7fca75f997d3b23ff8e73bd3f783619f9d03235
```

MENUS4 R31:

```text
length  1525
SHA256  583764b31d2c27827fbd33abe075d77e3436d495df7f1d8c5955ed40640adc6e
```

## DOS 3.3 allocation proof

The production Color Print Shop disk has no normally free non-system sectors.
R31 does not guess or reuse arbitrary data. The builder proves stale/deleted
provenance before reclaiming anything.

On the untouched base image:

- Track 34, sectors 0-15, is byte-for-byte identical to live track 16 and is
  unreferenced by every live file.
- `T32/S10` is the T/S list for the single deleted `MAINMENU` catalog
  entry and points to the stale `T32/S09..S02` chain.
- `T32/S09` is reused as one new final catalog sector.
- The other 17 proven-stale sectors are consumed exactly by DRAW6 and DRAW8.

Deterministic resulting allocation:

```text
new catalog sector  T32/S09

DRAW6
T/S                 T34/S15
data sectors        11

DRAW8
T/S                 T34/S03
data sectors        4
```

The builder aborts if the duplicate-track proof, deleted MAINMENU proof,
catalog chain, VTOC state, or resulting allocation differs from the known
production image.

## Complete final image

```text
size    143360 bytes
SHA256  6434fcf6c1fe4a802c894f8b4424e95443b02b0f060c7a61b0d05f38e3e1c834
```

The pinned GitHub workflow runs 23 regression tests, validates every compiled
overlay hash, builds this exact image, verifies the deterministic filesystem
allocation, and packages the final release artifacts.

## Rebuild locally

From the repository root on Windows:

```powershell
git switch r31-restore-okidata-92-93
git pull --ff-only origin r31-restore-okidata-92-93

.\scripts\Build-RuntimeDisk.ps1
```

Expected disk:

```text
build-runtime\PrintShop-Okidata82a83a-OkiGraphI.dsk
SHA256 6434fcf6c1fe4a802c894f8b4424e95443b02b0f060c7a61b0d05f38e3e1c834
```

## Physical validation sequence

1. Open printer setup and confirm both Okidata selections are visible:
   `OKIDATA MICROLINE 92,93` and `OKI 82A/83A OKIGRAPH I`.
2. Select **OKI 82A/83A OKIGRAPH I** and save setup.
3. Run **TEST PAPER POSITION** and confirm the R14 CR-only behavior remains.
4. Print one known greeting card and compare it with the R21/R30 golden
   geometry.
5. Print one known sign and compare with R26.
6. Print the known stationery sample and compare with R27.
7. Print the known banner text/graphic sample and compare with R30.
8. Re-enter setup and confirm **OKIDATA MICROLINE 92,93** is independently
   selectable and persists as printer type 5.

The complete sequence passed on the OkiGraph 82A/83A path. The restored stock
type-5 path was also checked on a real MICROLINE 92 and printed correctly.

## Promotion result

PASS. R31 replaces R30 as the final hardware-golden baseline and is released
as v1.0.0.
