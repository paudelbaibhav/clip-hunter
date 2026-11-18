"""Where everything lives and how the external tools are found. Every other script imports this."""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):              # chat is full of emoji: never crash a console that can't show them
    try:
        _s.reconfigure(errors="replace")
    except (AttributeError, ValueError):
        pass

HOME = Path(__file__).resolve().parent          # the project folder
RUNS = HOME / "runs"                            # every hunt / VOD run: chat log, clips, metadata
TOOLS = HOME / "tools"                          # put TwitchDownloaderCLI here (see GUIDE.md)
FONTS = HOME / "fonts"                          # optional: .ttf/.otf files for the captions
CHANNELS = HOME / "channels.json"               # your streamer list (copy channels.example.json)

_LOCAL_FFMPEG = TOOLS / "ffmpeg" / "bin"         # install.py puts ffmpeg here when the system has none
if _LOCAL_FFMPEG.is_dir():
    os.environ["PATH"] = str(_LOCAL_FFMPEG) + os.pathsep + os.environ.get("PATH", "")


def ytdlp() -> list[str]:
    """yt-dlp is installed with pip (requirements.txt) and run as a module, so no PATH setup is needed."""
    return [sys.executable, "-m", "yt_dlp"]


def ffmpeg() -> str | None:
    return shutil.which("ffmpeg")


def twitchdownloader() -> str | None:
    """TwitchDownloaderCLI (only needed for VOD mode): $TWITCHDOWNLOADER, tools/, or PATH."""
    exe = "TwitchDownloaderCLI.exe" if os.name == "nt" else "TwitchDownloaderCLI"
    for c in (os.environ.get("TWITCHDOWNLOADER"), TOOLS / exe, TOOLS / "TwitchDownloaderCLI" / exe,
              shutil.which("TwitchDownloaderCLI")):
        if c and Path(c).is_file():
            return str(c)
    return None
