@echo off
pyinstaller --onefile --noconsole --name RippleReborn --icon logo.ico --add-data "logo.png;." --add-data "logo.ico;." --collect-all winrt.runtime --collect-all winrt.windows.media.ocr --collect-all winrt.windows.graphics.imaging --collect-all winrt.windows.storage.streams --collect-all winrt.windows.foundation --collect-all winrt.windows.globalization ripple_reborn.py
pause
