"""Clip Hunter - the app: hunt every streamer in channels.json at the same time, one review page for all clips.

    python app.py                     # every enabled channel, until Ctrl+C
    python app.py --only streamer1 streamer2  # just these (must be in channels.json, or are added as Twitch)
    python app.py --minutes 120 --open # stop after 2 h; open the review page in the browser

channels.json  {"defaults": {...hunt.py options...}, "channels": [{"channel": "somestreamer", "platform": "twitch",
                "enabled": true, "layout": "cam", "cam": [0.0, 0.62, 0.27, 0.38], "note": "clipping campaign: ..."}]}
Each channel runs as its own hunt.py process (a crash in one never stops the others); every log line is prefixed
with the channel. Review: dashboard.html (refreshes itself every 20 s).
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

HUNTER = Path(__file__).resolve().parent
sys.path.insert(0, str(HUNTER))
import config  # noqa: E402

PY = sys.executable
OPTS = {"layout": "--layout", "ratio": "--ratio", "min_msgs": "--min-msgs", "audio_db": "--audio-db",
        "cooldown": "--cooldown", "before": "--before", "after": "--after", "height": "--height"}
FLAGS = {"no_audio": "--no-audio", "no_captions": "--no-captions", "beep": "--beep", "keep": "--keep"}


def command(ch: dict, defaults: dict, minutes: float) -> list[str]:
    o = {**defaults, **ch}
    cmd = [str(PY), "-u", str(HUNTER / "hunt.py"), o["channel"], "--platform", o.get("platform", "twitch")]
    for k, flag in OPTS.items():
        if o.get(k) is not None:
            cmd += [flag, str(o[k])]
    for k, flag in FLAGS.items():
        if o.get(k):
            cmd.append(flag)
    if o.get("cam"):
        cmd += ["--cam", *map(str, o["cam"])]
    if minutes:
        cmd += ["--minutes", str(minutes)]
    return cmd


def pump(name: str, proc: subprocess.Popen):
    for line in proc.stdout:
        line = line.rstrip()
        if line:
            print(f"[{name}] {line}", flush=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--only", nargs="+", help="hunt only these channels")
    ap.add_argument("--minutes", type=float, default=0)
    ap.add_argument("--open", action="store_true", help="open the review page")
    a = ap.parse_args()
    if not config.CHANNELS.exists():
        raise SystemExit("no channels.json yet - copy channels.example.json to channels.json and edit it")
    conf = json.loads(config.CHANNELS.read_text(encoding="utf-8"))
    defaults = conf.get("defaults", {})
    chans = [c for c in conf["channels"] if c.get("enabled", True)]
    if a.only:
        known = {c["channel"].lower(): c for c in conf["channels"]}
        chans = [known.get(n.lower(), {"channel": n, "platform": "twitch"}) for n in a.only]
    if not chans:
        raise SystemExit("no channels enabled in channels.json")
    import dashboard
    page = dashboard.build()
    if a.open:
        import webbrowser
        webbrowser.open(page.as_uri())
    procs = []
    for ch in chans:
        p = subprocess.Popen(command(ch, defaults, a.minutes), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                             text=True, encoding="utf-8", errors="replace", cwd=HUNTER,
                             env={**os.environ, "PYTHONIOENCODING": "utf-8"})
        procs.append((ch["channel"], p))
        threading.Thread(target=pump, args=(ch["channel"], p), daemon=True).start()
        print(f"APP started {ch.get('platform', 'twitch')}/{ch['channel']} (layout {ch.get('layout', defaults.get('layout', 'zoom'))})",
              flush=True)
    print(f"APP review page: {page}", flush=True)
    try:
        while any(p.poll() is None for _, p in procs):
            time.sleep(2)
    except KeyboardInterrupt:
        # Ctrl+C reaches every hunter in this console too; each one finishes its clips in progress and exits
        print("APP stopping every hunter (finishing clips in progress) ...", flush=True)
        for _, p in procs:
            try:
                p.wait(timeout=240)
            except subprocess.TimeoutExpired:
                p.kill()
    dashboard.build()
    print("APP done", flush=True)


if __name__ == "__main__":
    main()
