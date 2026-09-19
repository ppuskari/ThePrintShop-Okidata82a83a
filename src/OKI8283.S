* THE PRINT SHOP V2 - OKIDATA 82A/83A OKIGRAPH I
*
* R3 integration notes
*
* Proven graphics-byte conversion:
*
*   wire = $80 | reverse7(first | second)
*
* Print Shop type 5 continues to frame each graphics chunk as:
*
*   $03 <data> $03 $02
*
* GC5 marks FIX80=1 after completing a graphics chunk so the
* following CRLF can distinguish a graphics move from text CR/LF.
*
* R3 corrects two R2 hardware defects:
*
* 1. Print Shop CRLF with Y=0 still means carriage return only.
*    R2 emitted nothing, leaving the carriage at the right edge and
*    allowing later raster rows to wander across the wide platen.
*
* 2. $03,$0E is an OkiGraph command used while already in graphics
*    state.  Since GC5 has already exited graphics, R3 explicitly
*    enters graphics before issuing native feed commands.
*
* Therefore the type-5 post-graphics CRLF wire behavior is:
*
*   Y=0:
*       $0D
*
*   Y>0:
*       $03                 enter graphics
*       ($03,$0E) * Y       native graphics LF + CR
*       $03,$02             exit graphics
*
* Type-5 text CR/LF bypasses the incompatible legacy ML92/93
* ESC % 9 n programmable-spacing sequence.
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
*
* At normal GC5 completion, after $03,$02, R3 retains:
*
*       LDA #01
*       STA FIX80
*
* The following CRLF consumes and clears this marker.
