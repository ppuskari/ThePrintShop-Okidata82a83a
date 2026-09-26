# The Print Shop Color – Okidata v1.0.0

Final hardware-golden release for Apple II **The Print Shop Color v2** with:

- **Okidata MICROLINE 82A/83A + OkiGraph I** as printer type 10
- restored stock **OKIDATA MICROLINE 92,93** as printer type 5

## Hardware validation

The final R31 runtime was physically validated on:

- MICROLINE 82A with OkiGraph I
- MICROLINE 83A with OkiGraph I
- MICROLINE 92 using the restored historical 92/93 path

The OkiGraph path passed greeting cards, signs, stationery, banners, printer
selection, and TEST PAPER POSITION regression checks.

## Final runtime

```text
PrintShop-Okidata82a83a-OkiGraphI.dsk
size    143360 bytes
SHA256  6434fcf6c1fe4a802c894f8b4424e95443b02b0f060c7a61b0d05f38e3e1c834
```

## Principal release components

```text
PRCOMS.OKI
length  2044
SHA256  e5d235ac23ecfc5b593bd9b46c74bf1669265a1db0b73f9e280df811b31dfa95

MENUS7.OKI
length  3041
SHA256  f6177227faff75262e4cac378488e5ec244a956663ed3173d01fb4e72c13fd85

GCDRAW.OKI / runtime DRAW6
length  2810
SHA256  be8bbee04098717019870a60b5f16f002427412e7399cadbcc179d7c0f7d34a7

runtime DRAW8
length  1020
SHA256  4360a87c4663b50aad99c6a5f7fca75f997d3b23ff8e73bd3f783619f9d03235
```

## Printer architecture

```text
type 5   OKIDATA MICROLINE 92,93
type 10  OKI 82A/83A OKIGRAPH I
```

The historical type-5 Print Shop path is restored for the ML92/93.

Type 10 carries the hardware-proven OkiGraph behavior:
- 7-bit raster conversion and literal-$03 escaping
- native OkiGraph vertical movement
- R21 greeting-card geometry
- R26 sign geometry
- R27 stationery movement
- R30 banner raster densification and icon geometry

## DOS 3.3 disk integration

The original production disk has no ordinary free sectors. The release builder
uses only sectors whose stale/deleted provenance is proven before modification:

- track 34 is an unreferenced exact duplicate of live track 16
- T32/S10 belongs to the deleted MAINMENU T/S chain
- T32/S09 becomes one added catalog sector
- DRAW6 and DRAW8 consume the remaining 17 reclaimed sectors exactly

The build fails closed if any provenance, catalog, VTOC, or allocation check
changes.

## Reproducibility

On Windows:

```powershell
git checkout v1.0.0
.\scripts\Build-RuntimeDisk.ps1
```

The final SHA256 must be:

```text
6434fcf6c1fe4a802c894f8b4424e95443b02b0f060c7a61b0d05f38e3e1c834
```

The release includes the runnable disk, a ZIP containing the compiled OkiGraph
overlays and release documentation, and SHA256SUMS.txt.

## Historical milestones

- R11 — correct literal graphics-byte escaping
- R21 — greeting cards hardware-golden
- R26 — signs hardware-golden
- R27 — stationery hardware-golden
- R30 — banners hardware-golden
- R31 — restored 92/93 + separate OkiGraph type 10; final integration

This release closes the Print Shop Color Okidata driver project. Further
printer additions should use a separate overlay/disk architecture rather than
expanding this essentially full runtime disk.
