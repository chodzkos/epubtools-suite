"""epubTools Suite — GUI łączące epubQTools i konwerter EPUB."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import threading
import traceback
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

# ─── Kolory ──────────────────────────────────────────────────────────────────

BG        = "#1e1e1e"
BG2       = "#252526"
BG3       = "#2d2d30"
FG        = "#cccccc"
FG_DIM    = "#858585"
ACCENT    = "#0e639c"
ACCENT_HV = "#1177bb"
ENTRY_BG  = "#3c3c3c"
BORDER    = "#3f3f3f"
BTN_BG    = "#0e639c"
BTN_FG    = "#ffffff"
LOG_BG    = "#1e1e1e"
LOG_FG    = "#d4d4d4"
TAG_OK    = "#4ec9b0"
TAG_ERR   = "#f44747"
TAG_WARN  = "#dcdcaa"

CREATE_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0

# ─── Wykrywanie narzędzi ──────────────────────────────────────────────────────

def _find_epubqtools_main() -> Path | None:
    here = Path(sys.executable if getattr(sys, "frozen", False) else __file__).parent

    candidates = [
        here / "__main__.py",                   # fork – pliki w tym samym katalogu
        here / "epubQTools" / "__main__.py",     # podfolder
    ]

    if getattr(sys, "_MEIPASS", None):
        mei = Path(sys._MEIPASS)
        candidates += [mei / "__main__.py", mei / "epubQTools" / "__main__.py"]

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
        return sys.executable  # uruchomiono bezpośrednio przez python.exe

    # W bundlu PyInstaller sys.executable wskazuje na .exe GUI, nie na python.exe
    for name in ("python", "python3"):
        found = shutil.which(name)
        if found:
            return found

    # Typowe lokalizacje na Windows
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


def _config_path() -> Path:
    """Zwraca ścieżkę do config.json obok exe/skryptu (lub w home jako fallback)."""
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

    def __init__(self, parent, mode="dir", label="", filetypes=None, **kw):
        super().__init__(parent, bg=BG, **kw)
        self._mode = mode
        self._filetypes = filetypes or [("Wszystkie pliki", "*.*")]

        if label:
            tk.Label(self, text=label, bg=BG, fg=FG,
                     font=("Segoe UI", 9)).pack(side="left", padx=(0, 4))

        self.var = tk.StringVar()
        self._entry = ttk.Entry(self, textvariable=self.var)
        self._entry.pack(side="left", fill="x", expand=True, padx=(0, 4))
        ttk.Button(self, text="…", width=3, command=self._browse).pack(side="left")

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
    """Lista plików z paskiem narzędzi (dodaj, usuń, wyczyść, góra/dół)."""

    def __init__(self, parent, filetypes=None, **kw):
        super().__init__(parent, bg=BG, **kw)
        self._filetypes = filetypes or [("Wszystkie pliki", "*.*")]

        bar = tk.Frame(self, bg=BG2)
        bar.pack(fill="x")
        for text, cmd in [("+ Dodaj", self._add), ("✕ Usuń", self._remove),
                          ("Wyczyść", self._clear)]:
            ttk.Button(bar, text=text, command=cmd).pack(side="left", padx=2, pady=2)
        ttk.Button(bar, text="↑", width=2, command=self._up).pack(side="left", padx=2, pady=2)
        ttk.Button(bar, text="↓", width=2, command=self._down).pack(side="left", padx=2, pady=2)

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


# ─── Główna aplikacja ─────────────────────────────────────────────────────────

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("epubTools Suite")
        self.geometry("960x700")
        self.minsize(720, 500)
        self.configure(bg=BG)

        _setup_style(self)

        self._eq_path = _find_epubqtools_main()
        self._conv_engine, self._conv_path = _find_converter()

        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=8, pady=8)

        self._tab_eq   = ttk.Frame(nb)
        self._tab_conv = ttk.Frame(nb)
        nb.add(self._tab_eq,   text="  epubQTools  ")
        nb.add(self._tab_conv, text="  Konwerter EPUB  ")

        self._build_tab_epubqtools()
        self._build_tab_converter()
        self._load_config()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

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

        def _on_inner_resize(e):
            canvas.configure(scrollregion=canvas.bbox("all"))

        def _on_canvas_resize(e):
            canvas.itemconfig(win_id, width=e.width)

        left.bind("<Configure>", _on_inner_resize)
        canvas.bind("<Configure>", _on_canvas_resize)
        canvas.bind_all("<MouseWheel>",
                        lambda e: canvas.yview_scroll(-1 * (e.delta // 120), "units"))

        self._flags: dict[str, tk.BooleanVar] = {}

        # Ścieżka epubQTools
        eq_sec = Section(left, "Ścieżka epubQTools (__main__.py)")
        eq_sec.pack(fill="x", padx=6, pady=4)

        self._eq_entry = PathEntry(eq_sec, mode="file",
                                   filetypes=[("Python", "__main__.py"),
                                              ("Wszystkie", "*.*")])
        self._eq_entry.pack(fill="x")
        if self._eq_path:
            self._eq_entry.set(str(self._eq_path))

        txt = f"✓ Wykryto: {self._eq_path}" if self._eq_path else "✗ Nie znaleziono — wskaż ręcznie"
        clr = TAG_OK if self._eq_path else TAG_ERR
        tk.Label(eq_sec, text=txt, bg=BG, fg=clr, font=("Segoe UI", 8)).pack(anchor="w", pady=(2, 0))

        # Interpreter Python
        py_sec = Section(left, "Interpreter Python (python.exe)")
        py_sec.pack(fill="x", padx=6, pady=4)

        py_detected = _find_python()
        self._py_entry = PathEntry(py_sec, mode="file",
                                   filetypes=[("Python", "*.exe"), ("Wszystkie", "*.*")])
        self._py_entry.pack(fill="x")
        if py_detected:
            self._py_entry.set(py_detected)

        py_txt = f"✓ Wykryto: {py_detected}" if py_detected else "✗ Nie znaleziono — wskaż python.exe ręcznie"
        py_clr = TAG_OK if py_detected else TAG_ERR
        tk.Label(py_sec, text=py_txt, bg=BG, fg=py_clr,
                 font=("Segoe UI", 8)).pack(anchor="w", pady=(2, 0))

        # Katalog z plikami EPUB
        dir_sec = Section(left, "Katalog z plikami EPUB (wymagany)")
        dir_sec.pack(fill="x", padx=6, pady=4)

        self._epub_dir = PathEntry(dir_sec, mode="dir")
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

        # --book-margin
        bm_row = tk.Frame(misc_sec, bg=BG)
        bm_row.pack(fill="x", pady=2)
        self._flags["--book-margin"] = tk.BooleanVar()
        ttk.Checkbutton(bm_row, variable=self._flags["--book-margin"],
                        text="--book-margin").pack(side="left")
        self._book_margin = tk.StringVar(value="10")
        ttk.Spinbox(bm_row, from_=0, to=999, width=5,
                    textvariable=self._book_margin).pack(side="left", padx=4)
        tk.Label(bm_row, text="px", bg=BG, fg=FG_DIM).pack(side="left")

        # --replace-font-family
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

        # --tools z detekcją kindlegen i epubcheck
        tk.Label(paths_sec, text="--tools (kindlegen, epubcheck):", bg=BG, fg=FG,
                 font=("Segoe UI", 9)).pack(anchor="w")
        self._tools_path = PathEntry(paths_sec, mode="dir")
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

        for label, attr in [
            ("-l  katalog logów:", "_logs_path"),
            ("--font-dir:", "_font_dir"),
        ]:
            tk.Label(paths_sec, text=label, bg=BG, fg=FG,
                     font=("Segoe UI", 9)).pack(anchor="w")
            pe = PathEntry(paths_sec, mode="dir")
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

        # ── Prawa: log ────────────────────────────────────────────────────────
        right = tk.Frame(paned, bg=BG)
        paned.add(right, minsize=300)

        ttk.Button(right, text="▶  Uruchom epubQTools", style="Accent.TButton",
                   command=self._run_epubqtools).pack(fill="x", padx=6, pady=(6, 4))

        log_sec = Section(right, "Log")
        log_sec.pack(fill="both", expand=True, padx=6, pady=(0, 6))
        self._eq_log = self._make_log(log_sec)

    def _add_check(self, parent, flag: str, desc: str):
        self._flags[flag] = tk.BooleanVar()
        ttk.Checkbutton(parent, variable=self._flags[flag],
                        text=f"{flag}   {desc}").pack(anchor="w", pady=1)

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

        if self._conv_engine:
            eng_text = f"✓ {self._conv_engine}\n{self._conv_path}"
            eng_color = TAG_OK
        else:
            eng_text = "✗ Nie znaleziono pandoc ani calibre\nZainstaluj pandoc z pandoc.org"
            eng_color = TAG_ERR
        tk.Label(eng_sec, text=eng_text, bg=BG, fg=eng_color,
                 font=("Segoe UI", 8), justify="left").pack(anchor="w")

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
        self._conv_outdir = PathEntry(out_sec, mode="dir")
        self._conv_outdir.pack(fill="x", pady=(0, 2))
        tk.Label(out_sec, text="(puste = obok pliku wejściowego)",
                 bg=BG, fg=FG_DIM, font=("Segoe UI", 8)).pack(anchor="w")

        # Opcje pandoc
        if self._conv_engine == "pandoc":
            po_sec = Section(left, "Opcje pandoc")
            po_sec.pack(fill="x", padx=6, pady=4)

            self._pandoc_toc = tk.BooleanVar()
            ttk.Checkbutton(po_sec, variable=self._pandoc_toc,
                            text="--toc   Spis treści").pack(anchor="w")

            self._pandoc_standalone = tk.BooleanVar(value=True)
            ttk.Checkbutton(po_sec, variable=self._pandoc_standalone,
                            text="--standalone").pack(anchor="w")

            tk.Label(po_sec, text="--epub-chapter-level:", bg=BG, fg=FG,
                     font=("Segoe UI", 9)).pack(anchor="w", pady=(4, 0))
            self._pandoc_chapter = tk.StringVar(value="1")
            ttk.Spinbox(po_sec, from_=1, to=6, width=4,
                        textvariable=self._pandoc_chapter).pack(anchor="w", pady=2)

        # ── Prawa: pliki + log ────────────────────────────────────────────────
        right = tk.Frame(paned, bg=BG)
        paned.add(right, minsize=320)

        files_sec = Section(right, "Pliki do konwersji")
        files_sec.pack(fill="both", expand=True, padx=6, pady=(4, 2))

        conv_types = [
            ("Obsługiwane formaty",
             "*.txt *.md *.markdown *.docx *.html *.htm *.odt *.rtf *.rst *.org *.epub *.fb2 *.tex"),
            ("Wszystkie pliki", "*.*"),
        ]
        self._conv_files = FileList(files_sec, filetypes=conv_types)
        self._conv_files.pack(fill="both", expand=True)

        ttk.Button(right, text="▶  Konwertuj do EPUB", style="Accent.TButton",
                   command=self._run_converter).pack(fill="x", padx=6, pady=4)

        log_sec = Section(right, "Log")
        log_sec.pack(fill="both", expand=True, padx=6, pady=(0, 6))
        self._conv_log = self._make_log(log_sec)

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

    # ── Logika epubQTools ─────────────────────────────────────────────────────

    def _check_tools(self):
        """Sprawdza obecność kindlegen i epubcheck w katalogu --tools."""
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

        ec_found = (d / "epubcheck.jar").is_file()
        if not ec_found:
            ec_found = any(d.glob("**/epubcheck*.jar"))
        self._epubcheck_lbl.config(
            text="epubcheck: ✓" if ec_found else "epubcheck: ✗",
            fg=TAG_OK if ec_found else TAG_ERR,
        )

    def _save_config(self):
        """Zapisuje wszystkie ustawienia GUI do config.json."""
        config = {
            # epubQTools — ścieżki
            "eq_main":        self._eq_entry.get(),
            "py_interpreter": self._py_entry.get(),
            "epub_dir":       self._epub_dir.get(),
            "tools_path":     self._tools_path.get(),
            "logs_path":      self._logs_path.get(),
            "font_dir":       self._font_dir.get(),
            # epubQTools — wartości
            "book_margin":    self._book_margin.get(),
            "font_family":    self._font_family.get(),
            "single_i":       self._single_i.get(),
            "eq_author":      self._eq_author.get(),
            "eq_title":       self._eq_title.get(),
            # epubQTools — checkboxy
            "flags": {k: v.get() for k, v in self._flags.items()},
            # Konwerter
            "conv_outdir":  self._conv_outdir.get(),
            "conv_title":   self._conv_title.get(),
            "conv_author":  self._conv_author.get(),
            "conv_lang":    self._conv_lang.get(),
            # Pandoc (opcjonalne — tylko gdy wykryto)
            "pandoc_toc":        getattr(self, "_pandoc_toc",        tk.BooleanVar()).get(),
            "pandoc_standalone": getattr(self, "_pandoc_standalone",  tk.BooleanVar(value=True)).get(),
            "pandoc_chapter":    getattr(self, "_pandoc_chapter",     tk.StringVar(value="1")).get(),
            # Okno
            "geometry": self.geometry(),
        }
        try:
            _config_path().write_text(
                json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8"
            )
        except Exception:
            pass

    def _load_config(self):
        """Wczytuje ustawienia z config.json po zbudowaniu wszystkich widgetów."""
        try:
            p = _config_path()
            if not p.is_file():
                return
            config = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return

        # Geometria okna
        if geom := config.get("geometry"):
            try:
                self.geometry(geom)
            except Exception:
                pass

        # Ścieżki (PathEntry)
        for key, attr in [
            ("eq_main",        "_eq_entry"),
            ("py_interpreter", "_py_entry"),
            ("epub_dir",       "_epub_dir"),
            ("tools_path",     "_tools_path"),
            ("logs_path",      "_logs_path"),
            ("font_dir",       "_font_dir"),
            ("conv_outdir",    "_conv_outdir"),
        ]:
            val = config.get(key, "")
            if val:
                getattr(self, attr).set(val)

        # StringVar
        for key, attr in [
            ("book_margin", "_book_margin"),
            ("font_family", "_font_family"),
            ("single_i",    "_single_i"),
        ]:
            val = config.get(key)
            if val is not None:
                getattr(self, attr).set(val)

        # Entry (tekst)
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

        # Checkboxy (flagi epubQTools)
        for flag, saved in config.get("flags", {}).items():
            if flag in self._flags:
                self._flags[flag].set(saved)

        # Pandoc
        if hasattr(self, "_pandoc_toc") and "pandoc_toc" in config:
            self._pandoc_toc.set(config["pandoc_toc"])
        if hasattr(self, "_pandoc_standalone") and "pandoc_standalone" in config:
            self._pandoc_standalone.set(config["pandoc_standalone"])
        if hasattr(self, "_pandoc_chapter") and "pandoc_chapter" in config:
            self._pandoc_chapter.set(config["pandoc_chapter"])

        # Odśwież detekcję narzędzi po wczytaniu ścieżki
        self._check_tools()

    def _on_close(self):
        self._save_config()
        self.destroy()

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
            author = self._eq_author.get().strip()
            title  = self._eq_title.get().strip()
            if author:
                args += ["--author", author]
            if title:
                args += ["--title", title]

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
            messagebox.showwarning("Brak katalogu",
                "Wskaż katalog z plikami EPUB.")
            return

        args = self._build_q_args()
        action_flags = {"-e", "-q", "-p", "-n", "-a", "-k", "-d", "-t", "-z"}
        if not any(f in args for f in action_flags):
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
            messagebox.showwarning("Brak plików",
                "Dodaj przynajmniej jeden plik do konwersji.")
            return

        self._log_clear(self._conv_log)

        def _batch():
            ok = err = 0
            for f in files:
                cmd = self._build_conv_cmd(Path(f))
                self.after(0, self._log, self._conv_log,
                           " ".join(cmd) + "\n", "cmd")
                try:
                    result = subprocess.run(
                        cmd, capture_output=True, text=True,
                        creationflags=CREATE_NO_WINDOW,
                    )
                    if result.stdout:
                        self.after(0, self._log, self._conv_log, result.stdout)
                    if result.stderr:
                        self.after(0, self._log, self._conv_log, result.stderr, "warn")
                    if result.returncode == 0:
                        out = self._conv_output_path(Path(f))
                        self.after(0, self._log, self._conv_log,
                                   f"✓ {out}\n", "ok")
                        ok += 1
                    else:
                        self.after(0, self._log, self._conv_log,
                                   f"✗ Błąd (kod {result.returncode})\n", "err")
                        err += 1
                except Exception as ex:
                    self.after(0, self._log, self._conv_log, f"✗ {ex}\n", "err")
                    err += 1
            tag = "ok" if err == 0 else "err"
            self.after(0, self._log, self._conv_log,
                       f"\nGotowe: {ok} OK, {err} błędów\n", tag)

        threading.Thread(target=_batch, daemon=True).start()

    def _build_conv_cmd(self, input_path: Path) -> list[str]:
        out = self._conv_output_path(input_path)
        title  = self._conv_title.get().strip()
        author = self._conv_author.get().strip()
        lang   = self._conv_lang.get().strip()

        if self._conv_engine == "pandoc":
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
            cmd = [self._conv_path, str(input_path), str(out)]
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
                self.after(0, self._log, log,
                           f"✗ Nie znaleziono: {cmd[0]}\n", "err")
            except Exception as ex:
                self.after(0, self._log, log, f"✗ {ex}\n", "err")

        threading.Thread(target=_run, daemon=True).start()


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
