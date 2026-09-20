* THE PRINT SHOP V2 - OKIDATA 82A/83A OKIGRAPH I
*
* R7 integration notes
*
* R6 hardware validation proved that continuous OkiGraph graphics mode is the
* correct basis: most seven-dot border motifs became contiguous and the
* carriage stayed bounded.  It also proved that the inherited ML92/93
* ESC '%' '9' spacing sequence is not valid on this 82A/83A OkiGraph-I path:
* pieces of that sequence appeared literally on paper.
*
* R7 removes that command completely from the type-5 path.
*
* Graphics state:
*   FIX80 == 0  text/control
*   FIX80 == 1  graphics
*
* State is tested for the exact value 1; arbitrary stale nonzero zero-page
* contents can no longer be mistaken for graphics state.
*
* Normal Print Shop graphics setup:
*   X=7,Y=0     remember 7/72 spacing; CR only
*   X=0,Y=1     enter graphics if needed; native $03,$0E feed+CR
*   SENDGC      stays in graphics for the raster
*
* Subsequent X=0,Y>0 calls remain in graphics and use native $03,$0E.
*
* Boundary/text motion:
*   X=12        exit graphics, CR, ordinary LF (12/72 = 1/6 inch)
*   X=2         exit graphics, CR, suppress LF36
*
* The firmware-backed command set has no exact 1/36-inch host motion.  Omitting
* that small feed produces only -1/36 inch error; substituting an ordinary
* 1/6-inch LF would overfeed by +5/36 inch.
*
* R7 also flushes an odd final source column at SENDGC completion by pairing
* it with zero.  This prevents dynamic odd-length graphics chunks from silently
* dropping their last source column.
*
* The high-bit-safe raster conversion remains:
*
*   wire = $80 | reverse7(source0 | source1)
*
* and ordinary COUT1 output still exits graphics cleanly with $03,$02 first.
