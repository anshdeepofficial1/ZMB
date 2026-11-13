---
name: zmb-faceless-2d
description: Improve ZMB's original code-drawn 2D horror reels with precise narration-driven actions, expressive acting, strong composition and animation continuity.
---
# ZMB faceless 2D animation lab
Use this skill for a code-only candidate, not AI image or video generation. Inspired by the code-driven faceless shorts workflow; this is an original ZMB skill, not the downloaded Nafay package.
1. Read content/cast_bible.json, content/scenarios.json, content/shot_directions.json and scripts/visual_manifest.py. Preserve the Day 1 narration and cast. Every narrated physical action must appear visibly and in the right order.
2. Read scripts/characters.py, scripts/scenes.py, scripts/animate.py and scripts/svgkit.py. Improve original SVG acting, pose transitions, staging, prop attachment, car movement, shot composition and lighting. Do not import external assets, use diffusion, 3D, or stock footage.
3. Make concrete code edits only to scripts/characters.py, scripts/scenes.py and scripts/animate.py. Keep public interfaces and exact story timing. Improve the opening hook, expressions, readable silhouettes, teal/amber contrast and movement. Avoid repetitive generic loops or captions covering important actions.
4. Do not change narration, publishing, state, workflows, credentials, dependencies, tests or verification scripts. No network or shell tools are needed; the CI harness renders and checks the candidate separately.
5. A candidate is a draft, never a release. CI must export 1080x1920 H.264 with audio, run existing tests and trusted motion QA, and produce review frames. Human visual review is required; never post.
