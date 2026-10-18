"""Dev preview: ek scene + characters + caption ka single frame render karo.

Usage (Windows):
  python scripts/preview.py --place gas_station --time night --mood danger \
      --cast max:walk,biscuit:follow --caption "Biscuit, stay close." --out out/prev1.png

  python scripts/preview.py --sheet            # sab scenes ka contact sheet
"""
from __future__ import annotations

import argparse
import os
import sys
import time as _time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import characters as ch
import scenes as sc
import svgkit as sk

ROOT = Path(__file__).resolve().parents[1]
FONT_FILES = [
    ROOT / "assets" / "fonts" / "ArchivoBlack-Regular.ttf",
    ROOT / "assets" / "fonts" / "Barlow-Bold.ttf",
    ROOT / "assets" / "fonts" / "Barlow-Medium.ttf",
]

W, H = 1080, 1920
GROUND = sc.GROUND


def compose(place, tname, mood, cast, caption=None, hud=None, seed=1, zoom=1.0, fx=540.0):
    defs, layers = sc.build(place, tname, mood, seed)
    cam_x = fx - W / 2.0
    body = []
    for k, svg in layers:
        dx = cam_x * (1.0 - k)
        body.append(sk.g(f"translate({sk.n(dx)} 0)", svg))
    # actors
    n_actors = max(1, len(cast))
    spread = 190.0
    start = fx - spread * (n_actors - 1) / 2.0
    for i, item in enumerate(cast):
        who, act = (item if isinstance(item, (list, tuple)) else (item, "idle"))
        size = 430.0
        ax = start + i * spread
        if who == "biscuit":
            ax += 40
        disp = ch.render_actor(who, act, 1.1, size=size, flip=(i % 2 == 1))
        body.append(sk.g(f"translate({sk.n(ax)} {sk.n(GROUND)})", disp))
    tint, ta = sc.mood_tint(mood)
    overlay = sk.rect(0, 0, W, H, tint, op=ta)
    content = "".join(body)
    if hud:
        content += hud_layer(hud)
    if caption:
        content += caption_layer(caption)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'viewBox="0 0 {W} {H}"><defs>{defs}{_extra_defs()}</defs>{content}{overlay}</svg>'
    )


def _extra_defs():
    return (
        sk.lin_grad("cap_scrim", [(0, "#05070d", 0.0), (35, "#05070d", 0.55), (100, "#05070d", 0.92)])
        + sk.lin_grad("vig", [(0, "#05070d", 0.5), (100, "#05070d", 0.0)], x1=0, y1=0, x2=0, y2=1)
    )


def caption_layer(text, y=1620, size=52):
    s = sk.rect(0, y - 110, W, H - (y - 110), "url(#cap_scrim)")
    s += sk.text(W / 2, y, text, size, "Barlow", "#ffffff", weight="bold", stroke="#080c14", sw=9)
    return s


def hud_layer(hud):
    return ""


def render(svg, out, width=540, height=960):
    import resvg_py

    png = resvg_py.svg_to_bytes(
        svg_string=svg,
        font_files=[str(p) for p in FONT_FILES],
        skip_system_fonts=True,
        width=width,
        height=height,
    )
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    Path(out).write_bytes(png)
    return len(png)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--place", default="highway")
    ap.add_argument("--time", default="night")
    ap.add_argument("--mood", default="tense")
    ap.add_argument("--cast", default="max:walk,biscuit:follow")
    ap.add_argument("--caption", default="Biscuit, stay close.")
    ap.add_argument("--out", default="out/prev.png")
    ap.add_argument("--w", type=int, default=540)
    ap.add_argument("--h", type=int, default=960)
    ap.add_argument("--seed", type=int, default=1)
    args = ap.parse_args()
    cast = [c.split(":") for c in args.cast.split(",") if c]
    svg = compose(args.place, args.time, args.mood, cast, args.caption, seed=args.seed)
    t0 = _time.time()
    size = render(svg, args.out, args.w, args.h)
    print(f"{args.out}  {size/1024:.0f} KB  {( _time.time()-t0)*1000:.0f} ms  ({args.w}x{args.h})")


if __name__ == "__main__":
    main()
