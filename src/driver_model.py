"""Wire-level model of The Print Shop v2 OkiGraph I printer path."""

ETX = 0x03
EXIT_GRAPHICS = 0x02
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
    """Return one Print Shop graphics transaction."""
    return bytes([ETX]) + encode_columns(source) + bytes([ETX, EXIT_GRAPHICS])


def update_spacing_72(current_144: int, x_72: int) -> int:
    """Emulate Print Shop SETLF state for OkiGraph I.

    Print Shop supplies X in 1/72-inch units and expects X=0 to retain the
    previous spacing.  OkiGraph I's ESC % 9 n performs direct n/144-inch
    motion rather than storing persistent spacing, so the driver caches
    2*X itself.
    """
    if not 0 <= current_144 <= 0x7F:
        raise ValueError("current spacing must fit n/144 command")
    if not 0 <= x_72 <= 63:
        raise ValueError("X must fit doubled n/144 command")
    return current_144 if x_72 == 0 else x_72 * 2


def direct_feed_144(amount_144: int) -> bytes:
    """Return one OkiGraph direct n/144-inch vertical-motion command."""
    if not 0 <= amount_144 <= 0x7F:
        raise ValueError("amount must fit OkiGraph n/144 command")
    return bytes([ESC, ord("%"), ord("9"), amount_144])


def type5_crlf(current_144: int, x_72: int, y_count: int) -> tuple[bytes, int]:
    """Model R4 Print Shop type-5 CRLF semantics.

    Every call returns the carriage first.  Non-zero X updates the cached
    spacing.  Each of Y requested advances is then executed directly with
    ESC % 9 n using that cached 1/144-inch amount; no ordinary LF is sent.
    """
    if y_count < 0:
        raise ValueError("Y must be non-negative")
    spacing = update_spacing_72(current_144, x_72)
    stream = bytearray([0x0D])
    for _ in range(y_count):
        stream += direct_feed_144(spacing)
    return bytes(stream), spacing
