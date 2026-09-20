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
    """Encode source columns, padding an odd final column with zero."""
    out = bytearray()
    for i in range(0, len(source), 2):
        second = source[i + 1] if i + 1 < len(source) else 0
        out.append(encode_pair(source[i], second))
    return bytes(out)


def begin_graphics(in_graphics: bool) -> tuple[bytes, bool]:
    """Enter graphics unless the exact state flag already says graphics."""
    if in_graphics:
        return b"", True
    return bytes([ETX]), True


def end_for_text(in_graphics: bool) -> tuple[bytes, bool]:
    if not in_graphics:
        return b"", False
    return bytes([ETX, EXIT_GRAPHICS]), False


def crlf_r7(
    *,
    in_graphics: bool,
    cached_x_72: int,
    x_72: int,
    y_count: int,
) -> tuple[bytes, bool, int]:
    """Model R7 type-5 CRLF behavior.

    Nonzero X is remembered in Print Shop's native 1/72-inch units.

    * Normal in-graphics X=0,Y>0 uses native OkiGraph graphics feed+CR and
      remains in graphics state.
    * In text state with cached X=7, a requested feed enters graphics, performs
      the native feed, and remains there for the following SENDGC.
    * X=12 uses ordinary text LF (1/6 inch), matching Print Shop exactly.
    * X=2 is Print Shop's LF36 helper. OkiGraph I has no firmware-backed exact
      1/36-inch host command, so R7 intentionally omits that tiny feed rather
      than substituting a full 1/6-inch LF.
    * No ESC % 9 sequence is emitted.
    """
    if x_72 < 0 or y_count < 0:
        raise ValueError("X and Y must be non-negative")

    cached = x_72 if x_72 else cached_x_72
    out = bytearray()

    if in_graphics and x_72 == 0 and y_count > 0:
        for _ in range(y_count):
            out += bytes([ETX, GRAPHICS_LF_CR])
        return bytes(out), True, cached

    if in_graphics:
        out += bytes([ETX, EXIT_GRAPHICS])
        in_graphics = False

    out.append(0x0D)

    if y_count == 0:
        return bytes(out), in_graphics, cached

    if cached == 7:
        out.append(ETX)
        in_graphics = True
        for _ in range(y_count):
            out += bytes([ETX, GRAPHICS_LF_CR])
        return bytes(out), in_graphics, cached

    if cached == 2:
        return bytes(out), in_graphics, cached

    out += bytes([0x0A]) * y_count
    return bytes(out), in_graphics, cached
