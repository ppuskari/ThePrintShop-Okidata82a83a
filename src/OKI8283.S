* THE PRINT SHOP V2 - OKIDATA 82A/83A OKIGRAPH I
*
* v0.1 integration fragment
*
* This replaces the GC5A..GC5B transition inside the
* existing printer-type-5 path in PRCOMS.S.
*
* Entry/state are the original Print Shop type-5 ABI:
*   A      = second 120-cpi source column
*   GCOLD  = first 120-cpi source column
*   XTEMP  = scratch used by the original routine
*   COUT1  = configured printer-interface byte output
*   REVBITS= reverse lower seven graphics bits
*
* Result:
*   wire = $80 | reverse7(first | second)
*
* The five NOPs are intentional.  They make this block
* occupy the same 20 machine-code bytes as the original
* ML92/93 fragment, so all following PRCOMS addresses stay
* unchanged in the first hardware-test build.
*
GC5A   PLA
        ORA GCOLD
        STX XTEMP
        JSR REVBITS
        ORA #$80
        LDX XTEMP
        JSR COUT1
        NOP
        NOP
        NOP
        NOP
        NOP
GC5B   PHA
*
* Continue with the unmodified original GC5B byte-count
* handling.  SGC5 still emits $03 to enter graphics and the
* original terminal path still emits $03,$02 to leave it.
