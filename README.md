# epubTools Suite

Desktopowa aplikacja Windows łącząca **epubQTools** i **konwerter EPUB** w jednym oknie GUI.

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
- Zmiana nazw plików na schemat `autor - tytuł.epub` (`-n`) - poprawność zmiany zależy od metadanych zawartych w konwertowanym pliku .epub
- Konwersja do `.mobi` przez kindlegen (`-k`) z opcjonalną kompresją huffdic (`-d`)
- Pełna obsługa wszystkich flag CLI epubQTools
- Automatyczna detekcja kindlegen i epubcheck ZIP w katalogu narzędzi
- Automatyczne wykrywanie interpretera Python

### Zakładka Konwerter EPUB
- Konwersja TXT / DOCX / HTML / MD / ODT / RTF / MOBI / FB2 / LaTeX → EPUB
- Silnik: **Pandoc** (główny) lub **Calibre** ebook-convert (zapasowy) — wykrywany automatycznie
- Ustawianie metadanych: tytuł, autor, język
- Podgląd skonwertowanego pliku w Calibre viewer jednym kliknięciem
- Drag & drop plików na listę (wymaga `tkinterdnd2`)

### Ogólne
- Motyw **jasny / ciemny** — przełącznik w górnym pasku
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
pip install pyinstaller tkinterdnd2
python -m PyInstaller epubtools_suite.spec --clean
# → dist/epubTools_Suite.exe
```

Lub uruchom `build.bat` na Windows.

### GitHub Actions (automatyczny build)

- **Push do `master`** → buduje `.exe` jako artefakt (dostępny 30 dni w zakładce Actions)
- **Nowy Release** → `.exe` dołączany do Release jako plik do pobrania

Tworzenie nowego release:
```bash
git tag v1.0.0
git push origin v1.0.0
gh release create v1.0.0 --repo chodzkos/epubtools-suite --title "epubTools Suite v1.0.0" --generate-notes
```

---

## Struktura projektu

```
epubtools-suite/
├── gui_main.py               ← aplikacja GUI (Python 3.7+, tkinter)
├── __main__.py               ← epubQTools (fork quiris11/epubQTools)
├── lib/                      ← biblioteki epubQTools
├── epubtools_suite.spec      ← konfiguracja PyInstaller
├── build.bat                 ← lokalny skrypt budowania (Windows)
├── requirements.txt          ← zależności Python
└── .github/workflows/
    └── build.yml             ← GitHub Actions CI/CD
```

---

## Oparty na

- [quiris11/epubQTools](https://github.com/quiris11/epubQTools) — narzędzie do przetwarzania EPUB (fork, gałąź master)
- [Pandoc](https://pandoc.org) — konwersja dokumentów
- [Calibre](https://calibre-ebook.com) — konwersja i podgląd EPUB
- [EpubCheck](https://github.com/w3c/epubcheck) — walidacja EPUB
