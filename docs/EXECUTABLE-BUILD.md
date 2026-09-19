# Executable runtime build

## Status

The OkiGraph I driver has progressed beyond source patching.

The repository now reproduces the two modified Print Shop v2 executable
overlays with Merlin32 and injects them into a matching runnable DOS disk.

Validated output:

```
PrintShop-Okidata82a83a-OkiGraphI.dsk
143360 bytes
SHA256 947e0929d894d6cc47aad760098c4b92e49b5796d939795b2a29f8a58e49d2f8
```

This hash is for the repository's current v0.1/type-5 driver implementation.

## Runtime base identification

The historical source snapshot was assembled twice:

1. untouched, as a control build;
2. with the 82A/83A OkiGraph I modifications.

The untouched Merlin32 outputs are:

```
PRCOMS.ORIG
length 1962
SHA256 6fb3928799f085967822362a3e7ba0b88dadd21e7e33372951e5734578c4629a

MENUS7.ORIG
length 3014
SHA256 86d7fa76bfd693d461aa9085e3612253837e7f5f02a6027581beef3284c5355f
```

The archived `ColorPrintShop.DSK` runtime contains:

```
PRCOMS  A=$1800  length 1962
MENUS7  A=$6300  length 3014
```

and both shipped payloads are byte-for-byte identical to those untouched
control builds.

That establishes this disk as a compatible runtime base for the source tree
rather than merely a similarly named Print Shop release.

## Patched executable overlays

The OkiGraph builds are:

```
PRCOMS.OKI
length 1962
SHA256 1ade989cced56159d84d6bf1d37518726acfc9d65f8623ccc891d719452252cc

MENUS7.OKI
length 3014
SHA256 dcc17130eeb49dc829627dbd30e2594168d3c907b070a049850dc607742c6c32
```

The unchanged and modified versions remain exactly the same length.

This is important because the runtime disk can be patched in place without
changing DOS allocation, T/S chains, load addresses, or any other runtime
files.

## One-command Windows build

From the repository root:

```powershell
.\scripts\Build-RuntimeDisk.ps1
```

The script:

1. locates `merlin32.exe` in PATH, or downloads the pinned v1.1.10 Windows
   release if necessary;
2. retrieves the historical 1987-01-26 Print Shop source disks;
3. prepares both untouched control source and OkiGraph source;
4. performs the small Big Mac-to-Merlin32 syntax normalization required for
   punctuation character immediates;
5. assembles all four control/patched modules;
6. verifies every module's exact expected size and SHA-256;
7. downloads the known matching `ColorPrintShop.DSK` runtime base unless a
   local base is supplied;
8. verifies the original runtime's `PRCOMS` and `MENUS7` against the
   control build;
9. replaces only those two DOS binary payloads through their existing T/S
   chains;
10. rereads the files from the generated disk and verifies their load
    addresses, lengths, and hashes.

Output:

```
build-runtime\PrintShop-Okidata82a83a-OkiGraphI.dsk
```

A local base disk can be supplied instead:

```powershell
.\scripts\Build-RuntimeDisk.ps1 -BaseDisk C:\path\to\ColorPrintShop.DSK
```

The local base is accepted only if its executable overlays match the known
control build.

An existing Merlin32 executable can also be selected explicitly:

```powershell
.\scripts\Build-RuntimeDisk.ps1 -Merlin32 C:\path\to\merlin32.exe
```

## Why the full disk is not committed

The generated runtime contains Brøderbund's original application and
resources. The repository therefore stores the driver, source transformation,
compiler preparation, validators, and disk builder rather than redistributing
the complete application disk.

The build is nevertheless deterministic: starting from the verified archive
runtime and current driver sources produces the SHA-256 shown above.

## Current validation boundary

Verified:

- historical source extraction;
- Big Mac-to-Merlin32 source compatibility normalization;
- untouched control assembly;
- byte-for-byte match between control overlays and shipped runtime overlays;
- OkiGraph assembly;
- same-size executable overlays;
- DOS in-place replacement;
- preserved load addresses:
  - `PRCOMS $1800`
  - `MENUS7 $6300`
- read-back of modified files through DOS T/S chains;
- deterministic 143360-byte output disk;
- complete Windows build on GitHub Actions.

Not yet verified:

- emulator boot through the full Print Shop workflow;
- physical Apple II boot;
- actual 82A/83A printing;
- retained `ESC % 9 n` vertical-spacing behavior on the reconstructed
  OkiGraph I ROMs.

Those are the next validation gates.


## R2 hardware-validation build

The first physical print proved the raster path but exposed the legacy
MICROLINE 92/93 control sequence as incompatible with the 82A/83A OkiGraph I
ROMs: visible control garbage appeared around graphics entry, seven-dot bands
were separated vertically, borders appeared doubled, and a nominal one-page
design expanded to two sheets.

R2 therefore keeps the proven graphics conversion but changes type-5 CR/LF
handling:

- text CR/LF bypasses the legacy `ESC % 9 n` programmable-spacing sequence;
- a CR/LF immediately after a completed graphics chunk uses native OkiGraph
  `$03 $0E` graphics feed + carriage return;
- R2 then sends `$03 $02` to return to text/control state before the next
  Print Shop `SGC5` transaction.

Validated R2 executable:

```
PRCOMS.OKI
length 2022
SHA256 36bb58a82d312f51a26f1cd119faac56d9402a4e4fd9919d9c4700283d0ab3fb

PrintShop-Okidata82a83a-OkiGraphI.dsk
length 143360
SHA256 e404a536a5889ef051f58434b664fbcab22f31e060a9cd4c8077247a5e18d0f9
```

The PRCOMS overlay still loads at `$1800` and remains within its original
eight-sector DOS allocation.
