"""Wire-level model of The Print Shop v2 OkiGraph I printer path."""

ETX = 0x03
EXIT_GRAPHICS = 0x02
GRAPHICS_LF_CR = 0x0E

TEXT = 0
GRAPHICS = 1
FIRST_PRIME = 2
CONT_PRIME = 3


def reverse7(value: int) -> int:
    value &= 0x7F
    out = 0
    for bit in range(7):
        if value & (1 << bit):
            out |= 1 << (6 - bit)
    return out


def encode_pair(first: int, second: int) -> int:
    merged = (first | second) & 0x7F
    return 0x80 | reverse7(merged)


def encode_columns(source: bytes) -> bytes:
    if len(source) & 1:
        raise ValueError("Print Shop/Oki type-5 conversion requires byte pairs")
    return bytes(
        encode_pair(source[i], source[i + 1])
        for i in range(0, len(source), 2)
    )


def crlf_r8(*, state: int, x_72: int, y_count: int) -> tuple[bytes, int]:
    """Model R8 type-5 CRLF behavior.

    Print Shop DUMP begins each piece with X=7,Y=0 followed by X=0,Y=1.
    R8 marks the first such setup as FIRST_PRIME and later setups that occur
    after active graphics as CONT_PRIME.

    FIRST_PRIME enters graphics at the current physical paper position with
    no vertical feed. CONT_PRIME enters graphics and performs one native
    graphics feed+CR. Subsequent active X=0,Y>0 calls remain in graphics and
    use native feed+CR. X=2 (LF36) remains suppressed.
    """
    if state not in (TEXT, GRAPHICS, FIRST_PRIME, CONT_PRIME):
        state = TEXT
    if x_72 < 0 or y_count < 0:
        raise ValueError("X and Y must be non-negative")

    out = bytearray()

    if state == GRAPHICS:
        if x_72 == 0 and y_count > 0:
            for _ in range(y_count):
                out += bytes([ETX, GRAPHICS_LF_CR])
            return bytes(out), GRAPHICS

        out += bytes([ETX, EXIT_GRAPHICS])
        state = CONT_PRIME if x_72 == 7 else TEXT

    elif state in (FIRST_PRIME, CONT_PRIME):
        prime = state
        out.append(0x0D)
        state = GRAPHICS
        out.append(ETX)
        if prime == CONT_PRIME:
            out += bytes([ETX, GRAPHICS_LF_CR])
        return bytes(out), state

    elif x_72 == 7:
        state = FIRST_PRIME

    out.append(0x0D)

    if y_count == 0 or x_72 == 2:
        return bytes(out), state

    out += bytes([0x0A]) * y_count
    return bytes(out), state
