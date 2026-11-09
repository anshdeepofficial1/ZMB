"""Canonical art direction for ALL ZMB animated story assets.

The production target is a premium ORIGINAL stylized 3D animated thriller,
NOT live-action photorealism and NOT the legacy simplistic SVG cartoon.
This module centralizes positive/negative prompts to prevent style drift
between first-frame generation and image-to-video generation.
"""
from __future__ import annotations

STYLE_ID = "zmb_premium_animated_3d_v1"

LOOK = (
    "PREMIUM ORIGINAL 3D ANIMATED FEATURE FILM, stylized cinematic survival "
    "horror, sophisticated hand-crafted CGI aesthetic rather than live action. "
    "Distinctively ADULT animated faces and adult body proportions, "
    "angular mature silhouettes, subtle expressive brows and natural "
    "animated eyes rather than child-sized oversized eyes, sculpted hair, clean "
    "animated skin shaders, detailed stylized fabric, meticulously modeled "
    "objects and atmospheric volumetric fog. Cohesive animated character "
    "design as if every shot belongs to the SAME one feature film. "
    "High-end physically coherent animation with painterly PBR materials, "
    "not hyperreal flesh, not a real photographic person, not a live-action "
    "movie. Deep midnight navy and dark teal shadows contrasted against "
    "selective warm tungsten amber headlights and dashboard lights, "
    "dim red danger accents, sharp readable silhouettes, cinematic bounce "
    "lighting and rich controlled gradients, not washed out. "
    "Designed lens composition and cinematic depth, original art direction. "
)

CHARACTER_LOCK = (
    "The same original animated Max in every shot: a slim young adult survivor, "
    "tousled dark hair, distinct tired eyebrows and oval animated face, "
    "charcoal hooded jacket with rust-red seam, dark shirt, brown cargo pants. "
    "The same Biscuit in every shot: small tan stylized 3D dog with two darker "
    "floppy ears, dark muzzle, cream chest, red collar, anatomically coherent. "
    "Never replace, multiply, morph or redesign their faces, clothing, fur, "
    "proportions or silhouette between shots. "
)

SCENE_LOCK = (
    "Same single late-2000s dusty steel-blue-gray sedan, narrow angular "
    "headlights, silver five-spoke wheels, black cloth seats and dark dashboard. "
    "Same isolated gas station architecture, weathered canopy, three pump "
    "islands and locked glass storefront whenever it appears. No new vehicles, "
    "unmotivated objects or costume changes. "
)

NEGATIVE = (
    "NEGATIVE: photorealistic live-action humans, real photograph, "
    "uncanny real skin, selfie, documentary, gritty real camera photo, "
    "flat 2D shapes, simple vector cartoon, stick figures, puppet animation, "
    "cutout sprites, game screenshot, low-poly primitive characters, "
    "plastic dolls, neon oversaturation, muddy unreadable blacks, "
    "empty upper half of vertical frame, floating limbs, bad hands, "
    "duplicated fingers, body hanging outside car, random characters, "
    "inconsistent car shape, morphing, slideshow, static zoom, "
    "text, subtitles, typography, watermark, logo and game UI. "
)

COMPOSITION = (
    "Vertical 9:16 mobile animation; frame the meaningful story action "
    "at readable medium or close scale in the CENTRAL 70 percent. "
    "Keep moving characters and important props visible, leave an "
    "unobstructed lower-third area for editorial subtitles, no giant "
    "empty sky, avoid tiny people at the bottom. "
)

SHOT_ZERO = (
    "EXACT TIME 2:47 AM, PITCH-DARK DESERTED HIGHWAY. Premium 3D animated "
    "THRILLER opening, INSIDE a single steel-blue sedan. Camera bolted to "
    "the FRONT PASSENGER SIDE, in a tight medium shot looking diagonally "
    "toward Max and through the FRONT WINDSHIELD, steering wheel clearly "
    "visible foreground. Max is a distinctly ADULT male in his mid-20s, "
    "lean and tired, mature animated face not a child, charcoal jacket. "
    "Max sits FULLY SEATED and belted INSIDE the car, both properly formed "
    "hands touching the steering wheel, no hands or arms outside. "
    "The dark wet HIGHWAY road, lane stripes and faint fog are visible "
    "THROUGH the glass behind the dashboard. Background EMPTY rural road "
    "at midnight: NO gas station, no houses, no shop, no sunset, NO dawn, "
    "no bright blue morning sky. Near-black blue-black outside with "
    "limited cool teal headlight beams, subtle glowing AMBER instrument "
    "lights softly illuminate Max's cheek and fingers. High contrast "
    "animated film lighting with face and wheel both readable. "
    "ONLY Max is VISIBLE in this shot, NO dog in Max's lap, on dashboard, "
    "or obscuring driver's hands. Max and camera remain fully inside car. "
)

def style_header() -> str:
    # Do not mention the entire cast or gas station in EVERY shot.
    # Doing so can insert a dog/station into a lone-driver highway opener.
    return f"ZMB STYLE {STYLE_ID}. " + LOOK + COMPOSITION

def scene_prompt(shot: dict) -> str:
    if not str(shot.get("physical_direction") or "").strip():
        raise ValueError("Missing physical action; cannot invent video scene")
    framed = SHOT_ZERO if int(shot.get("index", -1)) == 0 else (
        "A carefully story-boarded stylized 3D feature-animation medium shot "
        "with clear character facial acting and physical prop interactions. "
    )
    characters = " ".join(
        f"VISIBLE CHARACTER {person['id']}: {person['identity']}. "
        for person in shot.get("characters", [])
        if not (int(shot.get("index", -1)) == 0 and person["id"] == "biscuit")
    )
    props = " ".join(
        f"CONSISTENT DESIGN {item['id']}: {item['identity']}. "
        for item in shot.get("prop_references", [])
    )
    return (
        style_header() + framed + characters + props
        + "EXACT PHYSICAL EVENT: " + str(shot["physical_direction"]) + ". "
        + "Make this frame an original beautifully designed 3D animated "
        "film still, showing the exact event before the motion begins. "
        + NEGATIVE
    )

def animation_prompt(shot: dict) -> str:
    action = str(shot.get("physical_direction") or "").strip()
    if not action:
        raise ValueError("Missing physical action; cannot invent animation")
    movement = (
        "Max stays buckled INSIDE the vehicle as it DRIVES forward, with "
        "the road lines moving naturally past the windscreen and headlights "
        "visibly pulsing through dark moonlit fog. His hands remain properly "
        "on the wheel with believable minor steering corrections, "
        "his animated adult face remains mature and consistent. "
        "NO dog enters the shot, NO gas station, NO daylight. "
        if int(shot.get("index", -1)) == 0 else
        "Animate the intended character/prop interaction with convincing "
        "keyframed-style easing and momentum; keep action continuous. "
    )
    return (
        "ONE CONTINUOUS SHOT from the same premium stylized 3D ANIMATED "
        "survival-thriller feature film. Not live action. "
        "Animate the exact scene composition and original animated character "
        "faces in the source frame. DO NOT change wardrobe, props, "
        "vehicle design, lighting identity or scene geography. "
        "STORY ACTION: " + action + ". " + movement +
        "Purposeful character acting, coherent animated biomechanics, "
        "physically believable object motion, smooth camera tracking, "
        "atmospheric moonlit fog and warm amber practical highlights. "
        "Maintain original 3D animated look in EVERY frame, not a cut to "
        "photographic footage. No static slide or false zoom; the narrated "
        "physical event must visibly occur. " + NEGATIVE
    )
