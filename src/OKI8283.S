* THE PRINT SHOP V2 - OKIDATA 82A/83A OKIGRAPH I
*
* R6 integration notes
*
* Proven graphics-byte conversion:
*
*   wire = $80 | reverse7(first | second)
*
* R5 hardware testing was the closest result yet: continuous graphics state
* eliminated most of the seven-dot seams and stopped the wide-platen runaway.
* The R5 sheet also exposed two remaining control problems:
*
*   - stale FIX80 state was possible before the first type-5 printer call;
*   - large/text-mode reposition calls still used the printer's default LF,
*     ignoring Print Shop's requested X spacing.
*
* R6 initializes the type-5 state when MENUS7 commits PRTYPE:
*
*   $B9 (FIX80) = 0         text/control state
*   $BC (QL)    = $18       default 24/144 = 1/6 inch spacing
*
* PRCOMS then caches every nonzero Print Shop X as:
*
*   QL = 2 * X             requested spacing in 1/144-inch units
*
* Normal in-graphics X=0,Y>0 band advances remain:
*
*   $03,$0E                native graphics LF + CR
*
* and OkiGraph remains in graphics mode across the next SENDGC.
*
* Spacing/boundary or text-mode CRLF exits graphics if needed, emits CR, then
* performs each requested Y advance as:
*
*   ESC '%' '9' QL         direct vertical motion
*
* with NO ordinary LF appended.  This preserves the improvement from R5 while
* removing the double/default-feed contribution to page-half spacing.
*
* Ordinary COUT1 output still forces a clean $03,$02 graphics exit first.
*
* R6 remains inside the original PRCOMS memory window:
*
*   load   $1800
*   length 2042 bytes
*   end    below $2000
