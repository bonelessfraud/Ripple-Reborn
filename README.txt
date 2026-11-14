Ripple Reborn v1.0
=================
1. Install Python 3.10+ and Tesseract OCR (https://github.com/UB-Mannheim/tesseract/wiki)
2. pip install -r requirements.txt
3. Put Fortnite in WINDOWED mode, then double-click run.bat
4. Settings > Tools > Position window, then Show zones / Calibrate if clicks are off
5. Make an exe: double-click make_exe.bat (needs Python installed) -> dist\RippleReborn.exe

Hotkeys (Ctrl+Alt+): 1 start, 2 stop, P pause, K kill, 3 position, 4 test OCR,
5 show zones, 6 test Discord, 7 screenshot, 8 debug folder, 9 test chat
Settings/log/debug live in %APPDATA%\RippleReborn

Automating Fortnite breaks Epic's rules and can get an account banned.

GET A READY-MADE .EXE WITHOUT INSTALLING ANYTHING (Tesseract is bundled in):
1. Make a free GitHub account, create a new repository, upload everything in this folder
   (including the hidden .github folder).
2. Open the Actions tab -> "Build RippleReborn.exe" -> Run workflow.
3. When it finishes (~3 min) open the run and download the RippleReborn artifact.
   Unzip it: RippleReborn.exe is a single file you just double-click.
