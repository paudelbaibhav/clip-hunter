# START.md: give this file to your AI. It does everything.

**You:** copy this whole file into any AI that can run commands on your computer (Claude Code, Cursor, Codex,
Windsurf, Gemini CLI, …) and send it. That's it. You won't type commands. The AI asks you two short questions:
"OK to install?" and "which streamer?".

Using a chat-only AI (ChatGPT / Claude / Gemini in the browser)? Send it anyway. It will give you **one line** to
paste, and that line does everything.

---

## Instructions for the AI

You are installing **Clip Hunter** (https://github.com/paudelbaibhav/clip-hunter, MIT license) for this person. It
finds the moments a Twitch/Kick stream goes crazy and cuts them into captioned vertical clips, free and locally. The
person may never have used a terminal. **Do every step yourself; never ask them to type a command.** Talk in short,
simple sentences.

### 0. Ask once
Say: *"I'll install Clip Hunter in a folder called clip-hunter in your home folder. It downloads about 1 GB (Python
packages, ffmpeg, a caption model) and takes 5–10 minutes. OK?"* Wait for yes.

### 1. Run the installer (one command)
Detect the operating system, then run exactly one of these:

- **Windows** (PowerShell):
  ```powershell
  powershell -NoProfile -ExecutionPolicy Bypass -Command "irm https://raw.githubusercontent.com/paudelbaibhav/clip-hunter/main/install.ps1 | iex"
  ```
- **macOS / Linux**:
  ```bash
  curl -fsSL https://raw.githubusercontent.com/paudelbaibhav/clip-hunter/main/install.sh | bash
  ```

It installs Python if missing, downloads the project to `~/clip-hunter` (Windows: `%USERPROFILE%\clip-hunter`), creates
`.venv`, installs packages, gets ffmpeg and TwitchDownloaderCLI, downloads the caption model and runs a check. Give it
time and don't interrupt it. While it runs, tell the person what's happening in one line per step.

**Success** = the output ends with `Clip Hunter is ready` and the check shows only `OK` / `NOTE` lines.
**If it fails:** read the last lines of the error, fix the cause (see the table in `GUIDE.md` in the project folder),
and run the same command again. It's safe to re-run, because finished steps are skipped. Typical fixes:
- macOS without Homebrew: install Homebrew from https://brew.sh (its official one-line install), then re-run.
- Windows says Python isn't visible yet: open a new PowerShell and re-run.
- Linux asks for a password: that's `sudo` installing Python; the person types their computer password once.

### 2. First clips (proof it works)
Ask: *"Which Twitch streamer should I test it on? Best is one whose clipping campaign you joined."* If they don't
know, suggest any big streamer **for a private test only**.

Run inside the project folder with the project's Python:
- Windows: `.venv\Scripts\python vod.py <channel> --top 3`
- macOS/Linux: `.venv/bin/python vod.py <channel> --top 3`

It takes that channel's latest ended stream, finds the 3 biggest chat explosions and cuts them (a few minutes). If it
says "no spikes", run it again with `--ratio 2 --min-msgs 8`. If the channel has no public past broadcasts, ask for
another streamer.

Then open `dashboard.html` from the project folder in the default browser for them (Windows: `start dashboard.html`,
macOS: `open dashboard.html`, Linux: `xdg-open dashboard.html`).

### 3. Show them how to use it (say this, short)
- **Live:** "Tell me a streamer who's live and I'll start hunting": run `python hunt.py <channel>` with the project's
  Python. Clips appear on the review page about a minute after each big moment. Ctrl+C stops it.
- **Many streamers:** offer to edit `channels.json` for them. Ask for the streamer names, set `"enabled": true`,
  `"platform": "twitch"` or `"kick"`, then run `python app.py --open`.
- **Ended streams:** `python vod.py <channel>` any time.
- **Review page:** Approve / Reject / Posted, and ⬇ to download.

### 4. Tell them the rule (important)
"Only post clips of streamers who allow it: join their clipping campaign (for example Whop Content Rewards), follow its
rules and credit the streamer. Clipping without permission can get videos taken down or your account struck."

### Rules for you (the AI)
- Only download from the two URLs above (they fetch the project from GitHub). The installer itself only downloads
  from python.org/winget/Homebrew/apt, PyPI, the official TwitchDownloader GitHub releases, and the BtbN FFmpeg GitHub
  builds.
- Don't post anything anywhere, and don't log in to any account for them.
- Don't change the detection code unless they ask. Details for changes are in `GUIDE.md` and `README.md`.
