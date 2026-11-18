"""One-command setup: installs everything Clip Hunter needs inside this folder. Nothing to type, nothing to edit.

    python install.py               # Windows (or: py install.py)
    python3 install.py              # macOS / Linux
    python install.py --demo <channel>   # also cut 3 clips from that Twitch channel's latest ended stream

What it does (each step is skipped when already done, so running it again is safe):
  1. .venv/                         a private Python environment for this project
  2. pip install -r requirements.txt
  3. ffmpeg                         uses yours if `ffmpeg` already works; otherwise downloads a full build into tools/ffmpeg
                                    (Windows + Linux; on macOS it uses Homebrew)
  4. TwitchDownloaderCLI            newest release for this computer, into tools/
  5. channels.json                  copied from channels.example.json (everything switched off)
  6. caption model                  downloaded once (~500 MB)
  7. doctor.py                      checks it all
Only the Python standard library is used here, so it runs before anything is installed.
"""
from __future__ import annotations

import argparse
import io
import json
import os
import platform
import shutil
import stat
import subprocess
import sys
import tarfile
import urllib.request
import zipfile
from pathlib import Path

HOME = Path(__file__).resolve().parent
TOOLS = HOME / "tools"
VENV = HOME / ".venv"
WIN = os.name == "nt"
MAC = sys.platform == "darwin"
ARM = platform.machine().lower() in ("arm64", "aarch64")
VPY = VENV / ("Scripts/python.exe" if WIN else "bin/python")
UA = {"User-Agent": "clip-hunter-setup"}


def say(msg: str):
    print(f"\n==> {msg}", flush=True)


def run(cmd: list, **kw):
    print("    $ " + " ".join(map(str, cmd)), flush=True)
    subprocess.run([str(c) for c in cmd], check=True, **kw)


def fetch(url: str, what: str) -> bytes:
    print(f"    downloading {what} ...", flush=True)
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=600) as r:
        total, buf, done = int(r.headers.get("Content-Length") or 0), io.BytesIO(), 0
        while chunk := r.read(1 << 20):
            buf.write(chunk)
            done += len(chunk)
            if total:
                print(f"\r    {done * 100 // total:3d}%  {done >> 20} / {total >> 20} MB", end="", flush=True)
        print()
        return buf.getvalue()


def step_venv():
    say("1/7  Python environment (.venv)")
    if sys.version_info < (3, 10):
        sys.exit(f"Python 3.10 or newer is needed (this is {sys.version.split()[0]}). Install it from python.org and run again.")
    if VPY.exists():
        print("    already there")
        return
    run([sys.executable, "-m", "venv", VENV])


def step_packages():
    say("2/7  Python packages")
    run([VPY, "-m", "pip", "install", "--disable-pip-version-check", "-q", "-U", "pip"])
    run([VPY, "-m", "pip", "install", "--disable-pip-version-check", "-q", "-r", HOME / "requirements.txt"])


def has_ffmpeg() -> bool:
    local = TOOLS / "ffmpeg" / "bin"
    return bool(shutil.which("ffmpeg") or (local / ("ffmpeg.exe" if WIN else "ffmpeg")).exists())


def step_ffmpeg(force_local: bool):
    say("3/7  ffmpeg")
    if has_ffmpeg() and not force_local:
        print("    already works")
        return
    if MAC:
        if not shutil.which("brew"):
            sys.exit("ffmpeg is missing. Install Homebrew (https://brew.sh), then run this again — it will do the rest.")
        run(["brew", "install", "ffmpeg"])
        return
    name = {(True, False): "win64", (True, True): "winarm64", (False, False): "linux64", (False, True): "linuxarm64"}[(WIN, ARM)]
    ext = "zip" if WIN else "tar.xz"
    url = f"https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-{name}-gpl.{ext}"
    data = fetch(url, f"ffmpeg ({name}, ~150-200 MB)")
    dest = TOOLS / "ffmpeg"
    shutil.rmtree(dest, ignore_errors=True)
    (dest / "bin").mkdir(parents=True)
    if WIN:
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            for m in z.namelist():
                if "/bin/" in m and m.endswith(".exe"):
                    (dest / "bin" / Path(m).name).write_bytes(z.read(m))
    else:
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:xz") as t:
            for m in t.getmembers():
                if "/bin/" in m.name and m.isfile():
                    p = dest / "bin" / Path(m.name).name
                    p.write_bytes(t.extractfile(m).read())
                    p.chmod(p.stat().st_mode | stat.S_IEXEC)
    print(f"    ffmpeg installed in {dest / 'bin'} (used automatically, nothing added to your system)")


def step_twitchdownloader():
    say("4/7  TwitchDownloaderCLI (for ended streams)")
    exe = TOOLS / ("TwitchDownloaderCLI.exe" if WIN else "TwitchDownloaderCLI")
    if exe.exists():
        print("    already there")
        return
    rel = json.loads(fetch("https://api.github.com/repos/lay295/TwitchDownloader/releases/latest", "release list"))
    want = ("Windows-x64" if WIN else ("MacOSArm64" if MAC and ARM else "MacOS-x64") if MAC else
            ("LinuxArm64" if ARM else "Linux-x64"))
    asset = next((a for a in rel["assets"] if a["name"].startswith("TwitchDownloaderCLI") and a["name"].endswith(f"-{want}.zip")), None)
    if not asset:
        sys.exit(f"No TwitchDownloaderCLI build for {want} — get it by hand: https://github.com/lay295/TwitchDownloader/releases")
    TOOLS.mkdir(exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(fetch(asset["browser_download_url"], asset["name"]))) as z:
        member = next(m for m in z.namelist() if Path(m).name == exe.name)
        exe.write_bytes(z.read(member))
    exe.chmod(exe.stat().st_mode | stat.S_IEXEC)
    if MAC:   # downloaded binaries are quarantined by macOS; this one comes from the official GitHub release
        subprocess.run(["xattr", "-d", "com.apple.quarantine", str(exe)], capture_output=True)
    print(f"    {asset['name']} -> {exe}")


def step_channels():
    say("5/7  channels.json")
    dst = HOME / "channels.json"
    if dst.exists():
        print("    already there")
        return
    shutil.copy(HOME / "channels.example.json", dst)
    print("    created (every streamer is switched off until you add your own)")


def step_model():
    say("6/7  caption model (once, ~500 MB)")
    run([VPY, "-c", "import captions; captions._model('small'); print('    ready')"], cwd=HOME)


def step_doctor() -> bool:
    say("7/7  final check")
    return subprocess.run([str(VPY), "doctor.py"], cwd=HOME).returncode == 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--demo", metavar="CHANNEL", help="after setup, clip the latest ended stream of this Twitch channel")
    ap.add_argument("--ffmpeg-local", action="store_true", help="download ffmpeg into tools/ even if one is installed")
    ap.add_argument("--no-model", action="store_true", help="skip the caption model download (it happens on first clip)")
    a = ap.parse_args()
    os.chdir(HOME)
    step_venv()
    step_packages()
    step_ffmpeg(a.ffmpeg_local)
    step_twitchdownloader()
    step_channels()
    if not a.no_model:
        step_model()
    ok = step_doctor()
    if not ok:
        sys.exit("\nSetup finished with problems — see the MISS lines above.")
    act = r".venv\Scripts\activate" if WIN else "source .venv/bin/activate"
    print(f"""
==> Clip Hunter is ready in {HOME}

    {act}
    python vod.py <twitch channel or VOD link> --top 3     # best moments of an ended stream
    python hunt.py <channel> --minutes 30                  # hunt a live stream
    python app.py --open                                   # every streamer in channels.json + review page
""")
    if a.demo:
        say(f"demo: latest ended stream of {a.demo}")
        run([VPY, "vod.py", a.demo, "--top", "3"], cwd=HOME)
        run([VPY, "dashboard.py"], cwd=HOME)
        print(f"\n    open {HOME / 'dashboard.html'} in your browser to watch the clips")


if __name__ == "__main__":
    main()
