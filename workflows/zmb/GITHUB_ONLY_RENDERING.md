# ZMB: GitHub-Only Cinematic Automation

**Current verification:** the GitHub-hosted workflow has executed its **free plan and unit-test run successfully**. Actual 1080x1920 AI-video inference has **not** been executed because no \`FAL_KEY\` secret and funded provider access have been verified. Do not call the story video finished or re-enable Instagram.

## What runs on GitHub itself?

The complete *orchestration* is in GitHub Actions. No personal laptop, Android phone, local ComfyUI setup, locally stored model, or 4GB Nvidia RTX 3050 is required.

- Code, actual prompt/story contracts: this GitHub repository
- Audio synthesis, FFmpeg compositing, dynamic subtitles, video validation: GitHub-hosted Ubuntu Actions runner
- Image generation of original recurring characters, the sedan, and station: fal.ai cloud GPU model \`fal-ai/flux-2-pro\`
- Identity-conditioned scene first frames: \`fal-ai/nano-banana-2/edit\`
- Real image-to-video motion: \`fal-ai/ltx-2.3/image-to-video\` (1080p, 9:16)
- Generated PNGs, MP4s, manifests, hashes, costs-plan and draft: GitHub Actions artifacts
- Approval of original identity images: explicit **GitHub-only** approval workflow, saving approved immutable PNGs and SHA receipts in the development branch
- Instagram publishing: **DISABLED**. All clips and previews are \`UNREVIEWED\`.

**Important honest limitation:** ordinary personal-repository GitHub-hosted runners have no CUDA video-inference GPU. If strictly *no outside inference service whatsoever* is allowed, professional AI video generation is currently impossible on standard GitHub runners. Github Team/Enterprise organizations can purchase GPU larger runners when enabled. Otherwise, this pipeline uses fal.ai for computation, while everything you interact with runs in GitHub.

Official references:
- https://docs.github.com/en/actions/reference/runners/github-hosted-runners
- https://fal.ai/models/fal-ai/flux-2-pro/api
- https://fal.ai/models/fal-ai/nano-banana-2/edit/api
- https://fal.ai/models/fal-ai/ltx-2.3/image-to-video/api

## First setup: one GitHub secret

On https://github.com/anshdeepofficial1/ZMB navigate to **Settings → Secrets and variables → Actions → New repository secret**, name it:

\`FAL_KEY\`

Paste a valid API key from your fal.ai account. GitHub encrypts this secret and injects it only into the Actions runner. **Never put this key into a JSON file, commit, comment or workflow input.** The model service is paid at its own rates; the code does not know or guarantee a fixed total. The system refuses to create paid media without explicit input consent.

## Test completely free — already verified on GitHub

Go to:
https://github.com/anshdeepofficial1/ZMB/actions/workflows/cinematic-github.yml

Select **Run workflow** on \`main\`. Choose:
- \`mode = plan\`
- leave authorization \`NO\`

The workflow installs CPU orchestration, runs the full regression suite, generates an exact Day 1 storyboard/price-call budget, and uploads \`zmb-cinematic-unreviewed-RUNID\` as an artifact. It does **not** need \`FAL_KEY\` or generate/post any video.

This also runs automatically daily as a zero-cost preflight. Scheduled executions can never choose paid generation modes.

## Generate original reference candidates only

Using the same GitHub workflow, choose:
- \`mode = references\`
- \`authorize_charges = I_ACCEPT_PROVIDER_CHARGES\`
- \`max_billable_calls = 24\`

GitHub sends requests for original character/vehicle/location stills to the cloud image model. Every generated PNG remains **unreviewed** and is available in the Actions artifact at \`references/<role>.png\`.

**Character consistency requires human sign-off.** Only after actually examining the PNG should you open:
https://github.com/anshdeepofficial1/ZMB/actions/workflows/approve-reference.yml

Enter the source \`RUN ID\`, exact \`role\`, and \`I_REVIEWED_ACTUAL_REFERENCE\`. This action takes just that generated PNG, records reviewer and SHA, commits it to the development branch at its canonical asset-bible path, and keeps Instagram locked. Later runs reuse the **same exact approved face/car**; they do not randomly redraw it. An existing approved identity is not overwritten without the explicit replacement switch.

The only roles needed by the first episode are generated automatically; later episodes can add characters by extending the story and reference workflow.

## Test real shot 0 before paying for a full series

Choose \`mode = shot\`, \`shot = 0\`, and explicit paid authorization.

The script:
1. Generates or reuses the **approved identity references**.
2. Synthesizes all real Day 1 voice lines with edge-tts, **before paid video requests**, to get accurate scene durations.
3. Produces a first-frame PNG using scene and identity references.
4. Sends it to the real LTX-2.3 model for **moving video**, not a simple zoom of a cartoon.
5. Checks the returned MP4's duration, portrait aspect, frame rate, SHA and dimensions.
6. Uploads the clip, PNG, script, and provenance as **unapproved** artifacts. No Instagram token exists in this workflow.

**Model output can still have bad anatomy, wrong props, faces that change or incoherent motion.** Green CI tests do not prove the result meets artistic quality. Inspect the real generated MP4 before moving on.

## Generate and review the entire Day 1

After the reference identity candidates are accepted, choose \`mode = day1\` with paid authorization. The default plan currently estimates **up to 18 billable model calls without reusable reference assets**: one for each required role plus two per each of 7 narrated shots. Approved references reduce call count.

The pipeline uses a separate 6-, 8- or 10-second model output per voice line. If voice duration exceeds 10 seconds, it blocks before buying any clips rather than looping footage deceptively. It creates:
- \`references/*.png\`
- \`frames/00.png ...\`
- \`clips/00.mp4 ...\`
- \`day1_UNREVIEWED_preview.mp4\`
- \`story.json\`, \`manifest.json\`, \`plan.json\` and per-file provenance
- \`caption.txt\`

The draft is marked **DRAFT - NOT APPROVED**, and FFmpeg adds concise captions above Instagram's bottom UI, avoiding the previous bottom-edge text placement. Original videos never include fake SVG cartoon characters or the old procedural HUD.

The publishing system remains paused until an independently verified clip-by-clip review and your explicit release approval. An automated daily **posting** schedule is **not** turned on by this implementation.

## Cost / security / known limits

- \`max_billable_calls\` caps the number of model calls the pipeline plans, **not their dollar price**. Provider charges and failed billable attempts are determined by your fal.ai account. Inspect provider pricing before authorizing day1.
- The normal GitHub workflow runs from \`main\`, checks out the cinematic development branch, and never checks out your laptop files.
- No bot commits unreviewed clips to GitHub source, and it never calls Instagram.
- Canonical approved PNGs are version-controlled; large MP4s remain temporary GitHub artifacts, which expire after 14 days. Long-term source storage for approved MP4s remains a separate release gate.
- The story shots, Face/vehicle consistency and full end-to-end professional quality remain unverified until actual cloud GPU generation has been run and inspected.
- The Vercel analytics dashboard is explicitly deferred until this video pipeline passes.
