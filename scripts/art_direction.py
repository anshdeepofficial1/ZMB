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
    "Expressive deliberately-designed animated adult faces with softly "
    "stylized proportions, distinctive silhouettes, sculpted hair, clean "
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
    "Interior passenger-seat camera in a designed 3D animated car cabin, "
    "looking diagonally at Max, who is FULLY SEATED with his seatbelt on. "
    "His animated face, torso and hands on the steering wheel are plainly "
    "visible. His arms, legs and head remain entirely INSIDE the car. "
    "Dark cabin and cyan fog beyond the windshield, warm amber dashboard "
    "shines on his cheek and hands. Wet highway lane markings move past "
    "the glass, headlights flicker ahead, wheel movement grounded. "
    "Biscuit is a small tan animated dog sitting naturally on the passenger "
    "side; no extra people, no limbs outside a car window. "
)

def style_header() -> str:
    return f"ZMB STYLE {STYLE_ID}. " + LOOK + CHARACTER_LOCK + SCENE_LOCK + COMPOSITION

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
        "clearly rotating wheels and environment moving naturally past "
        "the windscreen. His hands make believable minor wheel corrections, "
        "headlights visibly pulse, Biscuit stays seated. "
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
