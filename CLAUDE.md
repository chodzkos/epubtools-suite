# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Projekt

epubTools Suite — desktopowa aplikacja Windows (tkinter GUI skompilowana przez PyInstaller do jednego `.exe`). Repo: github.com/chodzkos/epubtools-suite. Branch główny: `master`.

Cały kod GUI to jeden plik: `gui_main.py`. Plik `__main__.py` + katalog `lib/` to fork epubQTools (quiris11) — uruchamiany jako subprocess przez systemowego Pythona, **nie** przez Python wbudowany w `.exe`.

## Zasady

- Conventional commits (`feat:`, `fix:`, `chore:` itp.)
- Komentarze w kodzie **po polsku**
- **Zawsze pytaj przed pushowaniem na GitHub**

## Budowanie `.exe`

```bash
# Lokalnie (Windows):
pip install pyinstaller tkinterdnd2 Pillow
python create_icon.py          # generuje icon.ico
python -m PyInstaller epubtools_suite.spec --clean
# → dist/epubTools_Suite.exe

# Lub:
build.bat
```

GitHub Actions buduje automatycznie przy push do `master` (artefakt 30 dni) i przy nowym Release (`.exe` dołączany do Release).

Tworzenie release:
```bash
git tag v0.X.Y
git push origin v0.X.Y
gh release create v0.X.Y --repo chodzkos/epubtools-suite --title "epubTools Suite v0.X.Y" --generate-notes
```

## Architektura `gui_main.py`

Klasa `App(tk.Tk)` z czterema zakładkami (`ttk.Notebook`):

| Zakładka | Metody budujące | Co robi |
|---|---|---|
| epubQTools | `_build_tab_eq()` | Uruchamia epubQTools jako subprocess z wybranymi flagami |
| Konwerter EPUB | `_build_tab_conv()` | Pandoc (główny) lub Calibre ebook-convert (fallback + PDF) |
| Kindle KFX | `_build_tab_kfx()` | Kindle Previewer 3 CLI lub Calibre + wtyczka KFX Output |
| Metadane | `_build_tab_meta()` | Odczyt/zapis Dublin Core bez zewnętrznych narzędzi (zipfile + xml.etree) |

**Auto-detekcja narzędzi** przy starcie — funkcje na poziomie modułu: `_find_epubqtools_main()`, `_find_python()`, `_find_converter()`, `_find_viewer()`, `_find_kindle_previewer()`, `_find_calibre_ebook_convert()`, `_calibre_has_kfx()`.

**Konfiguracja** zapisywana do `config.json` w katalogu obok exe/skryptu (`_save_config()` / `_load_config()`). Ważne: ścieżki z `sys._MEIPASS` **nie mogą być zapisywane** — każde uruchomienie exe tworzy nowy katalog tymczasowy `_MEI*`.

**Motywy** jasny/ciemny: słowniki `DARK`/`LIGHT` z globalnymi zmiennymi kolorów. Przełącznik w górnym pasku wywołuje `_apply_theme()` rekurencyjnie na wszystkich widgetach.

**Wyjście procesów** streamowane do `tk.Text` (pola logu) przez wątek w `_stream_to_log()`.

**Drag & drop** — opcjonalny, wymaga `tkinterdnd2`. Gdy niedostępny (`HAS_DND = False`), klasa `FileList` działa bez D&D.

## Ważne pułapki techniczne

**DLL conflict** (`python311.dll` vs Python użytkownika): PyInstaller pakuje `.pyd` do katalogu `_MEIPASS`. Subprocess uruchomiony z `sys.path[0]` wskazującym na ten katalog pobierze niekompatybilne `.pyd`. Rozwiązanie w `epubtools_suite.spec`: `__main__.py` i `lib/` trafiają do podkatalogu `epubqtools/` — z dala od `.pyd`.

**PDF → EPUB**: Pandoc nie obsługuje PDF. Przy PDF automatycznie używany jest `ebook-convert` z Calibre (przez `_kfx_calibre_path`).

**KFX przez KP3**: Kindle Previewer 3 tworzy własny podkatalog wyjściowy — trzeba `rglob("*.kfx")` po konwersji i przenieść plik do docelowego katalogu.
