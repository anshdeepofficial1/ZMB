# ZMB: Real self-hosted AI Video Model (no stock loop / no cartoon substitute)

**Status: IMPLEMENTED IN CODE, NOT YET END-TO-END RENDERED.**
Instagram publishing is off. A green unit test is not a generated 3D cinematic film.

## Actual model integration

The repository contains:
- \`scripts/setup_ltx_video.py\`: reproducible installer for the original open-source \`Lightricks/LTX-Video\` inference code, pinned to commit \`50f0aef1297574a4b29acbdb874e3a363a6d5f2e\`. Code and multi-GB weights stay outside Git under \`.models/\` / Hugging Face cache.
- \`scripts/ltx_local_video.py\`: genuine image-to-video GPU inference, loads one **scene-specific** source PNG per spoken action, runs LTX, exports unapproved 1080x1920 H.264 candidate MP4s, and records the actual *native resolution*. It does **not** call a paid service and cannot auto-post.
- \`scripts/comfyui_cinematic.py --image-only\`: optional **locally running** ComfyUI image model creates initial cinematic first frames from original approved reference images. It does not require a ComfyUI video node.
- \`scripts/first_frame_review.py\`: per-shot human approval for the actual PNG, physical action, face, car and colour grade; the receipt invalidates on any changed image/identity/shot prompt.
- \`scripts/cinematic_review.py\`: every **real** generated MP4 requires its own exact-SHA human review before assembly.
- \`scripts/render_cinematic.py\`: the production-only scene assembler. It now has clean 4-word/29-character captions above Instagram's bottom controls and a controlled exposure/teal-amber grade. Its caption layout is independent of the old SVG character renderer.

Official model sources:
- https://github.com/Lightricks/LTX-Video
- https://github.com/Lightricks/LTX-Video/blob/main/ltx_video/inference.py
- https://github.com/Lightricks/LTX-Video/blob/main/configs/ltxv-2b-0.9.8-distilled.yaml

The latest LTX-2.5 model is newer and substantially heavier than the legacy LTX 2B lightweight option. For a self-hosted pipeline, small **LTX-Video 2B 0.9.8 distilled** is a more realistic integration starting point, not an assertion it reaches a cinema studio's quality.

## CUDA VRAM reality

| Profile | Actual model | Internal frame | Conservative target | Status |
| --- | --- | --- | --- | --- |
| \`test\` | LTX 2B distilled | 448x800 | 8GB+ | Experimental diagnostic output only |
| \`quality\` | LTX 2B distilled | 704x1248 | 12GB+ | Default quality candidate |
| \`studio\` | LTX 13B distilled | 704x1248 | 24GB+ | More expensive, not verified here |

These VRAM targets are **safety defaults**, not official guarantees or measured benchmarks. The 4GB RTX 3050 does **not** meet the quality/studio target. \`test --experimental-low-vram\` allows an *explicit* research attempt with CPU offload and may fail with CUDA OOM; it is not a production promise. Normal GitHub-hosted Actions CPU runners cannot generate these clips. Genuine GPU inference has **not** been tested by this integration yet.

The final MP4 is upscaled to 1080x1920 for delivery, but the immutable provenance records \`native_width/native_height\`. This is not misrepresented as a native 1080p diffusion result. The artistic quality must be inspected by a human.

## Film-first workflow (Day 1, seven different physical actions)

**On a CUDA workstation:** install Python and CUDA-enabled PyTorch compatible with the upstream LTX repo, Git and FFmpeg. Use a separate virtual environment as appropriate.

1. Install original LTX code inside the repo workspace:
   \`\`\`bash
   python scripts/setup_ltx_video.py --install
   python scripts/setup_ltx_video.py --verify
   \`\`\`
   This is the only model-install action; LTX weights download on the first actual CUDA inference through the official code.

2. Inspect the exact shot list safely (no model downloads):
   \`\`\`bash
   python scripts/visual_manifest.py --day1
   python scripts/ltx_local_video.py --day1 --dry-run
   \`\`\`

3. Create and review the **canonical reference image** of Max, Biscuit, the same steel-blue sedan and gas station. The existing \`scripts/reference_candidates.py\` and \`scripts/reference_review.py\` generate and approve them using a locally available ComfyUI image workflow. These are **not** shipped as magically approved PNGs. A real model and your real reference approval are prerequisites.

4. Create an initial first frame for the actual action. Use a genuine local ComfyUI image workflow with real API-format bindings in \`workflows/zmb/bindings.json\`. No ComfyUI video model is needed for this step:
   \`\`\`bash
   python scripts/comfyui_cinematic.py --day1 --shot 0 --image-only \
     --server http://127.0.0.1:8188 --bindings workflows/zmb/bindings.json
   \`\`\`
   This outputs \`assets/cinematic/road/intro/00.png\`. Repeat for other shots.
   You may supply an externally created **original** scene PNG, provided it passes the same visual inspection and reference guards.

5. **Visually inspect** that the person is a consistent adult human (not a robot or flat illustration), the exact steel-blue car has the correct wheels, and the correct action is depicted in the first frame. Then explicitly review:
   \`\`\`bash
   python scripts/first_frame_review.py --day1 --shot 0 \
     --reviewer "Editor" --confirm-all-checks
   \`\`\`

6. Run the genuine locally installed image-to-video model:
   \`\`\`bash
   python scripts/ltx_local_video.py --day1 --shot 0 --profile quality --execute
   \`\`\`
   If the machine has only 4GB VRAM, this will **safely refuse** the professional profile. An unsupported research attempt can be requested with \`--profile test --experimental-low-vram --execute\`; success is not guaranteed.

7. Review the **actual original** \`assets/cinematic/road/intro/00.mp4\`. It must show the sedan MOVING with rolling wheels and scrolling road, not a parked vehicle with a virtual camera pan. After reviewing, use:
   \`\`\`bash
   python scripts/cinematic_review.py --day1 --shot 0 --reviewer "Editor" --confirm-all-checks
   \`\`\`
   Repeat stages 4-7 for all seven distinct actions. One action cannot reuse another action's clip. Do not approve malformed people/dogs, bad perspective, stutters, morphing headlights, static actors, blackened faces, duplicate car models, or generic footage.

8. When **all seven real source clips** are reviewed, run the cinematic assembler with \`visual_mode="cinematic_assets"\` and real TTS word timing. The default \`config.example.json\` now uses this mode; the old SVG preview is explicitly debug-only. Keep \`publishing_enabled=false\` and \`ZMB_PUBLISH_ENABLED=0\` until a real video is inspected and accepted.

## Frame/typography art direction

- **Characters:** natural photorealistic human anatomy with exact face, height, wardrobe and hair from approved character PNGs; Biscuit must be the same realistic tan dog in every frame.
- **Vehicle:** one blue-grey compact sedan, identical front, wheel, interior and damage mark at every camera angle.
- **Camera:** real action dominates the *middle 70% of the screen*; no empty sky over tiny people at the bottom.
- **Colours:** detailed midnight slate/teal shadows, warm amber practical lights, neutral skin, controlled highlights; no fake neon yellow, muddy blacks or overexposed beige actors.
- **Captions:** ivory, dark translucent background, max 4 words and 29 characters per phrase, sentence-aware, lower-third around 410 px above the bottom (1080x1920), with right-side UI-safe margin.
- **Not included:** procedural HUD/health bars, tiny top corner text, cartoon/vector scenes, baked AI text inside visual frames.

**Blockers:** actual GPU generation, reference images, scene-first-frame review, real footage review, soundtrack/sound effects and final approved Day 1 are **still pending**. Do not unpause Instagram or start the Vercel dashboard.
