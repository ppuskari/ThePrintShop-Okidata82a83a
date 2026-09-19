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
    """R2 type-5 text CR/LF: no legacy ESC % 9 spacing sequence."""
    if count < 0:
        raise ValueError("count must be non-negative")
    return bytes([0x0D]) + bytes([0x0A]) * count


def graphics_crlf(count: int) -> bytes:
    """R2 vertical move after a completed OkiGraph graphics transaction.

    Print Shop exits graphics at the end of each chunk.  Each requested
    vertical move therefore enters OkiGraph command state, performs the
    native graphics LF+CR, then explicitly exits so the next SGC5 $03 starts
    from the state expected by the original Print Shop transaction model.
    """
    if count < 0:
        raise ValueError("count must be non-negative")
    one = bytes([ETX, GRAPHICS_LF_CR, ETX, EXIT_GRAPHICS])
    return one * count
