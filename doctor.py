"""Checks that everything Clip Hunter needs is installed, and says how to fix what is missing.

    python doctor.py            # check
    python doctor.py --warm     # also download the caption model now (~500 MB, once) so the first clip is fast
"""
from __future__ import annotations

import argparse
import importlib.util
import subprocess
import sys

import config

ok_all = True


def line(ok: bool, what: str, fix: str = "", required: bool = True):
    global ok_all
    if required:
        ok_all &= ok
    tag = "OK  " if ok else ("MISS" if required else "NOTE")
    print(f"{tag} {what}" + ("" if ok else f"\n     -> {fix}"))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--warm", action="store_true")
    a = ap.parse_args()
    line(sys.version_info >= (3, 10), f"Python {sys.version.split()[0]} (3.10 or newer)", "install Python 3.10+ from python.org")
    ff = config.ffmpeg()
    line(bool(ff), f"ffmpeg {ff or ''}", "install ffmpeg and make sure `ffmpeg -version` works in a new terminal "
                                          "(Windows: winget install Gyan.FFmpeg · macOS: brew install ffmpeg · Linux: apt install ffmpeg)")
    for mod, pkg in (("yt_dlp", "yt-dlp"), ("numpy", "numpy"), ("faster_whisper", "faster-whisper")):
        line(importlib.util.find_spec(mod) is not None, f"python package {pkg}", "pip install -r requirements.txt")
    td = config.twitchdownloader()
    line(bool(td), f"TwitchDownloaderCLI {td or ''} (only for vod.py)",
         "download TwitchDownloaderCLI for your system from https://github.com/lay295/TwitchDownloader/releases "
         "and put the executable in the tools/ folder")
    line(config.CHANNELS.exists(), "channels.json (only for app.py, step 8)", "copy channels.example.json to channels.json and edit it",
         required=False)
    if ff:
        r = subprocess.run(["ffmpeg", "-hide_banner", "-filters"], capture_output=True, text=True)
        line("subtitles" in r.stdout, "ffmpeg can burn captions (subtitles filter / libass)",
             "use a full ffmpeg build (the Windows/macOS packages above include it)")
    if a.warm and importlib.util.find_spec("faster_whisper"):
        print("downloading the caption model (once) ...", flush=True)
        import captions
        captions._model("small")
        print("OK   caption model ready")
    print("\nAll good - try:  python vod.py <twitch VOD link> --top 3" if ok_all else "\nFix the MISS lines above, then run this again.")
    sys.exit(0 if ok_all else 1)


if __name__ == "__main__":
    main()
