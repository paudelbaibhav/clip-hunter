"""Clip Hunter - VOD mode: a stream that already ended -> its best moments as vertical clips.

    python vod.py <twitch VOD url or id>                    # top 8 moments of the whole VOD
    python vod.py <channel name>                            # the channel's latest ended stream
    python vod.py <vod> --list                              # only print the moments (fast, no video)
    python vod.py <vod> --top 5 --from 01:00:00 --to 03:00:00 --layout zoom

  1. TwitchDownloaderCLI downloads the chat replay (every message with its time in the stream) - fast, no video yet
  2. the same chat-spike scoring as live mode (10 s windows vs the stream's normal pace, hype words x1.6)
  3. picks the top N moments (at least 90 s apart)
  4. downloads ONLY those parts of the video (35 s before -> 8 s after) and runs clipmaker (layout, captions)
Clips land in runs/<channel>_vod_<id>/clips/ and on dashboard.html. Only clip streamers who allow it.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import statistics
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import clipmaker  # noqa: E402
import config  # noqa: E402
from hunt import HYPE  # noqa: E402


def latest_vod(channel: str) -> str:
    """Newest past broadcast of a Twitch channel (public VODs only)."""
    url = f"https://www.twitch.tv/{channel.strip('/').split('/')[-1]}/videos?filter=archives&sort=time"
    p = subprocess.run([*config.ytdlp(), "--flat-playlist", "--playlist-end", "1", "--print", "%(id)s", url],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    m = re.search(r"(\d{6,})", p.stdout)
    if not m:
        raise SystemExit(f"no public past broadcasts found for '{channel}' (check the name, or pass a VOD link)")
    return m.group(1)


def hms(s: float) -> str:
    s = max(int(s), 0)
    return f"{s // 3600:02d}:{s % 3600 // 60:02d}:{s % 60:02d}"


def secs(t: str | None) -> float | None:
    if not t:
        return None
    parts = [float(x) for x in t.split(":")]
    return sum(v * 60 ** i for i, v in enumerate(reversed(parts)))


def td(args: list[str], what: str):
    exe = config.twitchdownloader()
    if not exe:
        raise SystemExit("TwitchDownloaderCLI not found - put it in tools/ (see GUIDE.md) or set TWITCHDOWNLOADER")
    (config.RUNS / "_tmp").mkdir(parents=True, exist_ok=True)
    p = subprocess.run([exe, *args, "--collision", "Overwrite", "--temp-path", str(config.RUNS / "_tmp")],
                       stdin=subprocess.DEVNULL, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if p.returncode != 0:
        raise SystemExit(f"TwitchDownloader {what} failed:\n" + (p.stdout + p.stderr)[-600:])


def find_moments(comments: list[dict], a) -> list[dict]:
    if not comments:
        return []
    end = max(c["t"] for c in comments)
    start = min(c["t"] for c in comments)
    scores = []                                   # (t, score, lines) every 5 s, window 10 s
    i0 = 0
    t = start + 10
    cs = sorted(comments, key=lambda c: c["t"])
    while t <= end:
        while i0 < len(cs) and cs[i0]["t"] < t - 10:
            i0 += 1
        j = i0
        win = []
        while j < len(cs) and cs[j]["t"] < t:
            win.append(cs[j]["m"])
            j += 1
        scores.append((t, sum(1.6 if HYPE.search(m) else 1.0 for m in win), win))
        t += 5
    vals = [s for _, s, _ in scores]
    cands = []
    for k, (t, s, win) in enumerate(scores):
        lo, hi = max(0, k - 60), min(len(vals), k + 60)            # +-5 min around this point
        base = statistics.median(vals[lo:hi]) or 0.5
        if s >= max(a.min_msgs, base * a.ratio):
            cands.append({"t": t, "score": round(s, 1), "normal": round(base, 1), "lines": win})
    cands.sort(key=lambda c: c["score"] / max(c["normal"], 1), reverse=True)
    picked = []
    for c in cands:
        if all(abs(c["t"] - p["t"]) >= a.gap for p in picked):
            picked.append(c)
        if len(picked) >= a.top:
            break
    return sorted(picked, key=lambda c: c["t"])


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("vod", help="Twitch VOD link or id, or a channel name (= its latest ended stream)")
    ap.add_argument("--top", type=int, default=8)
    ap.add_argument("--from", dest="start", help="hh:mm:ss - only look from here")
    ap.add_argument("--to", dest="end", help="hh:mm:ss - only look up to here")
    ap.add_argument("--layout", choices=["blur", "zoom", "cam"], default="zoom")
    ap.add_argument("--cam", type=float, nargs=4, metavar=("X", "Y", "W", "H"))
    ap.add_argument("--ratio", type=float, default=2.5)
    ap.add_argument("--min-msgs", type=float, default=12)
    ap.add_argument("--gap", type=float, default=90, help="seconds between picked moments")
    ap.add_argument("--before", type=float, default=35)
    ap.add_argument("--after", type=float, default=8)
    ap.add_argument("--no-captions", action="store_true")
    ap.add_argument("--list", action="store_true", help="only print the moments, don't download video")
    a = ap.parse_args()
    if a.layout == "cam" and not a.cam:
        a.layout = "zoom"
    m = re.search(r"videos/(\d{6,})|^v?(\d{6,})$", a.vod.strip())
    vid = (m.group(1) or m.group(2)) if m else latest_vod(a.vod)
    if not m:
        print(f"VOD latest ended stream of {a.vod}: https://www.twitch.tv/videos/{vid}", flush=True)
    tmp = config.RUNS / f"_vod_{vid}"
    tmp.mkdir(parents=True, exist_ok=True)
    chat = tmp / "chat.json"
    rng = (["-b", a.start] if a.start else []) + (["-e", a.end] if a.end else [])
    print(f"CHAT downloading chat replay of VOD {vid} ...", flush=True)
    td(["chatdownload", "--id", vid, "-o", str(chat), *rng], "chat download")
    d = json.loads(chat.read_text(encoding="utf-8"))
    channel = (d.get("streamer") or {}).get("name") or "vod"
    comments = [{"t": float(c["content_offset_seconds"]), "m": (c.get("message") or {}).get("body", "")}
                for c in d.get("comments", [])]
    print(f"CHAT {len(comments)} messages from {channel}", flush=True)
    moments = find_moments(comments, a)
    run = config.RUNS / f"{channel.lower()}_vod_{vid}"
    clipdir = run / "clips"
    clipdir.mkdir(parents=True, exist_ok=True)
    shutil.move(str(chat), run / "chat.json") if not (run / "chat.json").exists() else None
    shutil.rmtree(tmp, ignore_errors=True)
    for n, m in enumerate(moments, 1):
        print(f"SPIKE {hms(m['t'])} chat {m['score']} vs normal {m['normal']} - "
              f"{', '.join(w for w, _ in clipmaker.chat_summary(m['lines'])[:5])}", flush=True)
    if a.list:
        return
    for n, m in enumerate(moments, 1):
        t0, t1 = m["t"] - a.before, m["t"] + a.after
        final = clipdir / f"clip_{n:02d}_{hms(m['t']).replace(':', '')}.mp4"
        work = clipdir / f"_work_{n:02d}"
        work.mkdir(parents=True, exist_ok=True)
        raw = work / "raw.mp4"
        td(["videodownload", "--id", vid, "-o", str(raw), "-b", hms(t0), "-e", hms(t1),
            "--ffmpeg-path", shutil.which("ffmpeg") or "ffmpeg"], f"video part {n}")
        info = clipmaker.make_vertical(raw, final, a.layout, a.cam, not a.no_captions, work)
        h, mnt, s = int(m["t"] // 3600), int(m["t"] % 3600 // 60), int(m["t"] % 60)
        clipmaker.write_meta(final, channel=channel, platform="twitch", mode="vod", layout=a.layout,
                             time=datetime.now().isoformat(timespec="seconds"), vod=vid, vod_time=hms(m["t"]),
                             duration=round(t1 - t0, 1), score=m["score"], normal=m["normal"], trigger="chat",
                             chat_top=clipmaker.chat_summary(m["lines"]), chat_lines=m["lines"][-25:],
                             source_url=f"https://www.twitch.tv/videos/{vid}?t={h}h{mnt}m{s}s", **info)
        shutil.rmtree(work, ignore_errors=True)
        print(f"CLIP {final}", flush=True)


if __name__ == "__main__":
    main()
