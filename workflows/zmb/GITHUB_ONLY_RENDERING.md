# ZMB Stories: zero-rupee GitHub video pipeline

**Permanent budget: Rs 0. No fal.ai, paid GPU, Replicate, credit card or laptop.**

Everything is controlled by GitHub Actions. Standard runners have CPUs, so any actual AI video inference must use a shared free service. Full daily professional quality cannot be guaranteed from a free quota.

## Verified

- ZMB is a public GitHub repository; standard public-repository GitHub Actions are free.
- GitHub 9:16 MP4 and subtitle/audio assembly tests have passed with synthetic footage, which does NOT establish actual cinematic quality.
- Old billable FalInference constructor is permanently disabled in scripts/github_cloud_video.py.
- The active GitHub workflow is .github/workflows/cinematic-github.yml; it has no publishing access or paid API key.
- scripts/hf_zerogpu_video.py provides free model planning, public model probing, and an optional one-clip experiment.

## Free GPU limits

Hugging Face ZeroGPU currently offers free users **five minutes per 24 hours** of shared GPU quota, with queues and unavailable demos possible. The selected ZeroCollabs/LTX-2.3-turbo Space can reserve around 200 seconds for one six-second clip. That cannot guarantee seven professional clips every day.

Sources:
- https://docs.github.com/en/actions/how-tos/write-workflows/choose-where-workflows-run/choose-the-runner-for-a-job
- https://huggingface.co/docs/hub/spaces-zerogpu
- https://huggingface.co/spaces/ZeroCollabs/LTX-2.3-turbo

## Use from GitHub Actions; no laptop

Open https://github.com/anshdeepofficial1/ZMB/actions/workflows/cinematic-github.yml and run one of these modes:

- **plan**: completely free, no GPU use, outputs a project plan.
- **probe**: free public Space status check, no GPU inference.
- **one_clip**: opt-in, at most one six-second experimental video using only free quota. Requires an HF_TOKEN belonging to a free Hugging Face account and an already human-approved action-specific first-frame PNG. No characters or footage are invented if that PNG is absent.

Save a read-only free Hugging Face token only as GitHub repository secret HF_TOKEN. Do not add a card, buy credits or use a paid plan. The inference script rejects absent tokens, low shared quota, paid/extended allowance, missing face/prop references and unavailable ZeroGPU hardware.

The previous reference-generation workflow depends on an actual free image model being connected and tested. Until real character references, first frames and moving clips are visually reviewed, **no Day 1 professional video is ready**.

**Instagram publishing remains disabled. No paid fallback. No fake completion.**
