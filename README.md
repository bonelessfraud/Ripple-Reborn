# Ripple Reborn (v1.2): AFK Fortnite bot for gizmos, treasure and pirate tokens

**Automating Fortnite breaks Epic's rules. Any account you run this on can be banned. Use an account you can afford to lose.**

**Download:** the ready-to-run `RippleReborn.exe` is on the [latest release](../../releases/latest). No Python and no installs needed: text reading uses the OCR built into Windows 10/11.

**Before you start:** set Fortnite to **Windowed Fullscreen** (Settings → Video → Window Mode) at **1920×1080** or **1920×1200**. Plain *Fullscreen* gives screen captures a black picture, and then the bot sees nothing.

## ⭐ What it does, in one line

Queues Battle Royale on its own, drops, plays like an idle human, claims your rewards, posts every **YOU FOUND** item to Discord, and leaves the match when the time, the players left or your team says so. Then it does it again.

| | |
| --- | --- |
| **Lobby** | finds the yellow **PLAY** button by its colour, sets **Squad** in the mode panel, never clicks Equip / Sprites / Treasure / Shop |
| **Rewards** | presses **CLAIM / CLAIM ALL** on *Treasure Found*, *Item Acquired* and *Pirate Shop Access* screens |
| **Surveys** | presses **SKIP** on *"We want to hear from you!"* |
| **Match** | waits on the bus, jumps, lands, sprints, hops, turns, glances, stops, swings: never stands still |
| **Leaving** | Esc → **≡** tab → **Return to lobby**, at your max match length, your players-left number, or when 2 teammates are out |
| **Discord** | only real finds (**YOU FOUND …**) and real rewards, with a screenshot, plus a summary when the bot stops |

## Quick start

1. Download `RippleReborn.exe` from the [latest release](../../releases/latest) and run it. If Windows says *"Windows protected your PC"*, click **More info → Run anyway** (the exe isn't code-signed).
2. Open Fortnite in **Windowed Fullscreen** and go to the lobby.
3. Optional: paste your Discord webhook in **Settings → Discord** and press **Test webhook**.
4. Press **Start** (or **Ctrl+Alt+1**). The bot window minimizes and the bot takes over.
5. **Ctrl+Alt+2** stops it, **Ctrl+Alt+P** pauses, **Ctrl+Alt+K** kills it.

Check you're on the newest build: the version shows under the title (**v1.2**) and in the first line of the session feed.

## The main window

| Part | What it shows / does |
| --- | --- |
| **Start / Stop** | starts the loop; closes Settings and minimizes the window so it never covers the game |
| **Settings** | the four tabs below |
| **Pause** | freezes the bot mid-match (keys are released first) |
| **Status** | what it's doing right now: *Waiting for lobby, Queueing, In bus, Dropping, In match (… leaving in 4m 12s), Leaving match* |
| **Time AFK** | how long it has been running, pauses not counted |
| **Players left** | read live from the counter next to the person icon, left of the minimap |
| **Gizmos** | gizmos found this session |
| **Matches · found · recoveries** | matches queued, items/rewards found, times it had to un-stick itself |
| **Toggles** | Movement, AFK messages, Reboot thanks, Play again, Leave if team is out |
| **Session feed** | every decision, in plain words, with a time stamp (also saved to `log.txt`) |

## Settings

Changes save the moment you make them, to `%APPDATA%\RippleReborn\settings.ini`.

### Match

| Setting | Default | What it does |
| --- | ---: | --- |
| Leave when players left are ≤ | 20 | leaves once the counter is at or under this (see *How it decides to leave*) |
| Max match length (minutes) | 9 | counted from when the match loads; checked in every phase, bus included |
| Wait before jumping (seconds) | 60 | time on the bus before it jumps |
| Landing wait (seconds) | 40 | glide time before it starts moving |
| Proceed anyway after (seconds) | 60 | jump even if the counter can't be read yet (0 = always wait for it) |
| AFK 2nd message after (seconds) | 40 | delay between the two chat messages, if AFK messages is on |
| Lobby settle wait (seconds) | 10 | pause after reaching the lobby before clicking anything |

### Options

| Setting | What it does |
| --- | --- |
| Detect the lobby with OCR | reads the lobby's top menu bar (PLAY, SHOP, LOCKER …) to know where it is |
| Set Quads every cycle | opens the mode panel and picks the 4th Team Size icon (Squad) if it isn't already |
| Keep bot window always on top | as it says |
| Save debug screenshots | saves every area it reads to the `debug` folder |
| Pickaxe key / Gun key | your slot keys for swings and shots (empty gun key = never shoots) |
| **Sprint key** | default `shift` (also `ctrl`, `alt`, `caps` or a letter); empty = walk only |
| Look up after landing | raises the camera after landing (pixels, 0 = off) |
| **Interface color** | 8 presets (Purple, Blue, Cyan, Green, Orange, Red, Pink, Gold) or any HEX code like `#ff8800`; recolours buttons, switches, checkboxes and tabs instantly |

### Discord

| Setting | What it does |
| --- | --- |
| Webhook URL | shows **● valid link** when it looks right; **Test webhook** sends a test message |
| Screenshot when an item is found | attaches a screenshot to every find / claim |
| Send a session summary when the bot stops | one message with time AFK, matches, gizmos, finds, recoveries and the items list |

### Tools

| Button | What it does |
| --- | --- |
| Test OCR | reports what the bot sees right now: lobby yes/no, where PLAY is, the players-left number, each teammate's state, and saves a screenshot |
| Show zones | draws the areas it reads over the game for 6 seconds |
| Test leave | runs the leave sequence once |
| Calibrate | point-and-capture any click spot or zone corner if your layout differs |

## Hotkeys (Ctrl+Alt + …)

| Key | Action | Key | Action |
| :---: | --- | :---: | --- |
| **1** | start | **5** | show zones |
| **2** | stop | **6** | test Discord |
| **P** | pause / resume | **7** | screenshot to the debug folder |
| **K** | kill (sends the summary first) | **8** | open the debug folder |
| **4** | test OCR | **9** | test chat |

## How a cycle works

1. **Lobby.** Waits for the menu bar, handles any pop-ups (rewards, surveys) up to 5 in a row, then waits the settle time.
2. **Mode.** With *Set Quads* on, clicks the *"Zero Build, Squad, Fill"* button, reads the Team Size row and clicks Squad if needed.
3. **Play.** Clicks the yellow **PLAY** (in the lobby or the mode panel) and checks it really started matchmaking; up to 3 tries. If it lands on another page (Treasure, Sprites …) it clicks the **PLAY tab** to go back instead of guessing.
4. **Bus.** Logs *"Will leave by HH:MM:SS"*, waits, jumps.
5. **Drop.** Glides for the landing wait, looks up, starts moving.
6. **Match.** Moves like a person, reads the counter, watches the squad list, posts finds, until one of the leave rules fires.
7. **Leave.** Esc → **≡** → **Return to lobby** (confirms if asked), then back to step 1. *Play again* (if on) requeues from the results screen instead.

## How it moves

- **Walks and sprints**: holds your sprint key about 80% of the time and now and then lets go to slow down, like a real player.
- **Hops** every 0.5–1.5 s while moving, so small rocks and ledges don't stop it.
- **Smooth camera turns** that speed up and slow down like a hand on a mouse, plus a slight aim drift while running.
- **Glances** left or right and back, **short stops** of 1–2 s where it looks around, the odd strafe, pickaxe swing or (if you set a gun key) shot.
- Every key is released when it stops, pauses or switches action: none get stuck down.

## How it decides to leave

| Rule | Details |
| --- | --- |
| **Max match length** | from the moment the match loads; the status line counts down |
| **Players left** | only trusted when the number behaves like the real counter: it showed 40+ earlier, never goes up, and two readings in a row agree at or under your setting |
| **Leave if team is out** | reads the squad list's colours (bottom left): **green bar** = alive, **red bar + red "+"** = knocked (doesn't count), **red name + cyan reboot card / power icon** = eliminated. A teammate who **leaves the match** counts as out too. It leaves when **2** teammates are out at the same time; a teammate who gets rebooted stops counting. Each change needs 3 matching readings, so a single misread can't trigger it. |

## Rewards, finds and surveys

- **YOU FOUND banner** (e.g. *YOU FOUND SPRITE GIZMO*): Gizmos +1 (if it's a gizmo), found +1, posted to Discord as *"You found Sprite Gizmo!"*. Nothing else in a match is posted: map names, *SPAWNED* banners, spectating screens are ignored.
- **Lobby rewards**: *Treasure Found*, *Item Acquired* and *Pirate Shop Access* get their **CLAIM / CLAIM ALL** pressed and posted as *"Claimed: …"*. Never on the Treasure tab or Sprites page, never on a button that says Equip.
- **Surveys**: *"We want to hear from you!"* gets **SKIP**, never Submit or a rating.
- **Discord blocked?** If Windows Firewall or an antivirus blocks the exe from the internet, it retries through Windows' own `curl.exe` and tells you in the feed if it still can't get through.

## Screens it supports

| Screen | Supported |
| --- | --- |
| 1920×1080 (16:9) | ✅ |
| 1920×1200 (16:10) | ✅ (HUD spots are mapped from the top, bottom or middle of the screen, like Fortnite does) |
| Windows display scaling (125%, 150% …) | ✅ the bot window scales with it |

## Files and folders

| Where | What |
| --- | --- |
| `%APPDATA%\RippleReborn\settings.ini` | your settings and calibrated spots |
| `%APPDATA%\RippleReborn\log.txt` | every session feed line |
| `%APPDATA%\RippleReborn\debug\` | screenshots: Test OCR, *stuck_…* (before a recovery), *noplay_…* (PLAY didn't start a game) |

## Building it yourself

Every push to this repo builds the exe on GitHub (Actions → *Build RippleReborn.exe*) and publishes it as the release named after the version in `ripple_reborn.py`. On your own PC: `make_exe.bat` (needs Python 3.10+), or `run.bat` to run the script directly.

## Troubleshooting

| Problem | Fix |
| --- | --- |
| Stuck on *Waiting for lobby* | Fortnite must be in **Windowed Fullscreen**; press **Ctrl+Alt+4** in the lobby and check the feed says *Lobby detected: True* |
| Doesn't find PLAY | open the main Play screen; Test OCR should say *Yellow PLAY button at …* |
| *Players left* stays `--` | Test OCR during a match prints what it reads; send that line |
| Leaves too early | the feed says why (*Team is out*, *players left*, *Max match length*); send those lines |
| Discord error *Permission denied* | allow RippleReborn in Windows Firewall / your antivirus |
| Old behaviour after updating | check the version under the title matches the latest release |

## Versions

| Version | What changed |
| --- | --- |
| **v1.2** | **Players left read from the real HUD counter** (the number next to the person icon, left of the minimap), at 1920×1080 and 1920×1200; old saved spots reset once. |
| **v1.1** | **Version numbering**: the app shows its version (title, Settings, feed) and every GitHub release is named after it (v1.1, v1.2 …). |
| **v1.0** | Everything before numbered releases (list below). |

<details>
<summary><b>Everything in v1.0</b></summary>

| Area | What it got |
| --- | --- |
| **App** | dark UI with rounded buttons, logo, dark title bars, Match / Options / Discord / Tools settings, hotkeys, session feed, auto-saved settings |
| **Screen** | fullscreen at 1920×1080 and 1920×1200, minimizes on Start, no window positioning needed |
| **Text reading** | Windows' built-in OCR (no install), Tesseract only as a fallback; ignores the bot's own windows |
| **Lobby** | yellow PLAY found by colour, mode panel + Squad icon, back to the PLAY tab from other pages, never clicks Equip / Sprite / Treasure / Shop buttons |
| **Pop-ups** | CLAIM on Treasure Found / Item Acquired / Pirate Shop Access, SKIP on feedback surveys |
| **Leaving** | Esc → ≡ → Return to lobby; max match length from load; trusted players-left counter |
| **Team** | squad-list colours: knocked vs eliminated, teammates who leave count, leave at 2 out |
| **Discord** | YOU FOUND finds only, real rewards only, screenshots, curl.exe fallback, session summary |
| **Movement** | sprint key, hops while moving, smooth turns, glances, short stops, strafes, swings |
| **Look** | interface colour: 8 presets or any HEX code |

</details>
