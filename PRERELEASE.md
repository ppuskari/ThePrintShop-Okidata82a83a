# R30 Hardware-Golden Prerelease

This repository snapshot is the current reproducible prerelease for the
Apple II **The Print Shop v2** driver targeting the **Okidata MICROLINE
82A/83A with OkiGraph I**.

## Hardware validation lock

Validated output milestones:

- R21 — greeting cards
- R26 — signs
- R27 — stationery
- R30 — banners, including the R29 icon geometry correction and R30
  true-row banner-text densification

R30 was physically validated on real OkiGraph I hardware and is the current
hardware-golden prerelease baseline.

## Canonical runtime hashes

```text
PRCOMS.OKI
length  2043
SHA256  f0763857572ee113b2806fd0262d2f38b83d9f58571fa721a83867aad00d46a5

MENUS7.OKI
length  3018
SHA256  1562e1ad72c5660ade0ccda7ef9cfa439805ee35e96fc3a5a923096c7d37d485

DRAW1 / GCDRAW.OKI
length  2810
SHA256  4bd76c9d9fbe1a32870b00edc3ca54061037dc6cd4491eb8202b5e7f26c9db4a

DRAW4 R30
load    $7800
length  1020
RAM     $7800-$7BFB
packed  1024/1024
SHA256  4360a87c4663b50aad99c6a5f7fca75f997d3b23ff8e73bd3f783619f9d03235

SYSLIB
load    $8800
length  4773
SHA256  3a407593c842b6efd2f01327d0b6cebc6cc80e81241775032a225650f5f3bc3e

runnable DOS 3.3 disk
size    143360
SHA256  2e5ab070988b3b36df0072577c2ebf57c61cf616551a0ef10c88f3cac0db387f
```

The runtime builder pins the R30 DRAW4 and complete disk hashes and fails if
the generated binaries drift.

## Rebuild

On Windows, from the repository root:

```powershell
.\scripts\Build-RuntimeDisk.ps1
```

Expected output:

```text
build-runtime\PrintShop-Okidata82a83a-OkiGraphI.dsk
SHA256 2e5ab070988b3b36df0072577c2ebf57c61cf616551a0ef10c88f3cac0db387f
```

The build downloads the historical Print Shop source/runtime basis when a
local copy is not supplied, verifies the original overlays, assembles the
reproducible OkiGraph overlays, patches the exact shipped DRAW4 runtime in
place, applies the fixed-length R14 paper-position patch, reads all modified
files back through their DOS T/S chains, and verifies the deterministic final
image.

## R30 fixed-address contract

```text
DRAW4 load          $7800
BSTR6               +$0085
STRSEND             +$00B7, 37 bytes
STRSUB              +$00FF
row-feed helper     $7906
BICON2              +$02BE
R29 icon helper     $7BF4-$7BFB
final DRAW4 end     $7BFB
```

No existing DRAW4 address moves. No DOS data sector is added. The VTOC and
T/S lists are not changed. Resident SYSLIB remains 4773 bytes.

## Scope

This is intentionally a prerelease rather than the final packaging milestone.
The next cleanup work can restore the original stock Okidata 92/93 choice as a
separate menu entry and package the OkiGraph 82A/83A driver as its own printer
selection without changing the hardware-golden output geometry.

For exact implementation history and hardware-test notes, see README.md.
