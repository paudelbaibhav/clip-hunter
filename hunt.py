"""Clip Hunter - watch ONE live stream, find the moments chat (and the audio) explode, cut ready-to-post vertical clips
while the stream is still live. For several streamers at once use app.py.

    python hunt.py <channel>                               # Twitch, until Ctrl+C
    python hunt.py <channel> --platform kick                # Kick (audio spikes only, see README)
    python hunt.py <channel> --minutes 30 --layout zoom --ratio 2.5 --min-msgs 12
    python hunt.py <channel> --layout cam --cam 0.0 0.65 0.25 0.35   # facecam box x y w h (fractions)
    python hunt.py <channel> --no-cut                       # dry run: only log spikes

  record  yt-dlp finds the live HLS stream; ffmpeg saves 6 s chunks named by wall-clock time (buffer 12 min)
  chat    Twitch chat read anonymously (IRC justinfan login: no account, no token) -> chat.jsonl
  audio   loudness of every finished chunk, 1 s steps, vs the stream's own normal -> screams / explosions
  detect  chat: messages per 10 s vs normal (median of last 5 min), hype words x1.6; audio: +dB over normal.
          one shared cooldown, so one moment = one clip; "both" when chat and audio agree
  cut     35 s before the spike (chat reacts late) to 8 s after -> clipmaker.py (layout, captions, -14 LUFS)
          -> runs/<channel>_<time>/clips/clip_NN_HHMMSS.mp4 + .json  -> dashboard.html refreshed
Every event prints one line: HUNT REC WAIT CHAT SPIKE CLIP MISS ERROR STOP.
Only clip streamers who allow it (clipping campaigns) - see README.md.
"""
from __future__ import annotations

import argparse
import collections
import json
import re
import socket
import statistics
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import clipmaker  # noqa: E402
import config  # noqa: E402

SEG = 6
BUFFER_KEEP = 12 * 60
HYPE = re.compile(r"\b(lul|lmao+|lmfao|kekw|omegalul|icant|pog+|poggers|w+|clip|clip it|no way|bro+|wtf|holy|omg|om|oml|lol+)\b|\?{3,}|😂|💀",
                  re.I)
stop = threading.Event()


def log(kind, msg):
    print(f"{kind} {datetime.now():%H:%M:%S} {msg}", flush=True)


def stream_page(platform, channel):
    return f"https://kick.com/{channel}" if platform == "kick" else f"https://www.twitch.tv/{channel}"


# ---------------------------------------------------------------- record
def hls_url(platform: str, channel: str, height: int) -> str | None:
    p = subprocess.run([*config.ytdlp(), "-g", "-f", f"best[height<={height}]/best", stream_page(platform, channel)],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    urls = [u for u in p.stdout.split() if u.startswith("http")]
    return urls[0] if urls else None


def recorder(a, segdir: Path):
    segdir.mkdir(parents=True, exist_ok=True)
    while not stop.is_set():
        url = hls_url(a.platform, a.channel, a.height)
        if not url:
            log("WAIT", f"{a.channel} is not live - checking again in 60 s")
            stop.wait(60)
            continue
        log("REC", f"recording {a.platform}/{a.channel} in {SEG}s chunks")
        proc = subprocess.Popen(["ffmpeg", "-v", "error", "-reconnect", "1", "-reconnect_streamed", "1",
                                 "-reconnect_delay_max", "10", "-i", url, "-map", "0:v:0", "-map", "0:a:0?", "-c", "copy",
                                 "-f", "segment", "-segment_time", str(SEG), "-reset_timestamps", "1", "-strftime", "1",
                                 str(segdir / "%Y%m%d_%H%M%S.ts")], stdin=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL)   # Twitch ad splices make ffmpeg chatty; harmless
        while proc.poll() is None and not stop.is_set():
            stop.wait(2)
        if proc.poll() is None:
            proc.terminate()
        if not stop.is_set():
            log("REC", "stream connection ended - reconnecting")
            stop.wait(5)


def seg_time(p: Path) -> float:
    return time.mktime(datetime.strptime(p.stem, "%Y%m%d_%H%M%S").timetuple())


def finished_segments(segdir: Path) -> list[Path]:
    return sorted(segdir.glob("*.ts"))[:-1]       # the newest chunk is still being written


def janitor(segdir: Path, keep: bool):
    while not stop.is_set():
        stop.wait(30)
        if keep:
            continue
        cutoff = time.time() - BUFFER_KEEP
        for p in sorted(segdir.glob("*.ts"))[:-3]:
            try:
                if seg_time(p) < cutoff:
                    p.unlink()
            except (ValueError, OSError):
                pass


# ---------------------------------------------------------------- chat (Twitch)
def chat_reader(channel: str, out: Path, msgs: collections.deque, lock: threading.Lock):
    while not stop.is_set():
        try:
            s = socket.create_connection(("irc.chat.twitch.tv", 6667), timeout=30)
            s.sendall(f"PASS SCHMOOPIIE\r\nNICK justinfan{int(time.time()) % 90000 + 10000}\r\nJOIN #{channel.lower()}\r\n".encode())
            log("CHAT", f"reading #{channel} anonymously")
            buf = ""
            with open(out, "a", encoding="utf-8") as f:
                while not stop.is_set():
                    try:
                        data = s.recv(65536).decode("utf-8", "replace")
                    except socket.timeout:
                        s.sendall(b"PING :tmi.twitch.tv\r\n")
                        continue
                    if not data:
                        raise ConnectionError("chat closed")
                    buf += data
                    *lines, buf = buf.split("\r\n")
                    for line in lines:
                        if line.startswith("PING"):
                            s.sendall(b"PONG :tmi.twitch.tv\r\n")
                            continue
                        m = re.match(r":(\w+)!\S+ PRIVMSG #\w+ :(.*)", line)
                        if m:
                            t = time.time()
                            with lock:
                                msgs.append((t, m.group(1), m.group(2)))
                            f.write(json.dumps({"t": round(t, 2), "u": m.group(1), "m": m.group(2)}, ensure_ascii=False) + "\n")
                    f.flush()
        except (OSError, ConnectionError) as e:
            if not stop.is_set():
                log("CHAT", f"reconnecting ({e})")
                stop.wait(5)


# ---------------------------------------------------------------- detectors
class Trigger:
    """One shared cooldown for every detector, so one moment becomes one clip."""

    def __init__(self, cooldown: float, events: collections.deque):
        self.cooldown, self.events, self.last, self.lock = cooldown, events, 0.0, threading.Lock()
        self.recent = {}                                  # detector -> last time it fired

    def fire(self, kind: str, t: float, ev: dict):
        with self.lock:
            self.recent[kind] = t
            other = [k for k, v in self.recent.items() if k != kind and abs(v - t) < 15]
            if t - self.last < self.cooldown:
                if other and self.events and self.events[-1].get("trigger") != "both":
                    self.events[-1]["trigger"] = "both"   # the other detector agrees with the clip already queued
                return False
            self.last = t
            ev["trigger"] = "both" if other else kind
            self.events.append(ev)
            return True


def chat_detector(msgs, lock, trig: Trigger, a):
    history = collections.deque(maxlen=60)                # 10 s scores sampled every 5 s -> last 5 min
    armed_at = time.time() + 60
    while not stop.is_set():
        stop.wait(5)
        now = time.time()
        with lock:
            while msgs and msgs[0][0] < now - 400:
                msgs.popleft()
            window = [m for m in msgs if m[0] >= now - 10]
        score = sum(1.6 if HYPE.search(t) else 1.0 for _, _, t in window)
        base = statistics.median(history) if len(history) >= 6 else None
        history.append(score)
        if base is None or now < armed_at:
            continue
        if score >= max(a.min_msgs, base * a.ratio):
            lines = [t for _, _, t in window]
            ev = {"t": now, "score": round(score, 1), "normal": round(base, 1),
                  "chat_top": clipmaker.chat_summary(lines), "chat_lines": lines[-25:]}
            if trig.fire("chat", now, ev):
                log("SPIKE", f"chat {score:.0f} vs normal {base:.0f} - {', '.join(w for w, _ in ev['chat_top'][:5])}")


def loudness(seg: Path) -> list[float]:
    p = subprocess.run(["ffmpeg", "-v", "quiet", "-i", str(seg), "-map", "0:a:0", "-ac", "1", "-ar", "8000", "-f", "s16le", "-"],
                       capture_output=True)
    x = np.frombuffer(p.stdout, np.int16).astype(np.float32) / 32768
    n = len(x) // 8000
    if not n:
        return []
    rms = np.sqrt((x[:n * 8000].reshape(n, 8000) ** 2).mean(axis=1)) + 1e-6
    return [float(v) for v in 20 * np.log10(rms)]   # plain floats (json-safe)


def audio_detector(segdir: Path, trig: Trigger, msgs, lock, a):
    seen, hist = set(), collections.deque(maxlen=300)    # 1 s loudness, last 5 min
    while not stop.is_set():
        stop.wait(3)
        for seg in finished_segments(segdir):
            if seg in seen:
                continue
            seen.add(seg)
            try:
                st = seg_time(seg)
            except ValueError:
                continue
            for i, db in enumerate(loudness(seg)):
                t = st + i
                base = statistics.median(hist) if len(hist) >= 60 else None
                hist.append(db)
                if base is None or db < a.audio_floor:
                    continue
                if db - base >= a.audio_db:
                    with lock:
                        lines = [m[2] for m in msgs if t - 5 <= m[0] <= t + 20]
                    ev = {"t": t, "score": None, "normal": None, "audio_db": round(db - base, 1),
                          "chat_top": clipmaker.chat_summary(lines), "chat_lines": lines[-25:]}
                    if trig.fire("audio", t, ev):
                        log("SPIKE", f"audio +{db - base:.0f} dB over normal")


# ---------------------------------------------------------------- cut
def cut_clip(ev: dict, n: int, segdir: Path, clipdir: Path, a) -> Path | None:
    t0, t1 = ev["t"] - a.before, ev["t"] + a.after
    limit = time.time() + a.after + 70
    while time.time() < t1 + SEG + 2 and time.time() < limit:      # wait for the chunks after the spike
        time.sleep(1)
    segs = []
    for p in sorted(segdir.glob("*.ts")):
        try:
            st = seg_time(p)
        except ValueError:
            continue
        if st + SEG >= t0 and st <= t1:
            segs.append((st, p))
    if not segs:
        log("MISS", f"no recorded chunks for spike {n} (not recording yet?)")
        return None
    stamp = datetime.fromtimestamp(ev["t"]).strftime("%H%M%S")
    final = clipdir / f"clip_{n:02d}_{stamp}.mp4"
    work = clipdir / f"_work_{n:02d}"
    work.mkdir(parents=True, exist_ok=True)
    lst = work / "list.txt"
    lst.write_text("".join(f"file '{p.as_posix()}'\n" for _, p in segs), encoding="utf-8")
    raw = work / "raw.mp4"
    off = max(t0 - segs[0][0], 0)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-ss", f"{off:.2f}",
                    "-t", f"{t1 - t0:.2f}", "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-c:a", "aac",
                    "-b:a", "192k", str(raw)], check=True, capture_output=True)
    info = clipmaker.make_vertical(raw, final, a.layout, a.cam, not a.no_captions, work)
    clipmaker.write_meta(final, channel=a.channel, platform=a.platform, mode="live", layout=a.layout,
                         time=datetime.fromtimestamp(ev["t"]).isoformat(timespec="seconds"),
                         window=[round(t0, 2), round(t1, 2)], duration=round(t1 - t0, 1),
                         source_url=stream_page(a.platform, a.channel), **info,
                         **{k: v for k, v in ev.items() if k != "t"})
    if not a.keep_work:
        import shutil
        shutil.rmtree(work, ignore_errors=True)
    log("CLIP", str(final))
    if a.beep:
        try:
            import winsound
            winsound.MessageBeep()
        except Exception:
            pass
    return final


def cutter(events, segdir, clipdir, a):
    n = 0
    while not stop.is_set() or events:
        if not events:
            stop.wait(1)
            continue
        ev = events.popleft()
        n += 1
        if a.no_cut:
            continue
        try:
            cut_clip(ev, n, segdir, clipdir, a)
        except Exception as e:                    # one bad clip must never stop the hunt
            log("ERROR", f"cutting spike {n} failed: {e}")


# ---------------------------------------------------------------- main
def parser():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("channel")
    ap.add_argument("--platform", choices=["twitch", "kick"], default="twitch")
    ap.add_argument("--minutes", type=float, default=0, help="stop after N minutes (0 = until Ctrl+C)")
    ap.add_argument("--layout", choices=["blur", "zoom", "cam"], default="zoom")
    ap.add_argument("--cam", type=float, nargs=4, metavar=("X", "Y", "W", "H"), help="facecam box (fractions) for --layout cam")
    ap.add_argument("--ratio", type=float, default=2.5, help="chat spike = this many times the stream's normal pace")
    ap.add_argument("--min-msgs", type=float, default=12, help="ignore chat spikes smaller than this (per 10 s)")
    ap.add_argument("--audio-db", type=float, default=9, help="audio spike = this many dB over the stream's normal")
    ap.add_argument("--audio-floor", type=float, default=-30, help="ignore sounds quieter than this (dBFS)")
    ap.add_argument("--no-audio", action="store_true", help="chat spikes only")
    ap.add_argument("--cooldown", type=float, default=45)
    ap.add_argument("--before", type=float, default=35)
    ap.add_argument("--after", type=float, default=8)
    ap.add_argument("--height", type=int, default=1080)
    ap.add_argument("--no-cut", action="store_true")
    ap.add_argument("--no-captions", action="store_true")
    ap.add_argument("--keep", action="store_true", help="keep every recorded chunk (needs disk)")
    ap.add_argument("--keep-work", action="store_true")
    ap.add_argument("--beep", action="store_true", help="sound when a clip is ready")
    return ap


def main():
    a = parser().parse_args()
    if a.layout == "cam" and not a.cam:
        a.layout = "zoom"
    run = config.RUNS / f"{a.channel.lower()}_{datetime.now():%Y%m%d_%H%M}"
    segdir, clipdir = run / "segments", run / "clips"
    clipdir.mkdir(parents=True, exist_ok=True)
    (run / "settings.json").write_text(json.dumps(vars(a), indent=1), encoding="utf-8")
    msgs, lock, events = collections.deque(), threading.Lock(), collections.deque()
    trig = Trigger(a.cooldown, events)
    jobs = [(recorder, (a, segdir)), (janitor, (segdir, a.keep)), (cutter, (events, segdir, clipdir, a))]
    if a.platform == "twitch":
        jobs += [(chat_reader, (a.channel, run / "chat.jsonl", msgs, lock)), (chat_detector, (msgs, lock, trig, a))]
    if not a.no_audio or a.platform == "kick":
        jobs.append((audio_detector, (segdir, trig, msgs, lock, a)))
    threads = [threading.Thread(target=f, args=args, daemon=True) for f, args in jobs]
    for t in threads:
        t.start()
    log("HUNT", f"{a.platform}/{a.channel} -> {run}")
    end = time.time() + a.minutes * 60 if a.minutes else None
    try:
        while not end or time.time() < end:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    log("STOP", "finishing - waiting for clips in progress")
    stop.set()
    time.sleep(3)
    threads[2].join(timeout=240)


if __name__ == "__main__":
    main()
