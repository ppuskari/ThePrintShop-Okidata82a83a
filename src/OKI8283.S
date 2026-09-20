* THE PRINT SHOP V2 - OKIDATA 82A/83A OKIGRAPH I
*
* R11 HORIZONTAL BYTE-STREAM TEST
*
* R11 preserves the R10 DRAW1 geometry and registration behavior.  Only the
* type-5 graphics-byte wire encoding changes.
*
* Historical type-5 behavior:
*
*   logical = reverse7(source0 | source1)
*
* The original driver emits that seven-bit value directly.  ETX ($03) is the
* OkiGraph command prefix, so a literal graphics value $03 is escaped by
* sending it twice:
*
*   $03 -> $03,$03
*
* Earlier builds instead forced bit 7:
*
*   wire = $80 | logical
*
* That is retired for this test.  If the OkiGraph parser masks or otherwise
* treats graphics data as seven-bit, $83 can still collide with ETX and consume
* following bytes as control, producing exactly the observed left-to-right
* shortening and missing right-edge columns.
*
* R11 therefore restores the original Oki type-5 escape semantics:
*
*   normal logical byte -> one seven-bit data byte
*   logical $03         -> $03,$03
*
* Pairing remains:
*
*   two Print Shop 120-cpi source columns -> one Oki 60-cpi logical column
*
* SENDGC counts, R9A vertical resampling, and R10 per-band hard carriage home
* are otherwise unchanged.
*
* Validated R11 overlays:
*   PRCOMS.OKI  2039 bytes
*   MENUS7.OKI  3018 bytes
*   GCDRAW.OKI  2807 bytes
