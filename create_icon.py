"""Generuje icon.ico dla epubTools Suite.

Używa Pillow jeśli dostępny, w przeciwnym razie generuje ICO z PNG
w czystym Pythonie (struct + zlib) — format Vista ICO obsługiwany
przez Windows Vista i nowsze.
"""
import struct
import zlib

# ─── Rysowanie ────────────────────────────────────────────────────────────────

_BOOK = {
    "BG":     (27,  58,  92, 255),
    "PAGE_L": (220, 238, 255, 255),
    "PAGE_R": (200, 224, 248, 255),
    "COVER":  (14,  99,  156, 255),
    "SPINE":  (6,   61,  110, 255),
    "LINE":   (141, 188, 216, 255),
}


def _draw_pixels(size: int) -> list:
    """Zwraca listę wierszy [(r,g,b,a), …] z rysunkiem otwartej książki."""
    g = [[_BOOK["BG"]] * size for _ in range(size)]
    sc = size / 32.0

    def rect(x1, y1, x2, y2, c):
        for ry in range(round(y1 * sc), round(y2 * sc)):
            for rx in range(round(x1 * sc), round(x2 * sc)):
                if 0 <= rx < size and 0 <= ry < size:
                    g[ry][rx] = c

    rect(3, 8, 15, 26, _BOOK["PAGE_L"])
    rect(3, 8,  5, 26, _BOOK["COVER"])
    rect(3, 8, 15, 10, _BOOK["COVER"])
    rect(3, 24, 15, 26, _BOOK["COVER"])

    rect(17, 8, 29, 26, _BOOK["PAGE_R"])
    rect(27, 8, 29, 26, _BOOK["COVER"])
    rect(17, 8, 29, 10, _BOOK["COVER"])
    rect(17, 24, 29, 26, _BOOK["COVER"])

    rect(14, 7, 18, 27, _BOOK["SPINE"])

    for y in (13, 16, 19):
        rect(6,  y, 13, y + 1, _BOOK["LINE"])
        rect(19, y, 27, y + 1, _BOOK["LINE"])

    return g


# ─── Generatory plików ────────────────────────────────────────────────────────

def _png_chunk(tag: bytes, data: bytes) -> bytes:
    return (struct.pack('>I', len(data)) + tag + data
            + struct.pack('>I', zlib.crc32(tag + data) & 0xFFFFFFFF))


def _to_png_rgba(grid: list, size: int) -> bytes:
    """Konwertuje siatkę do PNG RGBA (color type 6) — poprawny format dla ICO."""
    sig  = b'\x89PNG\r\n\x1a\n'
    ihdr = _png_chunk(b'IHDR',
                      struct.pack('>IIBBBBB', size, size, 8, 6, 0, 0, 0))
    raw = bytearray()
    for row in grid:
        raw.append(0)               # filter byte (None)
        for r, g, b, a in row:
            raw += bytes([r, g, b, a])
    idat = _png_chunk(b'IDAT', zlib.compress(bytes(raw), 9))
    iend = _png_chunk(b'IEND', b'')
    return sig + ihdr + idat + iend


def _write_ico_pure_python(path: str, sizes: tuple) -> None:
    """Tworzy ICO z PNG RGBA dla każdego rozmiaru (format Vista ICO)."""
    blobs = [(s, _to_png_rgba(_draw_pixels(s), s)) for s in sizes]

    ico = struct.pack('<HHH', 0, 1, len(blobs))

    # wpisy katalogu
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


def _write_ico_pillow(path: str, sizes: tuple) -> None:
    """Tworzy ICO przez Pillow: każdy rozmiar renderowany jako RGBA PNG,
    pliki PNG składane ręcznie do formatu Vista ICO."""
    import io
    from PIL import Image, ImageDraw  # type: ignore

    def make_png_bytes(size: int) -> bytes:
        img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        sc = size / 32.0

        def r(x1, y1, x2, y2, c):
            rx1, ry1 = round(x1 * sc), round(y1 * sc)
            rx2, ry2 = round(x2 * sc) - 1, round(y2 * sc) - 1
            if rx2 >= rx1 and ry2 >= ry1:
                d.rectangle([rx1, ry1, rx2, ry2], fill=c)

        r(0, 0, 32, 32, _BOOK["BG"])
        r(3, 8, 15, 26, _BOOK["PAGE_L"])
        r(3, 8,  5, 26, _BOOK["COVER"])
        r(3, 8, 15, 10, _BOOK["COVER"])
        r(3, 24, 15, 26, _BOOK["COVER"])
        r(17, 8, 29, 26, _BOOK["PAGE_R"])
        r(27, 8, 29, 26, _BOOK["COVER"])
        r(17, 8, 29, 10, _BOOK["COVER"])
        r(17, 24, 29, 26, _BOOK["COVER"])
        r(14, 7, 18, 27, _BOOK["SPINE"])
        for y in (13, 16, 19):
            r(6,  y, 13, y + 1, _BOOK["LINE"])
            r(19, y, 27, y + 1, _BOOK["LINE"])

        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()

    # Składamy ICO ręcznie — Pillow generuje poprawne PNG, struct = struktura ICO
    blobs = [(s, make_png_bytes(s)) for s in sizes]
    ico = struct.pack('<HHH', 0, 1, len(blobs))
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


# ─── Punkt wejścia ────────────────────────────────────────────────────────────

def create_ico(path: str = "icon.ico",
               sizes: tuple = (16, 32, 48, 256)) -> None:
    try:
        _write_ico_pillow(path, sizes)
        print(f"Zapisano {path}  [{', '.join(str(s) for s in sizes)}]  (Pillow)")
    except ImportError:
        _write_ico_pure_python(path, sizes)
        print(f"Zapisano {path}  [{', '.join(str(s) for s in sizes)}]  (stdlib PNG)")


if __name__ == "__main__":
    create_ico()
