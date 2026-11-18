# GUIDE.md — set up Clip Hunter with any AI

**For the person:** give this whole file to your AI and say *"Follow GUIDE.md and set this up for me step by step.
Ask me before installing anything."* You don't need to know code.

**For the AI:** you are helping someone who may never have used a terminal. Follow the steps in order. Before each
step, say in one or two simple sentences what you are about to do and why. Ask before installing anything. After
each step, check that it worked (each step has a check). If a check fails, use the "If it fails" notes and fix it
before moving on. Don't change the detection code unless the person asks.

**Fastest path:** use [START.md](START.md) instead. It runs one installer (`install.ps1` / `install.sh` →
`install.py`) that does steps 1–5 below by itself. This guide is the manual, step-by-step version and the place to
look when something fails.

---

## What we are building

A program on the person's own computer that:
1. watches a Twitch or Kick stream (live) or a Twitch VOD (an ended stream),
2. notices when chat explodes or the streamer screams,
3. cuts that moment into a vertical clip with captions, ready for TikTok / Shorts / Reels,
4. shows every clip on one review page.

Everything is free and local. No accounts, no API keys.

---

## Step 1: Python 3.10 or newer

Check: `python --version` (on macOS/Linux maybe `python3 --version`).

If it's missing or older than 3.10:
- Windows: `winget install Python.Python.3.12` (or python.org; tick "Add Python to PATH").
- macOS: `brew install python@3.12`
- Linux: `sudo apt install python3 python3-venv python3-pip`

Open a **new** terminal afterwards and check again.

## Step 2: ffmpeg

Check: `ffmpeg -version` prints a version.

If missing:
- Windows: `winget install Gyan.FFmpeg`, then open a new terminal.
- macOS: `brew install ffmpeg`
- Linux: `sudo apt install ffmpeg`

## Step 3: the project and its Python packages

In the project folder (the one with this file):

```
python -m venv .venv
```
Activate it:
- Windows (PowerShell): `.venv\Scripts\Activate.ps1`. If scripts are blocked, run
  `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once and try again.
- Windows (cmd): `.venv\Scripts\activate.bat`
- macOS/Linux: `source .venv/bin/activate`

Then:
```
pip install -r requirements.txt
```
Check: `python -c "import yt_dlp, numpy, faster_whisper; print('ok')"` prints `ok`.

From now on, always activate `.venv` first in every new terminal.

## Step 4: TwitchDownloaderCLI (for ended streams / VODs)

1. Open https://github.com/lay295/TwitchDownloader/releases and pick the newest release.
2. Download the **CLI** zip for the system: `TwitchDownloaderCLI-…-Windows-x64.zip`, `…-MacOS-x64` / `…-MacOSArm64`
   (Apple Silicon), or `…-Linux-x64`.
3. Unzip it and put the program (`TwitchDownloaderCLI.exe` on Windows, `TwitchDownloaderCLI` elsewhere) into the
   `tools/` folder of this project (create the folder).
4. macOS/Linux only: `chmod +x tools/TwitchDownloaderCLI`. On macOS, if it's blocked, allow it once in
   System Settings → Privacy & Security.

## Step 5: check everything

```
python doctor.py --warm
```
Every line should say `OK`. `--warm` downloads the caption model once (about 500 MB), so the first clip is fast.
Fix any `MISS` line with the hint it prints.

## Step 6: first test on an ended stream (no waiting for a live stream)

Ask the person for a Twitch VOD link (a past broadcast: `https://www.twitch.tv/videos/<numbers>`), ideally from a
streamer whose clipping campaign they joined. To keep the first test short, look at one hour only:

```
python vod.py <VOD link> --from 01:00:00 --to 02:00:00 --list
```
This only downloads chat and prints lines like `SPIKE 01:26:21 chat 50.2 vs normal 3.0 — lol, kekw, …`.
If it prints no spikes, the hour was quiet: try another hour, or add `--ratio 2 --min-msgs 8`.

Then cut the top 3:
```
python vod.py <VOD link> --from 01:00:00 --to 02:00:00 --top 3
```
Check: it prints `CLIP …/runs/<channel>_vod_<id>/clips/clip_01_….mp4` lines, and `dashboard.html` exists. Open
`dashboard.html` in a browser: the clips are there with chat and transcript.

## Step 7: hunt a live stream

Pick a channel that is live right now:
```
python hunt.py <channel> --minutes 15
```
It prints `HUNT`, `REC` (recording), `CHAT` (reading chat). After about a minute it is armed, then every spike
prints `SPIKE` and, about a minute later, `CLIP`. If the channel is offline it prints `WAIT` and checks every minute.
Ctrl+C stops it (clips in progress still finish).

## Step 8: many streamers at once

```
cp channels.example.json channels.json        # Windows: copy channels.example.json channels.json
```
Edit `channels.json`: put real channel names, set `"enabled": true` for the ones to hunt, `"platform"` to
`twitch` or `kick`. Then:
```
python app.py --open
```
It runs one hunter per streamer and opens the review page, which refreshes itself every 20 seconds.

## Step 9 (optional): facecam layout

For streamers with a facecam, `--layout cam` puts the face on top and the gameplay below. It needs the facecam box as
fractions of the video frame: `--cam X Y W H` (for example bottom-left `0.0 0.62 0.27 0.38`). To find it, take one
frame (`ffmpeg -ss 30 -i <clip or raw video> -frames:v 1 frame.jpg`), look where the face is, and estimate the box.
Put it in `channels.json` as `"layout": "cam", "cam": [x, y, w, h]`.

---

## Using the clips

1. On the review page: watch, press **Approve** or **Reject**, download with ⬇.
2. Post only clips of streamers who allow clipping (their clipping campaign), follow the campaign's rules, and
   credit the streamer.
3. Mark **Posted** so you don't post twice.

## If it fails

| problem | fix |
|---|---|
| `ffmpeg` not found after installing | open a new terminal; on Windows sign out/in if needed |
| `WAIT … is not live` but the stream is live | `pip install -U yt-dlp` (sites change often), then try again |
| VOD: `TwitchDownloaderCLI not found` | the program must be directly in `tools/` (not in a subfolder of the zip) |
| VOD download fails on a subscriber-only VOD | use a public VOD |
| no spikes | quieter stream: `--ratio 2 --min-msgs 8`; very busy stream: `--ratio 3 --min-msgs 25` |
| too many clips | raise `--ratio` / `--min-msgs`, or `--cooldown 90` |
| clip has no captions | `python doctor.py`: ffmpeg needs the `subtitles` filter (full build) |
| captions slow | the first clip loads the model; later clips are quicker. `captions.py --model base` is faster |
| face is cut off | use `--layout blur` or set up `cam` (step 9) |

## Changing it (for the AI, when asked)

- Detection: `hunt.py` (`chat_detector`, `audio_detector`, `HYPE` words) and `vod.py` (`find_moments`).
- Look of the clip: `clipmaker.py` (`layout_filter`), captions style: `captions.py` (`write_ass`).
- Review page: `dashboard.py`.
- Paths and tools: `config.py`.
Keep it free and local; test with `vod.py --list` on a known VOD before and after a change.
