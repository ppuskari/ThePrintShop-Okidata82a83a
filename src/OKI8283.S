* THE PRINT SHOP V2 - OKIDATA 82A/83A OKIGRAPH I
*
* R12 HARDWARE-VALIDATION BUILD
*
* R11 is the hardware-good OkiGraph-I driver baseline.  Its PRCOMS and
* MENUS7 binaries are unchanged in R12.
*
* R12 changes only the common GCDRAW/DRAW1 startup positioning used by every
* printer type for greeting cards/signs.
*
* Historical GCDRAW begins DOALL with:
*
*   JSR LF36
*
* before the first piece is built and dumped.  The drawing path then performs
* its own first-row positioning, so the job starts with two stacked vertical
* motions.  This behavior is printer-independent and therefore appears on
* Epson, DMP/ImageWriter, ImageWriter II, Okidata, and the other supported
* printers.
*
* R12 replaces only that initial JSR LF36 with three NOPs, preserving code
* size and all following addresses:
*
*   NOP
*   NOP
*   NOP
*
* End-of-job and fold/inter-piece LF36 calls are left intact.  The drawing
* path still supplies the single first-row advance needed to begin output.
*
* R11 OkiGraph behavior retained exactly:
*   - 7-bit logical graphics data
*   - literal $03 escaped as $03,$03
*   - R9A vertical resampling
*   - R10 per-band hard carriage registration
*
* Validated R12 overlays:
*   PRCOMS.OKI  2039 bytes
*   MENUS7.OKI  3018 bytes
*   GCDRAW.OKI  2807 bytes (runtime DRAW1)
