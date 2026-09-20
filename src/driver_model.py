"""Wire-level model of The Print Shop v2 OkiGraph I printer path."""

ETX = 0x03
EXIT_GRAPHICS = 0x02
GRAPHICS_LF_CR = 0x0E

TEXT = 0
GRAPHICS = 1
PRIMED = 2


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


def crlf_r7(*, state: int, x_72: int, y_count: int) -> tuple[bytes, int]:
    """Model the compact R7 type-5 CRLF state machine.

    State:
      0 text
      1 graphics
      2 graphics-primed by Print Shop X=7 setup

    No legacy ESC % 9 sequence is emitted.
    """
    if state not in (TEXT, GRAPHICS, PRIMED):
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
        state = TEXT

    if x_72:
        state = PRIMED if x_72 == 7 else TEXT

    out.append(0x0D)

    if y_count == 0:
        return bytes(out), state

    if x_72 == 2:
        return bytes(out), state

    if state == PRIMED:
        state = GRAPHICS
        out.append(ETX)
        for _ in range(y_count):
            out += bytes([ETX, GRAPHICS_LF_CR])
        return bytes(out), state

    out += bytes([0x0A]) * y_count
    return bytes(out), state
