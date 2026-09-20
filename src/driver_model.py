"""Wire-level model of The Print Shop v2 OkiGraph I printer path."""

ETX = 0x03
EXIT_GRAPHICS = 0x02
GRAPHICS_LF_CR = 0x0E


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


def begin_graphics(in_graphics: bool) -> tuple[bytes, bool]:
    """R5 SGC5: enter only when not already in graphics."""
    if in_graphics:
        return b"", True
    return bytes([ETX]), True


def end_for_text(in_graphics: bool) -> tuple[bytes, bool]:
    """R5 COUT1 wrapper: ordinary output auto-exits graphics."""
    if not in_graphics:
        return b"", False
    return bytes([ETX, EXIT_GRAPHICS]), False


def graphics_band_feed(in_graphics: bool, x: int, y: int) -> tuple[bytes, bool]:
    """Model R5 type-5 CRLF state transitions.

    While graphics is active, the normal Print Shop band call X=0,Y>0
    stays in graphics and emits native ETX,$0E commands.  A spacing/boundary
    change (X!=0) or CR-only request (Y=0) exits graphics first and then uses
    ordinary CR/LF.  In text state CR/LF is ordinary text motion.
    """
    if x < 0 or y < 0:
        raise ValueError("X and Y must be non-negative")

    out = bytearray()

    if in_graphics and x == 0 and y > 0:
        for _ in range(y):
            out += bytes([ETX, GRAPHICS_LF_CR])
        return bytes(out), True

    if in_graphics:
        out += bytes([ETX, EXIT_GRAPHICS])
        in_graphics = False

    out.append(0x0D)
    out += bytes([0x0A]) * y
    return bytes(out), in_graphics
