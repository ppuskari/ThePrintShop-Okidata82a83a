"""Wire-level model of The Print Shop v2 OkiGraph I printer path."""

ETX = 0x03
EXIT_GRAPHICS = 0x02
GRAPHICS_LF_CR = 0x0E


def reverse7(value: int) -> int:
    """Reverse bits 0..6; bit 7 is ignored."""
    value &= 0x7F
    out = 0
    for bit in range(7):
        if value & (1 << bit):
            out |= 1 << (6 - bit)
    return out


def encode_pair(first: int, second: int) -> int:
    """Convert two Print Shop 120-cpi columns to one OkiGraph 60-cpi byte."""
    merged = (first | second) & 0x7F
    return 0x80 | reverse7(merged)


def encode_columns(source: bytes) -> bytes:
    """Encode an even number of Print Shop source columns."""
    if len(source) & 1:
        raise ValueError("Print Shop/Oki type-5 conversion requires byte pairs")
    return bytes(
        encode_pair(source[i], source[i + 1])
        for i in range(0, len(source), 2)
    )


def graphics_record(source: bytes) -> bytes:
    """Return one Print Shop graphics transaction."""
    return bytes([ETX]) + encode_columns(source) + bytes([ETX, EXIT_GRAPHICS])


def text_crlf(count: int) -> bytes:
    """R3 type-5 text CR/LF: no legacy ESC % 9 spacing sequence."""
    if count < 0:
        raise ValueError("count must be non-negative")
    return bytes([0x0D]) + bytes([0x0A]) * count


def graphics_crlf(count: int) -> bytes:
    """R3 vertical move after a completed Print Shop graphics transaction.

    GC5 has already emitted ETX,EXIT_GRAPHICS.  A zero-count CRLF must still
    return the carriage.  For one or more vertical moves, enter graphics,
    issue native ETX,GRAPHICS_LF_CR commands while in graphics state, then
    exit graphics once at the end.
    """
    if count < 0:
        raise ValueError("count must be non-negative")
    if count == 0:
        return bytes([0x0D])
    return (
        bytes([ETX])
        + bytes([ETX, GRAPHICS_LF_CR]) * count
        + bytes([ETX, EXIT_GRAPHICS])
    )
