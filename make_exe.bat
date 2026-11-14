@echo off
REM One-click: installs the packages and builds dist\RippleReborn.exe
where python >nul 2>nul || (echo Python is not installed. Get it from python.org, tick "Add python.exe to PATH", then run this again. & pause & exit /b 1)
python -m pip install --upgrade pip
python -m pip install -r requirements.txt || (echo pip install failed & pause & exit /b 1)
python -m PyInstaller --onefile --noconsole --name RippleReborn --icon logo.ico --add-data "logo.png;." --add-data "logo.ico;." ripple_reborn.py || (echo build failed & pause & exit /b 1)
echo.
echo Done: dist\RippleReborn.exe
echo (Tesseract OCR must still be installed: github.com/UB-Mannheim/tesseract/wiki)
explorer dist
pause
