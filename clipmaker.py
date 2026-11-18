"""Raw moment -> ready-to-post vertical clip (1080x1920): layout + word captions + loudness -14 LUFS + metadata.

Layouts
  zoom   gameplay big: the 16:9 frame scaled up and cropped at the sides, blurred copy fills top and bottom (default)
  blur   the whole 16:9 frame in the middle, blurred copy fills the rest (safe for anything)
  cam    facecam on top, gameplay below; needs the facecam box as fractions of the frame: [x, y, w, h]
Used by hunt.py (live) and vod.py (ended streams).
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from collections import Counter
from datetime import datetime
from pathlib import Path

import captions
import config

W, H = 1080, 1920


def layout_filter(layout: str, cam: list | None) -> str:
    bg = (f"[0:v]split[a][b];[a]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},"
          f"gblur=sigma=30,eq=brightness=-0.07[bg];")
    if layout == "cam" and cam:
        x, y, w, h = cam
        cam_h = 700
        return (f"[0:v]split[c][g];[c]crop=iw*{w}:ih*{h}:iw*{x}:ih*{y},scale={W}:{cam_h}:force_original_aspect_ratio=increase,"
                f"crop={W}:{cam_h}[top];[g]scale=-2:{H - cam_h},crop={W}:{H - cam_h}[bot];[top][bot]vstack[v]")
    if layout == "zoom":
        return bg + f"[b]scale=-2:840,crop={W}:840[fg];[bg][fg]overlay=(W-w)/2:(H-h)/2-60[v]"
    return bg + f"[b]scale={W}:-2[fg];[bg][fg]overlay=(W-w)/2:(H-h)/2-60[v]"


def make_vertical(raw: Path, out: Path, layout: str = "zoom", cam: list | None = None, with_captions: bool = True,
                  work: Path | None = None) -> dict:
    """raw (any size) -> out (1080x1920, -14 LUFS, optional burned captions). Returns {"transcript": ...}."""
    work = work or out.parent / f"_work_{out.stem}"
    work.mkdir(parents=True, exist_ok=True)
    nocap = work / "vertical.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(raw), "-filter_complex", layout_filter(layout, cam),
                    "-map", "[v]", "-map", "0:a:0?", "-r", "30", "-c:v", "libx264", "-preset", "veryfast", "-crf", "19",
                    "-af", "loudnorm=I=-14:TP=-1.5:LRA=11", "-c:a", "aac", "-b:a", "160k", str(nocap)],
                   check=True, capture_output=True)
    info = {"transcript": ""}
    if with_captions:
        try:
            info["transcript"] = captions.make(nocap, work / "cap.ass")
            sub = "subtitles=filename=cap.ass"     # run inside the work folder: no drive letters in the filter string
            if config.FONTS.is_dir():
                sub += ":fontsdir=" + os.path.relpath(config.FONTS, work).replace("\\", "/")
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", "vertical.mp4", "-vf", sub, "-c:v", "libx264",
                            "-preset", "veryfast", "-crf", "19", "-c:a", "copy", str(out.resolve())],
                           check=True, capture_output=True, cwd=work)
        except Exception as e:                   # never lose a clip over its captions
            print(f"WARN captions failed ({e}) - saving the clip without them", flush=True)
    if not out.exists():
        shutil.copy(nocap, out)
    return info


STOP = {"the", "a", "is", "to", "and", "i", "it", "of", "you", "that", "in", "he", "this", "for", "on", "was", "my", "me"}


def chat_summary(lines: list[str]) -> list:
    """Most used words in the chat lines (what chat was screaming about)."""
    c = Counter(w.lower() for t in lines for w in re.findall(r"[\w?!']+", t) if len(w) > 1 and w.lower() not in STOP)
    return c.most_common(8)


def write_meta(out: Path, **meta) -> Path:
    meta.setdefault("file", out.name)
    meta.setdefault("made", datetime.now().isoformat(timespec="seconds"))
    p = out.with_suffix(".json")
    p.write_text(json.dumps(meta, ensure_ascii=False, indent=1,
                            default=lambda o: o.item() if hasattr(o, "item") else str(o)), encoding="utf-8")
    try:
        import dashboard
        dashboard.build()
    except Exception as e:                       # the page is a convenience; never lose a clip over it
        print("WARN dashboard:", e, flush=True)
    return p
