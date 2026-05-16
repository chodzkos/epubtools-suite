@echo off
echo === epubTools Suite - lokalny build ===
python -m pip install -r requirements.txt
python -m PyInstaller epubtools_suite.spec --clean
echo.
echo Gotowe: dist\epubTools_Suite.exe
pause
