"""Tiny SVG builder helpers for the cartoon renderer.

Sab kuch string-based hai — koi external SVG library nahi. Coordinates
"design space" mein hain: 1080 x 1920 (camera viewBox isi ko crop karta hai).
"""
from __future__ import annotations

import math

# ---------------------------------------------------------------- numbers ----


def n(x) -> str:
    """Compact number formatting (SVG output chhota rakhne ke liye)."""
    if isinstance(x, bool):
        return "1" if x else "0"
    if isinstance(x, int):
        return str(x)
    s = f"{float(x):.2f}".rstrip("0").rstrip(".")
    return s if s not in ("", "-0") else "0"


def esc(s) -> str:
    return (
        str(s)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


# ------------------------------------------------------------------ math -----


def dirv(angle_deg: float) -> tuple[float, float]:
    """Unit vector: 0 deg = straight down, + = forward (right)."""
    r = math.radians(angle_deg)
    return (math.sin(r), math.cos(r))


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def ease(t: float) -> float:
    """Smooth ease-in-out (camera + card motion ke liye)."""
    t = clamp(t, 0.0, 1.0)
    return t * t * (3 - 2 * t)


def ease_out(t: float) -> float:
    t = clamp(t, 0.0, 1.0)
    return 1 - (1 - t) ** 3


def ease_in(t: float) -> float:
    t = clamp(t, 0.0, 1.0)
    return t ** 3


def mix(c1: str, c2: str, t: float) -> str:
    """Do hex colors ko blend karo."""
    t = clamp(t, 0.0, 1.0)

    def rgb(c):
        c = c.lstrip("#")
        return tuple(int(c[i : i + 2], 16) for i in (0, 2, 4))

    a, b = rgb(c1), rgb(c2)
    out = tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3))
    return "#%02x%02x%02x" % out


def shade(color: str, amount: float) -> str:
    """amount < 0 = darker, > 0 = lighter."""
    if amount < 0:
        return mix(color, "#000000", -amount)
    return mix(color, "#ffffff", amount)


# ------------------------------------------------------------------ defs -----


def lin_grad(gid: str, stops, x1=0.0, y1=0.0, x2=0.0, y2=1.0) -> str:
    body = "".join(
        f'<stop offset="{n(o)}%" stop-color="{c}" stop-opacity="{n(op)}"/>'
        for o, c, op in stops
    )
    return (
        f'<linearGradient id="{gid}" x1="{n(x1)}" y1="{n(y1)}" '
        f'x2="{n(x2)}" y2="{n(y2)}">{body}</linearGradient>'
    )


def rad_grad(gid: str, stops, cx=0.5, cy=0.5, r=0.5) -> str:
    body = "".join(
        f'<stop offset="{n(o)}%" stop-color="{c}" stop-opacity="{n(op)}"/>'
        for o, c, op in stops
    )
    return f'<radialGradient id="{gid}" cx="{n(cx)}" cy="{n(cy)}" r="{n(r)}">{body}</radialGradient>'


def glow(cx: float, cy: float, r: float, gid: str, op: float = 1.0) -> str:
    o = f' opacity="{n(op)}"' if op != 1.0 else ""
    return f'<circle cx="{n(cx)}" cy="{n(cy)}" r="{n(r)}" fill="url(#{gid})"{o}/>'


# --------------------------------------------------------------- shapes ------


def rect(x, y, w, h, fill, rx=0, stroke=None, sw=0, op=None) -> str:
    s = f'<rect x="{n(x)}" y="{n(y)}" width="{n(w)}" height="{n(h)}" fill="{fill}"'
    if rx:
        s += f' rx="{n(rx)}"'
    if stroke and sw:
        s += f' stroke="{stroke}" stroke-width="{n(sw)}"'
    if op is not None:
        s += f' opacity="{n(op)}"'
    return s + "/>"


def circ(cx, cy, r, fill, stroke=None, sw=0, op=None) -> str:
    s = f'<circle cx="{n(cx)}" cy="{n(cy)}" r="{n(r)}" fill="{fill}"'
    if stroke and sw:
        s += f' stroke="{stroke}" stroke-width="{n(sw)}"'
    if op is not None:
        s += f' opacity="{n(op)}"'
    return s + "/>"


def ell(cx, cy, rx, ry, fill, stroke=None, sw=0, op=None, rotate=None) -> str:
    s = f'<ellipse cx="{n(cx)}" cy="{n(cy)}" rx="{n(rx)}" ry="{n(ry)}" fill="{fill}"'
    if stroke and sw:
        s += f' stroke="{stroke}" stroke-width="{n(sw)}"'
    if op is not None:
        s += f' opacity="{n(op)}"'
    if rotate:
        s += f' transform="rotate({n(rotate)} {n(cx)} {n(cy)})"'
    return s + "/>"


def path(d, fill="none", stroke=None, sw=0, op=None, cap="round", join="round") -> str:
    s = f'<path d="{d}" fill="{fill}"'
    if stroke and sw:
        s += f' stroke="{stroke}" stroke-width="{n(sw)}" stroke-linecap="{cap}" stroke-linejoin="{join}"'
    if op is not None:
        s += f' opacity="{n(op)}"'
    return s + "/>"


def line(x1, y1, x2, y2, color, w, cap="round", op=None, dash=None) -> str:
    s = (
        f'<line x1="{n(x1)}" y1="{n(y1)}" x2="{n(x2)}" y2="{n(y2)}" '
        f'stroke="{color}" stroke-width="{n(w)}" stroke-linecap="{cap}"'
    )
    if dash:
        s += f' stroke-dasharray="{dash}"'
    if op is not None:
        s += f' opacity="{n(op)}"'
    return s + "/>"


def limb(x1, y1, x2, y2, color, w, outline=None, ow=0, cap="round", op=None) -> str:
    """Cartoon limb: pehle outline (mota), phir fill (patla)."""
    s = ""
    if outline and ow:
        s += line(x1, y1, x2, y2, outline, w + ow * 2, cap=cap, op=op)
    s += line(x1, y1, x2, y2, color, w, cap=cap, op=op)
    return s


def g(transform: str, content: str, op=None) -> str:
    o = f' opacity="{n(op)}"' if op is not None else ""
    return f'<g transform="{transform}"{o}>{content}</g>'


def text(
    x,
    y,
    s,
    size,
    font="Archivo Black",
    fill="#ffffff",
    anchor="middle",
    stroke=None,
    sw=0,
    ls=None,
    op=None,
    weight="normal",
) -> str:
    parts = [
        f'<text x="{n(x)}" y="{n(y)}" font-family="{font}" font-size="{n(size)}"',
        f' fill="{fill}" text-anchor="{anchor}"',
    ]
    if weight != "normal":
        parts.append(f' font-weight="{weight}"')
    if stroke and sw:
        parts.append(f' stroke="{stroke}" stroke-width="{n(sw)}" stroke-linejoin="round"'
                     f' paint-order="stroke"')
    if ls is not None:
        parts.append(f' letter-spacing="{n(ls)}"')
    if op is not None:
        parts.append(f' opacity="{n(op)}"')
    parts.append(f">{esc(s)}</text>")
    return "".join(parts)


def tspan(x, y, s, fill, weight="normal", dx=None) -> str:
    d = f' x="{n(x)}" y="{n(y)}"' if x is not None else ""
    if dx is not None:
        d += f' dx="{n(dx)}"'
    w = f' font-weight="{weight}"' if weight != "normal" else ""
    return f'<tspan{d} fill="{fill}"{w}>{esc(s)}</tspan>'
