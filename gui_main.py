"""epubTools Suite — GUI łączące epubQTools i konwerter EPUB."""

from __future__ import annotations

import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import traceback
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    HAS_DND = True
except ImportError:
    HAS_DND = False

# ─── Motywy ───────────────────────────────────────────────────────────────────

DARK = dict(
    BG="#1e1e1e", BG2="#252526", BG3="#2d2d30",
    FG="#cccccc", FG_DIM="#858585",
    ACCENT="#0e639c", ACCENT_HV="#1177bb",
    ENTRY_BG="#3c3c3c", BORDER="#3f3f3f",
    BTN_BG="#0e639c", BTN_FG="#ffffff",
    LOG_BG="#1e1e1e", LOG_FG="#d4d4d4",
    TAG_OK="#4ec9b0", TAG_ERR="#f44747", TAG_WARN="#dcdcaa",
)
LIGHT = dict(
    BG="#f5f5f5", BG2="#ebebeb", BG3="#e0e0e0",
    FG="#1e1e1e", FG_DIM="#6e6e6e",
    ACCENT="#0e639c", ACCENT_HV="#1177bb",
    ENTRY_BG="#ffffff", BORDER="#c8c8c8",
    BTN_BG="#0e639c", BTN_FG="#ffffff",
    LOG_BG="#ffffff", LOG_FG="#1e1e1e",
    TAG_OK="#107c10", TAG_ERR="#c42b1c", TAG_WARN="#9e6a03",
)

# Bieżące kolory (zmieniane przy przełączeniu motywu)
BG = DARK["BG"]; BG2 = DARK["BG2"]; BG3 = DARK["BG3"]
FG = DARK["FG"]; FG_DIM = DARK["FG_DIM"]
ACCENT = DARK["ACCENT"]; ACCENT_HV = DARK["ACCENT_HV"]
ENTRY_BG = DARK["ENTRY_BG"]; BORDER = DARK["BORDER"]
BTN_BG = DARK["BTN_BG"]; BTN_FG = DARK["BTN_FG"]
LOG_BG = DARK["LOG_BG"]; LOG_FG = DARK["LOG_FG"]
TAG_OK = DARK["TAG_OK"]; TAG_ERR = DARK["TAG_ERR"]; TAG_WARN = DARK["TAG_WARN"]

CREATE_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0

# ─── Wykrywanie narzędzi ──────────────────────────────────────────────────────

def _find_epubqtools_main() -> Path | None:
    here = Path(sys.executable if getattr(sys, "frozen", False) else __file__).parent
    candidates = [
        here / "__main__.py",
        here / "epubQTools" / "__main__.py",
    ]
    if getattr(sys, "_MEIPASS", None):
        mei = Path(sys._MEIPASS)
        # epubqtools/ — podkatalog odizolowany od .pyd PyInstallera (bez konfliktu DLL)
        candidates += [
            mei / "epubqtools" / "__main__.py",
            mei / "__main__.py",
            mei / "epubQTools" / "__main__.py",
        ]
    try:
        import importlib.util
        spec = importlib.util.find_spec("epubQTools")
        if spec and spec.origin:
            candidates.append(Path(spec.origin).parent / "__main__.py")
    except Exception:
        pass
    eq = shutil.which("epubQTools")
    if eq:
        candidates.append(Path(eq).parent / "__main__.py")
    for c in candidates:
        if c.is_file():
            return c
    return None


def _find_converter() -> tuple[str, str]:
    pandoc = shutil.which("pandoc")
    if pandoc:
        return "pandoc", pandoc
    ec = shutil.which("ebook-convert")
    if ec:
        return "calibre", ec
    return "", ""


def _find_python() -> str:
    """Szuka systemowego python.exe — niezbędne gdy GUI działa jako skompilowany .exe."""
    if not getattr(sys, "frozen", False):
        return sys.executable
    for name in ("python", "python3"):
        found = shutil.which(name)
        if found:
            return found
    username = os.environ.get("USERNAME", "")
    for ver in ("312", "311", "310", "39", "38"):
        for base in (
            rf"C:\Python{ver}\python.exe",
            rf"C:\Program Files\Python{ver}\python.exe",
            rf"C:\Users\{username}\AppData\Local\Programs\Python\Python{ver}\python.exe",
        ):
            if os.path.isfile(base):
                return base
    return ""


def _find_viewer() -> str:
    """Szuka Calibre viewer (ebook-viewer)."""
    v = shutil.which("ebook-viewer")
    if v:
        return v
    # Typowe lokalizacje na Windows
    for p in [
        r"C:\Program Files\Calibre2\ebook-viewer.exe",
        r"C:\Program Files (x86)\Calibre2\ebook-viewer.exe",
    ]:
        if os.path.isfile(p):
            return p
    return ""


def _find_sigil() -> str:
    """Szuka edytora Sigil."""
    s = shutil.which("sigil") or shutil.which("Sigil")
    if s:
        return s
    for p in [
        r"C:\Program Files\Sigil\Sigil.exe",
        r"C:\Program Files (x86)\Sigil\Sigil.exe",
    ]:
        if os.path.isfile(p):
            return p
    return ""


def _find_ebook_editor() -> str:
    """Szuka Calibre e-book editor (ebook-edit)."""
    e = shutil.which("ebook-edit")
    if e:
        return e
    for p in [
        r"C:\Program Files\Calibre2\ebook-edit.exe",
        r"C:\Program Files (x86)\Calibre2\ebook-edit.exe",
    ]:
        if os.path.isfile(p):
            return p
    return ""


def _find_kindle_previewer() -> str:
    """Szuka Kindle Previewer 3 — preferuje .exe nad .bat (bat może startować KP3 asynchronicznie)."""
    username = os.environ.get("USERNAME", "")
    # KP3 może być zainstalowany jako "Kindle Previewer 3.exe" lub "KindlePreviewer.exe"
    kp3_dirs = [
        r"C:\Program Files\Amazon\Kindle Previewer 3",
        r"C:\Program Files (x86)\Amazon\Kindle Previewer 3",
        rf"C:\Users\{username}\AppData\Local\Amazon\Kindle Previewer 3",
        rf"C:\Users\{username}\AppData\Roaming\Amazon\Kindle Previewer 3",
    ]
    for d in kp3_dirs:
        for exe_name in ["Kindle Previewer 3.exe", "KindlePreviewer.exe"]:
            p = os.path.join(d, exe_name)
            if os.path.isfile(p):
                return p
    # szukaj w PATH — jeśli to .bat, spróbuj znaleźć .exe w tym samym katalogu lub podkatalogu
    kp = shutil.which("KindlePreviewer")
    if kp:
        if kp.lower().endswith(".bat"):
            bat_dir = os.path.dirname(kp)
            for rel in ["Kindle Previewer 3.exe", "KindlePreviewer.exe",
                        r"Kindle Previewer 3\Kindle Previewer 3.exe",
                        r"Kindle Previewer 3\KindlePreviewer.exe"]:
                candidate = os.path.join(bat_dir, rel)
                if os.path.isfile(candidate):
                    return candidate
            # .exe nie znalezione obok .bat — zwróć .bat z ostrzeżeniem (obsługa w _kfx_convert_one)
        return kp
    return ""


def _find_calibre_ebook_convert() -> str:
    """Szuka ebook-convert Calibre (osobna od konwertera EPUB → KFX)."""
    ec = shutil.which("ebook-convert")
    if ec:
        return ec
    for p in [
        r"C:\Program Files\Calibre2\ebook-convert.exe",
        r"C:\Program Files (x86)\Calibre2\ebook-convert.exe",
    ]:
        if os.path.isfile(p):
            return p
    return ""


def _calibre_has_kfx(ebook_convert: str) -> bool:
    """Sprawdza czy Calibre ma zainstalowaną wtyczkę KFX Output."""
    if not ebook_convert:
        return False
    for plugins_dir in [
        Path.home() / "AppData" / "Roaming" / "calibre" / "plugins",
        Path.home() / ".config" / "calibre" / "plugins",
    ]:
        if plugins_dir.is_dir() and any(
            f.name.lower().startswith("kfx") for f in plugins_dir.iterdir()
        ):
            return True
    return False


def _config_path() -> Path:
    if getattr(sys, "frozen", False):
        base = Path(sys.executable).parent
    else:
        base = Path(__file__).parent
    p = base / "config.json"
    if os.access(base, os.W_OK):
        return p
    fallback = Path.home() / ".epubtools_suite"
    fallback.mkdir(exist_ok=True)
    return fallback / "config.json"


# ─── Obsługa metadanych EPUB ─────────────────────────────────────────────────

_DC_NS  = "http://purl.org/dc/elements/1.1/"
_OPF_NS = "http://www.idpf.org/2007/opf"
_CNT_NS = "urn:oasis:names:tc:opendocument:xmlns:container"

# Kolejność i etykiety pól metadanych
_META_FIELDS = [
    ("title",       "Tytuł",                    "entry"),
    ("author",      "Autor (kilku: rozdziel ;)", "entry"),
    ("language",    "Język (np. pl, en)",        "entry"),
    ("publisher",   "Wydawca",                   "entry"),
    ("date",        "Data (RRRR-MM-DD)",          "entry"),
    ("identifier",  "Identyfikator (ISBN/UUID)",  "entry"),
    ("subject",     "Temat / Tagi (kilka: ;)",    "entry"),
    ("description", "Opis",                       "text"),
]


def _epub_opf_path(zf: zipfile.ZipFile) -> str:
    """Zwraca ścieżkę pliku OPF wewnątrz archiwum EPUB."""
    tree = ET.fromstring(zf.read("META-INF/container.xml"))
    rf = tree.find(f".//{{{_CNT_NS}}}rootfile")
    if rf is None:
        raise ValueError("Brak rootfile w META-INF/container.xml")
    return rf.attrib["full-path"]


def _epub_read_metadata(epub_path: str) -> tuple[dict, str]:
    """Czyta metadane Dublin Core z pliku EPUB.
    Zwraca (słownik metadanych, ścieżka OPF wewnątrz ZIP)."""
    with zipfile.ZipFile(epub_path, "r") as zf:
        opf_path = _epub_opf_path(zf)
        opf_bytes = zf.read(opf_path)

    # Rejestruj wszystkie przestrzenie nazw — zapobiega ns0/ns1 przy serializacji
    for m in re.finditer(rb'xmlns(?::(\w+))?=["\']([^"\']+)["\']', opf_bytes):
        prefix = (m.group(1) or b"").decode("ascii", errors="ignore")
        uri    = m.group(2).decode("ascii", errors="ignore")
        try:
            ET.register_namespace(prefix, uri)
        except Exception:
            pass

    tree = ET.fromstring(opf_bytes)

    def get(tag: str) -> str:
        el = tree.find(f".//{{{_DC_NS}}}{tag}")
        return (el.text or "").strip() if el is not None else ""

    def get_all(tag: str) -> str:
        els = tree.findall(f".//{{{_DC_NS}}}{tag}")
        return "; ".join((e.text or "").strip() for e in els if e.text)

    meta = {
        "title":       get("title"),
        "author":      get_all("creator"),
        "language":    get("language"),
        "publisher":   get("publisher"),
        "date":        get("date"),
        "identifier":  get("identifier"),
        "subject":     get_all("subject"),
        "description": get("description"),
    }
    return meta, opf_path


def _epub_write_metadata(epub_path: str, meta: dict, opf_path: str) -> None:
    """Zapisuje metadane do pliku EPUB; tworzy kopię zapasową .bak."""
    with zipfile.ZipFile(epub_path, "r") as zf:
        opf_bytes = zf.read(opf_path)

        # Rejestruj przestrzenie nazw przed parsowaniem
        for m in re.finditer(rb'xmlns(?::(\w+))?=["\']([^"\']+)["\']', opf_bytes):
            prefix = (m.group(1) or b"").decode("ascii", errors="ignore")
            uri    = m.group(2).decode("ascii", errors="ignore")
            try:
                ET.register_namespace(prefix, uri)
            except Exception:
                pass

        tree = ET.fromstring(opf_bytes)

        # Znajdź element <metadata> (może być w przestrzeni nazw OPF lub bez)
        meta_el = (tree.find(f"{{{_OPF_NS}}}metadata")
                   or tree.find("metadata"))
        if meta_el is None:
            raise ValueError("Brak elementu <metadata> w pliku OPF")

        # Pola z jedną wartością
        for key, tag in [("title",       "title"),
                         ("language",    "language"),
                         ("publisher",   "publisher"),
                         ("date",        "date"),
                         ("description", "description"),
                         ("identifier",  "identifier")]:
            value = meta.get(key, "").strip()
            el = meta_el.find(f"{{{_DC_NS}}}{tag}")
            if value:
                if el is None:
                    el = ET.SubElement(meta_el, f"{{{_DC_NS}}}{tag}")
                el.text = value
            elif el is not None:
                meta_el.remove(el)

        # Pola wielowartościowe (rozdzielone ;)
        for key, tag in [("author", "creator"), ("subject", "subject")]:
            value = meta.get(key, "").strip()
            for old in meta_el.findall(f"{{{_DC_NS}}}{tag}"):
                meta_el.remove(old)
            if value:
                for part in [v.strip() for v in value.split(";") if v.strip()]:
                    ET.SubElement(meta_el, f"{{{_DC_NS}}}{tag}").text = part

        # Serializuj zmodyfikowane OPF
        enc_match = re.search(rb'encoding=["\']([^"\']+)["\']', opf_bytes)
        encoding  = (enc_match.group(1).decode("ascii")
                     if enc_match else "utf-8")
        new_opf = (f'<?xml version="1.0" encoding="{encoding}"?>\n'
                   + ET.tostring(tree, encoding="unicode"))

        # Przepisz archiwum ZIP z nowym OPF
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf_out:
            # mimetype musi być pierwszy i niekompresowany
            if "mimetype" in zf.namelist():
                info = zipfile.ZipInfo("mimetype")
                info.compress_type = zipfile.ZIP_STORED
                zf_out.writestr(info, zf.read("mimetype"))
            for item in zf.infolist():
                if item.filename == "mimetype":
                    continue
                data = (new_opf.encode(encoding)
                        if item.filename == opf_path
                        else zf.read(item.filename))
                zf_out.writestr(item, data)

    shutil.copy2(epub_path, epub_path + ".bak")
    Path(epub_path).write_bytes(buf.getvalue())


# ─── Ikonka programu ──────────────────────────────────────────────────────────

def _create_app_icon() -> "tk.PhotoImage":
    """Tworzy ikonkę 32×32 — otwarta książka (rysowana programowo)."""
    img = tk.PhotoImage(width=32, height=32)
    BG_I   = "#1b3a5c"
    PAGE_L = "#dceeff"
    PAGE_R = "#c8e0f8"
    COVER  = "#0e639c"
    SPINE  = "#063d6e"
    LINE   = "#8dbcd8"

    img.put(BG_I,   to=(0,  0,  32, 32))
    # lewa strona
    img.put(PAGE_L, to=(3,  8,  15, 26))
    img.put(COVER,  to=(3,  8,   5, 26))
    img.put(COVER,  to=(3,  8,  15, 10))
    img.put(COVER,  to=(3, 24,  15, 26))
    # prawa strona
    img.put(PAGE_R, to=(17, 8,  29, 26))
    img.put(COVER,  to=(27, 8,  29, 26))
    img.put(COVER,  to=(17, 8,  29, 10))
    img.put(COVER,  to=(17, 24, 29, 26))
    # grzbiet
    img.put(SPINE,  to=(14, 7,  18, 27))
    # linie tekstu — lewa
    for y in (13, 16, 19):
        img.put(LINE, to=(6, y, 13, y + 1))
    # linie tekstu — prawa
    for y in (13, 16, 19):
        img.put(LINE, to=(19, y, 27, y + 1))
    return img


# ─── Dymki pomocy (tooltips) ──────────────────────────────────────────────────

_TIPS: dict[str, str] = {
    "-e":  "Naprawia plik EPUB:\n• normalizuje i czyści CSS\n• wstawia miękkie myślniki (dzielenie wyrazów)\n• wynik → _moh.epub",
    "-q":  "Szybka walidacja wewnętrzna epubQTools\nNie wymaga Java ani zewnętrznego EpubCheck",
    "-p":  "Pełna walidacja EpubCheck\nWymaga: Java + plik epubcheck-5.x.zip w katalogu narzędzi",
    "-n":  "Zmienia nazwy plików wg metadanych:\n<dc:creator> i <dc:title> z pliku EPUB → 'autor - tytuł.epub'",
    "-k":  "Konwertuje _moh.epub → .mobi przez kindlegen\nWymaga kindlegen.exe w katalogu narzędzi",
    "-d":  "Kompresja huffdic — mniejszy plik .mobi, wolniejsze ładowanie\nStosować tylko razem z -k",
    "-t":  "Kopiuje _moh.epub jako tytuł.epub (do wysyłki na Kindle przez e-mail)",
    "-z":  "Konwertuje .mobi → .azk (wymaga narzędzia azkcreator)",
    "-a":  "Alternatywny układ wyjścia logów",
    "-m":  "Przetwarzaj tylko pliki _moh.epub\nPrzydatne do walidacji już naprawionych plików",
    "-f":  "Nadpisuje istniejące pliki wyjściowe\nBez tej opcji epubQTools pomija już istniejące pliki",
    "-i":  "Tryb pojedynczego pliku — przetwarza plik o podanym numerze indeksu",
    "--skip-hyphenate":         "Nie wstawiaj miękkich myślników\nPrzydatne gdy tekst jest angielski lub ma już własne dzielenie",
    "--skip-hyphenate-headers": "Pomija dzielenie wyrazów w nagłówkach h1–h3",
    "--skip-reset-css":         "Nie dodawaj bloku reset CSS\nUżyj gdy EPUB ma własny, dopracowany CSS",
    "--skip-justify":           "Nie dodawaj text-align: justify\nUżyj dla poezji lub specjalnych układów",
    "--left":                   "Wyrównanie tekstu do lewej zamiast justify\nPrzydatne dla poezji",
    "--replace-font-files":     "Zamienia pliki fontów w EPUB\nWymaga ustawionego --font-dir",
    "--myk-fix":                "Eksperymentalna poprawka dla konwerterów MYK — stosować ostrożnie",
    "--remove-colors":          "Usuwa deklaracje kolorów z CSS\nPrzydatne gdy e-czytnik ma własny tryb nocny",
    "--remove-fonts":           "Usuwa osadzone fonty — zmniejsza rozmiar EPUB\ne-czytnik używa własnych fontów",
    "--fix-missing-container":  "Naprawia brak wymaganego pliku META-INF/container.xml",
    "--list-fonts":             "Wyświetla listę fontów użytych w EPUB (tylko z -q)",
    "--book-margin":            "Ustawia szerokość marginesów strony [px]",
    "--replace-font-family":    "Zamienia rodzinę fontów w CSS\nFormat: stara_nazwa,nowa_nazwa  (np. Arial,Georgia)",
}


class Tooltip:
    """Dymek pomocy wyświetlany po najechaniu kursorem na widget."""

    def __init__(self, widget: tk.Widget, text: str, delay: int = 600):
        self._widget   = widget
        self._text     = text
        self._delay    = delay
        self._after_id = None
        self._win: tk.Toplevel | None = None
        widget.bind("<Enter>",       self._schedule, add="+")
        widget.bind("<Leave>",       self._cancel,   add="+")
        widget.bind("<ButtonPress>", self._cancel,   add="+")

    def _schedule(self, _=None):
        self._cancel()
        self._after_id = self._widget.after(self._delay, self._show)

    def _cancel(self, _=None):
        if self._after_id:
            self._widget.after_cancel(self._after_id)
            self._after_id = None
        self._hide()

    def _show(self):
        if self._win:
            return
        x = self._widget.winfo_rootx() + 12
        y = self._widget.winfo_rooty() + self._widget.winfo_height() + 4
        self._win = tw = tk.Toplevel(self._widget)
        tw.wm_overrideredirect(True)
        tw.wm_attributes("-topmost", True)
        tw.wm_geometry(f"+{x}+{y}")
        tk.Label(tw, text=self._text, justify="left",
                 background="#ffffe0", foreground="#1a1a1a",
                 relief="solid", borderwidth=1,
                 font=("Segoe UI", 9), wraplength=320,
                 padx=6, pady=4).pack()

    def _hide(self):
        if self._win:
            self._win.destroy()
            self._win = None


# ─── Styl ─────────────────────────────────────────────────────────────────────

def _setup_style(root: tk.Tk) -> None:
    s = ttk.Style(root)
    s.theme_use("clam")
    s.configure(".", background=BG, foreground=FG, bordercolor=BORDER,
                 troughcolor=BG3, fieldbackground=ENTRY_BG, font=("Segoe UI", 9))
    s.configure("TFrame",      background=BG)
    s.configure("TLabel",      background=BG, foreground=FG)
    s.configure("TLabelframe", background=BG, foreground=FG, bordercolor=BORDER)
    s.configure("TLabelframe.Label", background=BG, foreground=ACCENT,
                 font=("Segoe UI", 9, "bold"))
    s.configure("TNotebook",     background=BG2, bordercolor=BORDER)
    s.configure("TNotebook.Tab", background=BG3, foreground=FG_DIM,
                 padding=[12, 5], bordercolor=BORDER, font=("Segoe UI", 9))
    s.map("TNotebook.Tab",
          background=[("selected", BG), ("active", BG2)],
          foreground=[("selected", FG), ("active", FG)])
    s.configure("TEntry", fieldbackground=ENTRY_BG, foreground=FG, insertcolor=FG,
                 bordercolor=BORDER, lightcolor=BORDER, darkcolor=BORDER)
    s.configure("TCheckbutton", background=BG, foreground=FG, indicatorcolor=ENTRY_BG)
    s.map("TCheckbutton",
          indicatorcolor=[("selected", ACCENT), ("pressed", ACCENT_HV)],
          foreground=[("disabled", FG_DIM)])
    s.configure("TScrollbar", background=BG3, troughcolor=BG,
                 arrowcolor=FG_DIM, bordercolor=BG3, relief="flat")
    s.configure("Accent.TButton", background=BTN_BG, foreground=BTN_FG,
                 bordercolor=BTN_BG, font=("Segoe UI", 9, "bold"), padding=[10, 5])
    s.map("Accent.TButton",
          background=[("active", ACCENT_HV), ("pressed", ACCENT)],
          foreground=[("disabled", FG_DIM)])
    s.configure("TButton", background=BG3, foreground=FG,
                 bordercolor=BORDER, padding=[8, 4])
    s.map("TButton", background=[("active", ENTRY_BG)])
    s.configure("TSpinbox", fieldbackground=ENTRY_BG, foreground=FG,
                 bordercolor=BORDER, arrowcolor=FG)


# ─── Widgety pomocnicze ───────────────────────────────────────────────────────

class Section(ttk.LabelFrame):
    def __init__(self, parent, text, **kw):
        super().__init__(parent, text=text, padding=8, **kw)


class PathEntry(tk.Frame):
    """Pole tekstowe + przycisk '…' do wyboru pliku lub katalogu."""

    def __init__(self, parent, mode="dir", label="", filetypes=None, tooltip="", **kw):
        super().__init__(parent, bg=BG, **kw)
        self._mode = mode
        self._filetypes = filetypes or [("Wszystkie pliki", "*.*")]
        if label:
            tk.Label(self, text=label, bg=BG, fg=FG,
                     font=("Segoe UI", 9)).pack(side="left", padx=(0, 4))
        self.var = tk.StringVar()
        self._entry = ttk.Entry(self, textvariable=self.var)
        self._entry.pack(side="left", fill="x", expand=True, padx=(0, 4))
        btn = ttk.Button(self, text="…", width=3, command=self._browse)
        btn.pack(side="left")
        if tooltip:
            Tooltip(self._entry, tooltip)
            Tooltip(btn, tooltip)

    def _browse(self):
        if self._mode == "dir":
            path = filedialog.askdirectory()
        else:
            path = filedialog.askopenfilename(filetypes=self._filetypes)
        if path:
            self.var.set(path)

    def get(self) -> str:
        return self.var.get().strip()

    def set(self, value: str):
        self.var.set(value)


class FileList(tk.Frame):
    """Lista plików z paskiem narzędzi i opcjonalnym drag & drop."""

    def __init__(self, parent, filetypes=None, **kw):
        super().__init__(parent, bg=BG, **kw)
        self._filetypes = filetypes or [("Wszystkie pliki", "*.*")]

        bar = tk.Frame(self, bg=BG2)
        bar.pack(fill="x")
        _btn_tips = {
            "+ Dodaj":  "Dodaj pliki do listy",
            "✕ Usuń":  "Usuń zaznaczone pliki z listy",
            "Wyczyść": "Wyczyść całą listę",
            "↑":        "Przesuń zaznaczony plik w górę",
            "↓":        "Przesuń zaznaczony plik w dół",
        }
        for text, cmd in [("+ Dodaj", self._add), ("✕ Usuń", self._remove),
                          ("Wyczyść", self._clear)]:
            btn = ttk.Button(bar, text=text, command=cmd)
            btn.pack(side="left", padx=2, pady=2)
            Tooltip(btn, _btn_tips[text])
        for text, cmd in [("↑", self._up), ("↓", self._down)]:
            btn = ttk.Button(bar, text=text, width=2, command=cmd)
            btn.pack(side="left", padx=2, pady=2)
            Tooltip(btn, _btn_tips[text])

        if HAS_DND:
            tk.Label(bar, text="  ⟵ przeciągnij pliki", bg=BG2, fg=FG_DIM,
                     font=("Segoe UI", 8)).pack(side="left", padx=6)

        frame = tk.Frame(self, bg=BORDER)
        frame.pack(fill="both", expand=True, pady=(2, 0))
        sb = ttk.Scrollbar(frame, orient="vertical")
        self._lb = tk.Listbox(frame, bg=ENTRY_BG, fg=FG, selectbackground=ACCENT,
                               selectforeground=FG, activestyle="none",
                               font=("Consolas", 9), yscrollcommand=sb.set,
                               borderwidth=0, highlightthickness=0)
        sb.config(command=self._lb.yview)
        sb.pack(side="right", fill="y")
        self._lb.pack(side="left", fill="both", expand=True)

        if HAS_DND:
            self._lb.drop_target_register(DND_FILES)
            self._lb.dnd_bind("<<Drop>>", self._on_drop)

    def _on_drop(self, event):
        existing = set(self._lb.get(0, "end"))
        # tkinterdnd2 zwraca ścieżki w formacie {ścieżka ze spacjami} lub ścieżka
        try:
            paths = self._lb.tk.splitlist(event.data)
        except Exception:
            paths = [event.data]
        for p in paths:
            p = p.strip("{}")
            if p and p not in existing:
                self._lb.insert("end", p)
                existing.add(p)

    def _add(self):
        paths = filedialog.askopenfilenames(filetypes=self._filetypes)
        existing = set(self._lb.get(0, "end"))
        for p in paths:
            if p not in existing:
                self._lb.insert("end", p)

    def _remove(self):
        for i in reversed(self._lb.curselection()):
            self._lb.delete(i)

    def _clear(self):
        self._lb.delete(0, "end")

    def _up(self):
        sel = self._lb.curselection()
        if not sel or sel[0] == 0:
            return
        i = sel[0]
        val = self._lb.get(i)
        self._lb.delete(i)
        self._lb.insert(i - 1, val)
        self._lb.selection_set(i - 1)

    def _down(self):
        sel = self._lb.curselection()
        if not sel or sel[0] == self._lb.size() - 1:
            return
        i = sel[0]
        val = self._lb.get(i)
        self._lb.delete(i)
        self._lb.insert(i + 1, val)
        self._lb.selection_set(i + 1)

    def get_all(self) -> list[str]:
        return list(self._lb.get(0, "end"))

    def get_selected(self) -> str | None:
        sel = self._lb.curselection()
        return self._lb.get(sel[0]) if sel else None


# ─── Baza App (TkinterDnD jeśli dostępne) ────────────────────────────────────

_AppBase: type = TkinterDnD.Tk if HAS_DND else tk.Tk


# ─── Główna aplikacja ─────────────────────────────────────────────────────────

class App(_AppBase):
    def __init__(self):
        super().__init__()
        self.title("epubTools Suite")
        self.geometry("960x700")
        self.minsize(720, 500)
        self.configure(bg=BG)

        self._dark_theme = True
        # Etykiety ze specjalnymi kolorami — odświeżane przy zmianie motywu
        self._label_roles: dict[tk.Label, str] = {}

        # Ikonka w pasku tytułu (zachowaj referencję, żeby GC nie zebrał)
        self._app_icon = _create_app_icon()
        self.iconphoto(True, self._app_icon)

        _setup_style(self)

        self._eq_path = _find_epubqtools_main()
        self._conv_engine, self._conv_path = _find_converter()
        self._viewer_path = _find_viewer()
        self._sigil_path = _find_sigil()
        self._ebook_editor_path = _find_ebook_editor()
        self._kfx_kp3_path = _find_kindle_previewer()
        self._kfx_calibre_path = _find_calibre_ebook_convert()
        self._last_converted: str = ""

        self._build_toolbar()

        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        self._tab_eq   = ttk.Frame(nb)
        self._tab_conv = ttk.Frame(nb)
        self._tab_meta = ttk.Frame(nb)
        self._tab_kfx  = ttk.Frame(nb)
        nb.add(self._tab_eq,   text="  epubQTools  ")
        nb.add(self._tab_conv, text="  Konwerter EPUB  ")
        nb.add(self._tab_meta, text="  Metadane  ")
        nb.add(self._tab_kfx,  text="  Kindle KFX  ")

        self._build_tab_epubqtools()
        self._build_tab_converter()
        self._build_tab_metadata()
        self._build_tab_kfx()
        self._load_config()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ── Pasek narzędzi (górny) ────────────────────────────────────────────────

    def _build_toolbar(self):
        bar = tk.Frame(self, bg=BG2, height=32)
        bar.pack(fill="x", padx=0, pady=0)
        bar.pack_propagate(False)

        self._theme_btn = ttk.Button(bar, text="☀ Jasny motyw",
                                     command=self._toggle_theme)
        self._theme_btn.pack(side="right", padx=8, pady=4)
        Tooltip(self._theme_btn, "Przełącza między motywem ciemnym i jasnym")

    # ── Zakładka 1: epubQTools ────────────────────────────────────────────────

    def _build_tab_epubqtools(self):
        tab = self._tab_eq
        paned = tk.PanedWindow(tab, orient="horizontal", bg=BORDER,
                               sashwidth=4, sashrelief="flat",
                               handlepad=0, handlesize=0)
        paned.pack(fill="both", expand=True)

        # ── Lewa: opcje (scrollowalna) ────────────────────────────────────────
        left_outer = tk.Frame(paned, bg=BG)
        paned.add(left_outer, width=370, minsize=300)

        canvas = tk.Canvas(left_outer, bg=BG, highlightthickness=0)
        vsb = ttk.Scrollbar(left_outer, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        left = tk.Frame(canvas, bg=BG)
        win_id = canvas.create_window((0, 0), window=left, anchor="nw")

        left.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(win_id, width=e.width))
        canvas.bind_all("<MouseWheel>",
                        lambda e: canvas.yview_scroll(-1 * (e.delta // 120), "units"))

        self._flags: dict[str, tk.BooleanVar] = {}

        # Ścieżka epubQTools
        eq_sec = Section(left, "Ścieżka epubQTools (__main__.py)")
        eq_sec.pack(fill="x", padx=6, pady=4)
        self._eq_entry = PathEntry(eq_sec, mode="file",
                                   filetypes=[("Python", "__main__.py"), ("Wszystkie", "*.*")],
                                   tooltip="Ścieżka do __main__.py epubQTools\nZazwyczaj wykrywany automatycznie (dołączony do programu)")
        self._eq_entry.pack(fill="x")
        if self._eq_path:
            self._eq_entry.set(str(self._eq_path))
        eq_lbl = self._status_label(eq_sec,
            f"✓ Wykryto: {self._eq_path}" if self._eq_path else "✗ Nie znaleziono — wskaż ręcznie",
            "ok" if self._eq_path else "err")
        eq_lbl.pack(anchor="w", pady=(2, 0))

        # Interpreter Python
        py_sec = Section(left, "Interpreter Python (python.exe)")
        py_sec.pack(fill="x", padx=6, pady=4)
        py_detected = _find_python()
        self._py_entry = PathEntry(py_sec, mode="file",
                                   filetypes=[("Python", "*.exe"), ("Wszystkie", "*.*")],
                                   tooltip="Ścieżka do python.exe\nNiezbędny gdy program działa jako .exe —\nwbudowany sys.executable wskazuje wtedy na .exe, nie na Python")
        self._py_entry.pack(fill="x")
        if py_detected:
            self._py_entry.set(py_detected)
        py_lbl = self._status_label(py_sec,
            f"✓ Wykryto: {py_detected}" if py_detected else "✗ Nie znaleziono — wskaż python.exe ręcznie",
            "ok" if py_detected else "err")
        py_lbl.pack(anchor="w", pady=(2, 0))

        # Katalog z plikami EPUB
        dir_sec = Section(left, "Katalog z plikami EPUB (wymagany)")
        dir_sec.pack(fill="x", padx=6, pady=4)
        self._epub_dir = PathEntry(dir_sec, mode="dir",
                                   tooltip="Katalog z plikami .epub do przetworzenia\nepubQTools przetwarza wszystkie pliki .epub z tego katalogu")
        self._epub_dir.pack(fill="x")

        # Akcje
        act_sec = Section(left, "Akcje (przynajmniej jedna wymagana)")
        act_sec.pack(fill="x", padx=6, pady=4)
        for flag, desc in [
            ("-e", "Napraw EPUB → _moh.epub (CSS, dzielenie wyrazów)"),
            ("-q", "Walidacja wewnętrzna (qcheck)"),
            ("-p", "Walidacja EpubCheck 4"),
            ("-n", "Zmień nazwy plików (autor - tytuł.epub)"),
            ("-a", "Alternatywny widok wyjścia"),
            ("-k", "Konwertuj _moh.epub → .mobi (kindlegen)"),
            ("-d", "Kompresja huffdic dla Kindle (tylko z -k)"),
            ("-t", "Kopiuj MOH → tytuł.epub (Send to Kindle)"),
            ("-z", "Konwertuj .mobi → .azk (azkcreator)"),
        ]:
            self._add_check(act_sec, flag, desc)

        # Opcje modyfikacji
        opt_sec = Section(left, "Opcje modyfikacji (z -e)")
        opt_sec.pack(fill="x", padx=6, pady=4)
        for flag, desc in [
            ("--skip-hyphenate",         "Pomiń dzielenie wyrazów"),
            ("--skip-hyphenate-headers", "Pomiń dzielenie w nagłówkach h1–h3"),
            ("--skip-reset-css",         "Pomiń reset CSS"),
            ("--skip-justify",           "Pomiń justify"),
            ("--left",                   "Wyrównanie do lewej (zamiast justify)"),
            ("--replace-font-files",     "Zamień pliki fontów"),
            ("--myk-fix",                "Poprawka MYK (eksperymentalne)"),
            ("--remove-colors",          "Usuń kolory z CSS"),
            ("--remove-fonts",           "Usuń osadzone fonty"),
            ("--fix-missing-container",  "Napraw brak container.xml"),
            ("--list-fonts",             "Lista fontów (tylko z -q)"),
        ]:
            self._add_check(opt_sec, flag, desc)

        # Różne
        misc_sec = Section(left, "Różne")
        misc_sec.pack(fill="x", padx=6, pady=4)
        for flag, desc in [
            ("-m", "Tylko pliki _moh.epub (z -q lub -p)"),
            ("-f", "Force — nadpisz istniejące pliki"),
        ]:
            self._add_check(misc_sec, flag, desc)

        bm_row = tk.Frame(misc_sec, bg=BG)
        bm_row.pack(fill="x", pady=2)
        self._flags["--book-margin"] = tk.BooleanVar()
        ttk.Checkbutton(bm_row, variable=self._flags["--book-margin"],
                        text="--book-margin").pack(side="left")
        self._book_margin = tk.StringVar(value="10")
        ttk.Spinbox(bm_row, from_=0, to=999, width=5,
                    textvariable=self._book_margin).pack(side="left", padx=4)
        dim = tk.Label(bm_row, text="px", bg=BG, fg=FG_DIM)
        dim.pack(side="left")
        self._label_roles[dim] = "dim"

        ff_row = tk.Frame(misc_sec, bg=BG)
        ff_row.pack(fill="x", pady=2)
        self._flags["--replace-font-family"] = tk.BooleanVar()
        ttk.Checkbutton(ff_row, variable=self._flags["--replace-font-family"],
                        text="--replace-font-family").pack(side="left")
        self._font_family = tk.StringVar(value="stary,nowy")
        ttk.Entry(ff_row, textvariable=self._font_family, width=22).pack(side="left", padx=4)

        # Ścieżki zewnętrzne
        paths_sec = Section(left, "Ścieżki zewnętrzne (opcjonalne)")
        paths_sec.pack(fill="x", padx=6, pady=4)

        tk.Label(paths_sec, text="--tools (kindlegen, epubcheck):", bg=BG, fg=FG,
                 font=("Segoe UI", 9)).pack(anchor="w")
        self._tools_path = PathEntry(paths_sec, mode="dir",
                                     tooltip="Katalog z narzędziami zewnętrznymi:\n• kindlegen.exe — konwersja do .mobi\n• epubcheck-5.x.zip — walidacja EpubCheck\n\nPliki muszą znajdować się bezpośrednio w tym katalogu")
        self._tools_path.pack(fill="x", pady=(0, 2))

        tools_row = tk.Frame(paths_sec, bg=BG)
        tools_row.pack(fill="x", pady=(0, 6))
        self._kindlegen_lbl = tk.Label(tools_row, text="kindlegen: —",
                                       bg=BG, fg=FG_DIM, font=("Segoe UI", 8))
        self._kindlegen_lbl.pack(side="left", padx=(0, 16))
        self._epubcheck_lbl = tk.Label(tools_row, text="epubcheck: —",
                                       bg=BG, fg=FG_DIM, font=("Segoe UI", 8))
        self._epubcheck_lbl.pack(side="left")
        self._tools_path.var.trace_add("write", lambda *_: self._check_tools())

        for label, attr, tip in [
            ("-l  katalog logów:", "_logs_path",
             "Opcjonalny katalog, do którego epubQTools zapisuje pliki logów"),
            ("--font-dir:", "_font_dir",
             "Katalog z fontami do zamiany\nStosować tylko razem z --replace-font-files"),
        ]:
            tk.Label(paths_sec, text=label, bg=BG, fg=FG,
                     font=("Segoe UI", 9)).pack(anchor="w")
            pe = PathEntry(paths_sec, mode="dir", tooltip=tip)
            pe.pack(fill="x", pady=(0, 4))
            setattr(self, attr, pe)

        # Tryb pojedynczego pliku
        single_sec = Section(left, "Tryb pojedynczego pliku (-i)")
        single_sec.pack(fill="x", padx=6, pady=4)
        i_row = tk.Frame(single_sec, bg=BG)
        i_row.pack(fill="x", pady=2)
        self._flags["-i"] = tk.BooleanVar()
        ttk.Checkbutton(i_row, variable=self._flags["-i"],
                        text="-i  numer pliku:").pack(side="left")
        self._single_i = tk.StringVar(value="1")
        ttk.Spinbox(i_row, from_=1, to=9999, width=6,
                    textvariable=self._single_i).pack(side="left", padx=4)
        tk.Label(single_sec, text="--author:", bg=BG, fg=FG,
                 font=("Segoe UI", 9)).pack(anchor="w")
        self._eq_author = ttk.Entry(single_sec)
        self._eq_author.pack(fill="x", pady=(0, 4))
        tk.Label(single_sec, text="--title:", bg=BG, fg=FG,
                 font=("Segoe UI", 9)).pack(anchor="w")
        self._eq_title = ttk.Entry(single_sec)
        self._eq_title.pack(fill="x")

        # ── Prawa: lista plików + log ─────────────────────────────────────────
        right = tk.Frame(paned, bg=BG)
        paned.add(right, minsize=340)

        # Lista wykrytych plików EPUB
        epub_list_sec = Section(right, "Pliki EPUB w katalogu")
        epub_list_sec.pack(fill="both", expand=True, padx=6, pady=(6, 2))

        # Listbox z plikami
        lb_frame = tk.Frame(epub_list_sec, bg=BORDER)
        lb_frame.pack(fill="both", expand=True)
        lb_sb = ttk.Scrollbar(lb_frame, orient="vertical")
        self._epub_lb = tk.Listbox(
            lb_frame, bg=ENTRY_BG, fg=FG, selectbackground=ACCENT,
            selectforeground=FG, activestyle="none",
            font=("Consolas", 9), yscrollcommand=lb_sb.set,
            borderwidth=0, highlightthickness=0,
        )
        lb_sb.config(command=self._epub_lb.yview)
        lb_sb.pack(side="right", fill="y")
        self._epub_lb.pack(side="left", fill="both", expand=True)
        self._epub_lb.bind("<Double-Button-1>", lambda e: self._open_in_default_editor())
        Tooltip(self._epub_lb,
                "Lista plików .epub w wybranym katalogu\n"
                "★ = plik _moh.epub (po naprawie przez -e)\n"
                "Dwuklik = otwiera w pierwszym dostępnym edytorze")

        # Przyciski edytorów
        ed_bar = tk.Frame(epub_list_sec, bg=BG)
        ed_bar.pack(fill="x", pady=(4, 0))

        sigil_txt  = "Sigil ✓" if self._sigil_path  else "Sigil ✗"
        caled_txt  = "Calibre editor ✓" if self._ebook_editor_path else "Calibre editor ✗"

        btn_sigil = ttk.Button(ed_bar, text=f"✎  {sigil_txt}",
                               command=self._open_in_sigil)
        btn_sigil.pack(side="left", padx=(0, 4))
        Tooltip(btn_sigil, "Otwiera zaznaczony plik EPUB w edytorze Sigil\nDwuklik na plik w liście też otwiera edytor")

        btn_caled = ttk.Button(ed_bar, text=f"✎  {caled_txt}",
                               command=self._open_in_calibre_editor)
        btn_caled.pack(side="left", padx=(0, 4))
        Tooltip(btn_caled, "Otwiera zaznaczony plik EPUB w Calibre e-book editor")

        btn_ref = ttk.Button(ed_bar, text="↺", width=3,
                             command=self._refresh_epub_list)
        btn_ref.pack(side="right")
        Tooltip(btn_ref, "Odświeża listę plików .epub w wybranym katalogu")

        self._epub_count_lbl = tk.Label(epub_list_sec, text="", bg=BG, fg=FG_DIM,
                                         font=("Segoe UI", 8))
        self._epub_count_lbl.pack(anchor="w", pady=(2, 0))
        self._label_roles[self._epub_count_lbl] = "dim"

        # Odśwież listę gdy zmieni się katalog
        self._epub_dir.var.trace_add("write", lambda *_: self.after(300, self._refresh_epub_list))

        btn_run_eq = ttk.Button(right, text="▶  Uruchom epubQTools", style="Accent.TButton",
                                command=self._run_epubqtools)
        btn_run_eq.pack(fill="x", padx=6, pady=4)
        Tooltip(btn_run_eq, "Uruchamia epubQTools z zaznaczonymi opcjami\n"
                            "Wymagane: katalog EPUB, interpreter Python i ≥1 akcja")

        log_sec = Section(right, "Log")
        log_sec.pack(fill="both", expand=True, padx=6, pady=(0, 6))
        self._eq_log = self._make_log(log_sec)

    def _add_check(self, parent, flag: str, desc: str):
        self._flags[flag] = tk.BooleanVar()
        cb = ttk.Checkbutton(parent, variable=self._flags[flag],
                             text=f"{flag}   {desc}")
        cb.pack(anchor="w", pady=1)
        if flag in _TIPS:
            Tooltip(cb, _TIPS[flag])

    def _status_label(self, parent, text: str, role: str) -> tk.Label:
        """Tworzy etykietę stanu z zapamiętaną rolą koloru (ok/err/dim)."""
        color = {"ok": TAG_OK, "err": TAG_ERR, "dim": FG_DIM}.get(role, FG)
        lbl = tk.Label(parent, text=text, bg=BG, fg=color, font=("Segoe UI", 8))
        self._label_roles[lbl] = role
        return lbl

    # ── Zakładka 3: Metadane ──────────────────────────────────────────────────

    def _build_tab_metadata(self):
        tab = self._tab_meta
        paned = tk.PanedWindow(tab, orient="horizontal", bg=BORDER,
                               sashwidth=4, sashrelief="flat",
                               handlepad=0, handlesize=0)
        paned.pack(fill="both", expand=True)

        # ── Lewa: katalog + lista plików ─────────────────────────────────────
        left = tk.Frame(paned, bg=BG)
        paned.add(left, width=290, minsize=220)

        dir_sec = Section(left, "Katalog z plikami EPUB")
        dir_sec.pack(fill="x", padx=6, pady=4)
        self._meta_dir = PathEntry(dir_sec, mode="dir",
                                   tooltip="Katalog z plikami .epub\nLista zostanie odświeżona automatycznie")
        self._meta_dir.pack(fill="x")
        self._meta_dir.var.trace_add("write",
                                     lambda *_: self.after(300, self._refresh_meta_list))

        epub_sec = Section(left, "Pliki EPUB")
        epub_sec.pack(fill="both", expand=True, padx=6, pady=(0, 4))

        lb_frame = tk.Frame(epub_sec, bg=BORDER)
        lb_frame.pack(fill="both", expand=True)
        lb_sb = ttk.Scrollbar(lb_frame, orient="vertical")
        self._meta_lb = tk.Listbox(
            lb_frame, bg=ENTRY_BG, fg=FG, selectbackground=ACCENT,
            selectforeground=FG, activestyle="none",
            font=("Consolas", 9), yscrollcommand=lb_sb.set,
            borderwidth=0, highlightthickness=0,
        )
        lb_sb.config(command=self._meta_lb.yview)
        lb_sb.pack(side="right", fill="y")
        self._meta_lb.pack(side="left", fill="both", expand=True)
        self._meta_lb.bind("<<ListboxSelect>>",
                           lambda _: self.after(50, self._meta_load))
        Tooltip(self._meta_lb,
                "Kliknij plik, aby wyświetlić jego metadane\n"
                "★ = plik _moh.epub\n"
                "Możesz przeciągnąć pliki .epub na tę listę")

        if HAS_DND:
            self._meta_lb.drop_target_register(DND_FILES)
            self._meta_lb.dnd_bind("<<Drop>>", self._on_meta_drop)

        btn_bar = tk.Frame(epub_sec, bg=BG)
        btn_bar.pack(fill="x", pady=(4, 0))
        btn_add = ttk.Button(btn_bar, text="+ Dodaj plik",
                             command=self._meta_add_file)
        btn_add.pack(side="left", padx=(0, 4))
        Tooltip(btn_add, "Otwórz okno wyboru i dodaj pojedynczy plik .epub")
        btn_ref = ttk.Button(btn_bar, text="↺", width=3,
                             command=self._refresh_meta_list)
        btn_ref.pack(side="right")
        Tooltip(btn_ref, "Odśwież listę plików z wybranego katalogu")

        self._meta_count_lbl = tk.Label(epub_sec, text="", bg=BG, fg=FG_DIM,
                                         font=("Segoe UI", 8))
        self._meta_count_lbl.pack(anchor="w", pady=(2, 0))
        self._label_roles[self._meta_count_lbl] = "dim"

        # ── Prawa: formularz metadanych ───────────────────────────────────────
        right = tk.Frame(paned, bg=BG)
        paned.add(right, minsize=380)

        # Etykieta aktualnie edytowanego pliku
        self._meta_file_lbl = tk.Label(
            right, text="(nie wybrano pliku)", bg=BG, fg=FG_DIM,
            font=("Segoe UI", 8), anchor="w", wraplength=500)
        self._meta_file_lbl.pack(fill="x", padx=8, pady=(6, 2))
        self._label_roles[self._meta_file_lbl] = "dim"

        # Scrollowalny obszar pól
        meta_outer = tk.Frame(right, bg=BG)
        meta_outer.pack(fill="both", expand=True, padx=6)

        canvas_m = tk.Canvas(meta_outer, bg=BG, highlightthickness=0)
        vsb_m = ttk.Scrollbar(meta_outer, orient="vertical", command=canvas_m.yview)
        canvas_m.configure(yscrollcommand=vsb_m.set)
        vsb_m.pack(side="right", fill="y")
        canvas_m.pack(side="left", fill="both", expand=True)

        fields_frame = tk.Frame(canvas_m, bg=BG)
        win_id_m = canvas_m.create_window((0, 0), window=fields_frame, anchor="nw")
        fields_frame.bind("<Configure>",
                          lambda e: canvas_m.configure(
                              scrollregion=canvas_m.bbox("all")))
        canvas_m.bind("<Configure>",
                      lambda e: canvas_m.itemconfig(win_id_m, width=e.width))
        canvas_m.bind_all("<MouseWheel>",
                          lambda e: canvas_m.yview_scroll(
                              -1 * (e.delta // 120), "units"))

        # Pola metadanych
        self._meta_fields: dict[str, tk.StringVar | tk.Text] = {}
        self._meta_desc_widget: tk.Text | None = None

        for key, label, kind in _META_FIELDS:
            tk.Label(fields_frame, text=label + ":", bg=BG, fg=FG,
                     font=("Segoe UI", 9)).pack(anchor="w", padx=4, pady=(4, 0))
            if kind == "text":
                txt = tk.Text(fields_frame, bg=ENTRY_BG, fg=FG,
                              insertbackground=FG, height=5,
                              font=("Segoe UI", 9), borderwidth=1,
                              relief="flat", wrap="word")
                txt.pack(fill="x", padx=4, pady=(2, 0))
                txt._entry_style = True   # oznaczenie dla _recolor_widgets
                self._meta_fields[key] = txt
                self._meta_desc_widget = txt
            else:
                var = tk.StringVar()
                ttk.Entry(fields_frame, textvariable=var).pack(
                    fill="x", padx=4, pady=(2, 0))
                self._meta_fields[key] = var

        # Przyciski
        btn_frame = tk.Frame(right, bg=BG)
        btn_frame.pack(fill="x", padx=6, pady=6)
        btn_save = ttk.Button(btn_frame, text="💾  Zapisz metadane",
                              style="Accent.TButton",
                              command=self._meta_save)
        btn_save.pack(side="left", fill="x", expand=True, padx=(0, 4))
        Tooltip(btn_save,
                "Zapisuje zmiany do pliku EPUB\n"
                "Kopia zapasowa zapisywana jako .epub.bak")
        btn_clr = ttk.Button(btn_frame, text="✕ Wyczyść",
                             command=self._meta_clear)
        btn_clr.pack(side="left")
        Tooltip(btn_clr, "Czyści wszystkie pola (nie modyfikuje pliku)")

        # Mały log
        log_sec = Section(right, "Log")
        log_sec.pack(fill="both", expand=False, padx=6, pady=(0, 6))
        self._meta_log = self._make_log(log_sec)

        # Lista ścieżek plików widocznych w listboxie
        self._meta_files: list[str] = []
        self._meta_current_opf: str = ""   # ścieżka OPF w aktualnym pliku
        self._meta_current_epub: str = ""  # ścieżka do aktualnego .epub

    # ── Zakładka 4: Kindle KFX ───────────────────────────────────────────────

    def _build_tab_kfx(self):
        tab = self._tab_kfx
        paned = tk.PanedWindow(tab, orient="horizontal", bg=BORDER,
                               sashwidth=4, sashrelief="flat",
                               handlepad=0, handlesize=0)
        paned.pack(fill="both", expand=True)

        # ── Lewa: ustawienia ─────────────────────────────────────────────────
        left = tk.Frame(paned, bg=BG)
        paned.add(left, width=340, minsize=280)

        # Silnik konwersji
        eng_sec = Section(left, "Silnik konwersji")
        eng_sec.pack(fill="x", padx=6, pady=4)

        self._kfx_engine = tk.StringVar(value="kp3")

        # Kindle Previewer 3
        kp3_row = tk.Frame(eng_sec, bg=BG)
        kp3_row.pack(fill="x")
        ttk.Radiobutton(kp3_row, text="Kindle Previewer 3  (zalecany)",
                        variable=self._kfx_engine, value="kp3").pack(side="left")
        kp3_lbl = self._status_label(eng_sec,
            "✓ Wykryto" if self._kfx_kp3_path else "✗ Nie znaleziono",
            "ok" if self._kfx_kp3_path else "err")
        kp3_lbl.pack(anchor="w", padx=(22, 0))
        self._kfx_kp3_entry = PathEntry(
            eng_sec, mode="file",
            filetypes=[("Kindle Previewer", "KindlePreviewer.exe"), ("Exe", "*.exe")],
            tooltip="Ścieżka do pliku .exe KP3 (nie .bat!)\n"
                    "Plik może nazywać się:\n"
                    "  'Kindle Previewer 3.exe' lub 'KindlePreviewer.exe'\n"
                    "Pobierz z: amazon.com/kindlepreview\n"
                    "Typowe lokalizacje:\n"
                    "C:\\Program Files\\Amazon\\Kindle Previewer 3\\\n"
                    "AppData\\Local\\Amazon\\Kindle Previewer 3\\\n"
                    "AppData\\Roaming\\Amazon\\Kindle Previewer 3\\")
        self._kfx_kp3_entry.pack(fill="x", pady=(0, 6))
        if self._kfx_kp3_path:
            self._kfx_kp3_entry.set(self._kfx_kp3_path)

        # Calibre KFX
        cal_row = tk.Frame(eng_sec, bg=BG)
        cal_row.pack(fill="x")
        ttk.Radiobutton(cal_row, text="Calibre  (wymaga wtyczki KFX Output)",
                        variable=self._kfx_engine, value="calibre").pack(side="left")
        cal_has = _calibre_has_kfx(self._kfx_calibre_path)
        if self._kfx_calibre_path:
            cal_status = "✓ Wykryto + wtyczka KFX" if cal_has else "✓ Wykryto  (brak wtyczki KFX — konwersja nie zadziała)"
            cal_role = "ok" if cal_has else "err"
        else:
            cal_status = "✗ Nie znaleziono Calibre"
            cal_role = "err"
        cal_lbl = self._status_label(eng_sec, cal_status, cal_role)
        cal_lbl.pack(anchor="w", padx=(22, 0))
        self._kfx_calibre_entry = PathEntry(
            eng_sec, mode="file",
            filetypes=[("ebook-convert", "ebook-convert.exe"), ("Exe", "*.exe")],
            tooltip="Ścieżka do ebook-convert Calibre\n"
                    "Wymaga zainstalowanej wtyczki 'KFX Output':\n"
                    "Calibre → Preferencje → Wtyczki → Pobierz nowe wtyczki")
        self._kfx_calibre_entry.pack(fill="x", pady=(0, 4))
        if self._kfx_calibre_path:
            self._kfx_calibre_entry.set(self._kfx_calibre_path)
        lnk = tk.Label(eng_sec,
                       text="Wtyczka KFX Output: Calibre → Preferencje → Wtyczki",
                       bg=BG, fg=FG_DIM, font=("Segoe UI", 8))
        lnk.pack(anchor="w")

        # Katalog wyjściowy
        out_sec = Section(left, "Katalog wyjściowy")
        out_sec.pack(fill="x", padx=6, pady=4)
        self._kfx_outdir = PathEntry(
            out_sec, mode="dir",
            tooltip="Katalog docelowy dla plików .kfx\n"
                    "Jeśli puste — plik .kfx trafia obok pliku wejściowego")
        self._kfx_outdir.pack(fill="x")
        lbl_out = tk.Label(out_sec, text="(domyślnie: katalog pliku wejściowego)",
                           bg=BG, fg=FG_DIM, font=("Segoe UI", 8))
        lbl_out.pack(anchor="w")
        self._label_roles[lbl_out] = "dim"

        # Przygotowanie EPUB
        prep_sec = Section(left, "Przygotowanie EPUB przed konwersją")
        prep_sec.pack(fill="x", padx=6, pady=4)

        self._kfx_fix = tk.BooleanVar(value=True)
        fix_cb = ttk.Checkbutton(prep_sec, variable=self._kfx_fix,
                                 text="Napraw EPUB przez epubQTools -e")
        fix_cb.pack(anchor="w")
        Tooltip(fix_cb,
                "Uruchamia epubQTools -e przed konwersją:\n"
                "• normalizuje i czyści CSS\n"
                "• wstawia miękkie myślniki\n"
                "• naprawia typowe błędy struktury\n\n"
                "Konwerter KFX jest wymagający — naprawa znacząco\n"
                "zwiększa szansę powodzenia konwersji.\n\n"
                "Wymaga: skonfigurowanego Python i epubQTools\n"
                "(zakładka epubQTools).")

        self._kfx_cleanup = tk.BooleanVar(value=True)
        cleanup_cb = ttk.Checkbutton(prep_sec, variable=self._kfx_cleanup,
                                     text="Usuń plik _moh.epub po konwersji")
        cleanup_cb.pack(anchor="w")
        Tooltip(cleanup_cb,
                "Usuwa tymczasowy _moh.epub po zakończeniu konwersji\n"
                "Odznacz, jeśli chcesz zachować naprawiony EPUB")

        info = tk.Label(prep_sec,
                        text="Konwerter KFX często odrzuca nieprawidłowe EPUB.\n"
                             "Zaleca się zawsze naprawiać przed konwersją.",
                        bg=BG, fg=FG_DIM, font=("Segoe UI", 8),
                        wraplength=280, justify="left")
        info.pack(anchor="w", pady=(6, 0))
        self._label_roles[info] = "dim"

        # ── Prawa: lista plików + log ─────────────────────────────────────────
        right = tk.Frame(paned, bg=BG)
        paned.add(right, minsize=340)

        files_sec = Section(right, "Pliki EPUB do konwersji")
        files_sec.pack(fill="both", expand=True, padx=6, pady=(6, 2))
        self._kfx_files = FileList(files_sec,
                                   filetypes=[("EPUB", "*.epub"), ("Wszystkie", "*.*")])
        self._kfx_files.pack(fill="both", expand=True)
        Tooltip(self._kfx_files._lb,
                "Lista plików .epub do konwersji do formatu KFX\n"
                "Przeciągnij pliki lub użyj '+ Dodaj'\n"
                "Wskazówka: możesz dodać pliki _moh.epub (już naprawione)")

        btn_run = ttk.Button(right, text="▶  Konwertuj do KFX",
                             style="Accent.TButton", command=self._run_kfx)
        btn_run.pack(fill="x", padx=6, pady=4)
        Tooltip(btn_run,
                "Konwertuje wszystkie pliki z listy do formatu .kfx\n"
                "Jeśli zaznaczono naprawę — najpierw uruchamia epubQTools -e\n"
                "Każdy plik przetwarzany jest sekwencyjnie")

        log_sec = Section(right, "Log")
        log_sec.pack(fill="both", expand=True, padx=6, pady=(0, 6))
        self._kfx_log = self._make_log(log_sec)

    # ── Zakładka 2: Konwerter ─────────────────────────────────────────────────

    def _build_tab_converter(self):
        tab = self._tab_conv
        paned = tk.PanedWindow(tab, orient="horizontal", bg=BORDER,
                               sashwidth=4, sashrelief="flat",
                               handlepad=0, handlesize=0)
        paned.pack(fill="both", expand=True)

        # ── Lewa: ustawienia ─────────────────────────────────────────────────
        left = tk.Frame(paned, bg=BG)
        paned.add(left, width=300, minsize=240)

        # Silnik
        eng_sec = Section(left, "Silnik konwersji")
        eng_sec.pack(fill="x", padx=6, pady=4)
        eng_text = (f"✓ {self._conv_engine}\n{self._conv_path}" if self._conv_engine
                    else "✗ Nie znaleziono pandoc ani calibre\nZainstaluj pandoc z pandoc.org")
        eng_lbl = self._status_label(eng_sec, eng_text, "ok" if self._conv_engine else "err")
        eng_lbl.configure(justify="left")
        eng_lbl.pack(anchor="w")

        # Calibre viewer
        viewer_sec = Section(left, "Podgląd EPUB")
        viewer_sec.pack(fill="x", padx=6, pady=4)
        vwr_text = (f"✓ ebook-viewer wykryty" if self._viewer_path
                    else "✗ Nie znaleziono — zainstaluj Calibre")
        vwr_lbl = self._status_label(viewer_sec, vwr_text,
                                     "ok" if self._viewer_path else "dim")
        vwr_lbl.pack(anchor="w", pady=(0, 4))
        btn_prev_sel = ttk.Button(viewer_sec, text="🔍 Otwórz wybrany plik w Calibre",
                                  command=self._preview_selected)
        btn_prev_sel.pack(fill="x")
        Tooltip(btn_prev_sel, "Otwiera zaznaczony plik z listy w Calibre viewer")

        btn_prev_last = ttk.Button(viewer_sec, text="🔍 Otwórz ostatnio skonwertowany",
                                   command=self._preview_last)
        btn_prev_last.pack(fill="x", pady=(4, 0))
        Tooltip(btn_prev_last, "Otwiera ostatnio skonwertowany plik EPUB w Calibre viewer")

        # Metadane
        meta_sec = Section(left, "Metadane EPUB (opcjonalne)")
        meta_sec.pack(fill="x", padx=6, pady=4)
        for label, attr, default in [
            ("Tytuł:", "_conv_title", ""),
            ("Autor:", "_conv_author", ""),
            ("Język:", "_conv_lang", "pl"),
        ]:
            tk.Label(meta_sec, text=label, bg=BG, fg=FG,
                     font=("Segoe UI", 9)).pack(anchor="w")
            entry = ttk.Entry(meta_sec)
            entry.pack(fill="x", pady=(0, 4))
            if default:
                entry.insert(0, default)
            setattr(self, attr, entry)

        # Katalog wyjściowy
        out_sec = Section(left, "Wyjście")
        out_sec.pack(fill="x", padx=6, pady=4)
        tk.Label(out_sec, text="Katalog wyjściowy:", bg=BG, fg=FG,
                 font=("Segoe UI", 9)).pack(anchor="w")
        self._conv_outdir = PathEntry(out_sec, mode="dir",
                                      tooltip="Katalog, do którego zapisywane są skonwertowane pliki .epub\nPuste = zapisuje obok pliku wejściowego")
        self._conv_outdir.pack(fill="x", pady=(0, 2))
        hint = tk.Label(out_sec, text="(puste = obok pliku wejściowego)",
                        bg=BG, fg=FG_DIM, font=("Segoe UI", 8))
        hint.pack(anchor="w")
        self._label_roles[hint] = "dim"

        # Opcje pandoc
        if self._conv_engine == "pandoc":
            po_sec = Section(left, "Opcje pandoc")
            po_sec.pack(fill="x", padx=6, pady=4)
            self._pandoc_toc = tk.BooleanVar()
            cb_toc = ttk.Checkbutton(po_sec, variable=self._pandoc_toc,
                                     text="--toc   Spis treści")
            cb_toc.pack(anchor="w")
            Tooltip(cb_toc, "Dodaje automatyczny spis treści (Table of Contents) do EPUB")
            self._pandoc_standalone = tk.BooleanVar(value=True)
            cb_stand = ttk.Checkbutton(po_sec, variable=self._pandoc_standalone,
                                       text="--standalone")
            cb_stand.pack(anchor="w")
            Tooltip(cb_stand, "Tworzy kompletny, samodzielny dokument EPUB z pełnym nagłówkiem")
            tk.Label(po_sec, text="--epub-chapter-level:", bg=BG, fg=FG,
                     font=("Segoe UI", 9)).pack(anchor="w", pady=(4, 0))
            self._pandoc_chapter = tk.StringVar(value="1")
            sp_ch = ttk.Spinbox(po_sec, from_=1, to=6, width=4,
                                textvariable=self._pandoc_chapter)
            sp_ch.pack(anchor="w", pady=2)
            Tooltip(sp_ch, "Poziom nagłówka Markdown (1–6), od którego zaczyna się nowy rozdział EPUB")

        # ── Prawa: pliki + log ────────────────────────────────────────────────
        right = tk.Frame(paned, bg=BG)
        paned.add(right, minsize=320)

        files_sec = Section(right, "Pliki do konwersji")
        files_sec.pack(fill="both", expand=True, padx=6, pady=(4, 2))

        conv_types = [
            ("Obsługiwane formaty",
             "*.txt *.md *.markdown *.docx *.html *.htm *.odt *.rtf "
             "*.rst *.org *.epub *.fb2 *.tex *.mobi *.pdf"),
            ("PDF", "*.pdf"),
            ("Wszystkie pliki", "*.*"),
        ]
        self._conv_files = FileList(files_sec, filetypes=conv_types)
        self._conv_files.pack(fill="both", expand=True)

        pdf_note = tk.Label(files_sec,
                            text="⚠ PDF wymaga Calibre (ebook-convert) — Pandoc nie obsługuje PDF.",
                            bg=BG, fg=FG_DIM, font=("Segoe UI", 8),
                            wraplength=340, justify="left")
        pdf_note.pack(anchor="w", pady=(2, 0))
        self._label_roles[pdf_note] = "dim"

        btn_row = tk.Frame(right, bg=BG)
        btn_row.pack(fill="x", padx=6, pady=4)
        btn_conv = ttk.Button(btn_row, text="▶  Konwertuj do EPUB", style="Accent.TButton",
                              command=self._run_converter)
        btn_conv.pack(side="left", fill="x", expand=True)
        Tooltip(btn_conv, "Konwertuje wszystkie pliki z listy do formatu EPUB\n"
                          "Silnik: Pandoc (główny) lub Calibre ebook-convert (zapasowy)")

        log_sec = Section(right, "Log")
        log_sec.pack(fill="both", expand=True, padx=6, pady=(0, 6))
        self._conv_log = self._make_log(log_sec)

    # ── Metadane — logika ─────────────────────────────────────────────────────

    def _refresh_meta_list(self):
        """Skanuje katalog i aktualizuje listę plików EPUB."""
        self._meta_lb.delete(0, "end")
        self._meta_files.clear()
        d = self._meta_dir.get()
        if d and Path(d).is_dir():
            files = sorted(Path(d).glob("*.epub"), key=lambda p: p.name.lower())
            for f in files:
                marker = "★ " if f.name.endswith("_moh.epub") else "  "
                self._meta_lb.insert("end", marker + f.name)
                self._meta_files.append(str(f))
            n = len(files)
            self._meta_count_lbl.config(text=f"{n} plików EPUB")
        else:
            self._meta_count_lbl.config(text="")

    def _on_meta_drop(self, event):
        """Obsługuje drag & drop plików .epub na listę metadanych."""
        try:
            paths = self._meta_lb.tk.splitlist(event.data)
        except Exception:
            paths = [event.data]
        existing = set(self._meta_files)
        for p in paths:
            p = p.strip("{}")
            if p.lower().endswith(".epub") and p not in existing:
                name = Path(p).name
                marker = "★ " if name.endswith("_moh.epub") else "  "
                self._meta_lb.insert("end", marker + name)
                self._meta_files.append(p)
                existing.add(p)
        self._meta_count_lbl.config(text=f"{len(self._meta_files)} plików EPUB")

    def _meta_add_file(self):
        """Dodaje pojedynczy plik .epub przez okno dialogowe."""
        paths = filedialog.askopenfilenames(
            filetypes=[("EPUB", "*.epub"), ("Wszystkie pliki", "*.*")])
        existing = set(self._meta_files)
        for p in paths:
            if p not in existing:
                name = Path(p).name
                marker = "★ " if name.endswith("_moh.epub") else "  "
                self._meta_lb.insert("end", marker + name)
                self._meta_files.append(p)
                existing.add(p)
        self._meta_count_lbl.config(text=f"{len(self._meta_files)} plików EPUB")

    def _meta_selected_path(self) -> str:
        sel = self._meta_lb.curselection()
        if not sel:
            return ""
        idx = sel[0]
        return self._meta_files[idx] if idx < len(self._meta_files) else ""

    def _meta_set(self, key: str, value: str):
        w = self._meta_fields.get(key)
        if w is None:
            return
        if isinstance(w, tk.StringVar):
            w.set(value)
        else:
            w.configure(state="normal")
            w.delete("1.0", "end")
            w.insert("1.0", value)

    def _meta_get(self, key: str) -> str:
        w = self._meta_fields.get(key)
        if w is None:
            return ""
        if isinstance(w, tk.StringVar):
            return w.get().strip()
        return w.get("1.0", "end-1c").strip()

    def _meta_load(self):
        """Wczytuje metadane zaznaczonego pliku EPUB do formularza."""
        path = self._meta_selected_path()
        if not path or not Path(path).is_file():
            return
        try:
            meta, opf_path = _epub_read_metadata(path)
        except Exception as ex:
            self._log(self._meta_log, f"✗ Błąd odczytu: {ex}\n", "err")
            return
        for key, *_ in _META_FIELDS:
            self._meta_set(key, meta.get(key, ""))
        self._meta_current_epub = path
        self._meta_current_opf  = opf_path
        self._meta_file_lbl.config(text=str(path), fg=FG_DIM)
        self._log(self._meta_log, f"✓ Załadowano: {Path(path).name}\n", "ok")

    def _meta_save(self):
        """Zapisuje zmiany metadanych do pliku EPUB."""
        path = self._meta_current_epub
        if not path or not Path(path).is_file():
            messagebox.showwarning("Brak pliku",
                "Najpierw zaznacz plik EPUB na liście.")
            return
        meta = {key: self._meta_get(key) for key, *_ in _META_FIELDS}
        try:
            _epub_write_metadata(path, meta, self._meta_current_opf)
        except Exception as ex:
            self._log(self._meta_log, f"✗ Błąd zapisu: {ex}\n", "err")
            messagebox.showerror("Błąd zapisu", str(ex))
            return
        self._log(self._meta_log,
                  f"✓ Zapisano: {Path(path).name}  "
                  f"(kopia: {Path(path).name}.bak)\n", "ok")

    def _meta_clear(self):
        """Czyści wszystkie pola formularza."""
        for key, *_ in _META_FIELDS:
            self._meta_set(key, "")
        self._meta_file_lbl.config(text="(nie wybrano pliku)", fg=FG_DIM)
        self._meta_current_epub = ""
        self._meta_current_opf  = ""

    # ── Motyw ─────────────────────────────────────────────────────────────────

    def _toggle_theme(self):
        self._dark_theme = not self._dark_theme
        self._apply_theme(self._dark_theme)

    def _apply_theme(self, dark: bool):
        global BG, BG2, BG3, FG, FG_DIM, ACCENT, ACCENT_HV
        global ENTRY_BG, BORDER, BTN_BG, BTN_FG, LOG_BG, LOG_FG
        global TAG_OK, TAG_ERR, TAG_WARN

        theme = DARK if dark else LIGHT
        BG = theme["BG"]; BG2 = theme["BG2"]; BG3 = theme["BG3"]
        FG = theme["FG"]; FG_DIM = theme["FG_DIM"]
        ACCENT = theme["ACCENT"]; ACCENT_HV = theme["ACCENT_HV"]
        ENTRY_BG = theme["ENTRY_BG"]; BORDER = theme["BORDER"]
        BTN_BG = theme["BTN_BG"]; BTN_FG = theme["BTN_FG"]
        LOG_BG = theme["LOG_BG"]; LOG_FG = theme["LOG_FG"]
        TAG_OK = theme["TAG_OK"]; TAG_ERR = theme["TAG_ERR"]; TAG_WARN = theme["TAG_WARN"]

        _setup_style(self)
        self.configure(bg=BG)
        self._recolor_widgets(self)

        # Aktualizuj etykiety z zapamiętaną rolą koloru
        role_colors = {"ok": TAG_OK, "err": TAG_ERR, "dim": FG_DIM}
        for lbl, role in self._label_roles.items():
            try:
                lbl.configure(bg=BG, fg=role_colors.get(role, FG))
            except Exception:
                pass

        # Odśwież dynamiczne etykiety narzędzi
        self._check_tools()

        self._theme_btn.configure(
            text="🌙 Ciemny motyw" if not dark else "☀ Jasny motyw"
        )

    def _recolor_widgets(self, widget):
        """Rekurencyjnie aktualizuje kolory tk.* widgetów."""
        cls = widget.winfo_class()
        try:
            if cls in ("Frame", "Labelframe"):
                widget.configure(bg=BG)
            elif cls == "Label":
                if widget not in self._label_roles:
                    widget.configure(bg=BG, fg=FG)
                else:
                    widget.configure(bg=BG)
            elif cls == "Text":
                if getattr(widget, "_entry_style", False):
                    widget.configure(bg=ENTRY_BG, fg=FG, insertbackground=FG)
                else:
                    widget.configure(bg=LOG_BG, fg=LOG_FG,
                                     insertbackground=LOG_FG)
                    for tag, clr in [("ok", TAG_OK), ("err", TAG_ERR),
                                      ("warn", TAG_WARN), ("cmd", ACCENT)]:
                        widget.tag_configure(tag, foreground=clr)
            elif cls == "Listbox":
                widget.configure(bg=ENTRY_BG, fg=FG, selectbackground=ACCENT)
            elif cls == "Canvas":
                widget.configure(bg=BG)
            elif cls == "PanedWindow":
                widget.configure(bg=BORDER)
        except Exception:
            pass
        for child in widget.winfo_children():
            self._recolor_widgets(child)

    # ── Log ───────────────────────────────────────────────────────────────────

    def _make_log(self, parent) -> tk.Text:
        frame = tk.Frame(parent, bg=BORDER)
        frame.pack(fill="both", expand=True)
        sb = ttk.Scrollbar(frame)
        sb.pack(side="right", fill="y")
        log = tk.Text(frame, bg=LOG_BG, fg=LOG_FG, font=("Consolas", 9),
                      wrap="word", state="disabled", yscrollcommand=sb.set,
                      borderwidth=0, highlightthickness=0)
        sb.config(command=log.yview)
        log.pack(side="left", fill="both", expand=True)
        for tag, color in [("ok", TAG_OK), ("err", TAG_ERR),
                           ("warn", TAG_WARN), ("cmd", ACCENT)]:
            log.tag_configure(tag, foreground=color)
        return log

    def _log(self, widget: tk.Text, text: str, tag: str = ""):
        widget.configure(state="normal")
        widget.insert("end", text, tag)
        widget.see("end")
        widget.configure(state="disabled")

    def _log_clear(self, widget: tk.Text):
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.configure(state="disabled")

    # ── Podgląd EPUB ──────────────────────────────────────────────────────────

    def _preview_epub(self, path: str):
        if not path or not Path(path).is_file():
            messagebox.showwarning("Brak pliku", f"Plik nie istnieje:\n{path}")
            return
        viewer = self._viewer_path
        if not viewer:
            messagebox.showerror("Brak Calibre",
                "Nie znaleziono ebook-viewer.\nZainstaluj Calibre z calibre-ebook.com.")
            return
        subprocess.Popen([viewer, path], creationflags=CREATE_NO_WINDOW)

    def _preview_selected(self):
        path = self._conv_files.get_selected()
        if not path:
            messagebox.showinfo("Brak zaznaczenia", "Zaznacz plik na liście.")
            return
        self._preview_epub(path)

    def _preview_last(self):
        if not self._last_converted:
            messagebox.showinfo("Brak pliku", "Nie skonwertowano jeszcze żadnego pliku.")
            return
        self._preview_epub(self._last_converted)

    # ── Lista plików EPUB i edytory ───────────────────────────────────────────

    def _refresh_epub_list(self):
        """Skanuje katalog EPUB i aktualizuje listbox."""
        self._epub_lb.delete(0, "end")
        d = self._epub_dir.get()
        if not d or not Path(d).is_dir():
            self._epub_count_lbl.config(text="")
            return
        files = sorted(Path(d).glob("*.epub"), key=lambda p: p.name.lower())
        for f in files:
            # _moh.epub oznaczamy inaczej
            marker = "★ " if f.name.endswith("_moh.epub") else "  "
            self._epub_lb.insert("end", marker + f.name)
        count = len(files)
        moh = sum(1 for f in files if f.name.endswith("_moh.epub"))
        lbl = f"{count} plików EPUB"
        if moh:
            lbl += f"  (★ {moh} _moh.epub)"
        self._epub_count_lbl.config(text=lbl)

    def _selected_epub_path(self) -> Path | None:
        """Zwraca pełną ścieżkę zaznaczonego pliku z listboxa."""
        sel = self._epub_lb.curselection()
        if not sel:
            return None
        name = self._epub_lb.get(sel[0]).lstrip("★ ").strip()
        d = self._epub_dir.get()
        if not d:
            return None
        return Path(d) / name

    def _open_in_editor(self, editor_path: str, editor_name: str):
        path = self._selected_epub_path()
        if not path:
            messagebox.showinfo("Brak zaznaczenia", "Zaznacz plik EPUB na liście.")
            return
        if not editor_path:
            messagebox.showerror("Brak edytora",
                f"{editor_name} nie został znaleziony.\n"
                "Zainstaluj go i upewnij się, że jest dostępny w PATH.")
            return
        if not path.is_file():
            messagebox.showwarning("Brak pliku", f"Plik nie istnieje:\n{path}")
            return
        subprocess.Popen([editor_path, str(path)], creationflags=CREATE_NO_WINDOW)

    def _open_in_sigil(self):
        self._open_in_editor(self._sigil_path, "Sigil")

    def _open_in_calibre_editor(self):
        self._open_in_editor(self._ebook_editor_path, "Calibre e-book editor")

    def _open_in_default_editor(self):
        """Otwiera plik w pierwszym dostępnym edytorze (dwuklik)."""
        if self._sigil_path:
            self._open_in_sigil()
        elif self._ebook_editor_path:
            self._open_in_calibre_editor()
        else:
            messagebox.showinfo("Brak edytora",
                "Nie znaleziono Sigil ani Calibre e-book editor.")

    # ── Logika Kindle KFX ────────────────────────────────────────────────────

    def _run_kfx(self):
        engine = self._kfx_engine.get()
        if engine == "kp3":
            kp3 = self._kfx_kp3_entry.get()
            if not kp3 or not Path(kp3).is_file():
                messagebox.showerror("Brak silnika",
                    "Wskaż ścieżkę do Kindle Previewer 3 (KindlePreviewer.exe).\n"
                    "Pobierz ze strony Amazon: amazon.com/kindlepreview")
                return
        else:
            ec = self._kfx_calibre_entry.get()
            if not ec or not Path(ec).is_file():
                messagebox.showerror("Brak silnika",
                    "Wskaż ścieżkę do ebook-convert Calibre.")
                return

        files = self._kfx_files.get_all()
        if not files:
            messagebox.showwarning("Brak plików",
                "Dodaj przynajmniej jeden plik EPUB do listy.")
            return

        self._log_clear(self._kfx_log)
        threading.Thread(target=self._kfx_batch, daemon=True).start()

    def _kfx_batch(self):
        files = self._kfx_files.get_all()
        ok = err = 0
        for f in files:
            if self._kfx_convert_one(Path(f)):
                ok += 1
            else:
                err += 1
        tag = "ok" if err == 0 else "err"
        self.after(0, self._log, self._kfx_log,
                   f"\nGotowe: {ok} OK, {err} błędów\n", tag)

    def _kfx_convert_one(self, epub_path: Path) -> bool:
        tmp_dir: Path | None = None
        input_path = epub_path

        # --- Opcjonalna naprawa przez epubQTools -e ---
        if self._kfx_fix.get():
            eq = self._eq_entry.get() or (str(self._eq_path) if self._eq_path else "")
            python = self._py_entry.get()
            if not eq or not Path(eq).is_file() or not python or not Path(python).is_file():
                self.after(0, self._log, self._kfx_log,
                           "⚠ Brak epubQTools lub Python — pomijam naprawę\n", "warn")
            else:
                tmp_dir = Path(tempfile.mkdtemp(prefix="epubkfx_"))
                shutil.copy2(str(epub_path), str(tmp_dir / epub_path.name))
                cmd = [python, eq, "-e", str(tmp_dir)]
                self.after(0, self._log, self._kfx_log,
                           f"⚙ Naprawa: {epub_path.name} …\n")
                subprocess.run(cmd, capture_output=True, text=True,
                               creationflags=CREATE_NO_WINDOW)
                moh = tmp_dir / (epub_path.stem + "_moh.epub")
                if moh.is_file():
                    input_path = moh
                    self.after(0, self._log, self._kfx_log,
                               f"✓ Naprawiono → {moh.name}\n", "ok")
                else:
                    self.after(0, self._log, self._kfx_log,
                               "⚠ _moh.epub nie powstał — konwertuję oryginał\n", "warn")

        # --- Katalog wyjściowy ---
        out_dir_str = self._kfx_outdir.get()
        out_dir = Path(out_dir_str) if out_dir_str else epub_path.parent
        out_dir.mkdir(parents=True, exist_ok=True)

        # --- Konwersja ---
        engine = self._kfx_engine.get()
        success = False

        if engine == "kp3":
            # KP3 tworzy własną strukturę w katalogu wyjściowym — używamy osobnego temp
            kp3_tmp = Path(tempfile.mkdtemp(prefix="epubkfx_out_"))
            try:
                kp3 = self._kfx_kp3_entry.get()
                # .bat może startować KP3 asynchronicznie — subprocess.run skończy się
                # zanim KP3 zapisze plik; należy użyć bezpośrednio KindlePreviewer.exe
                if kp3.lower().endswith(".bat"):
                    self.after(0, self._log, self._kfx_log,
                               "⚠ Wykryto plik .BAT zamiast .exe — konwersja może nie działać.\n"
                               "  Wskaż bezpośrednio KindlePreviewer.exe w polu ścieżki.\n", "warn")
                # KP3 nie obsługuje znaków spoza ASCII w ścieżce — kopiujemy do temp jako input.epub
                kp3_in = kp3_tmp / "input.epub"
                shutil.copy2(str(input_path), str(kp3_in))
                # KP3 używa flagi -output (nie -output_dir)
                cmd = [kp3, str(kp3_in), "-convert", "-output", str(kp3_tmp)]
                self.after(0, self._log, self._kfx_log, " ".join(cmd) + "\n", "cmd")
                result = subprocess.run(cmd, capture_output=True,
                                        creationflags=CREATE_NO_WINDOW, timeout=300)
                if result.stdout:
                    self.after(0, self._log, self._kfx_log,
                               result.stdout.decode("utf-8", errors="replace"))
                if result.stderr:
                    self.after(0, self._log, self._kfx_log,
                               result.stderr.decode("utf-8", errors="replace"), "warn")
                # KP3 tworzy .kpf (nowsze wersje) lub .kfx (starsze) w podkatalogu
                out_file = None
                for pattern in ["*.kpf", "*.kfx"]:
                    found = list(kp3_tmp.rglob(pattern))
                    if found:
                        out_file = found[0]
                        break
                if out_file:
                    dest = out_dir / (epub_path.stem + out_file.suffix)
                    shutil.move(str(out_file), str(dest))
                    self.after(0, self._log, self._kfx_log, f"✓ {dest}\n", "ok")
                    success = True
                else:
                    self.after(0, self._log, self._kfx_log,
                               "✗ Nie znaleziono pliku .kpf/.kfx w katalogu wyjściowym\n", "err")
            except subprocess.TimeoutExpired:
                self.after(0, self._log, self._kfx_log,
                           "✗ Przekroczono czas oczekiwania (5 min)\n", "err")
            except Exception as ex:
                self.after(0, self._log, self._kfx_log, f"✗ {ex}\n", "err")
            finally:
                shutil.rmtree(str(kp3_tmp), ignore_errors=True)

        else:  # calibre
            ec = self._kfx_calibre_entry.get()
            dest = out_dir / (epub_path.stem + ".kfx")
            cmd = [ec, str(input_path), str(dest)]
            self.after(0, self._log, self._kfx_log, " ".join(cmd) + "\n", "cmd")
            try:
                result = subprocess.run(cmd, capture_output=True, text=True,
                                        creationflags=CREATE_NO_WINDOW, timeout=300)
                if result.stdout:
                    self.after(0, self._log, self._kfx_log, result.stdout)
                if result.stderr:
                    self.after(0, self._log, self._kfx_log, result.stderr, "warn")
                if result.returncode == 0 and dest.is_file():
                    self.after(0, self._log, self._kfx_log, f"✓ {dest}\n", "ok")
                    success = True
                else:
                    self.after(0, self._log, self._kfx_log,
                               f"✗ Błąd konwersji Calibre (kod {result.returncode})\n", "err")
            except subprocess.TimeoutExpired:
                self.after(0, self._log, self._kfx_log,
                           "✗ Przekroczono czas oczekiwania (5 min)\n", "err")
            except Exception as ex:
                self.after(0, self._log, self._kfx_log, f"✗ {ex}\n", "err")

        # --- Cleanup tymczasowego katalogu z naprawą ---
        if tmp_dir:
            shutil.rmtree(str(tmp_dir), ignore_errors=True)

        return success

    # ── Logika epubQTools ─────────────────────────────────────────────────────

    def _check_tools(self):
        path = self._tools_path.get()
        if not path or not Path(path).is_dir():
            self._kindlegen_lbl.config(text="kindlegen: —", fg=FG_DIM)
            self._epubcheck_lbl.config(text="epubcheck: —", fg=FG_DIM)
            return
        d = Path(path)
        kg_found = any((d / n).is_file() for n in ("kindlegen.exe", "kindlegen"))
        self._kindlegen_lbl.config(
            text="kindlegen: ✓" if kg_found else "kindlegen: ✗",
            fg=TAG_OK if kg_found else TAG_ERR,
        )
        ec_found = (
            any(d.glob("epubcheck-5.*.zip")) or   # epubcheck 5.x ZIP (wymagany przez epubQTools)
            any(d.glob("epubcheck-4.*.zip")) or   # epubcheck 4.x ZIP
            any(d.glob("epubcheck*.jar"))          # rozpakowany JAR (fallback)
        )
        self._epubcheck_lbl.config(
            text="epubcheck: ✓" if ec_found else "epubcheck: ✗",
            fg=TAG_OK if ec_found else TAG_ERR,
        )

    def _build_q_args(self) -> list[str]:
        args = []
        simple = ["-a", "-n", "-q", "--list-fonts", "-p", "-m", "-e",
                  "--skip-hyphenate", "--skip-hyphenate-headers",
                  "--skip-reset-css", "--skip-justify", "--left",
                  "--replace-font-files", "--myk-fix", "--remove-colors",
                  "--remove-fonts", "--fix-missing-container",
                  "-f", "-k", "-d", "-t", "-z"]
        for f in simple:
            if self._flags.get(f, tk.BooleanVar()).get():
                args.append(f)
        if self._flags.get("--book-margin", tk.BooleanVar()).get():
            args += ["--book-margin", self._book_margin.get()]
        if self._flags.get("--replace-font-family", tk.BooleanVar()).get():
            args += ["--replace-font-family", self._font_family.get()]
        if self._flags.get("-i", tk.BooleanVar()).get():
            args += ["-i", self._single_i.get()]
            if self._eq_author.get().strip():
                args += ["--author", self._eq_author.get().strip()]
            if self._eq_title.get().strip():
                args += ["--title", self._eq_title.get().strip()]
        if self._tools_path.get():
            args += ["--tools", self._tools_path.get()]
        if self._logs_path.get():
            args += ["-l", self._logs_path.get()]
        if self._font_dir.get():
            args += ["--font-dir", self._font_dir.get()]
        return args

    def _run_epubqtools(self):
        eq = self._eq_entry.get() or (str(self._eq_path) if self._eq_path else "")
        if not eq or not Path(eq).is_file():
            messagebox.showerror("Błąd",
                "Nie znaleziono __main__.py epubQTools.\n"
                "Wskaż plik ręcznie w polu 'Ścieżka epubQTools'.")
            return
        epub_dir = self._epub_dir.get()
        if not epub_dir or not Path(epub_dir).is_dir():
            messagebox.showwarning("Brak katalogu", "Wskaż katalog z plikami EPUB.")
            return
        args = self._build_q_args()
        if not any(f in args for f in {"-e", "-q", "-p", "-n", "-a", "-k", "-d", "-t", "-z"}):
            messagebox.showwarning("Brak akcji",
                "Zaznacz przynajmniej jedną akcję (np. -e, -q, -p, -n).")
            return
        python = self._py_entry.get()
        if not python or not Path(python).is_file():
            messagebox.showerror("Błąd",
                "Nie znaleziono interpretera Python.\n"
                "Wskaż python.exe ręcznie w polu 'Interpreter Python'.")
            return
        cmd = [python, eq] + args + [epub_dir]
        self._log_clear(self._eq_log)
        self._log(self._eq_log, " ".join(cmd) + "\n", "cmd")
        self._launch(cmd, self._eq_log)

    # ── Logika konwertera ─────────────────────────────────────────────────────

    def _run_converter(self):
        if not self._conv_engine:
            messagebox.showerror("Błąd",
                "Nie znaleziono pandoc ani calibre.\n"
                "Zainstaluj pandoc z pandoc.org lub Calibre.")
            return
        files = self._conv_files.get_all()
        if not files:
            messagebox.showwarning("Brak plików", "Dodaj przynajmniej jeden plik do konwersji.")
            return
        # PDF wymaga Calibre — sprawdź czy jest dostępne
        has_pdf = any(Path(f).suffix.lower() == ".pdf" for f in files)
        calibre_avail = self._conv_engine == "calibre" or bool(self._kfx_calibre_path)
        if has_pdf and not calibre_avail:
            messagebox.showerror("Brak Calibre",
                "Konwersja PDF → EPUB wymaga Calibre (ebook-convert).\n"
                "Pandoc nie obsługuje plików PDF.\n\n"
                "Zainstaluj Calibre z calibre-ebook.com.")
            return
        self._log_clear(self._conv_log)

        def _batch():
            ok = err = 0
            last = ""
            for f in files:
                cmd = self._build_conv_cmd(Path(f))
                self.after(0, self._log, self._conv_log, " ".join(cmd) + "\n", "cmd")
                try:
                    result = subprocess.run(cmd, capture_output=True, text=True,
                                            creationflags=CREATE_NO_WINDOW)
                    if result.stdout:
                        self.after(0, self._log, self._conv_log, result.stdout)
                    if result.stderr:
                        self.after(0, self._log, self._conv_log, result.stderr, "warn")
                    if result.returncode == 0:
                        out = str(self._conv_output_path(Path(f)))
                        self.after(0, self._log, self._conv_log, f"✓ {out}\n", "ok")
                        last = out
                        ok += 1
                    else:
                        self.after(0, self._log, self._conv_log,
                                   f"✗ Błąd (kod {result.returncode})\n", "err")
                        err += 1
                except Exception as ex:
                    self.after(0, self._log, self._conv_log, f"✗ {ex}\n", "err")
                    err += 1
            if last:
                self._last_converted = last
            tag = "ok" if err == 0 else "err"
            self.after(0, self._log, self._conv_log,
                       f"\nGotowe: {ok} OK, {err} błędów\n", tag)

        threading.Thread(target=_batch, daemon=True).start()

    def _build_conv_cmd(self, input_path: Path) -> list[str]:
        out = self._conv_output_path(input_path)
        title  = self._conv_title.get().strip()
        author = self._conv_author.get().strip()
        lang   = self._conv_lang.get().strip()

        # PDF nie jest obsługiwany przez Pandoc — wymuś Calibre
        force_calibre = input_path.suffix.lower() == ".pdf"

        if self._conv_engine == "pandoc" and not force_calibre:
            cmd = [self._conv_path, str(input_path), "-o", str(out)]
            if getattr(self, "_pandoc_standalone", None) and self._pandoc_standalone.get():
                cmd.append("--standalone")
            if getattr(self, "_pandoc_toc", None) and self._pandoc_toc.get():
                cmd.append("--toc")
            ch = getattr(self, "_pandoc_chapter", None)
            if ch and ch.get() != "1":
                cmd += ["--epub-chapter-level", ch.get()]
            if title:
                cmd += ["--metadata", f"title={title}"]
            if author:
                cmd += ["--metadata", f"author={author}"]
            if lang:
                cmd += ["--metadata", f"lang={lang}"]
        else:
            # Calibre: bezpośrednio lub jako fallback dla PDF przy silniku Pandoc
            calibre_path = (self._conv_path if self._conv_engine == "calibre"
                            else self._kfx_calibre_path)
            cmd = [calibre_path, str(input_path), str(out)]
            if title:
                cmd += ["--title", title]
            if author:
                cmd += ["--authors", author]
            if lang:
                cmd += ["--language", lang]
        return cmd

    def _conv_output_path(self, input_path: Path) -> Path:
        outdir = self._conv_outdir.get()
        base = Path(outdir) if outdir else input_path.parent
        return base / (input_path.stem + ".epub")

    # ── Uruchamianie procesów ─────────────────────────────────────────────────

    def _launch(self, cmd: list[str], log: tk.Text):
        def _run():
            try:
                proc = subprocess.Popen(
                    cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    text=True, bufsize=1, creationflags=CREATE_NO_WINDOW,
                )
                for line in proc.stdout:
                    self.after(0, self._log, log, line)
                proc.wait()
                color = "ok" if proc.returncode == 0 else "err"
                self.after(0, self._log, log,
                           f"\n▶ Zakończono (kod {proc.returncode})\n", color)
            except FileNotFoundError:
                self.after(0, self._log, log, f"✗ Nie znaleziono: {cmd[0]}\n", "err")
            except Exception as ex:
                self.after(0, self._log, log, f"✗ {ex}\n", "err")
        threading.Thread(target=_run, daemon=True).start()

    # ── Konfiguracja ──────────────────────────────────────────────────────────

    def _save_config(self):
        # Nie zapisuj ścieżki z tymczasowego katalogu _MEI — zmienia się przy każdym
        # starcie .exe, więc zapisana wartość byłaby nieaktualna przy następnym uruchomieniu.
        _eq_val = self._eq_entry.get()
        _mei = getattr(sys, "_MEIPASS", None)
        if _mei and _eq_val.startswith(str(Path(_mei))):
            _eq_val = ""
        config = {
            "eq_main":        _eq_val,
            "py_interpreter": self._py_entry.get(),
            "epub_dir":       self._epub_dir.get(),
            "tools_path":     self._tools_path.get(),
            "logs_path":      self._logs_path.get(),
            "font_dir":       self._font_dir.get(),
            "book_margin":    self._book_margin.get(),
            "font_family":    self._font_family.get(),
            "single_i":       self._single_i.get(),
            "eq_author":      self._eq_author.get(),
            "eq_title":       self._eq_title.get(),
            "flags":          {k: v.get() for k, v in self._flags.items()},
            "conv_outdir":    self._conv_outdir.get(),
            "meta_dir":       self._meta_dir.get(),
            "kfx_kp3":        self._kfx_kp3_entry.get(),
            "kfx_calibre":    self._kfx_calibre_entry.get(),
            "kfx_outdir":     self._kfx_outdir.get(),
            "kfx_engine":     self._kfx_engine.get(),
            "kfx_fix":        self._kfx_fix.get(),
            "kfx_cleanup":    self._kfx_cleanup.get(),
            "conv_title":     self._conv_title.get(),
            "conv_author":    self._conv_author.get(),
            "conv_lang":      self._conv_lang.get(),
            "pandoc_toc":        getattr(self, "_pandoc_toc",        tk.BooleanVar()).get(),
            "pandoc_standalone": getattr(self, "_pandoc_standalone",  tk.BooleanVar(value=True)).get(),
            "pandoc_chapter":    getattr(self, "_pandoc_chapter",     tk.StringVar(value="1")).get(),
            "dark_theme":     self._dark_theme,
            "geometry":       self.geometry(),
        }
        try:
            _config_path().write_text(
                json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8"
            )
        except Exception:
            pass

    def _load_config(self):
        try:
            p = _config_path()
            if not p.is_file():
                return
            config = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return

        if geom := config.get("geometry"):
            try:
                self.geometry(geom)
            except Exception:
                pass

        for key, attr in [
            ("eq_main",        "_eq_entry"),
            ("py_interpreter", "_py_entry"),
            ("epub_dir",       "_epub_dir"),
            ("tools_path",     "_tools_path"),
            ("logs_path",      "_logs_path"),
            ("font_dir",       "_font_dir"),
            ("conv_outdir",    "_conv_outdir"),
            ("meta_dir",       "_meta_dir"),
            ("kfx_kp3",        "_kfx_kp3_entry"),
            ("kfx_calibre",    "_kfx_calibre_entry"),
            ("kfx_outdir",     "_kfx_outdir"),
        ]:
            val = config.get(key, "")
            if val:
                getattr(self, attr).set(val)

        if "kfx_engine" in config:
            self._kfx_engine.set(config["kfx_engine"])
        if "kfx_fix" in config:
            self._kfx_fix.set(config["kfx_fix"])
        if "kfx_cleanup" in config:
            self._kfx_cleanup.set(config["kfx_cleanup"])

        # Ścieżka do __main__.py z configa może być nieaktualna — PyInstaller
        # tworzy nowy katalog _MEI przy każdym starcie .exe. Jeśli zapisana ścieżka
        # nie istnieje, przywróć auto-wykrytą.
        saved_eq = self._eq_entry.get()
        if (not saved_eq or not Path(saved_eq).is_file()) and self._eq_path:
            self._eq_entry.set(str(self._eq_path))

        # Jeśli w configu zapisano .bat zamiast .exe, zastąp auto-wykrytym .exe
        saved_kp3 = self._kfx_kp3_entry.get()
        if saved_kp3.lower().endswith(".bat") and self._kfx_kp3_path \
                and not self._kfx_kp3_path.lower().endswith(".bat"):
            self._kfx_kp3_entry.set(self._kfx_kp3_path)

        for key, attr in [
            ("book_margin", "_book_margin"),
            ("font_family", "_font_family"),
            ("single_i",    "_single_i"),
        ]:
            val = config.get(key)
            if val is not None:
                getattr(self, attr).set(val)

        for key, attr in [
            ("eq_author",  "_eq_author"),
            ("eq_title",   "_eq_title"),
            ("conv_title", "_conv_title"),
            ("conv_author","_conv_author"),
            ("conv_lang",  "_conv_lang"),
        ]:
            val = config.get(key, "")
            if val:
                e = getattr(self, attr)
                e.delete(0, "end")
                e.insert(0, val)

        for flag, saved in config.get("flags", {}).items():
            if flag in self._flags:
                self._flags[flag].set(saved)

        if hasattr(self, "_pandoc_toc") and "pandoc_toc" in config:
            self._pandoc_toc.set(config["pandoc_toc"])
        if hasattr(self, "_pandoc_standalone") and "pandoc_standalone" in config:
            self._pandoc_standalone.set(config["pandoc_standalone"])
        if hasattr(self, "_pandoc_chapter") and "pandoc_chapter" in config:
            self._pandoc_chapter.set(config["pandoc_chapter"])

        dark = config.get("dark_theme", True)
        if dark != self._dark_theme:
            self._dark_theme = dark
            self._apply_theme(dark)
        else:
            self._check_tools()
        self._refresh_epub_list()
        self._refresh_meta_list()

    def _on_close(self):
        self._save_config()
        self.destroy()


# ─── Punkt wejścia ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    try:
        app = App()
        app.mainloop()
    except Exception:
        err = traceback.format_exc()
        try:
            Path("error.txt").write_text(err, encoding="utf-8")
        except Exception:
            pass
        try:
            messagebox.showerror("Błąd krytyczny",
                "Aplikacja napotkała nieoczekiwany błąd.\n"
                "Szczegóły zapisano w error.txt.")
        except Exception:
            pass
        raise
