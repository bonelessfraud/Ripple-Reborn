Ripple Reborn v1.0
=================
1. Install Python 3.10+ (Windows has a built-in OCR; Tesseract is only a fallback)
2. pip install -r requirements.txt
3. Fortnite: Settings > Video > Window Mode = Windowed Fullscreen (1920x1080 or 1920x1200)
4. Press Start (or Ctrl+Alt+1); the bot window minimizes. Ctrl+Alt+2 stops it.
5. Make an exe: see GitHub build (.github) or double-click make_exe.bat (needs Python)

Hotkeys (Ctrl+Alt+): 1 start, 2 stop, P pause, K kill, 4 test OCR,
5 show zones, 6 test Discord, 7 screenshot, 8 debug folder, 9 test chat
Settings/log/debug live in %APPDATA%\RippleReborn

Automating Fortnite breaks Epic's rules and can get an account banned.

GET A READY-MADE .EXE (no installs): push this folder to a GitHub repo; the workflow in
.github/workflows/build.yml builds RippleReborn.exe and attaches it to a Release.
