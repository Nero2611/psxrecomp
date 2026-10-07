"""Byte-oriented LZ whose ops are selected by the high bits of a control byte.

Each control byte ``b`` starts one op; the stream ends at ``b == 0`` and the
decoder reports how many source bytes it consumed. ``pos`` is the number of
bytes written so far, and every back-reference reads ``out[pos - offset - 3]``
onward one byte at a time, so a reference that overlaps the bytes it is
writing repeats them.

======== ================================================ ===============
Control  Output                                           Source bytes
======== ================================================ ===============
00       end of stream                                    1
01-3F    ``b`` literal bytes that follow                  1 + b
4x       ``(b & 15) + 3`` bytes continuing the byte step  1
         ``out[-1] - out[-2]`` (modulo 256)
5x       ``(b & 15) + 2`` little-endian halfwords         1
         continuing the step between the last two
         halfwords (modulo 65536)
6x       ``out[-1]`` repeated ``(b & 15) + 3`` times      1
7x       the pair ``out[-2], out[-1]`` repeated           1
         ``(b & 15) + 2`` times
80-BF    3 bytes from offset ``b & 63``                   1
C0-DF    ``((b >> 2) & 7) + 4`` bytes from offset         2
         ``((b & 3) << 8) | b1``
E0-FF    ``b2 + 5`` bytes from offset                     3
         ``((b & 31) << 8) | b1``
======== ================================================ ===============

The game's loader decodes a whole file this way, so a valid image consumes
its source exactly; trailing bytes, a reference before the start of the
output or a stream that runs off its source fail extraction rather than being
guessed. No emulated RAM, captured code or game-specific names are inputs.
"""


class StreamError(ValueError):
    """The source is not a complete, valid stream of this format."""


def decode(src, limit=1 << 24):
    """Decode ``src`` as one stream; return ``(output, consumed)``."""
    out = bytearray()
    i, size = 0, len(src)

    def need(count):
        if i + count > size:
            raise StreamError(f'stream truncated at source offset {i:#x}')

    while True:
        need(1)
        b = src[i]
        if b < 0x40:
            if b == 0:
                return bytes(out), i + 1
            need(1 + b)
            out += src[i + 1:i + 1 + b]
            i += 1 + b
        elif b < 0x50:
            if len(out) < 2:
                raise StreamError('byte step before two output bytes')
            step, value = (out[-1] - out[-2]) & 0xFF, out[-1]
            for _ in range((b & 15) + 3):
                value = (value + step) & 0xFF
                out.append(value)
            i += 1
        elif b < 0x60:
            if len(out) < 4:
                raise StreamError('halfword step before two output halfwords')
            previous = out[-4] | out[-3] << 8
            value = out[-2] | out[-1] << 8
            step = (value - previous) & 0xFFFF
            for _ in range((b & 15) + 2):
                value = (value + step) & 0xFFFF
                out += bytes((value & 0xFF, value >> 8))
            i += 1
        elif b < 0x70:
            if not out:
                raise StreamError('byte repeat before any output')
            out += bytes((out[-1],)) * ((b & 15) + 3)
            i += 1
        elif b < 0x80:
            if len(out) < 2:
                raise StreamError('pair repeat before two output bytes')
            out += bytes(out[-2:]) * ((b & 15) + 2)
            i += 1
        else:
            if b < 0xC0:
                offset, count, used = b & 0x3F, 3, 1
            elif b < 0xE0:
                need(2)
                offset, count, used = ((b & 3) << 8) | src[i + 1], ((b >> 2) & 7) + 4, 2
            else:
                need(3)
                offset, count, used = ((b & 0x1F) << 8) | src[i + 1], src[i + 2] + 5, 3
            start = len(out) - offset - 3
            if start < 0:
                raise StreamError(f'back-reference before the output start at {i:#x}')
            for k in range(count):
                out.append(out[start + k])
            i += used
        if len(out) > limit:
            raise StreamError('output exceeds the decode limit')


def decode_exact(src):
    """Decode a whole file: the end marker must be its final byte."""
    out, consumed = decode(src)
    if consumed != len(src):
        raise StreamError(f'stream ends at {consumed:#x} of {len(src):#x} source bytes')
    return out
