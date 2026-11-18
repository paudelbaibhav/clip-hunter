"""Word-by-word captions for a vertical clip: faster-whisper (runs on the CPU, free) -> .ass subtitle file.

    python captions.py clip.mp4 --out clip.ass        # stand-alone use
Used by clipmaker.py for every clip. Style: 3 words at a time, UPPER CASE, the spoken word highlighted, a small pop.
"""
from __future__ import annotations

import argparse
import re
import subprocess
from pathlib import Path

import numpy as np

_MODEL = {}


def _model(name: str):
    if name not in _MODEL:                       # loaded once per process (first run downloads it, ~500 MB for "small")
        from faster_whisper import WhisperModel
        _MODEL[name] = WhisperModel(name, device="cpu", compute_type="int8")
    return _MODEL[name]


def transcribe(video: Path, model: str = "small") -> list[dict]:
    """-> [{"start": s, "end": s, "word": "..."}]. Audio is decoded with ffmpeg (no extra audio libraries)."""
    pcm = subprocess.run(["ffmpeg", "-v", "quiet", "-i", str(video), "-map", "0:a:0", "-ac", "1", "-ar", "16000",
                          "-f", "s16le", "-"], capture_output=True).stdout
    if not pcm:
        return []
    audio = np.frombuffer(pcm, np.int16).astype(np.float32) / 32768
    segs, _ = _model(model).transcribe(audio, word_timestamps=True, vad_filter=True)
    return [{"start": w.start, "end": w.end, "word": w.word.strip()} for s in segs for w in (s.words or []) if w.word.strip()]


def _color(hexstr: str) -> str:                    # #RRGGBB -> ASS &HBBGGRR
    h = hexstr.lstrip("#")
    return f"&H00{h[4:6]}{h[2:4]}{h[0:2]}".upper()


def _ts(t: float) -> str:
    t = max(t, 0)
    h, rem = divmod(t, 3600)
    m, s = divmod(rem, 60)
    return f"{int(h)}:{int(m):02d}:{s:05.2f}"


def write_ass(words: list[dict], out: Path, width: int = 1080, height: int = 1920, font: str = "Arial",
              size: int = 72, color: str = "#FFFFFF", highlight: str = "#FFD400", per_chunk: int = 3,
              pos: float = 0.80, upper: bool = True, pop: bool = True) -> str:
    """Writes the .ass file and returns the plain transcript."""
    chunks = []
    for w in words:                                # up to N words, break on long pauses and sentence ends
        w = {**w, "start": max(0.0, w["start"] - 0.067)}
        if chunks and len(chunks[-1]) < per_chunk and w["start"] - chunks[-1][-1]["end"] <= 0.6 \
                and not re.search(r"[.!?]$", chunks[-1][-1]["word"]):
            chunks[-1].append(w)
        else:
            chunks.append([w])
    style = (f"Style: Cap,{font},{size},{_color(color)},{_color(color)},&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,6,0,"
             f"5,40,40,40,1")
    lines = ["[Script Info]", "ScriptType: v4.00+", f"PlayResX: {width}", f"PlayResY: {height}", "WrapStyle: 0",
             "ScaledBorderAndShadow: yes", "", "[V4+ Styles]",
             "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, "
             "Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, "
             "MarginR, MarginV, Encoding", style, "", "[Events]",
             "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"]
    at = rf"\an5\pos({width // 2},{int(height * pos)})"
    hl = _color(highlight)
    for ci, ch in enumerate(chunks):
        end = ch[-1]["end"]
        if ci + 1 < len(chunks) and chunks[ci + 1][0]["start"] - end < 0.35:
            end = chunks[ci + 1][0]["start"]
        texts = [(w["word"].upper() if upper else w["word"]).replace("{", "(").replace("}", ")") for w in ch]
        for wi, w in enumerate(ch):
            s, e = w["start"], ch[wi + 1]["start"] if wi + 1 < len(ch) else end
            body = " ".join(rf"{{\c{hl}}}{t}{{\r}}" if k == wi else t for k, t in enumerate(texts))
            p = r"\fscx85\fscy85\t(0,90,\fscx100\fscy100)" if pop and wi == 0 else ""
            lines.append(f"Dialogue: 0,{_ts(s)},{_ts(e)},Cap,,0,0,0,,{{{at}{p}}}{body}")
    out.write_text("\n".join(lines) + "\n", encoding="utf-8-sig")
    return " ".join(w["word"] for w in words)


def make(video: Path, out: Path, model: str = "small", **style) -> str:
    return write_ass(transcribe(video, model), out, **style)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("video", type=Path)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--model", default="small", help="tiny / base / small / medium (bigger = better, slower)")
    a = ap.parse_args()
    print(make(a.video, a.out or a.video.with_suffix(".ass"), a.model))
