# ZMB Stories — Original 2D animated zombie survival

**Current art direction:** original **2D** characters, illustrated environments,
and scene-by-scene animation built entirely with code. No AI image/video generation,
no 3D, no photo-real characters, no model weights, and no GPU required.

ZMB is a branching English-language zombie survival story for vertical social video.
Max, his dog Biscuit, Ada, Otto and the zombies are custom vector character rigs:
the same faces, costumes and poses are drawn frame by frame using Python SVG.

## How video is actually made

1. The **authored story graph** in `content/scenarios.json` supplies plot and dialogue.
2. `content/shot_directions.json` documents the physical action of each narration line.
3. `scripts/characters.py`, `scripts/scenes.py` and `scripts/animate.py`
   draw articulated 2D actors, props, parallax and motion into SVG frames.
4. `resvg-py` rasterizes the original SVG frames.
5. **eSpeak NG** synthesizes offline English narration without a neural model.
   Captions have approximate word timing from real narration duration.
6. **FFmpeg** creates 1080×1920 H.264/AAC videos.
7. `scripts/verify_2d_video.py` rejects missing video, frozen scenes,
   invalid portrait size and near-silent audio.

**No AI inference, GPU, photo assets, stock-footage substitution, or paid API**
is part of this active production path. Do not revive the obsolete 3D/ZeroGPU
experiments: they are not the user-approved ZMB animation style.

## Work status

The **seven-shot Day 1 story** has specifically authored physical beats:
a car driving, engine stalling, dead ignition, flashlight exit, station reveal,
shadow behind glass and a turning door handle. All use the procedural 2D renderer.

**Later episodes are not yet fully staged in the 2D engine.** Existing
`shot_directions.json` contains written directions, but written directions alone
do not create appropriate vector action. The visual contract must reject
unimplemented actions instead of substituting generic walking cartoons.
Do not describe the whole series as finished until these actions are implemented
and their MP4s have been reviewed.

**Instagram publishing is OFF** by default: both the configuration's
`procedural_release_approved` and `publishing_enabled` must explicitly be set
true, and `ZMB_PUBLISH_ENABLED=1` supplied after the owner approves the actual Reel.
A successful unit test alone is not visual approval.

## Run and test

On Ubuntu with FFmpeg, eSpeak NG, Python 3.12:

```bash
sudo apt-get install ffmpeg fonts-dejavu-core espeak-ng
python -m pip install -r scripts/requirements.txt
python -m unittest discover -s tests -v
python scripts/preview_day1.py --stills
python scripts/preview_day1.py --video
python scripts/verify_2d_video.py out/reel_s1_d000.mp4
```

The `.github/workflows/validate.yml` PR workflow runs tests and renders an
actual Day 1 MP4 artifact with technical QA. The `episode.yml` manual workflow
is preview-only and cannot publish.

**Note:** A non-neural eSpeak voice is less natural than a neural TTS voice,
but it meets the explicit no-AI requirement. Character animation is original
procedural 2D, rather than an AI video or 3D model.

## Repository guide

| Path | Purpose |
|---|---|
| `content/scenarios.json` | Authored branching stories |
| `content/shot_directions.json` | Scene-specific physical actions |
| `scripts/characters.py` | 2D rigged actors and dog |
| `scripts/scenes.py` | 2D backgrounds, weather and parallax |
| `scripts/animate.py` | Frame composition and scene-specific beats |
| `scripts/render.py` | Offline voice, frame rasterizer and MP4 |
| `scripts/preview_day1.py` | Isolated seven-shot preview |
| `scripts/verify_2d_video.py` | Video/audio/motion smoke test |
| `scripts/run_cycle.py` | Voting/scheduling with publication disabled |
| `tests/` | Unit and regression tests |

**Budget:** ₹0. No user laptop needs to stay running; use GitHub Actions
artifacts for video previews and review before any publishing.
