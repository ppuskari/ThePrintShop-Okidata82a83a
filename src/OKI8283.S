* THE PRINT SHOP V2 - OKIDATA 82A/83A OKIGRAPH I
*
* R2 integration notes
*
* The proven graphics byte conversion remains:
*
*   wire = $80 | reverse7(first | second)
*
* R2 adds a native OkiGraph control path around Print Shop CRLF.
*
* Type 5 text CR/LF:
*   - skips the legacy ML92/93 ESC % 9 n spacing sequence
*   - uses ordinary CR/LF so text remains in text state
*
* Type 5 CR/LF immediately after a completed graphics chunk:
*   - emits $03,$0E for native graphics LF + CR
*   - emits $03,$02 immediately afterward so the next SGC5
*     starts from text/control state as Print Shop expects
*
* GC5 marks FIX80=1 when it completes a graphics chunk.  FIX80 is
* otherwise the type-2 private variable, so it is available for type 5.
*
* The original fixed entry table remains at:
*   $1800 COUT1
*   $1803 CRLF
*   $1806 SENDGC
*   $1809 GCOUT1
*
* PRCOMS may grow inside its existing DOS allocation; all internal
* addresses are reassembled and the fixed jump-table entries do not move.
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
* At the normal GC5 completion path, after:
*
*       LDA #03
*       JSR COUT1
*       LDA #02
*       JSR COUT1
*
* R2 adds:
*
*       LDA #01
*       STA FIX80
*
* The following CRLF sees FIX80 and uses the native graphics feed path.
