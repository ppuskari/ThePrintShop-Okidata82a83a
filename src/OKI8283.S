* THE PRINT SHOP V2 - OKIDATA 82A/83A OKIGRAPH I
*
* R4 integration notes
*
* Proven graphics-byte conversion:
*
*   wire = $80 | reverse7(first | second)
*
* Print Shop type 5 still frames each graphics chunk as:
*
*   $03 <data> $03 $02
*
* R4 fixes vertical geometry by emulating Print Shop's line-spacing
* semantics in the driver instead of using the ML92/93 interpretation.
*
* Print Shop CRLF contract:
*   X = spacing in 1/72 inch
*   X = 0 means retain prior spacing
*   Y = number of line advances
*
* For the normal graphics loop Print Shop does:
*
*   X=7,Y=0    establish 7/72 inch spacing
*   X=0,Y=1    advance one graphics row
*   X=0,Y=1    advance next row
*   ...
*
* The 82A/83A OkiGraph I ROM's ESC % 9 n path schedules direct
* n/144-inch vertical motion; it is not the persistent SETLF state
* expected by the original ML92/93 driver.
*
* R4 therefore uses FIX80 as a type-5 cached spacing byte:
*
*   X != 0     FIX80 = 2*X
*   Y times    CR, then ESC % 9 FIX80 for each direct feed
*
* Thus the 7-dot graphics loop advances exactly 14/144 inch per
* band, matching Print Shop's requested 7/72-inch geometry.
*
* No ordinary LF is emitted on the type-5 R4 path.
*
* Fixed Print Shop entry table remains unchanged:
*   $1800 COUT1
*   $1803 CRLF
*   $1806 SENDGC
*   $1809 GCOUT1
*
* Graphics-byte core:
*
GC5A   PLA
        ORA GCOLD
        STX XTEMP
        JSR REVBITS
        ORA #$80
        LDX XTEMP
        JSR COUT1
GC5B   PHA
