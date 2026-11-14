@echo off
rem Builds dist\RetroCompanion.exe (needs Python; run this file on Windows by double-clicking it).
python -m pip install pyinstaller || goto :eof
python -m PyInstaller --onefile --noconsole --name RetroCompanion run.py
echo.
echo Done. The program is dist\RetroCompanion.exe
pause
