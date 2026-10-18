"""Cartoon character rig: Max, Ada, Otto, the shamblers — aur Biscuit (dog).

Sab kuch procedural hai: ek chhota skeleton (thigh / shin / spine / arms) aur
per-action pose functions. Character ka origin uske **pairon (feet) par** hai,
isliye position karna aasan hai: `translate(x, ground_y)`.

Angle convention (svgkit.dirv): 0 = neeche, positive = aage (right).
Knee sirf peeche mudta hai (knee_bend >= 0).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from svgkit import circ, dirv, ell, esc, g, limb, line, n, path, rect, text, shade

OUTLINE = "#151a22"

PALETTES = {
    "boy": dict(
        skin="#f4c79c", hair="#3a2a22", coat="#d1583f", pants="#3f5670",
        shoe="#23262b", accent="#f2d16b",
    ),
    "girl": dict(
        skin="#f4c79c", hair="#2a1e18", coat="#4f7fbf", pants="#333a48",
        shoe="#20242b", accent="#e08a3c",
    ),
    "old": dict(
        skin="#e6b98f", hair="#d8d4cc", coat="#6d5b45", pants="#494a52",
        shoe="#2a2622", accent="#8fa0b0",
    ),
    "zombie": dict(
        skin="#86ab6d", hair="#59684a", coat="#7f8570", pants="#4b4b3f",
        shoe="#2c2c26", accent="#3f4a35",
    ),
}

DOG_PAL = dict(
    body="#e9c188", belly="#f5dfc0", nose="#26262a",
    collar="#d1583f", tongue="#e2748a",
)

ROLE_ART = {"max": "boy", "ada": "girl", "old": "old", "zombie": "zombie"}

LOCOMOTION = {"walk", "run", "sneak", "shamble", "trot", "follow", "run_dog"}

# Speed in design-px per second (world scroll ke liye).
SPEEDS = {
    "walk": 78.0, "run": 330.0, "sneak": 34.0, "shamble": 44.0,
    "trot": 250.0, "run_dog": 330.0,
}


@dataclass
class Pose:
    lean: float = 4.0
    head_tilt: float = 0.0
    head_dx: float = 0.0
    thigh_f: float = 0.0
    knee_f: float = 4.0
    thigh_n: float = 0.0
    knee_n: float = 4.0
    arm_f: float = 5.0
    elbow_f: float = 14.0
    arm_n: float = 5.0
    elbow_n: float = 14.0
    hip_dx: float = 0.0
    hip_dy: float = 0.0
    mouth: str = "line"
    brow: float = 0.0
    arm_back: bool = False
    tag: str = ""


def _foot(th, kn, l1, l2):
    return l1 * math.cos(math.radians(th)) + l2 * math.cos(math.radians(th - kn))


def _joint(origin, angle, length):
    dx, dy = dirv(angle)
    return (origin[0] + dx * length, origin[1] + dy * length)


# ------------------------------------------------------------------ poses ----


def pose_idle(t, mood="calm"):
    br = math.sin(t * 1.9)
    return Pose(
        lean=5.0 + 1.2 * br,
        head_tilt=2.5 * math.sin(t * 0.9 + 1.1),
        thigh_f=2.0, knee_f=5.0, thigh_n=-3.0, knee_n=7.0,
        arm_f=-2.0 + 2.5 * br, elbow_f=17.0,
        arm_n=3.0 - 2.5 * br, elbow_n=15.0,
    )


def pose_walk(t):
    p = math.tau / 1.15
    a = t * p
    return Pose(
        lean=6.0,
        head_tilt=1.5 * math.sin(a * 0.5),
        thigh_f=25.0 * math.sin(a),
        knee_f=max(0.0, 8.0 + 34.0 * math.sin(a + 2.05)),
        thigh_n=25.0 * math.sin(a + math.pi),
        knee_n=max(0.0, 8.0 + 34.0 * math.sin(a + math.pi + 2.05)),
        arm_f=-17.0 * math.sin(a), elbow_f=22.0 + 6.0 * math.sin(a + 1.0),
        arm_n=-17.0 * math.sin(a + math.pi), elbow_n=22.0 + 6.0 * math.sin(a + 4.0),
    )


def pose_run(t):
    p = math.tau / 0.60
    a = t * p
    return Pose(
        lean=17.0,
        head_tilt=-3.0,
        thigh_f=42.0 * math.sin(a),
        knee_f=max(4.0, 14.0 + 62.0 * math.sin(a + 1.85)),
        thigh_n=42.0 * math.sin(a + math.pi),
        knee_n=max(4.0, 14.0 + 62.0 * math.sin(a + math.pi + 1.85)),
        arm_f=-38.0 * math.sin(a), elbow_f=62.0,
        arm_n=-38.0 * math.sin(a + math.pi), elbow_n=62.0,
        mouth="open",
    )


def pose_sneak(t):
    p = math.tau / 1.35
    a = t * p
    return Pose(
        lean=15.0,
        head_tilt=-4.0,
        thigh_f=12.0 + 15.0 * math.sin(a),
        knee_f=40.0 + 12.0 * math.sin(a + 1.0),
        thigh_n=12.0 + 15.0 * math.sin(a + math.pi),
        knee_n=40.0 + 12.0 * math.sin(a + math.pi + 1.0),
        arm_f=16.0, elbow_f=52.0, arm_n=20.0, elbow_n=48.0,
        hip_dy=14.0,
    )


def pose_crouch(t):
    s = math.sin(t * 1.4)
    return Pose(
        lean=22.0,
        head_tilt=-6.0,
        thigh_f=44.0, knee_f=78.0, thigh_n=38.0, knee_n=74.0,
        arm_f=22.0 + 2 * s, elbow_f=58.0,
        arm_n=26.0 - 2 * s, elbow_n=54.0,
        hip_dy=6.0,
    )


def pose_check(t):
    s = math.sin(t * 3.1)
    return Pose(
        lean=10.0 + 1.5 * s,
        head_tilt=-3.0,
        thigh_f=6.0, knee_f=12.0, thigh_n=-8.0, knee_n=16.0,
        arm_f=74.0 + 4.0 * s, elbow_f=40.0,
        arm_n=68.0 - 4.0 * s, elbow_n=48.0,
    )


def pose_reach(t):
    return Pose(
        lean=9.0, head_tilt=3.0,
        thigh_f=4.0, knee_f=8.0, thigh_n=-6.0, knee_n=12.0,
        arm_f=76.0, elbow_f=16.0, arm_n=60.0, elbow_n=30.0,
    )


def pose_point(t):
    s = math.sin(t * 2.2)
    return Pose(
        lean=6.0 + 1.0 * s, head_tilt=4.0,
        thigh_f=2.0, knee_f=6.0, thigh_n=-4.0, knee_n=10.0,
        arm_f=88.0 + 3.0 * s, elbow_f=4.0, arm_n=18.0, elbow_n=22.0,
        mouth="open",
    )


def pose_look(t):
    return Pose(
        lean=-3.0,
        head_tilt=-11.0 - 2.0 * math.sin(t * 1.3),
        thigh_f=-4.0, knee_f=9.0, thigh_n=3.0, knee_n=7.0,
        arm_f=-8.0, elbow_f=20.0, arm_n=6.0, elbow_n=16.0,
    )


def pose_call(t):
    s = math.sin(t * 4.2)
    return Pose(
        lean=-2.0, head_tilt=-4.0,
        thigh_f=2.0, knee_f=8.0, thigh_n=-3.0, knee_n=10.0,
        arm_f=104.0 + 6.0 * s, elbow_f=62.0,
        arm_n=118.0 - 6.0 * s, elbow_n=58.0,
        mouth="open",
    )


def pose_climb(t):
    a = t * math.tau / 1.0
    return Pose(
        lean=6.0, head_tilt=-14.0,
        thigh_f=26.0 + 22.0 * math.sin(a),
        knee_f=46.0 + 20.0 * math.sin(a + 1.0),
        thigh_n=26.0 + 22.0 * math.sin(a + math.pi),
        knee_n=46.0 + 20.0 * math.sin(a + math.pi + 1.0),
        arm_f=150.0 - 26.0 * math.sin(a), elbow_f=24.0,
        arm_n=150.0 - 26.0 * math.sin(a + math.pi), elbow_n=24.0,
        hip_dy=26.0,
    )


def pose_sit(t):
    s = math.sin(t * 1.5)
    return Pose(
        lean=-20.0 + 1.5 * s, head_tilt=6.0 + 2.0 * s,
        thigh_f=86.0, knee_f=62.0, thigh_n=80.0, knee_n=66.0,
        arm_f=-30.0, elbow_f=40.0, arm_n=-36.0, elbow_n=36.0,
        hip_dy=8.0,
    )


def pose_shamble(t):
    p = math.tau / 1.7
    a = t * p
    return Pose(
        lean=25.0,
        head_tilt=-14.0 + 4.0 * math.sin(a),
        thigh_f=19.0 * math.sin(a), knee_f=max(2.0, 12.0 + 26.0 * math.sin(a + 2.0)),
        thigh_n=19.0 * math.sin(a + math.pi), knee_n=max(2.0, 12.0 + 26.0 * math.sin(a + math.pi + 2.0)),
        arm_f=30.0 + 7.0 * math.sin(a), elbow_f=16.0,
        arm_n=27.0 - 7.0 * math.sin(a), elbow_n=20.0,
        mouth="open", brow=-6.0,
    )


def pose_zreach(t):
    s = math.sin(t * 2.4)
    return Pose(
        lean=28.0, head_tilt=-18.0 + 5.0 * s,
        thigh_f=14.0, knee_f=26.0, thigh_n=-14.0, knee_n=30.0,
        arm_f=82.0 + 8.0 * s, elbow_f=18.0,
        arm_n=74.0 - 8.0 * s, elbow_n=22.0,
        mouth="open", brow=-8.0,
    )


def pose_zstill(t):
    s = math.sin(t * 1.1)
    return Pose(
        lean=21.0, head_tilt=-12.0 + 3.0 * s,
        thigh_f=5.0, knee_f=14.0, thigh_n=-4.0, knee_n=16.0,
        arm_f=24.0 + 4.0 * s, elbow_f=18.0,
        arm_n=21.0 - 4.0 * s, elbow_n=20.0,
        mouth="open", brow=-6.0,
    )


HUMAN_ACTIONS = {
    "idle": pose_idle, "walk": pose_walk, "run": pose_run, "sneak": pose_sneak,
    "crouch": pose_crouch, "check": pose_check, "reach": pose_reach,
    "point": pose_point, "look": pose_look, "call": pose_call,
    "climb": pose_climb, "sit": pose_sit,
    "shamble": pose_shamble, "reach_z": pose_zreach, "still": pose_zstill,
}


# --------------------------------------------------------------- rendering ---


def _face_head(px, py, hr, pal, pose, art):
    """Head: hair circle + face circle + eye + brow + mouth."""
    o = OUTLINE
    ow = hr * 0.22
    out = []
    # ponytail / cap / hair mass
    if art == "girl":
        out.append(ell(px - hr * 0.85, py - hr * 0.25, hr * 0.42, hr * 0.72,
                       pal["hair"], o, ow, rotate=-18))
    elif art == "old":
        out.append(path(
            f"M {px - hr * 1.15} {py - hr * 0.35} L {px + hr * 1.1} {py - hr * 0.45} "
            f"L {px + hr * 1.05} {py - hr * 1.05} L {px - hr * 0.9} {py - hr * 1.2} Z",
            pal["accent"], o, ow * 0.8))
    # hair blob
    out.append(circ(px - hr * 0.08, py - hr * 0.1, hr * 1.02, pal["hair"], o, ow))
    # face
    out.append(circ(px + hr * 0.2, py + hr * 0.14, hr * 0.88, pal["skin"], o, ow * 0.85))
    # hair fringe over the forehead
    out.append(path(
        f"M {px - hr * 1.0} {py - hr * 0.42} "
        f"Q {px + hr * 0.1} {py - hr * 1.28} {px + hr * 0.98} {py - hr * 0.5} "
        f"Q {px + hr * 0.3} {py - hr * 0.72} {px - hr * 0.2} {py - hr * 0.44} Z",
        pal["hair"], o, ow * 0.7))
    # ear
    out.append(circ(px - hr * 0.72, py + hr * 0.2, hr * 0.2, pal["skin"], o, ow * 0.55))
    # eye
    ex, ey = px + hr * 0.46, py + hr * 0.02
    out.append(ell(ex, ey, hr * 0.13, hr * 0.17, o))
    out.append(circ(ex + hr * 0.04, ey - hr * 0.05, hr * 0.045, "#ffffff", op=0.9))
    # brow (zombie se gussa, max se tension)
    by = ey - hr * 0.34 + pose.brow * 0.4
    out.append(line(ex - hr * 0.2, by + hr * 0.06, ex + hr * 0.2, by, o, hr * 0.11))
    # mouth
    mx, my = px + hr * 0.4, py + hr * 0.52
    if pose.mouth == "open":
        out.append(ell(mx, my, hr * 0.22, hr * 0.2, "#3a1f22", o, ow * 0.6))
        out.append(ell(mx, my - hr * 0.04, hr * 0.1, hr * 0.07, "#e2748a"))
    else:
        out.append(path(
            f"M {mx - hr * 0.22} {my} Q {mx} {my + hr * 0.2} {mx + hr * 0.22} {my - hr * 0.02}",
            "none", o, hr * 0.11))
    return "".join(out)


def render_human(pal, pose: Pose, size=430.0, art="boy", op=None):
    l1, l2 = size * 0.235, size * 0.225
    l3 = size * 0.33
    lu, lf = size * 0.16, size * 0.155
    hr = size * 0.083
    o = OUTLINE
    ow = max(4.0, size * 0.017)

    hip_y = -max(_foot(pose.thigh_f, pose.knee_f, l1, l2),
                 _foot(pose.thigh_n, pose.knee_n, l1, l2)) + pose.hip_dy
    hip = (pose.hip_dx, hip_y)
    knee_f = _joint(hip, pose.thigh_f, l1)
    ank_f = _joint(knee_f, pose.thigh_f - pose.knee_f, l2)
    knee_n = _joint(hip, pose.thigh_n, l1)
    ank_n = _joint(knee_n, pose.thigh_n - pose.knee_n, l2)
    neck = _joint(hip, 180.0 - pose.lean, l3)
    head = _joint(neck, 180.0 - pose.lean - pose.head_tilt, hr * 1.25)
    head = (head[0] + pose.head_dx, head[1])
    # kandhe torso ke bahar rakhe gaye hain taaki baahein dikhein
    sh_n = (neck[0] + size * 0.058, neck[1] + size * 0.03)
    sh_f = (neck[0] - size * 0.014, neck[1] + size * 0.035)

    elbow_f = _joint(sh_f, pose.arm_f, lu)
    hand_f = _joint(elbow_f, pose.arm_f + pose.elbow_f, lf)
    elbow_n = _joint(sh_n, pose.arm_n, lu)
    hand_n = _joint(elbow_n, pose.arm_n + pose.elbow_n, lf)

    wl, wa = size * 0.061, size * 0.050
    coat_f, coat_n = shade(pal["coat"], -0.20), pal["coat"]
    pnt_f, pnt_n = shade(pal["pants"], -0.15), pal["pants"]
    shoe = pal["shoe"]

    out = []
    # far arm + far leg (peeche)
    out.append(limb(sh_f[0], sh_f[1], elbow_f[0], elbow_f[1], shade(pal["coat"], -0.28), wa, o, ow))
    out.append(limb(elbow_f[0], elbow_f[1], hand_f[0], hand_f[1], shade(pal["skin"], -0.22), wa * 0.86, o, ow))
    out.append(limb(hip[0], hip[1], knee_f[0], knee_f[1], pnt_f, wl, o, ow))
    out.append(limb(knee_f[0], knee_f[1], ank_f[0], ank_f[1], pnt_f, wl * 0.86, o, ow))
    out.append(limb(ank_f[0], ank_f[1], ank_f[0] + size * 0.055, ank_f[1], shade(shoe, -0.15), wl * 0.8, o, ow * 0.8))
    # torso (patla + halka taper)
    out.append(limb(hip[0], hip[1], neck[0], neck[1], coat_n, size * 0.162, o, ow))
    out.append(limb(hip[0] - size * 0.035, hip[1] + size * 0.006, hip[0] + size * 0.035, hip[1] - size * 0.004,
                    shade(pal["pants"], 0.06), size * 0.115, o, ow * 0.85))
    # scarf / accent
    out.append(limb(neck[0] - size * 0.012, neck[1] + size * 0.014,
                    neck[0] + size * 0.052, neck[1] + size * 0.058,
                    pal["accent"], size * 0.05, o, ow * 0.55))
    if art == "zombie":
        out.append(path(
            f"M {hip[0] - size * 0.05} {hip[1] - size * 0.05} l {size * 0.085} {size * 0.03} "
            f"l {-size * 0.04} {size * 0.055} l {size * 0.05} {size * 0.04}",
            "none", shade(pal["coat"], -0.35), size * 0.022))
    # head
    out.append(_face_head(head[0], head[1], hr, pal, pose, art))
    # near leg + near arm
    out.append(limb(hip[0], hip[1], knee_n[0], knee_n[1], pnt_n, wl, o, ow))
    out.append(limb(knee_n[0], knee_n[1], ank_n[0], ank_n[1], pnt_n, wl * 0.86, o, ow))
    out.append(limb(ank_n[0], ank_n[1], ank_n[0] + size * 0.055, ank_n[1], shoe, wl * 0.8, o, ow * 0.8))
    out.append(limb(sh_n[0], sh_n[1], elbow_n[0], elbow_n[1], coat_n, wa, o, ow))
    out.append(limb(elbow_n[0], elbow_n[1], hand_n[0], hand_n[1], pal["skin"], wa * 0.86, o, ow))
    out.append(circ(hand_n[0], hand_n[1], wa * 0.5, pal["skin"], o, ow * 0.6))

    body = "".join(out)
    if op is not None:
        return g("translate(0 0)", body, op=op)
    return body


# --------------------------------------------------------------------- dog ---


def render_dog(action, t, size=130.0, flip=False, op=None, mood="calm"):
    """Biscuit. `size` = shoulder height. Origin = pairon (feet) par, muh aage (right)."""
    o = OUTLINE
    ow = max(3.0, size * 0.055)
    L = size * 1.05                 # body length
    top, btm = -size * 0.99, -size * 0.47
    lw = size * 0.125
    body = DOG_PAL
    hrr = size * 0.33
    head_dy = head_dx = body_dy = 0.0
    tail_a, wag, ear_up = -38.0, 1.0, 0.0
    b = 0.0

    def leg(x0, phase, period=0.9, swing=54.0, lat=0.0, hip_y=None, knee_y=None, foot_y=None):
        hy = btm if hip_y is None else hip_y
        ky_ = (btm + size * 0.27) if knee_y is None else knee_y
        fy_ = 0.0 if foot_y is None else foot_y
        a = (math.sin(t * math.tau / period + phase) * 0.5 + 0.5) * swing - swing * 0.25
        s = math.sin(math.radians(a))
        kx, ky = x0 + s * size * 0.17, ky_
        fx, fyy = kx - s * size * 0.06, fy_
        col = shade(body["body"], lat)
        return (
            limb(x0, hy, kx, ky, col, lw, o, ow)
            + limb(kx, ky, fx, fyy, shade(col, -0.07), lw * 0.92, o, ow * 0.9)
            + limb(fx, fyy, fx + size * 0.10, fyy, shade(body["body"], -0.3), lw * 0.78, o, ow * 0.6)
        )

    bx = -L * 0.06
    front_x, back_x = bx + L * 0.30, bx - L * 0.30

    if action in ("follow", "trot", "run_dog"):
        period = {"follow": 0.9, "trot": 0.46, "run_dog": 0.34}[action]
        swing = {"follow": 54.0, "trot": 64.0, "run_dog": 72.0}[action]
        legs = [
            leg(back_x, math.pi, period, swing, lat=-0.2),      # far back
            leg(front_x, math.pi, period, swing, lat=-0.2),     # far front
            leg(back_x, 0.0, period, swing),                    # near back
            leg(front_x, 0.0, period, swing),                   # near front
        ]
        body_dy = math.sin(t * math.tau / period * 2) * size * 0.022
        tail_a = -20.0 - swing * 0.22 + math.sin(t * 10) * 12.0
    elif action == "sit":
        legs = [
            rect(back_x - size * 0.32, btm - size * 0.05, size * 0.62, size * 0.42,
                 body["body"], size * 0.18, o, ow),
            limb(front_x, btm, front_x - size * 0.02, 0, body["body"], lw, o, ow),
            limb(front_x - size * 0.02, 0, front_x + size * 0.08, 0, shade(body["body"], -0.3),
                 lw * 0.78, o, ow * 0.6),
            limb(front_x + size * 0.06, btm, front_x + size * 0.04, 0, shade(body["body"], -0.2),
                 lw * 0.95, o, ow * 0.9),
        ]
        body_dy = size * 0.16
        tail_a = 6.0 + math.sin(t * 6) * 14.0
    elif action == "bark":
        b = max(0.0, math.sin(t * 5.5))
        legs = [
            leg(back_x, math.pi, 1.0, 40.0, lat=-0.2), leg(front_x, math.pi, 1.0, 40.0, lat=-0.2),
            leg(back_x, 0.0, 1.0, 40.0), leg(front_x, 0.0, 1.0, 40.0),
        ]
        body_dy = -b * size * 0.13
        tail_a = -50.0 - b * 8.0 + math.sin(t * 20) * 18.0
        head_dy = -b * size * 0.05
    elif action == "scared":
        legs = [
            limb(back_x, btm - size * 0.06, back_x - size * 0.07, 0, shade(body["body"], -0.25), lw, o, ow),
            limb(front_x, btm - size * 0.06, front_x - size * 0.07, 0, body["body"], lw, o, ow),
            limb(front_x + size * 0.08, btm - size * 0.06, front_x + size * 0.01, 0,
                 shade(body["body"], -0.2), lw * 0.95, o, ow * 0.9),
            limb(back_x + size * 0.06, btm - size * 0.06, back_x - size * 0.01, 0,
                 shade(body["body"], -0.3), lw * 0.9, o, ow * 0.85),
        ]
        body_dy = size * 0.16 + math.sin(t * 13) * size * 0.008
        tail_a = 24.0
        head_dy = size * 0.06
        ear_up = -1.0
    elif action == "sniff":
        legs = [
            leg(back_x, math.pi, 1.1, 42.0, lat=-0.2), leg(front_x, math.pi, 1.1, 42.0, lat=-0.2),
            leg(back_x, 0.0, 1.1, 42.0), leg(front_x, 0.0, 1.1, 42.0),
        ]
        body_dy = size * 0.03
        head_dy = size * 0.30
        head_dx = size * 0.14
        tail_a = -14.0 + math.sin(t * 4) * 9.0
        wag = 0.25
    else:  # wag / stand (default)
        legs = [
            leg(back_x, math.pi, 1.0, 44.0, lat=-0.2), leg(front_x, math.pi, 1.0, 44.0, lat=-0.2),
            leg(back_x, 0.0, 1.0, 44.0), leg(front_x, 0.0, 1.0, 44.0),
        ]
        tail_a = -44.0
        wag = 1.0

    by = top + body_dy + size * 0.25
    body_g = (
        rect(bx - L * 0.5, by - size * 0.25, L, size * 0.5, body["body"], size * 0.21, o, ow)
        + rect(bx - L * 0.3, by + size * 0.12, L * 0.62, size * 0.14, body["belly"], size * 0.07)
    )
    tx, ty = bx - L * 0.46, by - size * 0.12
    ta = tail_a + math.sin(t * 11.0 * wag) * (16.0 * wag)
    tail = limb(tx, ty, tx - math.cos(math.radians(ta)) * size * 0.56,
                ty - math.sin(math.radians(ta)) * size * 0.56, body["body"], size * 0.095, o, ow * 0.75)

    hx, hy = bx + L * 0.48 + head_dx, top + size * 0.10 + head_dy
    ear = path(
        f"M {hx - hrr * 0.62} {hy - hrr * 0.62} q {-hrr * 0.95} {hrr * 0.1 + ear_up * hrr * 0.5} "
        f"{-hrr * 0.72} {hrr * 0.95 + ear_up * hrr * 0.7} "
        f"q {hrr * 0.6} {hrr * 0.15} {hrr * 0.86} {-hrr * 0.42} Z",
        shade(body["body"], -0.24), o, ow * 0.7)
    head = (
        ear
        + circ(hx, hy, hrr, body["body"], o, ow)
        + path(f"M {hx + hrr * 0.15} {hy + hrr * 0.1} q {hrr * 0.95} {-hrr * 0.1} {hrr * 1.02} {hrr * 0.34} "
               f"q {-hrr * 0.35} {hrr * 0.4} {-hrr * 1.0} {hrr * 0.3} Z",
               shade(body["body"], 0.14), o, ow * 0.7)
        + circ(hx + hrr * 1.1, hy + hrr * 0.34, hrr * 0.17, body["nose"])
        + circ(hx + hrr * 0.26, hy - hrr * 0.1, hrr * 0.14, "#1c1c20")
        + circ(hx + hrr * 0.3, hy - hrr * 0.15, hrr * 0.05, "#ffffff", op=0.85)
    )
    if action == "bark":
        head += ell(hx + hrr * 1.0, hy + hrr * 0.72, hrr * 0.28, hrr * 0.2, "#3a1f22", o, ow * 0.45)
    collar = rect(hx - hrr * 1.16, hy + hrr * 0.52, hrr * 0.42, hrr * 0.44,
                  DOG_PAL["collar"], hrr * 0.09, o, ow * 0.45)
    neck_g = limb(bx + L * 0.32, by - size * 0.04, hx - hrr * 0.45, hy + hrr * 0.18,
                  shade(body["body"], -0.08), size * 0.21, o, ow)

    inner = legs[0] + legs[1] + tail + body_g + neck_g + legs[2] + legs[3] + collar + head
    if flip:
        inner = g("scale(-1 1)", inner)
    if op is not None:
        inner = g("translate(0 0)", inner, op=op)
    return inner


# ------------------------------------------------------------------ actor ----


def render_actor(who, action, t, size=430.0, flip=False, op=None, art=None):
    """who: max | ada | old | zombie | biscuit. action ko pose/anim mein map karta hai."""
    if who == "biscuit":
        return render_dog(action, t, size=size * 0.3, flip=flip, op=op)
    a = art or ROLE_ART.get(who, "boy")
    pal = PALETTES[a]
    act = action
    if a == "zombie":
        act = {"reach": "reach_z", "idle": "still", "walk": "shamble"}.get(action, action)
    fn = HUMAN_ACTIONS.get(act) or HUMAN_ACTIONS["idle"]
    return render_human(pal, fn(t), size=size, art=a, op=op)
