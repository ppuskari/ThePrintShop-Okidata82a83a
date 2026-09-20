* THE PRINT SHOP V2 - OKIDATA 82A/83A OKIGRAPH I
*
* R9A HARDWARE-VALIDATION BUILD
*
* R9 (SHA256 29d2...) is retired.  It clobbered A/SIDE while checking PRTYPE
* inside GCDRAW, causing DUMP1 to select the wrong card-buffer base and decode
* unrelated memory as printer raster data.
*
* R9A keeps the exact validated R8 PRCOMS and MENUS7 binaries and changes only
* GCDRAW/DRAW1.
*
* R9A vertical correction:
*
*   Print Shop nominal band pitch = 14/144 inch
*   OkiGraph native graphics feed = 15/144 inch
*
* A monochrome greeting-card side historically contains 28 seven-row source
* bands (196 source rows).  R9A emits 26 bands while distributing fourteen
* single-row skips through the source walk.  The first source row and final
* source row remain represented.
*
* MAKEBUF proves one source scanline is $40 bytes:
*
*   DADDR += $40 for each of the seven rows decoded into one printer band.
*
* Therefore R9A advances BADDR by either:
*
*   +$01C0 / -$01C0   normal seven-row source step
*   +$0200 / -$0200   eight-row step (skip one source row)
*
* The printer-type test uses Y:
*
*   LDY $95F1
*   CPY #05
*
* so A remains the SIDE value required by DUMP1's subsequent CMP #01.
*
* R8 behavior retained:
*   - first outside-card raster starts at the physical head baseline;
*   - later DUMP boundaries use one native graphics feed;
*   - continuous graphics uses $03,$0E;
*   - legacy ML92/93 ESC '%' '9' is never emitted;
*   - LF36 remains suppressed.
*
* Validated R9A overlays:
*   PRCOMS.OKI  2034 bytes
*   MENUS7.OKI  3018 bytes
*   GCDRAW.OKI  2802 bytes (runtime DRAW1)
