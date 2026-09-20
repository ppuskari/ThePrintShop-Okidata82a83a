* THE PRINT SHOP V2 - OKIDATA 82A/83A OKIGRAPH I
*
* R8 HARDWARE-VALIDATION BUILD
*
* R8 keeps the hardware-proven compact R7 PRCOMS graphics path and patches
* the greeting-card/sign DRAW1 overlay (historical source GCDRAW.S) at the
* exact DUMP boundary that produced the repeatable THINKING -> PRINTING
* micro-feed.
*
* Runtime overlay mapping is byte-for-byte proven:
*
*   PRCOMS.S  -> PRCOMS   load $1800
*   MENUS7.S  -> MENUS7   load $6300
*   GCDRAW.S  -> DRAW1    load $7800
*
* R8 PRCOMS behavior:
*
*   FIX80 = 0             text/control state
*   FIX80 = 1             OkiGraph graphics state
*
*   active X=0,Y>0:
*       $03,$0E           native graphics feed + carriage return
*
*   spacing/boundary:
*       $03,$02           exit graphics when active
*       $0D               carriage return
*
*   X=2 (LF36):
*       no vertical feed  (firmware has no proven exact 1/36" host command)
*
* The inherited ML92/93 ESC '%' '9' sequence is never used; physical R6
* testing showed that bytes from that sequence can print literally.
*
* R8 DRAW1/GCDRAW behavior:
*
* Every DUMP begins with Print Shop's X=7,Y=0 setup followed historically by
* X=0,Y=1 before the first raster row.  R7 was therefore in text state for
* that first-row call and emitted an ordinary LF (~24/144"), causing the
* visible micro-step at each piece boundary.
*
* R8 explicitly enters graphics after the X=7 setup.
*
* For the first outside-card DUMP only, the historical first-row CRLF is
* skipped so the first graphics row prints at the operator's physical
* print-head position with no initial paper advance.
*
* For subsequent pieces, the first-row X=0,Y=1 runs while graphics is active,
* producing exactly one native $03,$0E feed, the same as ordinary in-piece
* band stepping.
*
* Graphics data conversion remains:
*
*   wire = $80 | reverse7(source0 | source1)
*
* Greeting-card GCDRAW uses fixed even SENDGC source counts ($0200/$0400);
* the persistent right-edge motif defect is therefore not explained by an
* odd source count or trailing-blank truncation.
*
* Known dimensional limit still under investigation:
*
*   Print Shop nominal band pitch = 7/72" = 14/144"
*   OkiGraph native band feed     = 15/144"
*
* That one-step difference predicts ~7.1% vertical stretch.  R8 intentionally
* does not disguise it with unsupported printer commands; a later build can
* address it by source-row resampling after the DUMP-boundary behavior is
* isolated on hardware.
*
* R8 executable overlays:
*
*   PRCOMS.OKI  2034 bytes
*   MENUS7.OKI  3018 bytes
*   GCDRAW.OKI  2762 bytes (installed as DRAW1)
