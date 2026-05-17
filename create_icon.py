"""Generuje icon.ico dla epubTools Suite — bez zewnętrznych zależności."""
import struct
import zlib


def _draw_pixels(size: int) -> list:
    """Rysuje otwartą książkę; zwraca listę wierszy [(r,g,b,a), ...]."""
    BG     = (27,  58,  92, 255)
    PAGE_L = (220, 238, 255, 255)
    PAGE_R = (200, 224, 248, 255)
    COVER  = (14,  99,  156, 255)
    SPINE  = (6,   61,  110, 255)
    LINE   = (141, 188, 216, 255)

    grid = [[BG] * size for _ in range(size)]
    sc   = size / 32.0

    def rect(x1, y1, x2, y2, c):
        for ry in range(round(y1 * sc), round(y2 * sc)):
            for rx in range(round(x1 * sc), round(x2 * sc)):
                if 0 <= rx < size and 0 <= ry < size:
                    grid[ry][rx] = c

    # lewa strona
    rect(3, 8, 15, 26, PAGE_L)
    rect(3, 8,  5, 26, COVER)
    rect(3, 8, 15, 10, COVER)
    rect(3, 24, 15, 26, COVER)
    # prawa strona
    rect(17, 8, 29, 26, PAGE_R)
    rect(27, 8, 29, 26, COVER)
    rect(17, 8, 29, 10, COVER)
    rect(17, 24, 29, 26, COVER)
    # grzbiet
    rect(14, 7, 18, 27, SPINE)
    # linie tekstu
    for y in (13, 16, 19):
        rect(6,  y, 13, y + 1, LINE)
        rect(19, y, 27, y + 1, LINE)

    return grid


def _to_png(grid: list, size: int) -> bytes:
    """Konwertuje siatkę pixeli do PNG (dla rozmiaru 256 w ICO)."""
    def chunk(tag: bytes, data: bytes) -> bytes:
        c = struct.pack('>I', len(data)) + tag + data
        return c + struct.pack('>I', zlib.crc32(tag + data) & 0xFFFFFFFF)

    sig = b'\x89PNG\r\n\x1a\n'
    ihdr = chunk(b'IHDR', struct.pack('>IIBBBBB', size, size, 8, 2, 0, 0, 0))

    raw = bytearray()
    for row in grid:
        raw.append(0)  # filter byte
        for r, g, b, _a in row:
            raw += bytes([r, g, b])
    idat = chunk(b'IDAT', zlib.compress(bytes(raw), 9))
    iend = chunk(b'IEND', b'')
    return sig + ihdr + idat + iend


def _to_bmp_dib(grid: list, size: int) -> bytes:
    """Konwertuje siatkę pixeli do formatu BMP DIB (dla małych rozmiarów ICO)."""
    # BITMAPINFOHEADER — biHeight = size*2 (XOR data + AND mask)
    header = struct.pack('<IiiHHIIiiII',
                         40, size, size * 2, 1, 32, 0, 0, 0, 0, 0, 0)
    # dane XOR: od dołu, BGRA
    xor = bytearray()
    for row in reversed(grid):
        for r, g, b, a in row:
            xor += bytes([b, g, r, a])
    # maska AND: 1bpp, wiersze wyrównane do 4 bajtów, wszystko 0 = użyj alfa
    mask_row = ((size + 31) // 32) * 4
    and_mask = bytes(mask_row * size)
    return header + bytes(xor) + and_mask


def create_ico(path: str, sizes: tuple = (16, 32, 48, 256)) -> None:
    blobs = []
    for s in sizes:
        grid = _draw_pixels(s)
        if s >= 256:
            # Vista ICO: PNG wewnątrz ICO (mniejszy plik, obsługiwany od Windows Vista)
            data = _to_png(grid, s)
        else:
            data = _to_bmp_dib(grid, s)
        blobs.append((s, data))

    # nagłówek ICO
    ico = struct.pack('<HHH', 0, 1, len(blobs))

    # wpisy katalogu (16 bajtów każdy)
    offset = 6 + len(blobs) * 16
    for s, blob in blobs:
        w = s if s < 256 else 0
        h = s if s < 256 else 0
        ico += struct.pack('<BBBBHHII', w, h, 0, 0, 1, 32, len(blob), offset)
        offset += len(blob)

    for _, blob in blobs:
        ico += blob

    with open(path, 'wb') as f:
        f.write(ico)
    total = sum(len(b) for _, b in blobs)
    print(f"Zapisano {path}  rozmiary={list(sizes)}  łącznie={len(ico)} bajtów")


if __name__ == '__main__':
    create_ico('icon.ico')
