* THE PRINT SHOP V2 - OKIDATA 82A/83A OKIGRAPH I
*
* R5 integration notes
*
* Proven graphics-byte conversion:
*
*   wire = $80 | reverse7(first | second)
*
* R4 hardware testing showed that repeated exit/re-enter framing was still
* producing bad band geometry and an occasional lost carriage at the
* left/right-half transition.
*
* Source tracing shows Print Shop's normal graphics loop is:
*
*   CRLF X=7,Y=0       setup before first row
*   CRLF X=0,Y=1       advance to row
*   SENDGC / GCOUT1    print one seven-line band
*   ...
*   CRLF X=0,Y=1       next band
*   SENDGC / GCOUT1
*
* R5 therefore keeps OkiGraph graphics state active across the ordinary
* X=0,Y>0 band-to-band CRLF calls and uses the firmware-backed native:
*
*   $03,$0E            graphics LF + carriage return
*
* FIX80 is type-5 graphics state:
*
*   0 = text/control mode
*   1 = graphics mode
*
* SGC5 emits the initial $03 only when FIX80=0.
* GC5 no longer emits $03,$02 at the end of every chunk.
*
* Any spacing/boundary CRLF (X!=0), CR-only call (Y=0), or ordinary COUT1
* output forces a clean:
*
*   $03,$02            exit graphics
*
* before returning to text/control output.  This is specifically intended to
* protect setup-test returns and left/right page-half transitions.
*
* Fixed Print Shop entry table remains:
*   $1800 COUT1
*   $1803 CRLF
*   $1806 SENDGC
*   $1809 GCOUT1
