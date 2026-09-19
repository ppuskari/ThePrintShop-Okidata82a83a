"""Wire-level model of The Print Shop v2 OkiGraph I printer path.

This models the deliberately small v0.1 change to Print Shop printer type 5:
two 120-column/inch source bytes are ORed together, the lower seven bits are
reversed for Okidata pin order, and bit 7 is forced high on the wire.
"""

ETX = 0x03
ESC = 0x1B


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
    """Return one OkiGraph I graphics transaction."""
    return bytes([ETX]) + encode_columns(source) + bytes([ETX, 0x02])


def line_spacing_72(amount: int) -> bytes:
    """Model Print Shop type-5 SETLF: ESC % 9 n, where n=2*amount.

    Print Shop passes X as X/72 inch.  The Okidata command expresses the
    spacing in 1/144-inch units, so the existing type-5 path doubles X.
    """
    if not 0 <= amount <= 63:
        raise ValueError("amount must fit the Okidata n/144-inch byte")
    return bytes([ESC, ord("%"), ord("9"), amount * 2])
