# ZMB — 3D production candidate

The owner superseded the earlier 2D direction on 15 November 2026. Original Roblox-inspired block rigs, original environments and fantasy/zombie stories are the new target. No third-party creator's characters or voice are cloned.

- The exact locally rendered hourglass V2 engine and original sound-design source are stored in `hourglass-engine.tar.xz` (extract with `tar -xJf hourglass-engine.tar.xz`). SHA-256 verified by produce.py.
- `hourglass.json`: 11 narration/action beats and original SFX timing. The new source adds glass highlight ribbons, 3,200 flowing sand particles, draining upper reservoir and growing lower sand pile.
- `neural_voice.py`: free CPU Kokoro 82M, Apache-2.0 model weights, `am_michael` proposed narrator, model-predicted token times. The preset must be auditioned; it is NOT verified to match GreenBroRants or ElevenLabs Liam.
- `produce.py`: real MP4 render, retimed original soundtrack and foley, decode checks, duration and stream verification.
- CI output: 1080x1920 H.264/AAC at 30 fps (native renderer 720x1280, 24 fps). Artifacts are review-only.
- The story animation is a bespoke pilot; new stories require new staged scenes and rigs. Do not use generic motions for unseen story events.

## Release gate
Do not publish until the final neural-voice artifact is reviewed, story-to-action matches each line, glass/sand continuity and family/dragon action are visually checked, captions are readable and not duplicated, soundtrack is subordinate to narration, and exact post/caption/account are approved. No paid credits; no robotic fallback. Existing 2D pipeline and history remain intact pending migration. No automatic publishing in this branch.

Model: https://huggingface.co/hexgrad/Kokoro-82M
