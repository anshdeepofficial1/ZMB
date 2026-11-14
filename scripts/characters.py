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

OUTLINE = "#122438"

PALETTES = {
    "boy": dict(
        skin="#f5bd96", hair="#142c43", coat="#167f97", pants="#75614d",
        shoe="#1a3145", accent="#ffce62",
    ),
    "girl": dict(
        skin="#f1b996", hair="#402238", coat="#b14c7b", pants="#3c6378",
        shoe="#1a3145", accent="#ffe083",
    ),
    "old": dict(
        skin="#f0bf9b", hair="#e0eae9", coat="#b57c4f", pants="#526779",
        shoe="#1a3145", accent="#73d8d6",
    ),
    "zombie": dict(
        skin="#a1c184", hair="#3d655d", coat="#568473", pants="#3e5550",
        shoe="#1b3532", accent="#ef8b77",
    ),
}

DOG_PAL = dict(
    body="#f6b95f", belly="#ffedcc", nose="#1f2b3f",
    collar="#ff5e5e", tongue="#e2748a",
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


def pose_walk_flashlight(t):
    """Natural stride, arm raised forward to HOLD the real handheld light."""
    p=pose_walk(t)
    p.arm_n=83.0+2.3*math.sin(t*2.8)
    p.elbow_n=-8.0
    p.mouth="line"
    return p


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
    "idle": pose_idle, "walk": pose_walk, "walk_flashlight": pose_walk_flashlight,
    "run": pose_run, "sneak": pose_sneak,
    "crouch": pose_crouch, "check": pose_check, "reach": pose_reach,
    "point": pose_point, "look": pose_look, "call": pose_call,
    "climb": pose_climb, "sit": pose_sit,
    "shamble": pose_shamble, "reach_z": pose_zreach, "still": pose_zstill,
}


# --------------------------------------------------------------- rendering ---


def _face_head(px, py, hr, pal, pose, art):
    """Designed 2D graphic-novel head, stable identity; never an AI portrait."""
    o = OUTLINE
    out = []
    if art == "girl":
        out.append(path(
            f"M {n(px-hr*.8)} {n(py-hr*.5)} Q {n(px-hr*1.5)} {n(py)} "
            f"{n(px-hr*1.04)} {n(py+hr*1.3)} L {n(px-hr*.25)} {n(py+hr*.7)} Z",
            shade(pal["hair"],-.1),o,hr*.1))
    if art == "old":
        out.append(path(
            f"M {n(px-hr*1.2)} {n(py-hr*.5)} L {n(px+hr*1.1)} {n(py-hr*.4)} "
            f"L {n(px+hr*.8)} {n(py-hr*1.25)} L {n(px-hr)} {n(py-hr*1.2)} Z",
            "#ffca85",o,hr*.12))
    # Angular hair mass with side locks.
    out.append(path(
        f"M {n(px-hr)} {n(py+hr*.17)} Q {n(px-hr*1.25)} {n(py-hr*.95)} "
        f"{n(px-hr*.29)} {n(py-hr*1.27)} Q {n(px+hr*.57)} {n(py-hr*1.49)} "
        f"{n(px+hr*1.07)} {n(py-hr*.46)} L {n(px+hr*.8)} {n(py+hr*.24)} Z",
        pal["hair"],o,hr*.17))
    # Faceted lower jaw instead of oversized flat circle.
    out.append(path(
        f"M {n(px-hr*.7)} {n(py-hr*.36)} Q {n(px-hr*.18)} {n(py-hr*.72)} "
        f"{n(px+hr*.56)} {n(py-hr*.55)} L {n(px+hr*1.02)} {n(py-hr*.18)} "
        f"L {n(px+hr*.87)} {n(py+hr*.55)} L {n(px+hr*.32)} {n(py+hr*.92)} "
        f"Q {n(px-hr*.52)} {n(py+hr*.72)} {n(px-hr*.7)} {n(py-hr*.36)} Z",
        pal["skin"],o,hr*.14))
    out.append(path(
        f"M {n(px+hr*.22)} {n(py-hr*.42)} L {n(px+hr*.87)} {n(py-hr*.06)} "
        f"Q {n(px+hr*.64)} {n(py+hr*.4)} {n(px+hr*.29)} {n(py+hr*.46)}",
        "none",shade(pal["skin"],-.22),hr*.12,op=.68))
    out.append(ell(px-hr*.69,py+hr*.01,hr*.18,hr*.28,pal["skin"],o,hr*.11))
    for ex in (px-hr*.13,px+hr*.45):
        ey=py-hr*.02
        out.append(ell(ex,ey,hr*.14,hr*.145,"#fff9f0",o,hr*.07))
        out.append(ell(ex+hr*.04,ey+hr*.01,hr*.072,hr*.102,"#193d55"))
        out.append(circ(ex+hr*.065,ey-hr*.04,hr*.028,"#ffffff"))
        out.append(line(ex-hr*.19,ey-hr*.28+pose.brow*.32,
                        ex+hr*.15,ey-hr*.38+pose.brow*.32,
                        pal["hair"],hr*.12))
    out.append(path(
        f"M {n(px+hr*.55)} {n(py+hr*.13)} l {n(hr*.24)} {n(hr*.16)} "
        f"l {n(-hr*.25)} {n(hr*.035)}",
        "none",shade(pal["skin"],-.35),hr*.095))
    mx,my=px+hr*.31,py+hr*.59
    if pose.mouth=="open":
        out.append(ell(mx,my,hr*.2,hr*.18,"#432932",o,hr*.075))
        out.append(ell(mx,my+hr*.06,hr*.09,hr*.05,"#e8899a"))
    else:
        out.append(path(
            f"M {n(mx-hr*.2)} {n(my)} Q {n(mx)} {n(my-hr*.12)} "
            f"{n(mx+hr*.22)} {n(my-hr*.03)}",
            "none",o,hr*.095))
    if art=="zombie":
        out.append(line(px-hr*.24,py+hr*.32,px+hr*.1,py+hr*.40,
                        "#f08388",hr*.12))
    # Signature sharp three tufts, stable at every frame/pose.
    out.append(path(
        f"M {n(px-hr*.97)} {n(py-hr*.45)} L {n(px-hr*.96)} {n(py-hr*1.23)} "
        f"L {n(px-hr*.34)} {n(py-hr*.96)} L {n(px+hr*.02)} {n(py-hr*1.39)} "
        f"L {n(px+hr*.34)} {n(py-hr*.96)} L {n(px+hr*.81)} {n(py-hr*.99)} "
        f"L {n(px+hr*.87)} {n(py-hr*.46)} Q {n(px)} {n(py-hr*.75)} "
        f"{n(px-hr*.97)} {n(py-hr*.45)} Z",pal["hair"],o,hr*.065))
    out.append(path(
        f"M {n(px-hr*.66)} {n(py-hr*.84)} Q {n(px-hr*.05)} {n(py-hr*1.13)} "
        f"{n(px+hr*.3)} {n(py-hr*.98)}",
        "none",shade(pal["hair"],.32),hr*.09,op=.68))
    return "".join(out)



def render_human(pal, pose: Pose, size=430.0, art="boy", op=None, held_prop=None, backpack=False):
    l1, l2 = size * 0.235, size * 0.225
    l3 = size * 0.33
    lu, lf = size * 0.16, size * 0.155
    hr = size * 0.103
    o = OUTLINE
    ow = max(4.0, size * 0.014)

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
    if backpack:
        # Same strapped rust-brown rucksack across every post-exit scene;
        # local skeleton coordinates preserve identity during motion/camera.
        px=neck[0]-size*.092
        py=neck[1]+size*.070
        out.append(path(
            f"M {n(px)} {n(py)} "
            f"Q {n(px-size*.090)} {n(py-size*.018)} {n(px-size*.116)} {n(py+size*.097)} "
            f"L {n(hip[0]-size*.085)} {n(hip[1]-size*.03)} "
            f"Q {n(hip[0]-size*.018)} {n(hip[1]+size*.006)} "
            f"{n(hip[0]+size*.007)} {n(hip[1]-size*.08)} "
            f"L {n(px+size*.032)} {n(py+size*.02)} Z",
            "#965533",o,ow*1.22))
        out.append(path(
            f"M {n(px-size*.070)} {n(py+size*.025)} "
            f"L {n(px+size*.008)} {n(py+size*.021)} "
            f"M {n(px-size*.073)} {n(py+size*.097)} "
            f"L {n(px+size*.005)} {n(py+size*.090)}",
            "none","#eebc72",max(3.0,size*.011)))
    # Structured 2D jacket silhouette (shoulders + taper + zipped front).
    # Moves with the real articulated skeleton; not an overlay sticker.
    out.append(path(
        f"M {n(neck[0]-size*.066)} {n(neck[1]+size*.003)} "
        f"Q {n(neck[0]-size*.12)} {n(neck[1]+size*.045)} "
        f"{n(neck[0]-size*.106)} {n(neck[1]+size*.115)} "
        f"L {n(hip[0]-size*.084)} {n(hip[1]-size*.024)} "
        f"L {n(hip[0]+size*.076)} {n(hip[1]-size*.024)} "
        f"L {n(neck[0]+size*.102)} {n(neck[1]+size*.113)} "
        f"Q {n(neck[0]+size*.11)} {n(neck[1]+size*.037)} "
        f"{n(neck[0]+size*.065)} {n(neck[1]+size*.006)} Z",
        coat_n,o,ow*1.25))
    out.append(limb(hip[0] - size * 0.035, hip[1] + size * 0.006, hip[0] + size * 0.035, hip[1] - size * 0.004,
                    shade(pal["pants"], 0.06), size * 0.115, o, ow * 0.85))
    # Designed graphic-novel jacket: zipper, raised collar and pocket marks.
    out.append(path(
        f"M {n(neck[0]-size*.06)} {n(neck[1]+size*.012)} "
        f"L {n(neck[0]+size*.012)} {n(neck[1]+size*.095)} "
        f"L {n(hip[0]+size*.025)} {n(hip[1]-size*.048)} "
        f"L {n(neck[0]-size*.023)} {n(neck[1]+size*.026)} Z",
        shade(pal["coat"],.26),op=.92))
    out.append(line(neck[0]+size*.012,neck[1]+size*.095,
                    hip[0]+size*.023,hip[1]-size*.04,
                    pal["accent"],max(3.0,size*.012)))
    out.append(path(
        f"M {n(hip[0]-size*.053)} {n(hip[1]-size*.13)} l {n(size*.031)} {n(size*.02)} "
        f"M {n(hip[0]+size*.036)} {n(hip[1]-size*.12)} l {n(size*.030)} {n(size*.01)}",
        "none",shade(pal["coat"],.38),max(2.0,size*.009)))
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
    if held_prop == "flashlight":
        # Handheld beam shares the near-hand joint every frame. This is not
        # the disembodied flashlight that previously drifted across the scene.
        out.append(g(
            f"translate({n(hand_n[0])} {n(hand_n[1])}) rotate({n(-5.5+(pose.arm_n-83.0)*.65)})",
            path("M 38 -14 L 440 -145 L 440 175 Z",
                 "#fff3a4",op=.17)
            + ell(385,13,88,112,"#fff0b2",op=.07)
            + rect(-8,-11,69,22,"#263a4d",8,
                   stroke="#ffc96c",sw=4)
            + rect(15,-12,7,25,"#a1bed0",3)
            + circ(63,0,15,"#fff8c1",stroke="#f4c77b",sw=3)))


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
        + ell(bx-L*.1,by-size*.11,L*.28,size*.11,"#ffe6b0",op=.76)
        + circ(bx-L*.31,by-size*.07,size*.083,"#d88340",op=.72)
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
    collar += circ(hx-hrr*.79,hy+hrr*.92,hrr*.15,"#ffda76",o,ow*.25)
    neck_g = limb(bx + L * 0.32, by - size * 0.04, hx - hrr * 0.45, hy + hrr * 0.18,
                  shade(body["body"], -0.08), size * 0.21, o, ow)

    inner = legs[0] + legs[1] + tail + body_g + neck_g + legs[2] + legs[3] + collar + head
    if flip:
        inner = g("scale(-1 1)", inner)
    if op is not None:
        inner = g("translate(0 0)", inner, op=op)
    return inner


# ------------------------------------------------------------------ actor ----


def render_actor(who, action, t, size=430.0, flip=False, op=None, art=None, backpack=False):
    """who: max | ada | old | zombie | biscuit. action ko pose/anim mein map karta hai."""
    if who == "biscuit":
        return render_dog(action, t, size=size * 0.3, flip=flip, op=op)
    a = art or ROLE_ART.get(who, "boy")
    pal = PALETTES[a]
    act = action
    if a == "zombie":
        act = {"reach": "reach_z", "idle": "still", "walk": "shamble"}.get(action, action)
    fn = HUMAN_ACTIONS.get(act) or HUMAN_ACTIONS["idle"]
    return render_human(
        pal, fn(t), size=size, art=a, op=op,
        held_prop="flashlight" if act == "walk_flashlight" else None,
        backpack=backpack
    )
