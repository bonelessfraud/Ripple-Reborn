@echo off
REM Builds a single RippleReborn.exe (run once: pip install -r requirements.txt)
pyinstaller --onefile --noconsole --name RippleReborn --icon logo.ico --add-data "logo.png;." --add-data "logo.ico;." ripple_reborn.py
echo Done. The exe is in the dist folder.
pause
