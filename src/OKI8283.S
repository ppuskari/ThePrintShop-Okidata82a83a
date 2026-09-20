* THE PRINT SHOP V2 - OKIDATA 82A/83A OKIGRAPH I
*
* R13 HARDWARE-VALIDATION BUILD
*
* R11 remains the hardware-good OkiGraph-I graphics baseline.
* R12 removed the common GCDRAW startup LF36.
*
* Hardware validation of R12 showed one remaining full first-row feed before
* the physically first greeting-card pane when the paper top is aligned with
* the top print-head pin.
*
* R13 leaves PRCOMS and MENUS7 exactly at their R11 hardware-good hashes and
* changes only GCDRAW/DRAW1 first-row positioning.
*
* The first inside-card pass has:
*
*   PIECE + YMAX = 392
*
* for both monochrome and color.  Its low byte is therefore $88:
*
*   monochrome: 196 + 196 = 392
*   color:      343 +  49 = 392
*
* While CREDBUF-1 is still zero, R13 checks that low-byte sum and skips only
* that first ROW CRLF.  The existing one-time outside-card first-row
* suppression remains intact, and later raster rows, folds, piece transitions,
* and R9A/R10/R11 OkiGraph behavior are unchanged.
*
* Validated R13 overlays:
*   PRCOMS.OKI  2039 bytes
*   MENUS7.OKI  3018 bytes
*   GCDRAW.OKI  2812 bytes (runtime DRAW1)
