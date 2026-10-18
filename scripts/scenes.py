"""Scene library: har jagah (place) ke liye layered vector background.

Scene builder `(defs, layers)` return karta hai:
  layers = [(parallax_k, svg_content_in_world_coords), ...]  far -> near
  k = 0   -> camera ke saath bilkul nahi hilta (sky)
  k = 1   -> camera ke saath poora hilta hai (foreground)

Staging guide (design space 1080 x 1920):
  HORIZON = 1180   G_FAR = 1250   G_MID = 1360 (characters ke pair)   G_NEAR = 1520
"""
from __future__ import annotations

import math
import random

from svgkit import circ, ell, esc, g, limb, line, lin_grad, mix, n, path, rad_grad, rect, shade, text

WORLD_X0 = -560.0
WORLD_W = 2200.0
GROUND = 1360.0
HORIZON = 1180.0
G_FAR = 1250.0
G_NEAR = 1520.0

TIME = {
    "night": dict(
        sky=[(0, "#060a16", 1), (40, "#101731", 1), (72, "#232c4b", 1), (100, "#3a3350", 1)],
        ground="#0b1020", far="#131a30", mid="#19203c", near="#0e1428",
        glowc="#ffd98a", warm="#ffbf5e", stars=1, celestial="moon"),
    "dusk": dict(
        sky=[(0, "#171b38", 1), (38, "#3a3355", 1), (68, "#8a4b5a", 1), (100, "#e08a52", 1)],
        ground="#16162c", far="#222244", mid="#2a2a52", near="#191a34",
        glowc="#ffc078", warm="#ff9a4a", stars=0, celestial="sun"),
    "dawn": dict(
        sky=[(0, "#101c3d", 1), (38, "#37456e", 1), (68, "#bb7a6b", 1), (100, "#f0c98a", 1)],
        ground="#19203a", far="#242b4c", mid="#2c3358", near="#1b2240",
        glowc="#ffd9a0", warm="#ffb86a", stars=0, celestial="sun"),
    "day": dict(
        sky=[(0, "#46597a", 1), (42, "#6d829c", 1), (78, "#9cadbb", 1), (100, "#c6c1ac", 1)],
        ground="#2a3226", far="#39432f", mid="#434d36", near="#2a3226",
        glowc="#fff3cf", warm="#ffe0a0", stars=0, celestial="none"),
}

MOOD = {
    "calm": dict(tint="#1d3a5c", ta=0.10, dark=0.0),
    "tense": dict(tint="#123048", ta=0.16, dark=0.06),
    "danger": dict(tint="#4a1020", ta=0.20, dark=0.16),
    "hope": dict(tint="#5c3a12", ta=0.10, dark=0.0),
}
DEFAULT_MOOD = MOOD["calm"]


# ---------------------------------------------------------------- helpers ----

def glow_def(gid, color, power=0.95):
    return rad_grad(gid, [
        (0, color, power), (34, color, power * 0.44), (66, color, power * 0.14),
        (100, color, 0.0),
    ])


def sky_grad(gid, tname, mood="calm"):
    m = MOOD.get(mood, DEFAULT_MOOD)
    stops = []
    for o, c, op in TIME[tname]["sky"]:
        c = mix(c, "#2a0f14", m["dark"] * 0.5)
        stops.append((o, c, op))
    return lin_grad(gid, stops)


def poly(pts, fill, op=None):
    d = "M " + " L ".join(f"{n(p[0])} {n(p[1])}" for p in pts) + " Z"
    return path(d, fill, op=op)


def pine(x, y, h, color):
    s = ""
    for i in range(3):
        w = h * (0.40 - i * 0.085)
        yy = y - h * (0.20 + i * 0.235)
        s += poly([(x - w, yy), (x, yy - h * 0.44), (x + w, yy)], color)
    s += rect(x - h * 0.028, y - h * 0.03, h * 0.056, h * 0.07, shade(color, -0.25))
    return s


def bush(x, y, s, color):
    return (
        ell(x, y - s * 0.42, s * 0.52, s * 0.44, color)
        + ell(x - s * 0.4, y - s * 0.3, s * 0.34, s * 0.3, shade(color, -0.12))
        + ell(x + s * 0.38, y - s * 0.34, s * 0.36, s * 0.32, shade(color, 0.08))
    )


def window_grid(x, y, w, h, cols, rows, color, lit=None, seed=1, ratio=0.35, gap=0.34):
    rnd = random.Random(seed)
    cw, ch = w / cols, h / rows
    s = ""
    for c in range(cols):
        for r in range(rows):
            on = rnd.random() < ratio
            if on and lit:
                s += rect(x + c * cw + cw * gap / 2, y + r * ch + ch * gap / 2,
                          cw * (1 - gap), ch * (1 - gap), lit)
            elif not on:
                s += rect(x + c * cw + cw * gap / 2, y + r * ch + ch * gap / 2,
                          cw * (1 - gap), ch * (1 - gap), color)
    return s


def stars(seed, count, ymax):
    rnd = random.Random(seed)
    s = ""
    for _ in range(count):
        x = rnd.uniform(WORLD_X0, WORLD_X0 + WORLD_W)
        y = rnd.uniform(0, ymax)
        r = rnd.choice([1.6, 2.0, 2.6, 3.2])
        op = rnd.uniform(0.3, 0.95)
        s += circ(x, y, r, "#fdf6dd", op=round(op, 2))
    return s


def grass_tufts(seed, x0, x1, y0, y1, count, color, scale=1.0):
    rnd = random.Random(seed)
    s = ""
    for _ in range(count):
        x = rnd.uniform(x0, x1)
        y = rnd.uniform(y0, y1)
        hh = rnd.uniform(10, 26) * scale
        s += path(f"M {n(x)} {n(y)} q {-hh * 0.3} {-hh * 0.6} {-hh * 0.5} {-hh}",
                  "none", color, 2.4 * scale)
        s += path(f"M {n(x)} {n(y)} q {hh * 0.2} {-hh * 0.7} {hh * 0.5} {-hh * 0.9}",
                  "none", color, 2.2 * scale)
    return s


def car(x, y, s, color, flip=False, op=None, lit=None):
    """Simple side-view car. (x,y) = front-bottom. s = width."""
    h = s * 0.42
    body = poly([(0, 0), (s * 0.06, -h * 0.72), (s * 0.34, -h * 0.78),
                 (s * 0.56, -h * 1.42), (s * 0.86, -h * 1.42), (s, -h * 0.72), (s, 0)], color)
    win = poly([(s * 0.60, -h * 1.34), (s * 0.82, -h * 1.34), (s * 0.92, -h * 0.82), (s * 0.52, -h * 0.82)],
               "#131a2b", op=0.9)
    out = body + win
    for cx in (s * 0.24, s * 0.78):
        out += circ(cx, 0, h * 0.34, "#14161c")
        out += circ(cx, 0, h * 0.15, "#3a3f4a")
    if lit:
        out += circ(s, -h * 0.66, h * 0.5, lit, op=0.5)
    if flip:
        return g(f"translate({n(x * 2)} 0) scale(-1 1)", out)
    return g(f"translate({n(x)} {n(y)})", out)


def pole(x, y, h, color, arm=None, lamp=None):
    s = rect(x - h * 0.012, y - h, h * 0.024, h, color)
    if arm is not None:
        s += rect(x, y - h, h * 0.3 * (1 if arm > 0 else -1), h * 0.016, color)
    if lamp:
        s += rect(x + h * 0.26 - h * 0.02, y - h - h * 0.01, h * 0.09, h * 0.02, shade(color, -0.3))
    return s


def interior_floor(y, color, top=None):
    return rect(WORLD_X0, y, WORLD_W, 1920 - y, color) + (
        rect(WORLD_X0, y, WORLD_W, 8, top) if top else "")


# ------------------------------------------------------------------ SCENES ---

def highway(tname, mood="calm", seed=1):
    T = TIME[tname]
    defs = sky_grad("hw_sky", tname, mood) + glow_def("hw_glow", T["glowc"]) + glow_def("hw_warm", T["warm"])
    L = []
    sky = rect(WORLD_X0, 0, WORLD_W, HORIZON + 90, "url(#hw_sky)")
    if T["stars"]:
        sky += stars(seed, 130, 900)
    if T["celestial"] == "moon":
        sky += circ(880, 320, 74, "#f7f1d8", op=0.95) + circ(906, 300, 66, "#0e1530", op=0.55)
        sky += circ(880, 320, 210, "url(#hw_glow)", op=0.55)
    elif T["celestial"] == "sun":
        sky += circ(830, 1020, 92, T["warm"], op=0.9) + circ(830, 1020, 320, "url(#hw_warm)", op=0.75)
    L.append((0.10, sky))

    far = poly([(WORLD_X0, HORIZON + 60), (WORLD_X0 + 300, HORIZON - 96), (WORLD_X0 + 620, HORIZON + 30),
                (WORLD_X0 + 980, HORIZON - 120), (WORLD_X0 + 1360, HORIZON + 40),
                (WORLD_X0 + 1720, HORIZON - 70), (WORLD_X0 + WORLD_W, HORIZON + 20),
                (WORLD_X0 + WORLD_W, HORIZON + 200), (WORLD_X0, HORIZON + 200)], T["far"])
    rnd = random.Random(seed + 3)
    for i in range(26):
        x = WORLD_X0 + 40 + i * 84 + rnd.uniform(-20, 20)
        far += pine(x, HORIZON + 46, rnd.uniform(60, 128), T["far"])
    far += rect(WORLD_X0, HORIZON + 40, WORLD_W, 200, T["far"])
    # kahani ka landmark: us door ki roshni wali gas station jo Max dekhta hai
    gsx = 812.0
    far += rect(gsx, HORIZON - 44, 196, 13, shade(T["far"], 0.28))       # canopy
    far += rect(gsx - 4, HORIZON - 31, 204, 8, shade(T["far"], -0.1))
    for px in (gsx + 22, gsx + 162):
        far += rect(px, HORIZON - 23, 8, 66, shade(T["far"], -0.30))     # pillars
    far += rect(gsx + 232, HORIZON - 14, 122, 82, shade(T["far"], -0.22)) # store
    far += rect(gsx + 244, HORIZON - 2, 40, 26, "#ffd98a", op=0.85)       # lit window
    far += rect(gsx + 292, HORIZON - 2, 40, 26, "#ffd98a", op=0.6)
    far += rect(gsx + 206, HORIZON - 52, 10, 120, shade(T["far"], -0.3))  # sign pole
    far += rect(gsx + 196, HORIZON - 66, 30, 44, mix(T["glowc"], "#ffffff", 0.25), op=0.75)
    far += circ(gsx + 98, HORIZON + 44, 118, "url(#hw_warm)", op=0.42)    # warm glow
    L.append((0.28, far))

    mid = ""
    rnd = random.Random(seed + 7)
    for i in range(13):
        x = WORLD_X0 + 90 + i * 176 + rnd.uniform(-30, 30)
        mid += pole(x, GROUND + 40, 300, shade(T["mid"], -0.35), arm=1)
        mid += line(x, GROUND + 40 - 292, x + 150, GROUND + 40 - 306, shade(T["mid"], -0.5), 3)
    for cd in ((210, 1), (1160, 0), (1860, 1)):
        mid += car(cd[0], GROUND + 66, 150, shade(T["mid"], -0.15), flip=bool(cd[1]))
    L.append((0.58, mid))

    road = rect(WORLD_X0, GROUND - 4, WORLD_W, 108, T["near"])
    road += rect(WORLD_X0, GROUND - 10, WORLD_W, 8, shade(T["near"], 0.22))
    for i in range(28):
        road += rect(WORLD_X0 + 20 + i * 80, GROUND + 44, 44, 7, "#d9d2b4", op=0.55)
    road += rect(WORLD_X0, GROUND + 104, WORLD_W, 12, shade(T["near"], -0.35))
    road += rect(WORLD_X0, GROUND + 116, WORLD_W, 1920 - (GROUND + 116), shade(T["near"], -0.5))
    # Max ki gaadi — kahani yahi shuru hoti hai; actors ke bagal mein parked:
    hero = car(40, GROUND + 4, 240, "#8b97a6")
    hero += line(227, 1218, 268, 1148, "#3d434c", 9)       # khula bonnet
    hero += ell(300, 1172, 62, 22, "#aeb8c2", op=0.30)     # engine smoke
    hero += ell(366, 1120, 88, 28, "#aeb8c2", op=0.22)
    hero += ell(448, 1064, 116, 34, "#aeb8c2", op=0.15)
    road += hero
    road += grass_tufts(seed + 11, WORLD_X0, WORLD_X0 + WORLD_W, GROUND + 130, 1760, 90,
                        shade(T["ground"], 0.1), 1.5)
    L.append((0.86, road))

    fg = rect(WORLD_X0, 1760, WORLD_W, 160, shade(T["near"], -0.72))
    rnd = random.Random(seed + 13)
    for i in range(16):
        fg += pine(WORLD_X0 + i * 148 + rnd.uniform(-30, 30), 1900, rnd.uniform(110, 190),
                   shade(T["near"], -0.62))
    L.append((1.0, fg))
    return defs, L


def gas_station(tname, mood="calm", seed=2):
    T = TIME[tname]
    defs = (sky_grad("gs_sky", tname, mood) + glow_def("gs_glow", T["glowc"])
            + glow_def("gs_warm", T["warm"], 0.85) + glow_def("gs_neon", "#7dffd0", 0.8))
    L = []
    sky = rect(WORLD_X0, 0, WORLD_W, HORIZON + 120, "url(#gs_sky)")
    if T["stars"]:
        sky += stars(seed, 110, 860)
    sky += circ(300, 300, 62, "#f7f1d8", op=0.92) + circ(324, 282, 56, "#0c1228", op=0.5)
    sky += rect(WORLD_X0, HORIZON + 40, WORLD_W, 220, T["far"])
    rnd = random.Random(seed + 2)
    for i in range(20):
        sky += pine(WORLD_X0 + i * 116, HORIZON + 90, rnd.uniform(70, 140), shade(T["far"], -0.15))
    L.append((0.12, sky))

    bld = rect(1160, 860, 400, 500, T["mid"])
    bld += rect(1160, 840, 400, 26, shade(T["mid"], 0.16))
    bld += window_grid(1200, 900, 320, 130, 4, 1, shade(T["mid"], -0.3), "#ffe9b0", seed + 4, 0.75)
    bld += rect(1200, 1060, 130, 300, shade(T["mid"], -0.5))
    bld += rect(1216, 1076, 98, 260, mix(T["glowc"], "#ffffff", 0.2), op=0.85)
    for i in range(7):
        bld += line(1216, 1090 + i * 36, 1314, 1090 + i * 36, shade(T["mid"], -0.2), 5)
    bld += circ(1265, 1210, 190, "url(#gs_glow)", op=0.6)
    bld += rect(1360, 1150, 190, 210, shade(T["mid"], -0.25))
    bld += window_grid(1380, 1180, 150, 90, 3, 1, shade(T["mid"], -0.4), "#ffe9b0", seed + 6, 0.6)
    L.append((0.34, bld))

    canopy = (rect(300, 700, 700, 54, shade(T["mid"], 0.1))
              + rect(330, 754, 640, 16, shade(T["mid"], -0.3))
              + rect(360, 754, 260, 520, shade(T["mid"], -0.42))
              + rect(620, 754, 260, 520, shade(T["mid"], -0.42))
              + rect(340, 700, 620, 44, "#d8dce4", op=0.13))
    for lx in (430, 550, 670, 790, 910):
        canopy += rect(lx - 46, 706, 92, 18, mix(T["glowc"], "#ffffff", 0.45))
        canopy += circ(lx, 745, 145, "url(#gs_glow)", op=0.55)
    canopy += rect(350, 1240, 330, 40, shade(T["mid"], -0.5))
    for i in range(3):
        canopy += rect(380 + i * 110, 1150, 70, 90, shade(T["mid"], -0.1))
        canopy += rect(388 + i * 110, 1160, 54, 40, "#151a24")
    canopy += rect(1030, 1120, 96, 240, shade(T["mid"], -0.12))
    canopy += rect(1042, 1140, 72, 60, mix(T["glowc"], "#55ffcc", 0.35), op=0.85)
    canopy += circ(1078, 1210, 120, "url(#gs_neon)", op=0.5)
    L.append((0.60, canopy))

    ground = rect(WORLD_X0, GROUND + 120, WORLD_W, 300, T["near"])
    ground += rect(WORLD_X0, GROUND + 120, WORLD_W, 10, shade(T["near"], 0.25))
    for i in range(24):
        ground += rect(WORLD_X0 + i * 94, GROUND + 150, 8, 118, "#c9c9b8", op=0.22)
    ground += rect(300, GROUND + 150, 700, 250, "#20242e", op=0.5)
    ground += car(WORLD_X0 + 120, GROUND + 200, 160, shade(T["mid"], -0.28))
    ground += car(WORLD_X0 + 1700, GROUND + 190, 150, shade(T["mid"], -0.22), flip=True)
    L.append((0.86, ground))

    fg = rect(WORLD_X0, 1780, WORLD_W, 140, shade(T["near"], -0.6))
    fg += bush(WORLD_X0 + 180, 1840, 130, shade(T["near"], -0.5))
    fg += bush(WORLD_X0 + 1820, 1850, 150, shade(T["near"], -0.5))
    L.append((1.0, fg))
    return defs, L


def store(tname, mood="calm", seed=3):
    T = TIME[tname]
    defs = (sky_grad("st_sky", tname, mood) + glow_def("st_glow", T["glowc"], 0.7)
            + glow_def("st_tube", "#eaf6ff", 0.65) + glow_def("st_warn", "#ff9a52", 0.8))
    wall = "#2a2f3d"
    L = []
    back = rect(WORLD_X0, 0, WORLD_W, 1920, wall)
    back += rect(WORLD_X0, 0, WORLD_W, 420, shade(wall, -0.25))
    for i in range(9):
        back += rect(WORLD_X0 + i * 246, 420, 12, 760, shade(wall, -0.18))
    # STAFF ONLY door + sign
    door = rect(700, 700, 240, 480, shade(wall, -0.42), 6)
    door += rect(716, 716, 208, 200, "#161b26")
    door += circ(900, 950, 16, "#c8cbd2")
    door += rect(660, 640, 320, 62, "#3a2a20", 6)
    door += text(820, 686, "STAFF ONLY", 40, "Barlow", "#ffd27a", weight="bold", ls=2)
    door += circ(820, 810, 300, "url(#st_warn)", op=0.28)
    back += door
    L.append((0.32, back))
    # shelving rows
    rnd = random.Random(seed + 5)
    for row, (sy, sw, sc) in enumerate([(1180, 1080, 1.0), (1420, 1240, 1.15), (1680, 1400, 1.3)]):
        sh = rect(60, sy, sw, 22, "#3a4152")
        sh += rect(60, sy - 150, sw, 14, "#3a4152")
        sh += rect(60, sy + 22, sw, 130, shade(wall, -0.3))
        for i in range(int(sw / 62)):
            cx = 80 + i * 62
            col = rnd.choice(["#c9553f", "#4f8f6a", "#d9a13f", "#4f6f9f", "#a05aa8", "#d9d2b4"])
            sh += rect(cx, sy - 138, 40, 60, col, 4)
            if rnd.random() < 0.5:
                sh += rect(cx, sy - 74, 40, 48, rnd.choice(["#7a6a4f", "#5f7a4f"]), 4)
        L.append((0.55 + row * 0.15, sh))
    ceiling = ""
    for i in range(4):
        lx = 180 + i * 300
        ceiling += rect(lx - 90, 250, 180, 26, "#e9f4ff", 8)
        ceiling += rect(lx - 90, 276, 180, 10, "#8fa4b8")
        ceiling += circ(lx, 300, 165, "url(#st_tube)", op=0.16)
    L.insert(0, (0.3, ceiling))
    L.append((0.9, rect(WORLD_X0, 1900, WORLD_W, 20, "#151922")))
    return defs, L


def motel_lot(tname, mood="calm", seed=4):
    T = TIME[tname]
    defs = (sky_grad("ml_sky", tname, mood) + glow_def("ml_glow", T["glowc"], 0.85)
            + glow_def("ml_neon", "#ff5f8a", 0.9))
    L = []
    sky = rect(WORLD_X0, 0, WORLD_W, HORIZON + 80, "url(#ml_sky)")
    if T["stars"]:
        sky += stars(seed, 120, 840)
    sky += circ(1180, 300, 66, "#f7f1d8", op=0.9) + circ(1204, 282, 58, "#101632", op=0.5)
    sky += circ(1180, 300, 200, "url(#ml_glow)", op=0.45)
    sky += rect(WORLD_X0, HORIZON + 30, WORLD_W, 240, T["far"])
    rnd = random.Random(seed + 3)
    for i in range(18):
        sky += pine(WORLD_X0 + 60 + i * 128, HORIZON + 80, rnd.uniform(60, 132), shade(T["far"], -0.12))
    L.append((0.12, sky))

    bld = rect(180, 940, 1240, 420, T["mid"])
    bld += poly([(160, 940), (700, 820), (1440, 940)], shade(T["mid"], -0.35))
    for i in range(9):
        dx = 240 + i * 132
        bld += rect(dx, 1100, 104, 260, shade(T["mid"], -0.45), 4)
        bld += circ(dx + 92, 1230, 9, "#cfd4dc")
        if i in (2, 6):
            bld += rect(dx + 12, 1112, 80, 74, "#ffd98a", op=0.35)
    bld += window_grid(240, 990, 1160, 80, 9, 1, shade(T["mid"], -0.3), "#ffe9b0", seed + 5, 0.4)
    L.append((0.36, bld))

    sign = rect(1610, 900, 26, 460, shade(T["mid"], -0.3))
    sign += rect(1490, 700, 270, 210, shade(T["mid"], -0.12), 10)
    sign += text(1625, 780, "MOTEL", 62, "Archivo Black", "#ff8fb0")
    sign += text(1625, 846, "VACANCY", 40, "Barlow", "#7dffd0", weight="bold", ls=3)
    sign += circ(1625, 800, 320, "url(#ml_neon)", op=0.4)
    sign += rect(1380, 1180, 120, 180, shade(T["mid"], -0.4))
    sign += rect(1420, 1360, 40, 30, shade(T["mid"], -0.5))
    L.append((0.62, sign))

    ground = rect(WORLD_X0, GROUND + 60, WORLD_W, 360, T["near"])
    ground += rect(WORLD_X0, GROUND + 60, WORLD_W, 10, shade(T["near"], 0.22))
    for i in range(20):
        ground += rect(WORLD_X0 + 40 + i * 114, GROUND + 96, 60, 8, "#c9c9b8", op=0.2)
    ground += car(WORLD_X0 + 210, GROUND + 190, 210, shade(T["mid"], -0.3))
    ground += rect(1500, GROUND + 30, 150, 170, shade(T["mid"], -0.22), 6)
    ground += rect(1516, GROUND + 46, 118, 70, "#8fa4b8", op=0.5)
    ground += circ(1575, GROUND + 60, 90, "url(#ml_glow)", op=0.3)
    L.append((0.86, ground))

    fg = rect(WORLD_X0, 1786, WORLD_W, 134, shade(T["near"], -0.62))
    fg += line(WORLD_X0 + 190, GROUND + 60, WORLD_X0 + 190, GROUND - 260, shade(T["near"], -0.5), 8)
    fg += line(WORLD_X0 + 190, GROUND - 260, WORLD_X0 + 700, GROUND - 190, shade(T["near"], -0.5), 8)
    L.append((1.0, fg))
    return defs, L


def motel_hall(tname, mood="calm", seed=5):
    T = TIME[tname]
    defs = (sky_grad("mh_sky", tname, mood) + glow_def("mh_lamp", "#ffd9a0", 0.6)
            + glow_def("mh_cool", "#8fc8ff", 0.45))
    wall = "#2b2c3c"
    floor = "#241f2c"
    L = []
    back = rect(WORLD_X0, 0, WORLD_W, 1300, wall)
    back += rect(WORLD_X0, 0, WORLD_W, 210, shade(wall, -0.3))
    back += rect(WORLD_X0, 1290, WORLD_W, 630, floor)
    back += rect(WORLD_X0, 1290, WORLD_W, 16, shade(floor, 0.22))
    for i in range(10):
        back += line(WORLD_X0 + i * 240, 1300, WORLD_X0 + i * 240, 1920, shade(floor, -0.25), 4)
    # window at the end
    back += rect(1780, 760, 260, 240, "#0d1428", 8)
    back += rect(1792, 772, 236, 216, "#1b2a4a")
    back += circ(1910, 880, 260, "url(#mh_cool)", op=0.35)
    for i in range(4):
        dx = 90 + i * 330
        back += rect(dx, 900, 170, 390, shade(wall, -0.34), 6)
        back += circ(dx + 148, 1100, 11, "#cfd4dc")
        back += rect(dx + 24, 930, 122, 60, shade(wall, -0.5))
    L.append((0.3, back))

    lamps = ""
    for i in range(5):
        lx = 200 + i * 300
        lamps += rect(lx - 26, 700, 52, 30, "#ffd9a0", 8)
        lamps += circ(lx, 700, 150, "url(#mh_lamp)", op=0.20)
    lamps += rect(150, 1180, 220, 40, shade(wall, 0.05), 6)
    lamps += rect(170, 1220, 180, 90, shade(wall, -0.4), 6)
    lamps += circ(260, 1265, 40, "#c9553f", 8, op=0.8)
    L.append((0.62, lamps))

    near = rect(WORLD_X0, 1560, WORLD_W, 360, shade(floor, 0.06))
    near += rect(WORLD_X0, 1560, WORLD_W, 12, shade(floor, 0.3))
    near += rect(300, 1380, 260, 210, shade(wall, -0.44), 8)
    near += rect(330, 1410, 200, 60, shade(wall, -0.28))
    near += rect(330, 1486, 200, 60, shade(wall, -0.28))
    L.append((0.88, near))
    return defs, L


def forest(tname, mood="calm", seed=6):
    T = TIME[tname]
    defs = (sky_grad("fo_sky", tname, mood) + glow_def("fo_glow", T["glowc"], 0.6)
            + glow_def("fo_beam", "#dff0ff", 0.35))
    L = []
    sky = rect(WORLD_X0, 0, WORLD_W, HORIZON + 120, "url(#fo_sky)")
    if T["stars"]:
        sky += stars(seed, 90, 780)
    sky += circ(560, 280, 56, "#f7f1d8", op=0.85) + circ(580, 264, 50, "#0d1531", op=0.5)
    sky += rect(WORLD_X0, HORIZON - 40, WORLD_W, 360, T["far"], op=0.85)
    rnd = random.Random(seed + 4)
    for i in range(30):
        sky += pine(WORLD_X0 + 30 + i * 76, HORIZON + 70, rnd.uniform(90, 180), shade(T["far"], -0.25))
    L.append((0.15, sky))

    mid = ""
    rnd = random.Random(seed + 8)
    for i in range(12):
        x = WORLD_X0 + 60 + i * 190 + rnd.uniform(-40, 40)
        mid += pine(x, GROUND + 40, rnd.uniform(320, 470), shade(T["mid"], -0.1))
    mid += rect(WORLD_X0, GROUND + 30, WORLD_W, 260, shade(T["mid"], -0.3))
    L.append((0.55, mid))

    road = rect(WORLD_X0, GROUND + 30, WORLD_W, 150, "#1a1c1c")
    road += rect(WORLD_X0, GROUND + 30, WORLD_W, 8, "#2b2e2e")
    for i in range(22):
        road += rect(WORLD_X0 + 40 + i * 100, GROUND + 96, 52, 6, "#b8b49a", op=0.35)
    road += bush(WORLD_X0 + 130, GROUND + 190, 150, shade(T["ground"], 0.05))
    road += bush(WORLD_X0 + 1900, GROUND + 175, 170, shade(T["ground"], 0.05))
    road += grass_tufts(seed + 12, WORLD_X0, WORLD_X0 + WORLD_W, GROUND + 180, 1820, 110,
                        shade(T["ground"], 0.12), 1.6)
    L.append((0.84, road))

    mist = ""
    for i in range(7):
        yy = 1150 + i * 130
        mist += ell(WORLD_X0 + 200 + i * 300, yy, 420, 62, "#cfe0ea", op=0.05)
    L.append((0.7, mist))

    fg = rect(WORLD_X0, 1800, WORLD_W, 120, "#080d08")
    rnd = random.Random(seed + 14)
    for i in range(14):
        fg += pine(WORLD_X0 + i * 168 + rnd.uniform(-30, 30), 1930, rnd.uniform(140, 230), "#0c130c")
    L.append((1.0, fg))
    return defs, L


def bridge(tname, mood="calm", seed=7):
    T = TIME[tname]
    defs = (sky_grad("br_sky", tname, mood) + glow_def("br_glow", T["glowc"], 0.7)
            + glow_def("br_alarm", "#ff5a4a", 0.85))
    L = []
    sky = rect(WORLD_X0, 0, WORLD_W, HORIZON + 60, "url(#br_sky)")
    if T["stars"]:
        sky += stars(seed, 100, 800)
    sky += circ(1320, 330, 60, "#f7f1d8", op=0.85) + circ(1342, 314, 54, "#101834", op=0.5)
    sky += rect(WORLD_X0, HORIZON + 10, WORLD_W, 300, T["far"])
    rnd = random.Random(seed + 6)
    for i in range(22):
        sky += pine(WORLD_X0 + 20 + i * 106, HORIZON + 60, rnd.uniform(70, 150), shade(T["far"], -0.2))
    L.append((0.12, sky))

    towers = ""
    for tx in (420, 1560):
        towers += rect(tx - 22, 520, 44, 640, shade(T["mid"], -0.3))
        towers += rect(tx - 60, 520, 120, 30, shade(T["mid"], -0.3))
        towers += line(tx, 560, tx, 200, shade(T["mid"], -0.35), 6)
    towers += line(420, 240, 1560, 240, shade(T["mid"], -0.4), 7)
    towers += line(420, 400, 1560, 400, shade(T["mid"], -0.4), 5)
    for i in range(14):
        towers += line(420 + i * 82, 240, 460 + i * 82, 460, shade(T["mid"], -0.45), 3)
    L.append((0.4, towers))

    deck = rect(WORLD_X0, GROUND, WORLD_W, 120, "#1d2128")
    deck += rect(WORLD_X0, GROUND - 8, WORLD_W, 10, "#33383f")
    deck += rect(WORLD_X0, GROUND - 120, WORLD_W, 14, shade(T["mid"], -0.2))
    for i in range(24):
        deck += rect(WORLD_X0 + i * 92, GROUND - 118, 10, 110, shade(T["mid"], -0.32))
    deck += line(WORLD_X0, GROUND - 104, WORLD_X0 + WORLD_W, GROUND - 104, "#6b7280", 10)
    L.append((0.62, deck))

    cars = ""
    rnd = random.Random(seed + 9)
    for i in range(7):
        cx = WORLD_X0 + 180 + i * 300 + rnd.uniform(-60, 60)
        cars += car(cx, GROUND + 40, 190, shade(T["near"], 0.1), flip=i % 2 == 1)
    cars += circ(760, 900, 300, "url(#br_alarm)", op=0.18)
    L.append((0.84, cars))

    water = rect(WORLD_X0, GROUND + 120, WORLD_W, 420, "#0d1424")
    for i in range(9):
        water += rect(WORLD_X0, GROUND + 170 + i * 42, WORLD_W, 5, "#2a3a58", op=0.5)
    fg = rect(WORLD_X0, 1840, WORLD_W, 80, "#080b14")
    L.append((0.95, water + fg))
    return defs, L


def tower(tname, mood="calm", seed=8):
    T = TIME[tname]
    defs = (sky_grad("tw_sky", tname, mood) + glow_def("tw_lamp", "#ffd98a", 0.85)
            + glow_def("tw_win", "#bfe4ff", 0.6))
    L = []
    sky = rect(WORLD_X0, 0, WORLD_W, HORIZON + 100, "url(#tw_sky)")
    if T["stars"]:
        sky += stars(seed, 110, 820)
    sky += circ(260, 260, 54, "#f7f1d8", op=0.8) + circ(280, 244, 48, "#101834", op=0.5)
    sky += rect(WORLD_X0, HORIZON + 20, WORLD_W, 300, T["far"])
    rnd = random.Random(seed + 5)
    for i in range(28):
        sky += pine(WORLD_X0 + 10 + i * 80, HORIZON + 80, rnd.uniform(80, 170), shade(T["far"], -0.25))
    L.append((0.14, sky))

    tw = ""
    for lx in (700, 1180):
        tw += rect(lx - 16, 620, 32, 700, shade(T["mid"], -0.34))
    for i in range(9):
        yy = 700 + i * 74
        tw += line(700, yy, 1180, yy - 30, shade(T["mid"], -0.42), 9)
        tw += line(700, yy - 30, 1180, yy, shade(T["mid"], -0.42), 5)
        for j in range(5):
            tw += line(716 + j * 116, yy, 716 + j * 116, yy - 30, shade(T["mid"], -0.5), 3)
    tw += rect(620, 470, 660, 170, shade(T["mid"], -0.16), 8)
    tw += poly([(600, 470), (950, 380), (1300, 470)], shade(T["mid"], -0.3))
    tw += rect(660, 500, 120, 90, "#ffe9b0", op=0.85)
    tw += rect(1140, 500, 120, 90, "#ffe9b0", op=0.6)
    tw += rect(770, 780, 150, 90, "#ffe9b0", op=0.4)
    tw += circ(720, 545, 300, "url(#tw_lamp)", op=0.35)
    tw += rect(880, 640, 130, 680, shade(T["mid"], -0.55))
    tw += rect(890, 700, 110, 300, shade(T["mid"], -0.3))
    L.append((0.52, tw))

    ground = rect(WORLD_X0, GROUND + 20, WORLD_W, 400, T["near"])
    ground += rect(WORLD_X0, GROUND + 20, WORLD_W, 10, shade(T["near"], 0.2))
    ground += grass_tufts(seed + 11, WORLD_X0, WORLD_X0 + WORLD_W, GROUND + 60, 1800, 120,
                          shade(T["ground"], 0.14), 1.7)
    ground += bush(WORLD_X0 + 300, GROUND + 130, 170, shade(T["ground"], 0.04))
    ground += bush(WORLD_X0 + 1740, GROUND + 120, 190, shade(T["ground"], 0.04))
    L.append((0.86, ground))

    fg = rect(WORLD_X0, 1800, WORLD_W, 120, shade(T["near"], -0.66))
    rnd = random.Random(seed + 13)
    for i in range(12):
        fg += pine(WORLD_X0 + i * 196 + rnd.uniform(-40, 40), 1930, rnd.uniform(150, 240),
                   shade(T["near"], -0.56))
    L.append((1.0, fg))
    return defs, L


def tower_top(tname, mood="calm", seed=9):
    T = TIME[tname]
    defs = (sky_grad("tt_sky", tname, mood) + glow_def("tt_lamp", "#ffe0a0", 0.7)
            + glow_def("tt_blue", "#9fd0ff", 0.45))
    wood = "#382a22"
    L = []
    back = rect(WORLD_X0, 0, WORLD_W, 1300, "#181c2a")
    back += rect(WORLD_X0, 700, WORLD_W, 120, wood)
    back += rect(WORLD_X0, 820, WORLD_W, 24, shade(wood, 0.12))
    for i in range(7):
        wx = 120 + i * 300
        back += rect(wx, 300, 220, 400, "#0e1730", 6)
        back += rect(wx + 10, 310, 200, 380, mix("#1d2c52", T["sky"][-1][1], 0.25))
        back += line(wx + 110, 300, wx + 110, 700, shade(wood, -0.2), 8)
        back += line(wx, 500, wx + 220, 500, shade(wood, -0.2), 8)
        back += circ(wx + 110, 500, 200, "url(#tt_blue)", op=0.2)
    L.append((0.35, back))

    furn = rect(940, 980, 300, 240, shade(wood, -0.15), 8)
    furn += rect(970, 900, 240, 90, shade(wood, 0.08), 6)
    furn += rect(1180, 1020, 46, 100, "#c9cbd2", 6)
    furn += ell(1203, 1010, 27, 11, "#8a6a4a")
    furn += rect(1180, 1140, 46, 60, "#c9cbd2", 6)
    furn += circ(1200, 880, 400, "url(#tt_lamp)", op=0.4)
    furn += path("M 460 1220 q 60 -40 120 0 q 60 40 120 0", "none", shade(wood, -0.2), 14)
    furn += rect(500, 1010, 200, 210, shade(wood, -0.3), 8)
    furn += rect(560, 900, 90, 120, "#2a3548", 8)
    L.append((0.6, furn))

    floor = rect(WORLD_X0, 1220, WORLD_W, 700, shade(wood, -0.42))
    for i in range(16):
        floor += line(WORLD_X0 + i * 140, 1220, WORLD_X0 + i * 140, 1920, shade(wood, -0.5), 6)
    floor += rect(WORLD_X0, 1220, WORLD_W, 14, shade(wood, -0.1))
    L.append((0.88, floor))
    L.append((1.0, rect(WORLD_X0, 1860, WORLD_W, 60, "#0a0d16")))
    return defs, L


def radio_room(tname, mood="calm", seed=10):
    T = TIME[tname]
    defs = (sky_grad("rr_sky", tname, mood) + glow_def("rr_lamp", "#ffd08a", 0.6)
            + glow_def("rr_radio", "#7dffd0", 0.75) + glow_def("rr_dial", "#ff9f4a", 0.6))
    wood = "#2f2a30"
    L = []
    back = rect(WORLD_X0, 0, WORLD_W, 1360, wood)
    back += rect(WORLD_X0, 0, WORLD_W, 200, shade(wood, -0.35))
    back += rect(1700, 560, 380, 320, "#0d1428", 10)
    back += rect(1712, 572, 356, 296, "#16234a")
    for i in range(8):
        back += circ(1740 + i * 44, 610, 3, "#dce8ff", op=0.5)
    back += rect(300, 300, 560, 240, "#e8e0cc", 6, op=0.14)
    back += rect(320, 320, 520, 200, "#e8e0cc", 4, op=0.08)
    for i in range(5):
        back += line(330, 350 + i * 40, 830, 350 + i * 40, "#7a8aa0", 3, op=0.5)
    L.append((0.32, back))

    console = rect(560, 1000, 620, 360, "#232a36", 10)
    console += rect(580, 1016, 580, 120, "#161c28", 6)
    for i in range(14):
        cx = 600 + i * 40
        console += rect(cx, 1030, 24, 24, "#2f3a4c", 4)
        console += rect(cx, 1064, 24, 62, "#3a4658", 4)
    console += rect(620, 1150, 240, 190, "#1b222c", 6)
    console += circ(740, 1180, 20, "#7dffd0", op=0.9)
    console += circ(740, 1230, 14, "#ff9f4a", op=0.8)
    console += circ(740, 1275, 10, "#ff5a4a", op=0.7)
    console += circ(740, 1200, 300, "url(#rr_radio)", op=0.20)
    console += rect(1290, 900, 130, 200, "#22283a", 8)
    console += rect(1305, 918, 100, 90, "#3a4658", 6)
    console += rect(1310, 1100, 90, 60, "#2c3444", 6)
    desk = rect(420, 1330, 900, 34, shade(wood, 0.1), 6)
    desk += rect(430, 1220, 120, 110, "#e8e0cc", 4, op=0.5)
    desk += rect(1300, 1210, 200, 120, "#c9553f", 6, op=0.75)
    L.append((0.62, console + desk))

    floor = rect(WORLD_X0, 1510, WORLD_W, 410, shade(wood, -0.3))
    floor += rect(WORLD_X0, 1510, WORLD_W, 12, shade(wood, -0.05))
    for i in range(14):
        floor += line(WORLD_X0 + i * 160, 1522, WORLD_X0 + i * 160, 1920, shade(wood, -0.4), 5)
    L.append((0.9, floor))
    return defs, L


def coast(tname, mood="calm", seed=11):
    T = TIME[tname]
    defs = (sky_grad("co_sky", tname, mood) + glow_def("co_glow", T["warm"], 0.8)
            + glow_def("co_fire", "#ff9a4a", 0.85) + glow_def("co_star", "#fff0c0", 0.5))
    L = []
    sea_y = 1240.0
    sky = rect(WORLD_X0, 0, WORLD_W, sea_y, "url(#co_sky)")
    if T["stars"]:
        sky += stars(seed, 140, 900)
    if T["celestial"] == "sun":
        sky += circ(760, sea_y - 90, 84, T["warm"], op=0.92)
        sky += circ(760, sea_y - 90, 300, "url(#co_glow)", op=0.8)
    else:
        sky += circ(900, 300, 66, "#f7f1d8", op=0.9) + circ(924, 282, 58, "#0d152e", op=0.5)
    L.append((0.1, sky))

    sea = rect(WORLD_X0, sea_y, WORLD_W, 260, mix(T["sky"][1][1], "#0a1626", 0.55))
    sea += rect(WORLD_X0, sea_y, WORLD_W, 14, mix(T["warm"], "#ffffff", 0.4), op=0.35)
    rnd = random.Random(seed + 3)
    for i in range(26):
        wy = sea_y + 26 + i * 12
        sea += rect(WORLD_X0 + rnd.uniform(0, 200), wy, WORLD_X0 * -1 + 1600 + rnd.uniform(0, 400), 4,
                    "#cfe6ff", op=0.06 + rnd.random() * 0.06)
    L.append((0.3, sea))

    dock = rect(1300, 1200, 520, 26, "#4a4038")
    dock += rect(1300, 1226, 520, 20, "#332c26")
    for i in range(6):
        dock += rect(1320 + i * 92, 1246, 20, 130, "#2b2620")
    boat = path("M 1420 1160 q 90 -30 190 0 q -20 60 -95 60 q -75 0 -95 -60 Z", "#2a3340")
    boat += rect(1500, 1090, 12, 70, "#3f4a58")
    L.append((0.58, dock + boat))

    beach = rect(WORLD_X0, 1290, WORLD_W, 630, mix(T["ground"], "#c9b189", 0.35))
    beach += rect(WORLD_X0, 1290, WORLD_W, 18, mix(T["ground"], "#e8d4a8", 0.4))
    beach += grass_tufts(seed + 9, WORLD_X0, WORLD_X0 + WORLD_W, 1450, 1800, 90,
                         mix(T["ground"], "#5a6a3a", 0.4), 1.5)
    tents = (poly([(300, 1400), (420, 1290), (540, 1400)], "#3f5a4a")
             + poly([(560, 1400), (650, 1310), (740, 1400)], "#4a5a6a"))
    fire = circ(880, 1400, 60, "#ff9a4a", op=0.85) + circ(880, 1400, 160, "url(#co_fire)", op=0.6)
    fire += poly([(840, 1400), (880, 1310), (920, 1400)], "#ffd27a", op=0.9)
    tents += fire
    L.append((0.86, beach + tents))

    fg = rect(WORLD_X0, 1820, WORLD_W, 100, shade(mix(T["ground"], "#c9b189", 0.35), -0.5))
    rnd = random.Random(seed + 12)
    for i in range(10):
        fg += bush(WORLD_X0 + i * 260 + rnd.uniform(-60, 60), 1880, rnd.uniform(90, 160),
                   shade(mix(T["ground"], "#4a5a3a", 0.5), -0.35))
    L.append((1.0, fg))
    return defs, L


def city(tname, mood="calm", seed=12):
    T = TIME[tname]
    defs = (sky_grad("ci_sky", tname, mood) + glow_def("ci_win", "#ffe9b0", 0.5)
            + glow_def("ci_signal", "#7dffd0", 0.9) + glow_def("ci_street", "#ffd98a", 0.55))
    L = []
    sky = rect(WORLD_X0, 0, WORLD_W, HORIZON + 60, "url(#ci_sky)")
    if T["stars"]:
        sky += stars(seed, 70, 620)
    sky += circ(980, 240, 60, "#f7f1d8", op=0.7) + circ(1000, 224, 54, "#0e1530", op=0.5)
    L.append((0.1, sky))

    far = rect(WORLD_X0, HORIZON - 40, WORLD_W, 300, T["far"])
    rnd = random.Random(seed + 4)
    x = WORLD_X0
    while x < WORLD_X0 + WORLD_W:
        w = rnd.uniform(130, 260)
        h = rnd.uniform(320, 760)
        far += rect(x, HORIZON - h, w, h + 120, shade(T["far"], -0.1))
        far += window_grid(x + 10, HORIZON - h + 20, w - 20, h * 0.8, 5, 12,
                           shade(T["far"], 0.05), "#ffe9b0", int(x), 0.11)
        x += w + rnd.uniform(8, 40)
    L.append((0.32, far))

    tall = ""
    rnd = random.Random(seed + 8)
    x = WORLD_X0 + 60
    while x < WORLD_X0 + WORLD_W:
        w = rnd.uniform(180, 340)
        h = rnd.uniform(420, 900)
        tall += rect(x, HORIZON - h + 120, w, h + 300, shade(T["mid"], -0.05))
        tall += window_grid(x + 14, HORIZON - h + 150, w - 28, h * 0.72, 6, 10,
                            shade(T["mid"], 0.06), "#ffe9b0", int(x), 0.14)
        tall += rect(x, HORIZON - h + 120, w, 16, shade(T["mid"], 0.2))
        x += w + rnd.uniform(30, 90)
    tall += circ(1500, 700, 340, "url(#ci_signal)", op=0.35)
    tall += rect(1476, 560, 48, 90, "#7dffd0", 6, op=0.9)
    tall += circ(1500, 605, 26, "#0c1a18")
    L.append((0.56, tall))

    street = rect(WORLD_X0, GROUND + 40, WORLD_W, 360, T["near"])
    street += rect(WORLD_X0, GROUND + 40, WORLD_W, 12, "#4a4f58", op=0.5)
    for i in range(24):
        street += rect(WORLD_X0 + 30 + i * 96, GROUND + 120, 54, 8, "#c9c9b8", op=0.3)
    for i in range(6):
        lx = WORLD_X0 + 220 + i * 400
        street += rect(lx, GROUND - 320, 14, 360, shade(T["mid"], -0.45))
        street += path(f"M {n(lx)} {n(GROUND - 320)} q 70 -20 130 -6", "none", shade(T["mid"], -0.45), 12)
        street += circ(lx + 120, GROUND - 330, 22, "#ffe9b0", op=0.85)
        street += circ(lx + 120, GROUND - 320, 250, "url(#ci_street)", op=0.35)
    rnd = random.Random(seed + 6)
    for i in range(6):
        street += car(WORLD_X0 + 120 + i * 340 + rnd.uniform(-40, 40), GROUND + 90, 200,
                      shade(T["near"], 0.12), flip=i % 2 == 1)
    L.append((0.86, street))

    fg = rect(WORLD_X0, 1800, WORLD_W, 120, shade(T["near"], -0.6))
    rnd = random.Random(seed + 10)
    for i in range(14):
        fg += rect(WORLD_X0 + i * 160 + rnd.uniform(-40, 40), 1840, rnd.uniform(60, 130),
                   rnd.uniform(30, 90), shade(T["near"], -0.45), 8)
    L.append((1.0, fg))
    return defs, L


def metro(tname, mood="calm", seed=13):
    T = TIME[tname]
    defs = (sky_grad("me_sky", tname, mood) + glow_def("me_lamp", "#dfe8ff", 0.6)
            + glow_def("me_exit", "#ffd98a", 0.8) + glow_def("me_deep", "#0a0f1e", 0.9))
    L = []
    wall = "#232636"
    back = rect(WORLD_X0, 0, WORLD_W, 1380, wall)
    back += rect(WORLD_X0, 0, WORLD_W, 260, shade(wall, -0.35))
    for i in range(26):
        back += line(WORLD_X0 + i * 88, 260, WORLD_X0 + i * 88, 1000, shade(wall, 0.06), 3)
    for i in range(9):
        back += line(WORLD_X0, 260 + i * 88, WORLD_X0 + WORLD_W, 260 + i * 88, shade(wall, 0.06), 3)
    back += rect(60, 560, 70, 90, "#4a5a7a", 6)
    back += text(95, 620, "METRO", 30, "Barlow", "#c9d6ee", weight="bold", ls=2)
    L.append((0.35, back))

    tunnel = rect(1500, 520, 620, 700, "#05080f")
    tunnel += circ(1810, 870, 300, "url(#me_deep)", op=0.9)
    tunnel += rect(1480, 500, 40, 720, shade(wall, -0.2))
    tunnel += rect(1500, 500, 620, 30, shade(wall, -0.15))
    lamps = ""
    for i in range(5):
        lx = 180 + i * 320
        lamps += rect(lx - 70, 200, 140, 18, "#dfe8ff", 6)
        lamps += circ(lx, 240, 165, "url(#me_lamp)", op=0.20)
    L.append((0.55, tunnel + lamps))

    plat = rect(WORLD_X0, 1240, WORLD_W, 90, "#2b2f3c")
    plat += rect(WORLD_X0, 1232, WORLD_W, 12, "#ffd98a", op=0.5)
    plat += rect(WORLD_X0, 1330, WORLD_W, 26, "#15181f")
    for i in range(20):
        plat += rect(WORLD_X0 + 40 + i * 110, 1256, 60, 30, "#33405a", op=0.7)
    track = rect(WORLD_X0, 1356, WORLD_W, 180, "#0e1119")
    track += rect(WORLD_X0, 1356, WORLD_W, 8, "#4a4f58")
    for i in range(30):
        track += rect(WORLD_X0 + i * 76, 1366, 40, 10, "#2b2f38")
    track += rect(WORLD_X0, 1360, WORLD_W, 6, "#5a6070")
    track += rect(WORLD_X0, 1420, WORLD_W, 6, "#5a6070")
    track += rect(WORLD_X0, 1536, WORLD_W, 384, "#0a0d14")
    L.append((0.86, plat + track))

    fg = rect(WORLD_X0, 1780, WORLD_W, 140, "#05070c")
    for i in range(6):
        fg += rect(WORLD_X0 + 100 + i * 380, 1400, 60, 380, "#121620")
    L.append((1.0, fg))
    return defs, L


def lab(tname, mood="calm", seed=14):
    T = TIME[tname]
    defs = (sky_grad("lb_sky", tname, mood) + glow_def("lb_flick", "#dff2ff", 0.75)
            + glow_def("lb_up", "#7dffd0", 0.6) + glow_def("lb_warn", "#ff6a5a", 0.5))
    L = []
    tile = "#222634"
    back = rect(WORLD_X0, 0, WORLD_W, 1400, tile)
    back += rect(WORLD_X0, 0, WORLD_W, 200, shade(tile, -0.4))
    for i in range(24):
        back += line(WORLD_X0 + i * 96, 200, WORLD_X0 + i * 96, 1400, shade(tile, 0.07), 3)
    for i in range(10):
        back += line(WORLD_X0, 200 + i * 120, WORLD_X0 + WORLD_W, 200 + i * 120, shade(tile, 0.07), 3)
    # note wall
    rnd = random.Random(seed + 3)
    for i in range(26):
        nx = 240 + rnd.uniform(0, 1000)
        ny = 320 + rnd.uniform(0, 520)
        back += rect(nx, ny, rnd.uniform(80, 150), rnd.uniform(60, 110), "#e8e4d6",
                     2, op=rnd.uniform(0.5, 0.9))
    # stairs up
    for i in range(9):
        back += rect(1420 + i * 26, 1180 - i * 62, 190, 62, shade(tile, 0.05))
    back += rect(1600, 560, 40, 620, shade(tile, -0.3))
    back += rect(1360, 540, 300, 40, shade(tile, -0.34))
    back += circ(1480, 640, 320, "url(#lb_up)", op=0.28)
    # cages
    for i in range(4):
        cx = 420 + i * 190
        back += rect(cx, 1180, 150, 180, shade(tile, -0.2), 6)
        back += rect(cx + 6, 1186, 138, 168, "#121828")
        for j in range(6):
            back += line(cx + 14 + j * 24, 1186, cx + 14 + j * 24, 1354, "#4a5568", 4)
    L.append((0.34, back))

    ceil = ""
    for i in range(4):
        lx = 200 + i * 340
        flick = 0.55 + 0.45 * abs(math.sin(i * 2.1 + 0.6))
        ceil += rect(lx - 110, 120, 220, 22, "#dff2ff", 6, op=round(flick, 2))
        ceil += circ(lx, 180, 185, "url(#lb_flick)", op=round(0.16 * flick, 2))
    L.insert(0, (0.22, ceil))

    bench = rect(500, 1100, 900, 40, shade(tile, 0.1), 6)
    bench += rect(520, 1140, 40, 60, shade(tile, -0.25))
    bench += rect(1340, 1140, 40, 60, shade(tile, -0.25))
    bench += rect(700, 1040, 90, 60, "#3a4658", 6)
    bench += rect(880, 1010, 70, 90, "#4a5a7a", 6)
    bench += circ(730, 1050, 200, "url(#lb_warn)", op=0.16)
    L.append((0.6, bench))

    floor = rect(WORLD_X0, 1360, WORLD_W, 560, shade(tile, -0.28))
    floor += rect(WORLD_X0, 1360, WORLD_W, 12, shade(tile, 0.08))
    for i in range(14):
        floor += line(WORLD_X0 + i * 160, 1372, WORLD_X0 + i * 160, 1920, shade(tile, -0.36), 4)
    L.append((0.88, floor))
    return defs, L


def farm(tname, mood="calm", seed=15):
    T = TIME[tname]
    defs = (sky_grad("fa_sky", tname, mood) + glow_def("fa_glow", T["glowc"], 0.7)
            + glow_def("fa_win", "#ffd98a", 0.75))
    L = []
    sky = rect(WORLD_X0, 0, WORLD_W, HORIZON + 60, "url(#fa_sky)")
    if T["stars"]:
        sky += stars(seed, 90, 700)
    if T["celestial"] == "sun":
        sky += circ(480, 980, 80, T["warm"], op=0.9) + circ(480, 980, 300, "url(#fa_glow)", op=0.7)
    else:
        sky += circ(1200, 260, 58, "#f7f1d8", op=0.85) + circ(1220, 244, 52, "#0e1630", op=0.5)
    L.append((0.1, sky))

    hills = poly([(WORLD_X0, HORIZON + 60), (WORLD_X0 + 400, HORIZON - 90), (WORLD_X0 + 900, HORIZON + 30),
                  (WORLD_X0 + 1400, HORIZON - 70), (WORLD_X0 + 1900, HORIZON + 40),
                  (WORLD_X0 + WORLD_W, HORIZON - 40), (WORLD_X0 + WORLD_W, HORIZON + 260),
                  (WORLD_X0, HORIZON + 260)], T["far"])
    rnd = random.Random(seed + 2)
    for i in range(14):
        hills += bush(WORLD_X0 + 80 + i * 170, HORIZON + 70, rnd.uniform(50, 90), shade(T["far"], -0.18))
    L.append((0.26, hills))

    field = rect(WORLD_X0, HORIZON + 120, WORLD_W, 700, mix(T["ground"], "#7a6a30", 0.35))
    for i in range(26):
        fy = HORIZON + 160 + i * 28
        field += line(WORLD_X0, fy, WORLD_X0 + WORLD_W, fy + 6, shade(mix(T["ground"], "#8a7a3a", 0.4), -0.05),
                      4, op=0.5)
    L.append((0.44, field))

    house = rect(700, 980, 620, 420, "#5a4a3a")
    house += poly([(660, 980), (1010, 800), (1360, 980)], "#7a3f34")
    house += rect(760, 1060, 150, 130, "#0f1626", 6)
    house += rect(772, 1072, 126, 106, "#ffd98a", op=0.8)
    house += circ(835, 1120, 220, "url(#fa_win)", op=0.45)
    house += rect(1000, 1060, 130, 340, "#3f3228", 6)
    house += rect(1016, 1100, 98, 130, "#2a2318")
    house += rect(1330, 1090, 200, 310, "#4a4038")
    house += rect(1360, 1120, 60, 90, "#0f1626", 4)
    silo = rect(1420, 700, 260, 700, "#6a6a62")
    silo += poly([(1400, 700), (1550, 620), (1700, 700)], "#5a5a52")
    for i in range(6):
        silo += line(1420, 760 + i * 100, 1680, 760 + i * 100, "#5a5a52", 5)
    L.append((0.6, house + silo))

    fence = ""
    for i in range(30):
        fx = WORLD_X0 + i * 74
        fence += rect(fx, GROUND - 6, 16, 140, "#4a3f30", 3)
    fence += rect(WORLD_X0, GROUND + 20, WORLD_W, 14, "#4a3f30")
    fence += rect(WORLD_X0, GROUND + 76, WORLD_W, 12, "#4a3f30")
    fence += grass_tufts(seed + 7, WORLD_X0, WORLD_X0 + WORLD_W, GROUND + 150, 1820, 110,
                         mix(T["ground"], "#8a9a3a", 0.35), 1.6)
    well = rect(320, 1240, 150, 130, "#6a6258", 8)
    well += poly([(300, 1240), (395, 1130), (490, 1240)], "#4a4038")
    L.append((0.86, fence + well))

    fg = rect(WORLD_X0, 1830, WORLD_W, 90, shade(mix(T["ground"], "#7a6a30", 0.35), -0.5))
    rnd = random.Random(seed + 11)
    for i in range(12):
        fg += bush(WORLD_X0 + i * 200 + rnd.uniform(-50, 50), 1890, rnd.uniform(80, 130),
                   shade(mix(T["ground"], "#5a6a30", 0.5), -0.3))
    L.append((1.0, fg))
    return defs, L


SCENES = {
    "highway": highway, "gas_station": gas_station, "store": store,
    "motel_lot": motel_lot, "motel_hall": motel_hall, "forest": forest,
    "bridge": bridge, "tower": tower, "tower_top": tower_top,
    "radio_room": radio_room, "coast": coast, "city": city,
    "metro": metro, "lab": lab, "farm": farm,
}


def build(place, tname="night", mood="calm", seed=1):
    fn = SCENES.get(place) or highway
    defs, layers = fn(tname, mood, seed)
    # base fill: koi transparent gap na bache (layers ke beech)
    base = rect(WORLD_X0, 0, WORLD_W, 1920, mix(TIME[tname]["ground"], TIME[tname]["far"], 0.4))
    return defs, [(0.02, base)] + layers


def mood_tint(mood):
    m = MOOD.get(mood, DEFAULT_MOOD)
    return m["tint"], m["ta"]
