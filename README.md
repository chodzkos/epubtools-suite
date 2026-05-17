# epubTools Suite

Desktopowa aplikacja Windows do pracy z plikami EPUB: walidacja, naprawa, konwersja, edycja metadanych i eksport do Kindle KFX — wszystko w jednym oknie GUI.

[![Build](https://github.com/chodzkos/epubtools-suite/actions/workflows/build.yml/badge.svg)](https://github.com/chodzkos/epubtools-suite/actions/workflows/build.yml)
[![Release](https://img.shields.io/github/v/release/chodzkos/epubtools-suite)](https://github.com/chodzkos/epubtools-suite/releases/latest)

---

## Pobieranie

Gotowy plik `.exe` (bez instalacji Pythona) — sekcja [Releases](https://github.com/chodzkos/epubtools-suite/releases/latest).

---

## Funkcje

### Zakładka epubQTools
- Walidacja plików EPUB narzędziem wewnętrznym (`-q`) i EpubCheck 5.x (`-p`)
- Naprawa i dzielenie wyrazów → `_moh.epub` (`-e`)
- Zmiana nazw plików na schemat `autor - tytuł.epub` (`-n`)
- Konwersja do `.mobi` przez kindlegen (`-k`) z opcjonalną kompresją huffdic (`-d`)
- Pełna obsługa wszystkich flag CLI epubQTools
- Automatyczna detekcja kindlegen i epubcheck ZIP w katalogu narzędzi
- Automatyczne wykrywanie interpretera Python
- Panel plików EPUB: lista z odświeżaniem, otwieranie w Sigil / Calibre e-book editor

### Zakładka Konwerter EPUB
- Konwersja TXT / DOCX / HTML / MD / ODT / RTF / MOBI / FB2 / LaTeX → EPUB
- Silnik: **Pandoc** (główny) lub **Calibre** ebook-convert (zapasowy) — wykrywany automatycznie
- Ustawianie metadanych: tytuł, autor, język
- Podgląd skonwertowanego pliku w Calibre viewer jednym kliknięciem
- Drag & drop plików na listę (wymaga `tkinterdnd2`)

### Zakładka Kindle KFX
- Konwersja EPUB → `.kfx` (format Kindle na nowszych czytnikach)
- Silnik: **Kindle Previewer 3** (zalecany, oficjalny konwerter Amazon) lub **Calibre** z wtyczką KFX Output
- Auto-detekcja obu silników i wtyczki KFX w katalogu Calibre
- Opcjonalna naprawa EPUB przez epubQTools `-e` przed konwersją (domyślnie włączona)
- Wybór katalogu wyjściowego dla plików `.kfx`
- Drag & drop plików EPUB na listę

### Zakładka Metadane
- Podgląd i edycja metadanych Dublin Core: tytuł, autor, język, wydawca, data, identyfikator (ISBN/UUID), temat, opis
- Wiele autorów / tematów — rozdzielane średnikami
- Skanowanie katalogu i wyświetlanie listy plików `.epub` (z odświeżaniem)
- Drag & drop plików `.epub` na listę
- Zapis bezpośrednio do pliku EPUB z automatyczną kopią zapasową (`.epub.bak`)
- Odczyt i zapis bez zewnętrznych narzędzi (stdlib Python: `zipfile` + `xml.etree`)

### Ogólne
- Motyw **jasny / ciemny** — przełącznik w górnym pasku
- Dymki pomocy (tooltips) na wszystkich kontrolkach — wystarczy najechać kursorem
- Ikonka programu widoczna w Eksploratorze Windows i na pasku zadań
- Zapamiętywanie wszystkich ustawień, ścieżek i zaznaczonych opcji (`config.json`)
- Streaming wyjścia procesów do okna logu w czasie rzeczywistym
- Zapis błędów do `error.txt` przy nieoczekiwanym zamknięciu

---

## Wymagania

### Do uruchomienia skompilowanego `.exe`
| Narzędzie | Rola | Instalacja |
|---|---|---|
| **Python 3.7+** | uruchamia epubQTools | [python.org](https://python.org) |
| **Pandoc** | konwersja → EPUB | [pandoc.org](https://pandoc.org/installing.html) |
| **Calibre** | konwersja zapasowa + podgląd EPUB | [calibre-ebook.com](https://calibre-ebook.com) |
| **Java** | wymagana przez EpubCheck | [adoptium.net](https://adoptium.net) |
| **epubcheck-5.x.zip** | walidacja EpubCheck | [GitHub Releases](https://github.com/w3c/epubcheck/releases) |
| **kindlegen** | konwersja → .mobi | archiwum Amazon |
| **Kindle Previewer 3** | konwersja → .kfx | [amazon.com/kindlepreview](https://www.amazon.com/gp/feature.html?ie=UTF8&docId=1000765261) |

Zakładka Metadane nie wymaga żadnych zewnętrznych narzędzi.
Zakładka Kindle KFX wymaga Kindle Previewer 3 **lub** Calibre z wtyczką KFX Output.

### Do uruchomienia ze źródeł (dodatkowo)
```
pip install lxml css-parser
pip install tkinterdnd2   # opcjonalne — drag & drop
```

---

## Szybki start (ze źródeł)

```bash
git clone https://github.com/chodzkos/epubtools-suite
cd epubtools-suite
pip install lxml css-parser
python gui_main.py
```

---

## Konfiguracja katalogu narzędzi (`--tools`)

W wybranym katalogu umieść:
```
tools/
├── kindlegen.exe            ← binarny plik kindlegen (bez instalacji)
├── epubcheck-5.3.0.zip      ← ZIP pobrany z github.com/w3c/epubcheck/releases
└── (opcjonalnie .jar itp.)
```

> **Ważne:** epubQTools wymaga pliku ZIP epubcheck — nie wypakowuj go.

---

## Build — skompilowany `.exe`

```bash
pip install pyinstaller tkinterdnd2 Pillow
python create_icon.py        # generuje icon.ico
python -m PyInstaller epubtools_suite.spec --clean
# → dist/epubTools_Suite.exe
```

Lub uruchom `build.bat` na Windows.

### GitHub Actions (automatyczny build)

- **Push do `master`** → buduje `.exe` jako artefakt (dostępny 30 dni w zakładce Actions)
- **Nowy Release** → `.exe` dołączany do Release jako plik do pobrania

Tworzenie nowego release:
```bash
git tag v0.9.0
git push origin v0.9.0
gh release create v0.9.0 --repo chodzkos/epubtools-suite --title "epubTools Suite v0.9.0" --generate-notes
```

---

## Pierwsze uruchomienie — Windows SmartScreen

Po pobraniu `.exe` Windows może wyświetlić ostrzeżenie:
**„System Windows ochronił ten komputer"** (SmartScreen).

Dzieje się tak, ponieważ plik `.exe` nie jest podpisany certyfikatem kodu (code-signing certificate). Plik jest bezpieczny — możesz zweryfikować źródło w zakładce [Actions](https://github.com/chodzkos/epubtools-suite/actions) na GitHub.

**Jak uruchomić mimo ostrzeżenia:**
1. Kliknij **„Więcej informacji"** w oknie SmartScreen.
2. Kliknij przycisk **„Uruchom mimo to"**.

Ostrzeżenie pojawi się tylko przy pierwszym uruchomieniu danego pliku.

> **Alternatywnie:** kliknij plik prawym przyciskiem myszy → **Właściwości** → zaznacz **„Odblokuj"** → OK.

---

## Struktura projektu

```
epubtools-suite/
├── gui_main.py               ← aplikacja GUI (Python 3.7+, tkinter)
├── __main__.py               ← epubQTools (fork quiris11/epubQTools)
├── lib/                      ← biblioteki epubQTools
├── create_icon.py            ← generator icon.ico (stdlib + Pillow)
├── icon.ico                  ← ikonka programu
├── epubtools_suite.spec      ← konfiguracja PyInstaller
├── build.bat                 ← lokalny skrypt budowania (Windows)
├── requirements.txt          ← zależności Python (build)
├── NOTICE                    ← informacje o licencjach
└── .github/workflows/
    └── build.yml             ← GitHub Actions CI/CD
```

---

## Oparty na

- [quiris11/epubQTools](https://github.com/quiris11/epubQTools) — narzędzie do przetwarzania EPUB (fork, gałąź master)
- [Pandoc](https://pandoc.org) — konwersja dokumentów
- [Calibre](https://calibre-ebook.com) — konwersja i podgląd EPUB
- [EpubCheck](https://github.com/w3c/epubcheck) — walidacja EPUB
- [KFX Output](https://www.mobileread.com/forums/showthread.php?t=272407) (wtyczka Calibre, jhowell) — konwersja do KFX przez Calibre
