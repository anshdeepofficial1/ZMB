---
name: zmb-cinematic-storyboarding
description: Convert ZMB episode narration into exact, visually demonstrable cinematic shots with consistent characters, props, and actions. Never invent footage or publish before approval.
---

# ZMB Cinematic Storyboarding Skill

## Non-negotiable production contract

Every spoken verb and important physical object must have a matching visible event.
A character talking about a vehicle does not count as a vehicle shot. If the line
says **driving**, show the car moving (rolling wheels, moving road, correct camera).
If the engine dies, show the engine/vehicle deceleration and car stopping on the
road. If headlights flicker, show that flicker. If a flashlight turns on, show
the source and illumination. If a door handle turns, animate that handle.

No random slideshow, repeated stills, generic walking loop, or ambiguous fog
may substitute for a physical action. When an action cannot be rendered faithfully,
stop and mark **requires new shot asset**.

## Canonical characters

Read `content/cast_bible.json` first. Create and approve one clean reference image
per recurring character at the exact `reference` paths. Reuse those assets for
every shot's reference conditioning (e.g. IPAdapter/consistent-character workflow
in ComfyUI). Never generate a new identity each scene. Keep Max's charcoal
jacket, brown cargo trousers, and brown pack stable; Biscuit is a small tan dog,
not a robot. Assets must be original/licensed.

## Story and shot planning

1. Read `content/scenarios.json` and determine continuity from the previous node.
2. Write concise, visual narration: subject → action → result → escalating threat.
3. Give each spoken line its own shot: physical location, time, camera, cast,
   props, concrete beat/action, FX, and precise cause/effect.
4. Generate `out/day1_visual_manifest.json` via
   `python scripts/visual_manifest.py --day1`.
5. Use the exact `prompt` fields. Provide the same reference image for each
   recurring character in the actual image/video generation workflow.
6. For vehicles, use a single approved vehicle model/reference; all angles must
   match. Wheels must rotate while driving and stop when parked.
7. Produce unique 9:16 clips matching the narration timestamps; keep generated
   clips under `assets/cinematic/<arc>/<node>/<index>.mp4`.
8. Preview with the episode's real narration, captions, and audio before release.

## Image-to-video options

Recommended: ComfyUI on a real NVIDIA GPU with an image model, reference-guidance
workflow, and a compatible image-to-video model. The GitHub Actions CPU runner
cannot reliably create high-fidelity diffusion video. Providing this skill does
**not** install models or pay for GPU inference. Keep the old procedural renderer
only for local draft previews, not as a silent substitute for missing cinematic clips.

A ComfyUI workflow must be validated on the deployment actually used; models,
conditioning nodes, and endpoints vary. Do not claim working AI video until its
output passes clip, character, motion, and lip/narration checks.

## Real generation and review

Read `workflows/zmb/README.md` for the real ComfyUI API workflow
integration and setup. `python scripts/comfyui_cinematic.py --day1 --dry-run`
checks prompt directions, while `--server ... --bindings ...` performs
actual generation only on a working authorized ComfyUI GPU server.

**Do not claim finished video until original reference stills, all unique
motion clips and their manual SHA-256-bound review receipts exist.**
A screenshot, still-frame slideshow, a mock video, or an arbitrary clip
is not a passing implementation.

## Acceptance gates

- Opening 0-2 seconds: clearly visible threat/action, not a generic title card.
- Narration, character action and props agree in every shot.
- Every shot has a corresponding generated artifact; no empty placeholders.
- Character wardrobe, body proportions and identities stay fixed across shots.
- Camera/lighting match time and location; the same car stays the same car.
- Actions follow cause → consequence (drive → stall → ignition fails → exit).
- No misleading prompts, no fabricated vote results.
- No Instagram publishing until the full video is reviewed and approved.
