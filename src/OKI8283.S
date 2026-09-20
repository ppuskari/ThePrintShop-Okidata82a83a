* THE PRINT SHOP V2 - OKIDATA 82A/83A OKIGRAPH I
*
* R7 hardware-validation build
*
* R6 proved two important facts on the physical printer:
*
*   1. R5-style continuous graphics is the correct foundation.
*   2. The inherited ML92/93 ESC '%' '9' spacing sequence is not valid
*      for this 82A/83A OkiGraph-I path; pieces of it print visibly.
*
* R7 therefore returns to the compact R5 state machine and removes the
* unsupported spacing sequence completely.
*
* MENUS7 initializes FIX80 ($B9) to zero when printer type 5 is selected.
*
* FIX80:
*   0 = text/control state
*   1 = OkiGraph graphics state
*
* While graphics is active, normal Print Shop X=0,Y>0 row advances use:
*
*   $03,$0E                native graphics line feed + carriage return
*
* and graphics remains active for the following SENDGC transaction.
*
* Spacing/boundary calls first exit graphics with:
*
*   $03,$02
*
* then emit an ordinary carriage return.
*
* For X=12 (12/72 = 1/6 inch), R7 uses the printer's ordinary LF.
*
* Print Shop's LF36 helper asks for X=2 (1/36 inch).  OkiGraph I has no
* firmware-backed exact 1/36-inch host command, so R7 suppresses that feed.
* The resulting -1/36-inch error is much smaller than substituting a full
* +1/6-inch LF, and removes the large card-half separation seen previously.
*
* The high-bit-safe graphics conversion remains:
*
*   wire = $80 | reverse7(source0 | source1)
*
* Greeting-card GCDRAW uses fixed even SENDGC sizes ($0200/$0400), so no
* odd-byte edge handling is needed in this hardware-validation build.
*
* R7 executable overlay:
*   PRCOMS load   $1800
*   PRCOMS length 2034 bytes
*   end address   below $2000
