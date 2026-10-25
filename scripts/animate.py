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




# --------------------------------------------------------- story-specific beats
def narrative_beat_layer(meta, t):
    """Explicit visual beats for the opening Reel; screen-space, smoothly animated."""
    beat = (meta or {}).get("beat")
    if not beat:
        return ""

    out = []

    def puffs(cx, cy, count=7, speed=38.0, spread=92.0):
        items = []
        for i in range(count):
            phase = (t * speed + i * 31.0) % 190.0
            x = cx + math.sin(t * 1.45 + i * 1.7) * spread * 0.42 + phase * 0.18
            y = cy - phase
            r = 13.0 + (phase / 190.0) * 32.0 + (i % 3) * 4.0
            opacity = max(0.0, 0.32 * (1.0 - phase / 220.0))
            items.append(sk.ell(x, y, r * 0.88, r * 1.18, "#b9c5d2", op=opacity,
                                rotate=math.sin(t + i) * 24.0))
        return "".join(items)

    def car_body(x=70.0, y=1505.0, scale=1.0, color="#56677b", broken=False):
        # side view, nose/engine on the right; wheels and glass remain distinct
        body = (
            sk.path("M 0 0 L 24 -105 Q 34 -142 88 -150 L 315 -150 "
                    "L 402 -260 L 635 -260 L 745 -147 L 862 -119 "
                    "Q 888 -109 890 -72 L 890 -2 Q 886 16 864 16 L 28 16 Z",
                    color, "#172230", 13)
            + sk.path("M 331 -161 L 411 -244 L 487 -244 L 487 -161 Z",
                      "#15283c", "#a6c5db", 5)
            + sk.path("M 504 -244 L 625 -244 L 707 -161 L 504 -161 Z",
                      "#19324a", "#a6c5db", 5)
            + sk.path("M 510 -234 L 619 -234 L 689 -171 L 510 -171 Z",
                      "#284b68", op=0.52)
            + sk.rect(60, -127, 245, 18, "#91a2b5", 8, op=0.72)
            + sk.rect(60, -101, 220, 8, "#202e40", 4, op=0.7)
            + sk.circ(185, 5, 59, "#111820", "#667386", 10)
            + sk.circ(185, 5, 28, "#738195", "#182332", 7)
            + sk.circ(733, 5, 59, "#111820", "#667386", 10)
            + sk.circ(733, 5, 28, "#738195", "#182332", 7)
            + sk.ell(867, -90, 18, 12, "#ffda8a", op=0.95)
        )
        if broken:
            body += sk.path("M 698 -145 L 770 -294 L 844 -275 L 771 -131 Z",
                            "#7b8a9b", "#172230", 10)
            body += sk.path("M 697 -147 L 771 -294", "none", "#d5e0eb", 5)
        return sk.g(f"translate({n(x)} {n(y)}) scale({n(scale)})", body)

    if beat == "breakdown":
        out.append(sk.rect(0, 970, W, 640, "#05080f", op=0.15))
        out.append(sk.ell(520, 1508, 470, 42, "#02050a", op=0.58))
        # large, readable car foreground and driver visible through the side window
        out.append(car_body(72, 1515, 1.05, "#596b80", broken=True))
        out.append('<defs><clipPath id="zmb-break-window" clipPathUnits="userSpaceOnUse">'
                   '<path d="M 420 1351 L 505 1265 L 584 1265 L 584 1350 Z '
                   'M 597 1265 L 720 1265 L 797 1350 L 597 1350 Z"/></clipPath></defs>')
        out.append(sk.g("translate(505 1410)",
                        ch.render_actor("max", "sit", t, size=315),
                        op=0.98))
        # mask the driver to the side windows, then redraw window frames
        out[-1] = '<g clip-path="url(#zmb-break-window)">' + out[-1] + '</g>'
        out.append(sk.path("M 420 1351 L 505 1265 L 584 1265 L 584 1350 M 597 1265 L 720 1265 L 797 1350 L 597 1350",
                           "none", "#182739", 9))
        out.append(puffs(785, 1215, 8, 42, 88))
        out.append(sk.path("M 788 1257 L 852 1172 L 912 1188", "none", "#a9b7c5", 11))
        out.append(sk.ell(880, 1317, 105, 28, "#ffbd63", op=0.075))
        out.append(sk.text(540, 1075, "ENGINE FAILURE", 27, "Barlow", "#ffd58d",
                           anchor="middle", weight="bold", ls=3, op=0.92))
        out.append(sk.text(540, 1115, "2:47 AM  ·  NO SIGNAL", 23, "Barlow", "#e4ebf4",
                           anchor="middle", weight="bold", ls=2, op=0.82))

    elif beat == "car_interior":
        # Opaque front-seat view: windshield, road disappearing into the night,
        # Max and Biscuit inside, dashboard in the foreground.
        out.append(sk.rect(0, 0, W, H, "#07101d"))
        out.append(sk.rect(58, 110, 964, 1340, "#0a1424", 60))
        out.append(sk.path("M 104 1120 L 170 450 Q 182 330 300 280 L 780 280 "
                           "Q 900 335 911 450 L 976 1120 Z",
                           "#101f31", "#657b91", 14))
        out.append(sk.rect(188, 365, 704, 740, "#0d1d31", 24))
        out.append(sk.circ(780, 530, 47, "#fff0c3", op=0.85))
        out.append(sk.ell(780, 530, 112, 100, "#f2c779", op=0.105))
        # distant road, lane markings, and the one still-lit station
        out.append(sk.path("M 236 1100 L 450 820 L 630 820 L 845 1100 Z", "#202c3c"))
        out.append(sk.path("M 535 1090 L 535 970 M 535 920 L 535 872",
                           "none", "#d9d5c5", 9, op=0.72))
        out.append(sk.rect(650, 700, 160, 12, "#f6d99a", 7, op=0.95))
        out.append(sk.rect(665, 712, 9, 96, "#b1a28a", 5))
        out.append(sk.rect(785, 712, 9, 96, "#b1a28a", 5))
        out.append(sk.rect(687, 744, 32, 29, "#ffe7b0", op=0.92))
        out.append(sk.rect(733, 744, 32, 29, "#ffe7b0", op=0.76))
        # seat backs and passengers, held inside the cabin silhouette
        out.append(sk.path("M 112 1290 L 112 1100 Q 112 1040 176 1025 L 255 1060 L 255 1455 L 112 1455 Z",
                           "#172536", "#30445a", 13))
        out.append(sk.path("M 824 1290 L 824 1100 Q 824 1040 887 1025 L 960 1060 L 960 1455 L 824 1455 Z",
                           "#172536", "#30445a", 13))
        out.append(sk.g("translate(425 1492)", ch.render_actor("max", "sit", t, size=370)))
        out.append(sk.g("translate(692 1454)", ch.render_actor("biscuit", "scared", t + 0.35, size=510)))
        # dashboard and steering wheel are layered in front of the occupants
        out.append(sk.path("M 74 1385 Q 200 1335 328 1386 L 430 1510 L 74 1574 Z",
                           "#182535", "#3d5268", 13))
        out.append(sk.path("M 655 1380 Q 836 1328 1006 1390 L 1006 1580 L 642 1515 Z",
                           "#182535", "#3d5268", 13))
        out.append(sk.ell(334, 1436, 80, 82, "none", stroke="#9bafc2", sw=13, op=0.92))
        out.append(sk.ell(334, 1436, 12, 12, "#9bafc2", op=0.92))
        out.append(sk.path("M 335 1436 L 278 1495 M 335 1436 L 390 1492",
                           "none", "#9bafc2", 10))
        out.append(sk.path("M 0 1580 Q 190 1485 360 1532 Q 550 1586 730 1525 Q 905 1485 1080 1573 L 1080 1920 L 0 1920 Z",
                           "#101722", "#26384b", 14))
        out.append(sk.rect(450, 1584, 180, 16, "#263a4d", 8))
        out.append(sk.text(540, 1700, "STALLED  ·  2:47 AM", 27, "Barlow", "#ffd58d",
                           anchor="middle", weight="bold", ls=2, op=0.95))

    elif beat in ("spot_station", "door_shadow"):
        # The illuminated destination now takes over the composition.
        out.append(car_body(28, 1570, 0.62, "#42546a", broken=False))
        out.append(puffs(515, 1455, 4, 24, 38))
        out.append(sk.ell(820, 1000, 260, 210, "#ffca76", op=0.065))
        out.append(sk.path("M 640 770 L 1040 770", "none", "#ffdf9e", 9, op=0.85))
        out.append(sk.text(839, 730, "OPEN 24 HOURS", 29, "Barlow", "#ffe7b1",
                           anchor="middle", weight="bold", ls=2, op=0.94))
        if beat == "door_shadow":
            # The shadow moves behind the lit shop door rather than remaining a vague glow.
            sx = 812.0 + math.sin(t * 1.65) * 24.0
            shadow_op = 0.78 + 0.12 * math.sin(t * 2.4)
            out.append(sk.rect(738, 894, 168, 270, "#101b28", 9,
                               stroke="#cbb184", sw=7, op=0.84))
            out.append(sk.rect(752, 909, 140, 242, "#192637", 5, op=0.96))
            out.append(sk.ell(sx, 972, 31, 39, "#05090f", op=shadow_op))
            out.append(sk.path(
                f"M {n(sx - 26)} 1008 Q {n(sx)} 991 {n(sx + 26)} 1008 "
                f"L {n(sx + 45)} 1138 L {n(sx - 43)} 1138 Z",
                "#05090f", op=shadow_op))
            out.append(sk.path(
                f"M {n(sx - 16)} 1026 L {n(sx - 57)} 1070 "
                f"M {n(sx + 16)} 1026 L {n(sx + 55)} 1061",
                "none", "#05090f", 18, op=shadow_op))
            out.append(sk.circ(sx - 10, 969, 4, "#f7b96d", op=0.75 + 0.15 * math.sin(t * 3.0)))
            out.append(sk.circ(sx + 10, 969, 4, "#f7b96d", op=0.75 + 0.15 * math.sin(t * 3.0 + 0.4)))

    elif beat == "backpack_exit":
        # A visible, strapped pack placed against Max's upper back + parked car.
        out.append(car_body(6, 1580, 0.52, "#344456", broken=False))
        out.append(sk.ell(245, 1420, 210, 28, "#02050a", op=0.46))
        out.append(sk.g("translate(0 0)",
            sk.path("M 342 1028 Q 354 1004 389 1008 L 431 1030 L 429 1154 "
                    "Q 392 1172 356 1152 Z",
                    "#7b3f2b", "#f0c28c", 8)
            + sk.path("M 355 1048 Q 378 1032 410 1049 L 412 1092 L 357 1092 Z",
                      "#b6683d", "#3f251d", 6)
            + sk.rect(374, 1096, 30, 28, "#dba766", 6, op=0.95)
            + sk.path("M 349 1020 Q 367 1005 388 1032 M 421 1028 Q 435 1050 426 1073",
                      "none", "#dca878", 9)))

    elif beat == "choice_teaser":
        # Explicit choice teaser while the station remains in the background.
        out.append(sk.rect(86, 1110, 908, 330, "#07101de8", 28,
                           stroke="#e4c778", sw=3, op=0.96))
        out.append(sk.text(540, 1170, "YOUR FIRST DECISION", 31, "Barlow", "#f5d88b",
                           anchor="middle", weight="bold", ls=3))
        pulse = 0.78 + 0.12 * math.sin(t * 2.1)
        out.append(sk.rect(125, 1212, 390, 138, "#1a2f43", 22,
                           stroke="#79b8e8", sw=4, op=pulse))
        out.append(sk.rect(565, 1212, 390, 138, "#30251d", 22,
                           stroke="#e8a45e", sw=4, op=pulse))
        out.append(sk.text(320, 1278, "RUN", 58, "Archivo Black", "#edf6ff",
                           anchor="middle", weight="bold", ls=2))
        out.append(sk.text(320, 1322, "GET OUT FAST", 21, "Barlow", "#a9d6ff",
                           anchor="middle", weight="bold", ls=2))
        out.append(sk.text(760, 1278, "CHECK", 58, "Archivo Black", "#fff0df",
                           anchor="middle", weight="bold", ls=2))
        out.append(sk.text(760, 1322, "OPEN THE DOOR", 21, "Barlow", "#ffd09b",
                           anchor="middle", weight="bold", ls=2))
        out.append(sk.text(540, 1408, "COMMENT ON TOMORROW'S REEL", 22, "Barlow",
                           "#e6edf7", anchor="middle", weight="bold", ls=1.5))
    return "".join(out)


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

def chunk_words(words, Texts, size, max_w=930.0, max_words=7):
    """words: [{w,start,end}] -> sentence-safe karaoke chunks."""
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

        # Keep each caption chunk inside the sentence; do not join a question
        # to the follow/subscribe CTA that follows it.
        token = wd["w"]
        while token and token[-1] in ('"', "”", "’", ")", "]", "}"):
            token = token[:-1]
        if token.endswith((".", "!", "?")):
            if cur:
                chunks.append(cur)
                cur = []
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


def caption_layer(chunks, t, Texts, size=54.0, max_w=930.0):
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
        if cur and wid > max_w:
            lines.append(cur)
            cur = [wd]
        else:
            cur = trial
    if cur:
        lines.append(cur)
    out = [rect(0, 1435, W, H - 1435, "url(#cap_scrim)")]
    # Keep subtitles above the bottom safe area; anchor the last line consistently.
    base_y = 1590 - (len(lines) - 1) * 70
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
                            weight="bold", stroke="#05070c", sw=11, op=op))
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
    # The two car-centric shots have their own composition/passengers; all other
    # story beats keep the normal character rig and scene parallax.
    beat = meta.get("beat") if shot.kind == "line" else None
    if beat not in ("breakdown", "car_interior"):
        body.append(actors_layer(meta, t, fx, cache))

    ov = []  # screen space
    if shot.kind == "line" and beat:
        ov.append(narrative_beat_layer(meta, local))
    if shot.kind == "line":
        ov.append(fx_layer(meta.get("fx", "none"), local, shot.dur, t_abs=t))
    elif shot.kind == "vote":
        ov.append(fx_layer("fog", t, shot.dur))
    if shot.kind == "line":
        chunks = cache.setdefault(("chunks", id(shot)), None)
        if chunks is None:
            size = float(cfg.get("render", cfg).get("caption_size", 52))
            render_cfg = cfg.get("render", cfg)
            chunks = chunk_words(
                shot.words, Texts, size,
                max_w=float(render_cfg.get("caption_max_width", 930)),
                max_words=int(render_cfg.get("caption_max_words", 6)),
            ) if shot.words else _fake_words(shot, Texts, size)
            cache[("chunks", id(shot))] = chunks
        render_cfg = cfg.get("render", cfg)
        ov.append(caption_layer(
            chunks, local, Texts,
            float(render_cfg.get("caption_size", 54)),
            float(render_cfg.get("caption_max_width", 930)),
        ))
    if shot.kind != "title":
        ov.append(hud_layer(ep.get("stats", {}), ep.get("stats_labels", {}),
                            dict(meta, subtitle=ep.get("subtitle", "")), t, ep))
    if shot.kind == "title":
        ov.append(title_card(ep, local, shot.dur, Texts))
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
