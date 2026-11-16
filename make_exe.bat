@echo off
where python >nul 2>nul || (echo Python is not installed. Get it from python.org, tick "Add python.exe to PATH", then run this again. & pause & exit /b 1)
python -m pip install --upgrade pip
python -m pip install -r requirements.txt || (echo pip install failed & pause & exit /b 1)
python -m PyInstaller --onefile --noconsole --name RippleReborn --icon logo.ico --add-data "logo.png;." --add-data "logo.ico;." --collect-all winrt.runtime --collect-all winrt.windows.media.ocr --collect-all winrt.windows.graphics.imaging --collect-all winrt.windows.storage.streams --collect-all winrt.windows.foundation --collect-all winrt.windows.globalization ripple_reborn.py || (echo build failed & pause & exit /b 1)
echo Done: dist\RippleReborn.exe
explorer dist
pause
