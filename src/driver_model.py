"""Wire-level model of The Print Shop v2 OkiGraph I printer path."""

ETX = 0x03
EXIT_GRAPHICS = 0x02
GRAPHICS_LF_CR = 0x0E
ESC = 0x1B


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


def direct_feed(spacing_144: int) -> bytes:
    if not 0 <= spacing_144 <= 0x7F:
        raise ValueError("spacing must fit one OkiGraph byte")
    return bytes([ESC, ord("%"), ord("9"), spacing_144])


def crlf_r6(
    *,
    in_graphics: bool,
    cached_spacing_144: int,
    x_72: int,
    y_count: int,
) -> tuple[bytes, bool, int]:
    """Model R6 type-5 CRLF semantics.

    Nonzero X updates the cached spacing to 2*X (1/144-inch units).
    Ordinary in-graphics X=0,Y>0 calls use the native graphics LF+CR and
    remain in graphics mode. Boundary/text calls exit graphics, emit CR,
    then perform Y direct ESC % 9 spacing motions with no ordinary LF.
    """
    if x_72 < 0 or y_count < 0:
        raise ValueError("X and Y must be non-negative")

    spacing = cached_spacing_144
    if x_72:
        spacing = x_72 * 2

    out = bytearray()

    if in_graphics and x_72 == 0 and y_count > 0:
        for _ in range(y_count):
            out += bytes([ETX, GRAPHICS_LF_CR])
        return bytes(out), True, spacing

    if in_graphics:
        out += bytes([ETX, EXIT_GRAPHICS])
        in_graphics = False

    out.append(0x0D)

    if y_count:
        if spacing:
            for _ in range(y_count):
                out += direct_feed(spacing)
        else:
            out += bytes([0x0A]) * y_count

    return bytes(out), in_graphics, spacing
