"""Animation compositor: camera, actors, FX, captions, cards -> frame SVG strings.

Ek "shot" = ek narration line (ya title / vote / ending card). Shot ke andar
camera presets, world scroll, actors ki pose animation, fog/rain/flash FX,
HUD pills, karaoke captions aur cards sab time-based hain.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from pathlib import Path

import characters as ch
import scenes as sc
import svgkit as sk
from svgkit import circ, ease, ease_out, g, lerp, n, path, rect, shade, text

W = 1080.0
H = 1920.0
GROUND = sc.GROUND

PLACE_NAME = {
    "highway": "EMPTY HIGHWAY", "gas_station": "GAS STATION", "store": "GAS STATION STORE",
    "motel_lot": "MOTEL PARKING LOT", "motel_hall": "MOTEL ROOM 6", "forest": "FOREST ROAD",
    "bridge": "THE BLOCKED BRIDGE", "tower": "LOOKOUT TOWER THREE", "tower_top": "TOWER CABIN",
    "radio_room": "RADIO ROOM", "coast": "THE COAST", "city": "DEAD CITY",
    "metro": "METRO TUNNELS", "lab": "RESEARCH LAB", "farm": "RIVER FARM",
}

CAM = {
    "static": dict(z=(1.0, 1.03), x=(0.0, 0.0), y=(0.0, 0.0)),
    "push":   dict(z=(1.0, 1.24), x=(0.0, -14.0), y=(0.0, 10.0)),
    "pull":   dict(z=(1.26, 1.02), x=(16.0, 0.0), y=(8.0, 0.0)),
    "panl":   dict(z=(1.08, 1.12), x=(120.0, -160.0), y=(0.0, 0.0)),
    "panr":   dict(z=(1.08, 1.12), x=(-120.0, 160.0), y=(0.0, 0.0)),
    "tilt":   dict(z=(1.06, 1.12), x=(0.0, 0.0), y=(-70.0, 60.0)),
    "shake":  dict(z=(1.14, 1.18), x=(0.0, 0.0), y=(0.0, 0.0), shake=1),
    "creep":  dict(z=(1.02, 1.10), x=(-30.0, 30.0), y=(0.0, 0.0)),
}


# ---------------------------------------------------------------- text meas --

class Texts:
    """PIL se text width measure karo (wrapping + karaoke highlight ke liye)."""

    def __init__(self, font_dirs):
        self.bold = font_dirs["bold"]
        self.med = font_dirs["med"]
        self._cache = {}

    def _font(self, size, bold=True):
        key = (round(size, 1), bold)
        f = self._cache.get(key)
        if f is None:
            from PIL import ImageFont

            f = ImageFont.truetype(str(self.bold if bold else self.med), max(6, int(round(size))))
            self._cache[key] = f
        return f

    def w(self, s, size, bold=True):
        return self._font(size, bold).getlength(s)


# ------------------------------------------------------------------- shot ----

@dataclass
class Shot:
    kind: str                    # line | title | vote | ending
    start: float
    dur: float
    text: str = ""
    words: list = field(default_factory=list)
    meta: dict = field(default_factory=dict)
    prev: dict = field(default_factory=dict)   # card shots background ke liye

    @property
    def end(self):
        return self.start + self.dur


def _meta(shot: dict, default_place="highway"):
    s = dict(shot or {})
    s.setdefault("place", default_place)
    s.setdefault("time", "night")
    s.setdefault("mood", "tense")
    s.setdefault("cam", "static")
    s.setdefault("fx", "none")
    s.setdefault("cast", [])
    s.setdefault("zeds", None)
    return s


def build_timeline(ep, cfg, voices):
    """voices: [{text, dur, words, shot}]  ->  (shots, total_seconds, lead_silence)"""
    r = cfg.get("render", cfg)
    shots = []
    t = 0.0
    lead = 0.0
    if ep.get("title_card"):
        d = float(r.get("title_card_seconds", 3.0))
        shots.append(Shot("title", 0.0, d, meta=_meta(voices[0]["shot"] if voices else {})))
        t = d
        lead = d
    for v in voices:
        m = _meta(v["shot"])
        shots.append(Shot("line", t, max(1.2, v["dur"]), text=v["text"], words=v["words"], meta=m))
        t += max(1.2, v["dur"])
    if ep.get("kind") == "vote" and ep.get("choices"):
        d = float(r.get("choice_card_seconds", 3.6))
        shots.append(Shot("vote", t, d, text=ep.get("subtitle", ""),
                          meta=dict(shots[-1].meta if shots else {}), prev=shots[-1].meta if shots else {}))
        t += d
    if ep.get("kind") == "ending":
        d = float(r.get("ending_card_seconds", 4.2))
        shots.append(Shot("ending", t, d, text=ep.get("subtitle", ""),
                          meta=dict(shots[-1].meta if shots else {}), prev=shots[-1].meta if shots else {}))
        t += d
    return shots, t, lead


# ------------------------------------------------------------------ camera ---

def _cam_preset(shot, scroll_active):
    meta = shot.meta or {}
    name = meta.get("cam", "static")
    if scroll_active and name in (None, "static"):
        name = "push"
    return CAM.get(name) or CAM["static"]


def _cam_pivot(meta, p, scroll_active):
    """Preset ke pure numbers (bina shake) — continuity math ke liye."""
    c = _cam_preset(type("_S", (), {"meta": meta})(), scroll_active)
    z = lerp(c["z"][0], c["z"][1], ease(p))
    dx = lerp(c["x"][0], c["x"][1], ease(p))
    dy = lerp(c["y"][0], c["y"][1], ease(p))
    return (W / 2.0 + dx, H / 2.0 + dy, z)


# Same-preset consecutive shots par camera apni jagah RUKTA hai (no zoom oscillation);
# alag preset par quick blend (0.9s) hota hai — har cut par knock nahi.
BLEND_S = 0.9


def cam_at(shot, p, t, scroll_active, prev_shot=None, place=None):
    fx, fy, z = _cam_pivot(shot.meta, p, scroll_active)
    c = _cam_preset(shot, scroll_active)
    if c.get("shake"):
        s = 1.0 - 0.3 * p
        fx += math.sin(t * 41.0) * 10.0 * s + math.sin(t * 17.0) * 5.0
        fy += math.sin(t * 33.0 + 1.1) * 8.0 * s

    if prev_shot is not None and (prev_shot.meta or {}).get("place") == place:
        pc = _cam_pivot(prev_shot.meta, 1.0, scroll_active)
        same = (_cam_preset(shot, scroll_active) is _cam_preset(prev_shot, scroll_active))
        if same and not c.get("shake"):
            # preset same hai → previous end par hold (smooth, no snap)
            fx, fy, z = pc
        elif same and c.get("shake"):
            fx = pc[0] + (fx - W / 2.0)
            fy = pc[1] + (fy - H / 2.0)
            z = pc[2]
        else:
            b = ease(min(1.0, (t - shot.start) / BLEND_S))
            fx = lerp(pc[0], fx, b)
            fy = lerp(pc[1], fy, b)
            z = lerp(pc[2], z, b)
    return fx, fy, z


# --------------------------------------------------------------------- fx ----

def fx_layer(kind, t, dur, t_abs=None):
    """t = shot-local (flash decay), t_abs = absolute (weather continuity)."""
    if kind in (None, "none"):
        return ""
    if t_abs is None:
        t_abs = t
    out = []
    if kind == "fog":
        for i in range(3):
            sp = 26.0 + i * 14.0
            x = ((t_abs * sp + i * 520.0) % (W + 900)) - 450.0
            y = 1150 + i * 130
            out.append(sk.ell(x, y, 460, 74, "#cfe2ee", op=0.052))
    elif kind == "rain":
        rnd = random.Random(7)
        for i in range(70):
            x0 = rnd.uniform(-100, W + 100)
            sp = rnd.uniform(1500, 2300)
            y0 = ((rnd.uniform(0, H) + t_abs * sp) % (H + 300)) - 150
            ln = 46 + (i % 5) * 8
            out.append(sk.line(x0, y0, x0 - ln * 0.28, y0 + ln, "#cfe0ea", 3.2, op=0.24))
    elif kind == "embers":
        rnd = random.Random(11)
        for i in range(34):
            x0 = rnd.uniform(0, W)
            sp = rnd.uniform(60, 150)
            y0 = H - ((rnd.uniform(0, H) + t_abs * sp) % (H + 200))
            sway = math.sin(t_abs * 1.6 + i) * 16
            r = rnd.uniform(2.4, 5.2)
            out.append(circ(x0 + sway, y0, r, "#ffb45e", op=0.55))
    elif kind == "flash":
        # ek tez flash shot ke shuru mein, phir khatam
        k = max(0.0, 1.0 - t / 0.85)
        if k > 0:
            out.append(rect(0, 0, W, H, "#ffffff", op=round(0.62 * k ** 1.6, 3)))
        out.append(rect(0, 0, W, H, "#ff6a4a", op=round(0.05 + 0.05 * math.sin(t * 6), 3)))
    return "".join(out)


# ------------------------------------------------------------------ actors ---

def zed_silhouette(x, y, s, color, t, phase):
    sw = math.sin(t * 1.4 + phase) * 3.0
    out = (sk.limb(x, y - s * 0.42, x - s * 0.1, y - s * 0.02, color, s * 0.11)
           + sk.limb(x, y - s * 0.42, x + s * 0.12, y - s * 0.02, color, s * 0.11)
           + sk.rect(x - s * 0.13, y - s * 0.88, s * 0.26, s * 0.5, color, s * 0.1))
    out += sk.circ(x + sw * 0.3, y - s * 0.95, s * 0.15, color)
    out += sk.limb(x + s * 0.1, y - s * 0.8, x + s * 0.3, y - s * 0.62 + sw, color, s * 0.085)
    out += sk.limb(x - s * 0.1, y - s * 0.8, x - s * 0.26, y - s * 0.58 - sw, color, s * 0.085)
    return out


def actors_layer(meta, t, fx, cache):
    """Screen-anchored actors (camera hero ko follow karta hai)."""
    cast = meta.get("cast") or []
    out = []
    zeds = meta.get("zeds")
    time_name = meta.get("time", "night")
    far_col = shade(sc.TIME[time_name]["far"], -0.35)
    if zeds == "far":
        for i in range(3):
            out.append(g(f"translate({n(fx - 300 + i * 300)} {n(GROUND - 52)})",
                         ch.render_actor("zombie", "shamble", t + i * 0.7, size=190, op=0.92),
                         op=0.9))
    elif zeds == "near":
        for i in range(2):
            out.append(g(f"translate({n(fx - 330 - i * 90)} {n(GROUND - 14)})",
                         ch.render_actor("zombie", "reach_z" if i == 0 else "shamble",
                                         t + i * 0.5, size=440)))
    elif zeds == "horde":
        for i in range(9):
            out.append(zed_silhouette(fx - 460 + i * 118, GROUND - 30, 210, far_col, t, i * 1.1))
    if not cast:
        return "".join(out)
    humans = [c for c in cast if c[0] != "biscuit"]
    size = 500.0 if len(humans) <= 1 else 470.0
    spread = 250.0 if len(humans) <= 1 else 225.0
    k = len(cast)
    for i, item in enumerate(cast):
        who, act = item[0], item[1]
        x = fx + (i - (k - 1) / 2.0) * spread
        if who == "biscuit":
            x += 52.0
            out.append(g(f"translate({n(x)} {n(GROUND)})",
                         ch.render_actor(who, act, t * 1.0 + 0.2, size=size)))
        else:
            out.append(g(f"translate({n(x)} {n(GROUND)})",
                         ch.render_actor(who, act, t, size=size)))
    return "".join(out)


# ------------------------------------------------------------------- HUD -----

HUD_COLORS = {"hp": "#ff6a6a", "noise": "#ffb347", "food": "#7ddc8f", "dog": "#7dc4ff"}


def hud_layer(stats, labels, meta, t, ep):
    x, y = 46.0, 92.0
    out = []
    for i, key in enumerate(["hp", "noise", "food", "dog"]):
        if key not in stats:
            continue
        val = max(0, min(100, stats.get(key, 0)))
        col = HUD_COLORS[key]
        yy = y + i * 62
        slide = ease_out(min(1.0, t / 0.5 + i * 0.06))
        ox = -60 * (1 - slide)
        op = 0.55 + 0.45 * slide
        out.append(g(f"translate({n(ox)} 0)",
                     rect(x, yy, 316, 48, "#080c14", 24, op=0.52 * op)
                     + rect(x + 16, yy + 15, 18, 18, col, 9, op=op)
                     + text(x + 46, yy + 34, labels.get(key, key.upper()), 26, "Barlow",
                            "#e8eef6", anchor="start", weight="bold", op=op)
                     + rect(x + 150, yy + 17, 150, 14, "#1b2330", 7, op=0.75 * op)
                     + rect(x + 150, yy + 17, max(4.0, 150 * val / 100.0), 14,
                            col, 7, op=0.95 * op)
                     + text(x + 306, yy + 34, str(int(val)), 24, "Barlow", "#ffffff",
                            anchor="end", weight="bold", op=op)))
    # top-right: season / day / place
    tag = f"S{ep.get('season', 1)}  DAY {ep.get('day', 1)}"
    place = PLACE_NAME.get(meta.get("place", ""), "")
    out.append(g("translate(0 0)",
                 text(W - 46, 122, tag, 30, "Barlow", "#f2d16b", anchor="end",
                      weight="bold", ls=1.5)
                 + text(W - 46, 162, place, 26, "Barlow", "#9fb2c6", anchor="end", weight="bold")
                 + text(W - 46, 196, meta.get("subtitle", ""), 22, "Barlow", "#6f8296",
                        anchor="end")))
    return "".join(out)


# --------------------------------------------------------------- captions ----

def chunk_words(words, Texts, size, max_w=900.0, max_words=5):
    """words: [{w,start,end}] -> chunks [{words:[...], start, end}]"""
    chunks = []
    cur = []
    for wd in words:
        trial = cur + [wd]
        wid = sum(Texts.w(x["w"] + " ", size) for x in trial)
        if cur and (wid > max_w or len(trial) > max_words):
            chunks.append(cur)
            cur = [wd]
        else:
            cur = trial
    if cur:
        chunks.append(cur)
    out = []
    for i, c in enumerate(chunks):
        out.append(dict(
            words=c,
            start=c[0]["start"],
            end=c[-1]["end"] + 0.22,
        ))
    for i in range(len(out) - 1):
        out[i]["end"] = min(out[i]["end"], out[i + 1]["start"] + 0.1)
    return out


def caption_layer(chunks, t, Texts, size=52.0):
    if not chunks:
        return ""
    active = None
    for idx, c in enumerate(chunks):
        if c["start"] - 0.06 <= t <= c["end"]:
            active = (idx, c)
            break
    if active is None:
        for idx, c in enumerate(chunks):
            if t < c["start"]:
                active = (idx, c)
                break
    if active is None:
        return ""
    idx, c = active
    words = c["words"]
    # do line mein todo agar zaroorat ho
    lines, cur = [], []
    for wd in words:
        trial = cur + [wd]
        wid = sum(Texts.w(x["w"] + " ", size) for x in trial)
        if cur and wid > 880:
            lines.append(cur)
            cur = [wd]
        else:
            cur = trial
    if cur:
        lines.append(cur)
    out = [rect(0, 1470, W, H - 1470, "url(#cap_scrim)")]
    base_y = 1650 if len(lines) == 2 else 1690
    for li, ln in enumerate(lines):
        wid = sum(Texts.w(x["w"] + " ", size) for x in ln) - Texts.w(" ", size)
        x = (W - wid) / 2.0
        y = base_y + li * 74
        for wd in ln:
            spoken = t >= wd["start"]
            is_now = wd["start"] <= t <= wd["end"] + 0.16
            col = "#ffe08a" if is_now else ("#ffffff" if spoken else "#c8d4e0")
            op = 1.0 if (spoken or is_now) else 0.72
            out.append(path(f"M {n(x)} {n(y - size * 0.72)} L {n(x + Texts.w(wd['w'], size))} {n(y - size * 0.72)}",
                            "none", "#080c14", 26, op=0.0))
            out.append(text(x, y, wd["w"], size, "Barlow", col, anchor="start",
                            weight="bold", stroke="#070a11", sw=9, op=op))
            x += Texts.w(wd["w"] + " ", size)
    return "".join(out)


# ----------------------------------------------------------------- cards -----

def title_card(ep, t, dur, Texts):
    p = min(1.0, t / 0.7)
    fade = min(1.0, max(0.0, (dur - t) / 0.6))
    op = min(p, fade)
    z = 1.0 + 0.06 * (1 - ease(min(1.0, t / 2.2)))
    out = [rect(0, 0, W, H, "#05080e", op=0.72 * op)]
    out.append(g(f"translate({n(W / 2)} {n(700)}) scale({n(z)})",
                 text(0, 0, "ZOMBIE", 128, "Archivo Black", "#ffffff", op=op)
                 + text(0, 122, "APOCALYPSE", 128, "Archivo Black", "#d1583f", op=op)))
    out.append(g("translate(0 0)",
                 rect(W / 2 - 170, 880, 340, 8, "#f2d16b", 4, op=0.9 * op)
                 + text(W / 2, 990, "YOU DECIDE", 62, "Archivo Black", "#8fc8ff", op=op)
                 + text(W / 2, 1090, f"DAY {ep.get('day', 1)}  ·  {ep.get('subtitle', '')}".upper(),
                        40, "Barlow", "#cfd9e4", weight="bold", ls=2, op=op)
                 + text(W / 2, 1250, "The story stops every night.", 36, "Barlow", "#9fb2c6", op=op)
                 + text(W / 2, 1300, "Your comments decide what happens next.", 36, "Barlow",
                        "#9fb2c6", op=op)))
    return "".join(out)


def vote_card(ep, t, dur, Texts, stats=None, labels=None):
    p = ease_out(min(1.0, t / 0.55))
    fade = min(1.0, max(0.0, (dur - t) / 0.5))
    op = min(1.0, fade)
    out = [rect(0, 0, W, H, "#05080e", op=0.80 * op)]
    out.append(g(f"translate(0 {n(-30 * (1 - p))})",
                 text(W / 2, 400, f"DAY {ep.get('day', 1)}  ·  {ep.get('subtitle', '')}".upper(),
                      34, "Barlow", "#f2d16b", weight="bold", ls=2.5, op=op)
                 + text(W / 2, 512, "WHAT SHOULD MAX DO?", 66, "Archivo Black", "#ffffff", op=op)
                 + rect(W / 2 - 150, 556, 300, 7, "#d1583f", 4, op=op)))
    choices = (ep.get("choices") or [])[:2]
    for i, c in enumerate(choices):
        cp = ease_out(max(0.0, min(1.0, (t - 0.22 - i * 0.16) / 0.5)))
        cy = 700 + i * 300 + (1 - cp) * 70
        out.append(g(f"translate(0 0)", "", op=1))
        out.append(g(f"translate({n((1 - cp) * 60)} 0)",
                     rect(90, cy, W - 180, 250, "#111a26", 28, "#2c3a4d", 3, op=0.94 * op * cp)
                     + circ(190, cy + 125, 52, "#d1583f", op=op * cp)
                     + text(190, cy + 143, str(i + 1), 58, "Archivo Black", "#ffffff", op=op * cp)
                     + text(282, cy + 118, c["text"].split(" - ")[0], 54, "Archivo Black",
                            "#ffffff", anchor="start", op=op * cp)
                     + text(282, cy + 176, (c["text"].split(" - ")[1] if " - " in c["text"] else ""),
                            32, "Barlow", "#9fb2c6", anchor="start", weight="bold", op=op * cp)))
    pulse = 1.0 + 0.04 * math.sin(t * 5.0)
    out.append(g(f"translate({n(W / 2)} {n(1450)}) scale({n(pulse)})",
                 rect(-320, -56, 640, 112, "#1d2b3c", 56, "#f2d16b", 3, op=op)
                 + text(0, 14, "COMMENT 1 OR 2", 46, "Archivo Black", "#f2d16b", op=op)))
    out.append(text(W / 2, 1600, "The choice with the most comments wins.", 36, "Barlow",
                    "#cfd9e4", weight="bold", op=op))
    out.append(text(W / 2, 1652, "Tomorrow, it becomes real.", 34, "Barlow", "#9fb2c6", op=op))
    if stats:
        out.append(_stat_strip(stats, labels or {}, t, 1760, op))
    return "".join(out)


def _stat_strip(stats, labels, t, y, op=1.0):
    keys = [k for k in ("hp", "noise", "food", "dog") if k in stats]
    if not keys:
        return ""
    wgt = 1040 / len(keys)
    out = []
    for i, k in enumerate(keys):
        val = max(0, min(100, stats.get(k, 0)))
        x = 40 + i * wgt
        col = HUD_COLORS[k]
        out.append(rect(x, y, wgt - 24, 22, "#1b2330", 11, op=0.8 * op))
        out.append(rect(x, y, max(6.0, (wgt - 24) * val / 100.0), 22, col, 11, op=op))
        out.append(text(x + (wgt - 24) / 2, y - 16, labels.get(k, k.upper()), 26, "Barlow",
                        "#cfd9e4", weight="bold", op=op))
    return "".join(out)


def ending_card(ep, t, dur, Texts, stats=None, labels=None):
    end = ep.get("ending") or {}
    p = ease_out(min(1.0, t / 0.7))
    out = [rect(0, 0, W, H, "#04070c", op=0.86 * min(1.0, p))]
    out.append(g(f"translate({n(W / 2)} {n(690)}) scale({n(1.0 + 0.05 * (1 - p))})",
                 text(0, 0, end.get("title", "THE END").upper(), 76, "Archivo Black",
                      "#f2d16b", op=p)
                 + text(0, 96, end.get("subtitle", ""), 40, "Barlow", "#cfd9e4",
                        weight="bold", op=p)))
    out.append(g("translate(0 0)",
                 rect(W / 2 - 200, 830, 400, 8, "#d1583f", 4, op=p)
                 + text(W / 2, 990, f"DAY {ep.get('day', 1)} COMPLETE", 44, "Archivo Black",
                        "#ffffff", op=p)
                 + text(W / 2, 1080, "Your votes wrote this ending.", 38, "Barlow",
                        "#9fb2c6", weight="bold", op=p)
                 + text(W / 2, 1180, "SEASON 2  ·  CITY OF ECHOES", 40, "Archivo Black",
                        "#8fc8ff", op=p)
                 + text(W / 2, 1240, "comments decide what happens next", 30, "Barlow",
                        "#6f8296", op=p)))
    if stats:
        out.append(_stat_strip(stats, labels or {}, t, 1500, p))
    out.append(text(W / 2, 1700, "FOLLOW FOR THE NEXT CHAPTER", 40, "Archivo Black",
                    "#f2d16b", op=p * (0.6 + 0.4 * math.sin(t * 3.0) ** 2)))
    return "".join(out)


# ----------------------------------------------------------------- frames ----

def _scene_cached(cache, place, tname, mood, seed):
    key = (place, tname, mood, seed)
    if key not in cache:
        cache[key] = sc.build(place, tname, mood, seed)
    return cache[key]


def frame_svg(ep, cfg, shots, t, Texts, cache, seed=1):
    shot = shots[-1]
    for s in shots:
        if s.start <= t < s.end:
            shot = s
            break
    local = t - shot.start
    p = 0.0 if shot.dur <= 0 else min(1.0, local / shot.dur)
    meta = shot.meta if shot.kind == "line" else (shot.prev or shot.meta)
    place = meta.get("place", "highway")
    tname = meta.get("time", "night")
    mood = meta.get("mood", "tense")

    def _loco(m):
        lo = 0.0
        for who, act in (m.get("cast") or []):
            if act in ch.LOCOMOTION:
                lo = max(lo, ch.SPEEDS.get(act, 0.0) * (0.85 if who == "biscuit" else 1.0))
        return lo

    call_idx = next(i for i, s in enumerate(shots) if s is shot)
    # locomotion scroll — POORE timeline par continuous (same place), warna har line
    # par world background apni jagah se teleport karta tha = jitter
    scroll = 0.0
    for s in shots[:call_idx]:
        if s.kind == "line" and (s.meta or {}).get("place") == place:
            scroll += _loco(s.meta) * s.dur
    loco = _loco(meta)
    scroll += loco * local
    prev = shots[call_idx - 1] if call_idx > 0 else None
    fx, fy, z = cam_at(shot, p, t, loco > 0, prev_shot=prev, place=place)

    defs, layers = _scene_cached(cache, place, tname, mood, seed)
    vw, vh = W / z, H / z
    vx, vy = fx - vw / 2.0, fy - vh / 2.0

    body = []
    for k, content in layers:
        dx = (fx - W / 2.0) * (1.0 - k) - scroll * (0.25 + 0.75 * k)
        dy = (fy - H / 2.0) * (1.0 - k) * 0.4
        body.append(g(f"translate({n(dx)} {n(dy)})", content))
    # gait phase absolute t — shot boundary par walk cycle mid-stride reset nahi hoga
    body.append(actors_layer(meta, t, fx, cache))

    ov = []  # screen space
    if shot.kind == "line":
        ov.append(fx_layer(meta.get("fx", "none"), local, shot.dur, t_abs=t))
    elif shot.kind == "vote":
        ov.append(fx_layer("fog", t, shot.dur))
    if shot.kind == "line":
        chunks = cache.setdefault(("chunks", id(shot)), None)
        if chunks is None:
            size = float(cfg.get("render", cfg).get("caption_size", 52))
            chunks = chunk_words(shot.words, Texts, size) if shot.words else _fake_words(shot, Texts, size)
            cache[("chunks", id(shot))] = chunks
        ov.append(caption_layer(chunks, local, Texts,
                                float(cfg.get("render", cfg).get("caption_size", 52))))
    ov.append(hud_layer(ep.get("stats", {}), ep.get("stats_labels", {}),
                        dict(meta, subtitle=ep.get("subtitle", "")), t, ep))
    if shot.kind == "title":
        ov.append(title_card(ep, local, shot.dur, Texts))
        ov.append(hud_layer(ep.get("stats", {}), ep.get("stats_labels", {}),
                            dict(meta, subtitle=ep.get("subtitle", "")), t, ep))
    if shot.kind == "vote":
        ov.append(vote_card(ep, t, shot.dur, Texts, ep.get("stats"), ep.get("stats_labels")))
    if shot.kind == "ending":
        ov.append(ending_card(ep, t, shot.dur, Texts, ep.get("stats"), ep.get("stats_labels")))

    tint, ta = sc.mood_tint(mood)
    vig = rect(0, 0, W, H, "url(#vig_top)", op=0.30)
    scrim = rect(0, 0, W, 420, "url(#vig_top)", op=0.34)
    overlay_g = g(f"translate({n(vx)} {n(vy)}) scale({n(1.0 / z)})",
                  "".join(ov) + scrim + vig)
    tint_g = rect(0, 0, W, H, tint, op=ta)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{int(W)}" height="{int(H)}" '
        f'viewBox="{n(vx)} {n(vy)} {n(vw)} {n(vh)}">'
        f"<defs>{defs}{_ui_defs()}</defs>{''.join(body)}{tint_g}{overlay_g}</svg>"
    )


def _fake_words(shot, Texts, size):
    words = shot.text.split()
    if not words:
        return []
    total = sum(len(w) + 1 for w in words) or 1
    t0 = 0.15
    span = max(0.8, shot.dur - 0.5)
    out = []
    cur = t0
    for w in words:
        d = span * (len(w) + 1) / total
        out.append(dict(w=w, start=cur, end=cur + d))
        cur += d
    return chunk_words(out, Texts, size)


def _ui_defs():
    return (
        sk.lin_grad("cap_scrim", [(0, "#05070d", 0.0), (30, "#05070d", 0.62), (100, "#05070d", 0.94)])
        + sk.lin_grad("vig_top", [(0, "#05070d", 0.85), (100, "#05070d", 0.0)])
    )
