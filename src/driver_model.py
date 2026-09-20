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


def sendgc_begin(in_graphics: bool) -> tuple[bytes, bool]:
    """R7/R8 SGC5: enter graphics only when not already active."""
    if in_graphics:
        return b"", True
    return bytes([ETX]), True


def crlf_type5(
    *,
    in_graphics: bool,
    x_72: int,
    y_count: int,
) -> tuple[bytes, bool]:
    """Model the compact PRCOMS type-5 CR/LF path used by R8.

    Active graphics with X=0,Y>0 uses native OkiGraph feed+CR and remains
    in graphics. Other calls exit graphics first, then emit text-mode CR.
    Print Shop's X=2 LF36 helper is suppressed; other requested text-mode
    feeds use ordinary LF. The invalid legacy ESC % 9 sequence is never sent.
    """
    if x_72 < 0 or y_count < 0:
        raise ValueError("X and Y must be non-negative")

    out = bytearray()

    if in_graphics and x_72 == 0 and y_count > 0:
        for _ in range(y_count):
            out += bytes([ETX, GRAPHICS_LF_CR])
        return bytes(out), True

    if in_graphics:
        out += bytes([ETX, EXIT_GRAPHICS])
        in_graphics = False

    out.append(0x0D)

    if y_count == 0 or x_72 == 2:
        return bytes(out), in_graphics

    out += bytes([0x0A]) * y_count
    return bytes(out), in_graphics


def gcdraw_piece_start(
    *,
    in_graphics: bool,
    first_outside_piece: bool,
) -> tuple[bytes, bool]:
    """Model the R8 GCDRAW DUMP boundary.

    Every DUMP first performs Print Shop's X=7,Y=0 setup. R8 then explicitly
    enters OkiGraph graphics before the first raster row.

    For the first outside-card DUMP only, GCDRAW skips the historical
    X=0,Y=1 first-row CRLF so printing starts at the physical head position.
    Later pieces perform exactly one native graphics feed before their first
    raster row, matching ordinary in-piece band stepping.
    """
    out = bytearray()

    stream, in_graphics = crlf_type5(
        in_graphics=in_graphics,
        x_72=7,
        y_count=0,
    )
    out += stream

    stream, in_graphics = sendgc_begin(in_graphics)
    out += stream

    if not first_outside_piece:
        stream, in_graphics = crlf_type5(
            in_graphics=in_graphics,
            x_72=0,
            y_count=1,
        )
        out += stream

    return bytes(out), in_graphics
