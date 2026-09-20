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


def crlf_r7(*, in_graphics: bool, x_72: int, y_count: int) -> tuple[bytes, bool]:
    """Compact R7 type-5 control path based on hardware-proven R5.

    * Active graphics + X=0,Y>0: native graphics feed+CR; remain in graphics.
    * Other calls exit graphics first, then return carriage.
    * X=2 is Print Shop LF36 and is suppressed instead of overfeeding 1/6 inch.
    * Other text/boundary Y advances use ordinary LF.
    * No ESC % 9 sequence is emitted.
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
