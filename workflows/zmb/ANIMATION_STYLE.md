# ZMB ANIMATED FILM STYLE — Canonical Creative Decision

**User direction (9 November 2026): produce premium ANIMATED zombie-story videos, not realistic/live-action video.**

The target is **original cinematic stylized 3D animation**, with expressive adult characters and a high-quality animated film look. The earlier vector cartoons are also rejected. The central source of truth is `scripts/art_direction.py` using style ID `zmb_premium_animated_3d_v1`.

## Nonnegotiable design

- Max: consistent mature adult animated face, messy dark hair, charcoal hooded jacket, rust-red seams, expressive but tense eyes. Never photorealistic, child-like, plastic, or generic.
- Biscuit: the same tan animated dog with dark floppy ears, cream chest and red collar. Only include him where story staging warrants; **never obscure the driver's hands in the opening shot**.
- Sedan: same worn steel-blue four-door car, five-spoke wheels and cabin design throughout.
- Opening scene: Max alone visibly driving INSIDE the car, belted, worried—not smiling—on a pitch-dark foggy deserted highway at 2:47 AM. No gas station, sunrise or dog in driver's lap.
- Palette: deep navy/teal night, small warm amber headlights/dashboard accents; readable faces; cinematic light shaping.
- Motion: purposeful 3D animated physical actions with genuine character/prop movement, not slideshow, camera-only zoom, random morphing or stock footage.
- Screen: 9:16 portrait, important action centrally framed, captions in Instagram-safe region with 4-word phrases. No game HUD and no text baked into model frames.

## Verified experiments (all UNREVIEWED)

- Generated a 3D animated source image on a free FLUX.1 Schnell demo via GitHub Actions, run **42580628263**. The second candidate improves adult appearance, car placement, dark highway and removal of unwanted dog.
- Generated a **real 4-second animated** LTX-2.5 image-to-video MP4 via GitHub Actions, run **42581032812**, using that source image with an exact SHA.
- Generated the same **animated MP4 with English voice and timed captions**, run **42581403938**, technical FFmpeg/audio checks passed.

**Visual review:** Animated result is a valid stylized 3D test, but Max switches from worried to an incongruously broad happy grin; steering/hand motion and headlight flicker need further iterations. Latest animation prompt forbids cheerful expressions. Do not call the shot final or publish it.

## Budget and approval

The user requires **₹0**, GitHub-hosted automation without their laptop. Hugging Face ZeroGPU free shared limits apply; do not activate fal.ai, Replicate, premium GPU, paid subscription, or Instagram posting. Current free quota cannot guarantee a complete seven-scene premium Reel per day.

No movie-quality guarantee, no artificial claims from green unit tests, and no release before the real visual audit of **all seven unique shot clips**.
