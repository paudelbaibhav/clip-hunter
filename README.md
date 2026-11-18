# Clip Hunter

**Finds the moments a stream goes crazy and cuts them into ready-to-post vertical clips, by itself.**
Free, runs on your own computer, no accounts, no API keys, no monthly fee.

- **Live:** it records the stream, reads the chat, and when chat explodes (or the streamer screams) it cuts the clip
  *while the stream is still live*. Your clip can be out before the stream is even over.
- **Ended streams (VODs):** it downloads only the chat replay, finds the top moments, and downloads only those
  seconds of video.
- **Every clip** comes out 1080×1920 with word-by-word captions and normal loudness, and goes onto one review page where
  you press **Approve / Reject / Posted**.

Tested on a real GTA 5 roleplay stream: 2 hours, 1,384 chat messages, 6 clips found and cut, 0 minutes watched.

## Install: nothing to type

**Easiest:** open Claude (or any AI) and paste this:

```text
Hi Claude! Please set up "Clip Hunter" on my computer. It's a free app that finds the craziest moments of Twitch streams and cuts them into clips.
Instructions: https://raw.githubusercontent.com/paudelbaibhav/clip-hunter/main/START.md
Do every step for me, use simple words, and ask me before installing anything.
If you can't run things on my computer, tell me exactly where to paste this one line:
Windows: irm https://raw.githubusercontent.com/paudelbaibhav/clip-hunter/main/install.ps1 | iex
Mac: curl -fsSL https://raw.githubusercontent.com/paudelbaibhav/clip-hunter/main/install.sh | bash
```

**With an AI:** give [START.md](START.md) to any AI that can run commands (Claude Code, Cursor, Codex, …). It installs
everything, cuts your first clips and opens the review page. You only answer "OK" and "which streamer?".
A chat-only AI (ChatGPT, Claude, Gemini in the browser) will hand you the one line below to paste.

**Or paste one line yourself:**

Windows (PowerShell):
```powershell
irm https://raw.githubusercontent.com/paudelbaibhav/clip-hunter/main/install.ps1 | iex
```
macOS / Linux (Terminal):
```bash
curl -fsSL https://raw.githubusercontent.com/paudelbaibhav/clip-hunter/main/install.sh | bash
```
It installs Python if needed, then the packages, ffmpeg, TwitchDownloaderCLI and the caption model, all inside
`~/clip-hunter`. Run it again any time to update; your clips and settings are kept.

## Quick start (if you know a terminal)

```bash
git clone https://github.com/paudelbaibhav/clip-hunter && cd clip-hunter
python install.py                                        # venv, packages, ffmpeg, TwitchDownloaderCLI, model, check
source .venv/bin/activate                                # Windows: .venv\Scripts\activate

python vod.py <channel or VOD link> --top 5              # best 5 moments of an ended stream
python hunt.py <channel> --minutes 30                    # hunt one live stream
# edit channels.json (your streamers), then:
python app.py --open                                     # hunt all of them at once + open the review page
```

Manual, step-by-step setup and troubleshooting: [GUIDE.md](GUIDE.md).

Clips land in `runs/<channel>_.../clips/` with a `.json` next to each one (chat at that moment, transcript, score),
and on `dashboard.html`.

## How it works

| step | what happens | file |
|---|---|---|
| record | yt-dlp finds the live stream; ffmpeg saves it in 6-second pieces (keeps the last 12 minutes) | `hunt.py` |
| chat | Twitch chat is read anonymously (no account, no token) | `hunt.py` |
| detect | messages per 10 s compared with *this* stream's normal pace (median of the last 5 min); hype words (LUL, KEKW, W, 💀, …) count 1.6×. A spike = 2.5× normal and at least 12 messages. Audio: 9 dB louder than normal. | `hunt.py`, `vod.py` |
| cut | 35 s before the spike (chat reacts late) to 8 s after | `hunt.py`, `vod.py` |
| make | vertical layout (`zoom`, `blur`, or `cam` = facecam on top), captions, -14 LUFS loudness | `clipmaker.py`, `captions.py` |
| review | one page with every clip, chat and transcript; Approve / Reject / Posted | `dashboard.py` |

Tune the detector with `--ratio`, `--min-msgs`, `--audio-db`, `--cooldown`, `--before`, `--after`. Run any script
with `--help`.

## Rules: read this before you post anything

- **Only clip streamers who allow it.** Most big streamers pay clippers through official clipping campaigns
  (for example Whop "Content Rewards"). Join the campaign first, follow its rules, and credit the streamer.
- Clipping someone without permission can get your videos claimed, taken down, or your account struck.
- This tool only finds and cuts moments. What you post, and where, is your responsibility.

## Requirements

Python 3.10+, ffmpeg, about 1 GB of disk for the caption model. VOD mode also needs
[TwitchDownloaderCLI](https://github.com/lay295/TwitchDownloader/releases) (free, MIT). Works on Windows, macOS and Linux.
Kick works for live hunting with audio spikes (Kick chat isn't read).

## License

MIT. Use it, change it, sell clips made with it. A star or a credit is appreciated.
