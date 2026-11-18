"""Clip Hunter — review page: every clip from every run, newest first. Rebuilt after each clip.

    python dashboard.py        # -> dashboard.html (open it in a browser; it refreshes itself)
Approve / reject / posted marks are saved in your browser (localStorage).
"""
from __future__ import annotations

import json
import subprocess
from datetime import datetime
from pathlib import Path

HUNTER = Path(__file__).resolve().parent
RUNS = HUNTER / "runs"
PAGE = HUNTER / "dashboard.html"


def poster(mp4: Path, at: float) -> Path | None:
    """Thumbnail at the spike moment (made once, next to the clip)."""
    jpg = mp4.with_suffix(".jpg")
    if not jpg.exists():
        subprocess.run(["ffmpeg", "-v", "quiet", "-y", "-ss", f"{max(at, 0):.2f}", "-i", str(mp4), "-frames:v", "1",
                        "-vf", "scale=540:-2", "-q:v", "4", str(jpg)], capture_output=True)
    return jpg if jpg.exists() else None


def collect() -> list[dict]:
    items = []
    for js in RUNS.glob("*/clips/clip_*.json"):
        try:
            m = json.loads(js.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        mp4 = js.with_suffix(".mp4")
        if not mp4.exists():
            continue
        run = js.parents[1].name
        w = m.get("window") or [0, 0]
        spike_at = (m.get("duration") or 43) - 8 if not w[0] else 35
        thumb = poster(mp4, min(spike_at, (m.get("duration") or 43) - 1))
        items.append({
            "key": f"{run}/{js.stem}", "run": run, "file": mp4.relative_to(HUNTER).as_posix(),
            "poster": thumb.relative_to(HUNTER).as_posix() if thumb else "",
            "channel": m.get("channel") or run.split("_")[0], "platform": m.get("platform", "twitch"),
            "mode": m.get("mode", "live"), "time": m.get("time", ""), "made": m.get("made", ""),
            "score": m.get("score"), "normal": m.get("normal"), "trigger": m.get("trigger", "chat"),
            "chat_top": m.get("chat_top", []), "chat_lines": m.get("chat_lines", [])[-12:],
            "transcript": m.get("transcript", ""), "layout": m.get("layout", "blur"),
            "url": m.get("source_url", ""), "duration": m.get("duration"),
        })
    items.sort(key=lambda x: x["made"], reverse=True)
    return items


def build() -> Path:
    data = {"built": datetime.now().strftime("%d %b %H:%M:%S"), "items": collect()}
    blob = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    PAGE.write_text(TEMPLATE.replace("__DATA__", blob), encoding="utf-8")
    return PAGE


TEMPLATE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Clip Hunter</title>
<style>
:root{--bg:#0d0b12;--panel:#16131d;--line:#2c2638;--ink:#f3eff8;--mute:#9d94ad;--pink:#ff4f8b;--ok:#4ade80;--bad:#f87171;--warn:#fbbf24}
@media (prefers-color-scheme: light){:root:not([data-theme="dark"]){--bg:#f6f4fa;--panel:#fff;--line:#e3dfeb;--ink:#1b1724;--mute:#6b6478}}
*{box-sizing:border-box} body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.45 system-ui,Segoe UI,sans-serif}
.wrap{max-width:1300px;margin:0 auto;padding:20px 16px 60px}
header{display:flex;flex-wrap:wrap;gap:12px;align-items:center;justify-content:space-between;margin-bottom:16px}
h1{margin:0;font-size:24px} .sub{color:var(--mute);font-size:13px}
.filters{display:flex;gap:8px;flex-wrap:wrap} select,button,input{font:inherit;color:var(--ink);background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:6px 10px}
button{cursor:pointer} button.on{border-color:var(--pink);color:var(--pink)}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:14px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:12px;overflow:hidden;display:flex;flex-direction:column}
.card.approved{border-color:var(--ok)} .card.rejected{opacity:.45}
video{width:100%;aspect-ratio:9/16;background:#000;display:block;max-height:520px}
.body{padding:10px 12px;display:flex;flex-direction:column;gap:6px;font-size:13px}
.row{display:flex;justify-content:space-between;gap:8px;align-items:center}
.ch{font-weight:700;font-size:15px} .tag{font-size:11px;padding:2px 7px;border-radius:6px;border:1px solid var(--line);color:var(--mute)}
.chips span{display:inline-block;margin:2px 4px 0 0;padding:1px 7px;border-radius:10px;background:rgba(255,79,139,.15);color:var(--pink);font-size:12px}
.tr{color:var(--mute);max-height:5.4em;overflow:auto} .lines{max-height:7em;overflow:auto;color:var(--mute);font-size:12px;border-top:1px dashed var(--line);padding-top:4px}
.acts{display:flex;gap:6px;flex-wrap:wrap} .acts a{color:var(--ink);text-decoration:none;font-size:13px;padding:6px 10px;border:1px solid var(--line);border-radius:8px}
.empty{color:var(--mute);padding:40px;text-align:center;border:1px dashed var(--line);border-radius:12px}
</style></head><body><div class="wrap">
<header><div><h1>Clip Hunter</h1><div class="sub" id="sub"></div></div>
<div class="filters"><select id="fch"><option value="">All streamers</option></select>
<select id="fst"><option value="">All</option><option value="new">New</option><option value="approved">Approved</option><option value="rejected">Rejected</option><option value="posted">Posted</option></select>
<button id="auto" class="on">Auto-refresh on</button></div></header>
<div id="grid" class="grid"></div></div>
<script type="application/json" id="data">__DATA__</script>
<script>
const D = JSON.parse(document.getElementById('data').textContent);
const store = { get(k){ try { return localStorage.getItem('hunter:' + k); } catch(e){ return null; } },
                set(k, v){ try { v == null ? localStorage.removeItem('hunter:' + k) : localStorage.setItem('hunter:' + k, v); } catch(e){} } };
const el = (t, a = {}, ...kids) => { const n = document.createElement(t);
  for (const [k, v] of Object.entries(a)) { if (k === 'onclick') n.onclick = v; else n.setAttribute(k, v); }
  for (const k of kids.flat()) n.append(k instanceof Node ? k : document.createTextNode(k ?? '')); return n; };
const status = (it) => store.get(it.key + ':st') || 'new';
function card(it){
  const st = status(it);
  const c = el('div', {class:'card ' + st});
  const mk = (s, label) => el('button', {class: st === s ? 'on' : '', onclick: () => { store.set(it.key + ':st', st === s ? null : s); render(); }}, label);
  const when = it.time ? new Date(it.time).toLocaleString(undefined, {weekday:'short', hour:'2-digit', minute:'2-digit'}) : '';
  c.append(el('video', {src: it.file, poster: it.poster || '', controls: '', preload: 'none', playsinline: ''}),
    el('div', {class:'body'},
      el('div', {class:'row'}, el('span', {class:'ch'}, it.channel), el('span', {class:'tag'}, `${it.platform} · ${it.mode} · ${it.trigger}`)),
      el('div', {class:'row'}, el('span', {}, when), el('span', {class:'tag'}, it.score != null ? `chat ${it.score} vs ${it.normal}` : it.layout)),
      el('div', {class:'chips'}, (it.chat_top || []).slice(0, 6).map(([w, n]) => el('span', {}, `${w} ×${n}`))),
      it.transcript ? el('div', {class:'tr'}, '“' + it.transcript + '”') : '',
      (it.chat_lines || []).length ? el('div', {class:'lines'}, it.chat_lines.map(l => el('div', {}, l))) : '',
      el('div', {class:'acts'}, mk('approved', '✓ Approve'), mk('rejected', '✗ Reject'), mk('posted', 'Posted'),
        el('a', {href: it.file, download: ''}, '⬇'), it.url ? el('a', {href: it.url, target: '_blank', rel: 'noopener'}, 'Stream ↗') : '')));
  return c;
}
function render(){
  const fch = document.getElementById('fch').value, fst = document.getElementById('fst').value;
  const grid = document.getElementById('grid'); grid.innerHTML = '';
  const list = D.items.filter(it => (!fch || it.channel === fch) && (!fst || status(it) === fst));
  if (!list.length) grid.append(el('div', {class:'empty'}, D.items.length ? 'No clips match this filter.' : 'No clips yet — start a hunt: python app.py  (or python vod.py <twitch vod>)'));
  list.forEach(it => grid.append(card(it)));
  const ap = D.items.filter(it => status(it) === 'approved').length;
  document.getElementById('sub').textContent = `${D.items.length} clips · ${ap} approved · updated ${D.built}`;
}
const chs = [...new Set(D.items.map(i => i.channel))].sort();
chs.forEach(c => document.getElementById('fch').append(el('option', {value: c}, c)));
['fch', 'fst'].forEach(id => { const s = document.getElementById(id); s.value = store.get('f:' + id) || ''; s.onchange = () => { store.set('f:' + id, s.value || null); render(); }; });
let auto = store.get('auto') !== 'off';
const ab = document.getElementById('auto');
const paintAuto = () => { ab.textContent = auto ? 'Auto-refresh on' : 'Auto-refresh off'; ab.classList.toggle('on', auto); };
ab.onclick = () => { auto = !auto; store.set('auto', auto ? null : 'off'); paintAuto(); }; paintAuto();
setInterval(() => { const playing = [...document.querySelectorAll('video')].some(v => !v.paused); if (auto && !playing) location.reload(); }, 20000);
render();
</script></body></html>
"""

if __name__ == "__main__":
    print(build())
