# ZMB AI Pipeline: Setup, limits, and failure behaviour

## What this implementation does

- Uses the existing authored story graph as the canonical source for choices and branching.
- When `HF_TOKEN` is configured, asks a hosted chat model to improve spoken dialogue and per-shot metadata. It must return valid JSON with the same number of lines; the code rejects malformed output and does not alter vote choices or next-node links.
- Generates a separate cinematic 9:16 image for each narration beat. Hugging Face Inference Providers is attempted first when configured. Pollinations is used only if its own `POLLINATIONS_KEY` is configured and the Hugging Face attempt fails.
- Adds captions/cards, motion, narration and sound through the existing FFmpeg renderer.
- Keeps the existing GitHub Actions publishing schedule and Instagram Graph API publisher. AI failures stop the production cycle; they do not silently publish fake AI output.

## GitHub Actions secrets

In repository **Settings → Secrets and variables → Actions → New repository secret**:

- `HF_TOKEN`: Hugging Face user token with Inference Providers permission. The code never prints the token.
- `POLLINATIONS_KEY` (optional): a separately obtained Pollinations API key, used only as an image fallback.

Optional repository variables:

- `HF_STORY_MODEL`: default `Qwen/Qwen2.5-7B-Instruct`; choose a currently supported chat model with an acceptable licence.
- `HF_IMAGE_MODEL`: default `black-forest-labs/FLUX.1-schnell`; choose a currently supported text-to-image model and review its model card/licence.

## Free-tier reality

Hugging Face's published pricing currently lists $0.10 in monthly Inference Providers credits for free accounts, subject to change. This is useful for testing, not a guarantee of enough credits to generate a daily multi-scene Reel. Provider availability and model routing can change. A request may fail due to exhausted credits, unavailable hardware, access restrictions, or provider throttling. No unlimited free generation is promised.

The GitHub runner performs orchestration and FFmpeg composition; hosted models run on their provider's infrastructure. Standard GitHub-hosted runners are not general-purpose GPU video-generation machines.

## Validation and failure policy

- AI story JSON must parse and preserve line count; empty lines or incomplete shot metadata are rejected.
- Each image is decoded and normalized to 720×1280 before use.
- Image requests retry up to three times; the render stops if no configured provider can generate an image.
- Do not enable production posting until a manual dry run succeeds and the resulting MP4 is reviewed.
- Do not commit tokens or paste them into issue comments/logs.
