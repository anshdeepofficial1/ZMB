# ZMB — Real Cinematic Image + Video Generation

**Status:** Integration code is present; no film-generation GPU is connected by this repository.
This is a genuine ComfyUI API client, not a pretend AI clip generator. It refuses
to publish, requires approved character reference PNGs, saves scene-specific
images and MP4s, and marks **every** generated clip UNREVIEWED.

## GPU feasibility: do not promise zero-cost professional video

Current open diffusion-video models are substantially more memory-hungry than
traditional image generation. For example, LTX-2.5's official ComfyUI guide
calls for 32GB+ VRAM, and Tencent's HunyuanVideo 1.5 documents 14GB minimum
with offloading. A 4GB consumer GPU is **not validated for professional
LTX-2.5/Hunyuan image-to-video**. The ComfyUI adapter is model-agnostic; this
does not mean an API workflow is installed or can fit a given card.

If there is no compatible GPU available, **do not pretend a CPU GitHub Actions
job can produce realistic 3D human motion**. An actual GPU provider and matching
API-format workflows are an operational prerequisite. Explore native quantized
low-VRAM alternatives only with a real 9:16 test clip that passes physical-motion
and temporal-consistency review; do not mark them production-ready based on
speculation.

Sources:
- https://docs.ltx.io/open-source-model/integration-tools/comfy-ui
- https://github.com/Tencent-Hunyuan/HunyuanVideo-1.5

## Why a separate GPU system?

The GitHub-hosted Ubuntu CPU runner can run the original vector preview, but
cannot realistically render seven high-quality diffusion-based video shots per
Reel. The production workflow is paused. A ComfyUI machine with enough VRAM
is necessary, or a compatible externally hosted ComfyUI server.

For a reference workflow, see [ComfyUI Wan 2.2 5B TI2V](https://comfy.org/hub/workflows/wan-2-2-5b-video-generation-f83ee3caa04e/).
It supports text-to-video and image-to-video. Model files and video
conditioning nodes must actually be installed. Export the **API format**
node graph, not the editor UI format. Official ComfyUI docs list
`POST /prompt`, `GET /history/{prompt_id}`, `POST /upload/image`, and
`GET /view`; the ZMB adapter uses these real endpoints.

**Do not open an unauthenticated ComfyUI instance to the public internet.**
Run localhost, VPN, or a secure, authenticated reverse proxy. Only the
user-approved generator can access paid/cloud GPUs; this script never creates
one or spends credits by itself.

## Character and vehicle identity

Before generating any footage, create **original** approved 9:16 character
reference files at:

- `assets/character_refs/max.png`
- `assets/character_refs/biscuit.png`
- `assets/character_refs/ada.png`
- `assets/character_refs/otto.png`
- `assets/character_refs/zombie.png`

Descriptions are pinned in `content/cast_bible.json`. Max's face, clothes,
proportions and hair must remain unchanged. Biscuit must be a living tan dog,
not a robot. The same approved blue-grey sedan must appear in driving, crash,
parked, exterior, and interior shots. Add a separate sedan conditioning
reference to both stage workflows before the next release.

**Every visible character, hero sedan and gas station must have a reference
node bound in both image and video workflows.** This adapter will error otherwise,
rather than silently render inconsistent characters.

## Connect your own ComfyUI API workflows

1. Export a functioning image workflow using **Export (API Format)**. Ensure
   it has a text conditioning input, one reference conditioning path per
   character who might appear, and a SaveImage output node.
2. Export a functioning image-to-video workflow as API JSON. It needs text
   conditioning, a LoadImage input for the scene's initial frame, reference
   conditioning inputs, and a SaveVideo output node producing **MP4**.
3. Save the exported graphs, for example
   `workflows/zmb/image_api.json` and `workflows/zmb/video_api.json`.
4. Create a private or local `workflows/zmb/bindings.json` mapping the
   *real* node IDs and input keys, in this exact shape:

```json
{
  "image": {
    "workflow_file": "workflows/zmb/image_api.json",
    "prompt": ["6", "text"],
    "negative_prompt": ["7", "text"],
    "reference_nodes": {
      "max": ["90", "image"],
      "biscuit": ["91", "image"],
      "ada": ["92", "image"],
      "old": ["93", "image"],
      "zombie": ["94", "image"],
      "sedan": ["95", "image"],
      "station": ["96", "image"]
    },
    "output_node": "9"
  },
  "video": {
    "workflow_file": "workflows/zmb/video_api.json",
    "prompt": ["6", "text"],
    "source_image": ["12", "image"],
    "reference_nodes": {
      "max": ["90", "image"],
      "biscuit": ["91", "image"],
      "ada": ["92", "image"],
      "old": ["93", "image"],
      "zombie": ["94", "image"]
    },
    "output_node": "58"
  }
}
```

**Node IDs in the example are illustrative and NOT expected to match your
actual exported model workflows.** Inspect the exported files and replace
every binding with your real input and output node IDs. If the needed
node does not exist, the adapter fails immediately.

## Step 1 — Create the original reference assets (before video)

No characters, vehicles or environments are approved yet. The first task is to
generate *candidate images*, not to claim that such approved files already exist.

```powershell
python scripts/reference_candidates.py --all --dry-run
python scripts/reference_candidates.py --role max --count 3 --server http://127.0.0.1:8188 --bindings workflows/zmb/bindings.json
```

Repeat for `biscuit`, `ada`, `old`, `zombie`, `sedan` and `station`.
For reference creation, only the `image` stage of bindings.json is needed.

The model writes **unreviewed** candidate PNGs under
`out/reference_candidates/<role>/candidate_01.png`. Watch every result to
choose a consistent original look. When you have actually inspected one
candidate, approve it with the independent explicit action:

```powershell
python scripts/reference_review.py --role max --candidate out/reference_candidates/max/candidate_01.png --reviewer "Editor" --confirm-reviewed
python scripts/reference_review.py --role max --verify
```

This promotes only that checked file to
`assets/character_refs/max.png` with a matching `.reference.json` receipt.
The same approach applies to `assets/prop_refs/hero_sedan.png` and
`assets/prop_refs/gas_station.png`. If reference bytes or identity definitions
change, approval is invalid. Only after all needed roles are reviewed can
`comfyui_cinematic.py` generate shot footage.

## Commands

```powershell
python scripts/comfyui_cinematic.py --day1 --dry-run
python scripts/comfyui_cinematic.py --day1 --server http://127.0.0.1:8188 --bindings workflows/zmb/bindings.json --shot 0
python scripts/comfyui_cinematic.py --day1 --server http://127.0.0.1:8188 --bindings workflows/zmb/bindings.json --resume
python scripts/audit_story_coverage.py
```

Generated outputs are in:
`assets/cinematic/road/intro/00.png`,
`assets/cinematic/road/intro/00.mp4`, and corresponding numbered files.
Each MP4 has a `.provenance.json` containing input prompt/required props,
content hashes, and `UNREVIEWED` status.

**Nothing is ready to post yet.** A human must inspect real clips for
identity consistency, correct narration, visible physical action, lighting,
motion and story continuity. Only after passing all gates can the
release-approval flag change. The repository's Instagram publishing lock
remains OFF.

## Real footage review and release gating

**Video generation does not equal approval.** After manually watching each
generated MP4 together with its matching narration and prompts, a named
reviewer must explicitly attest to all five criteria for the *exact* file.

```powershell
python scripts/cinematic_review.py --day1 --shot 0 --reviewer "Editor" --confirm-all-checks
python scripts/cinematic_review.py --day1 --verify
```

This writes `assets/cinematic/road/intro/00.review.json` containing the MP4
SHA-256, exact narration+physical-prompt SHA-256, reviewer identity, time,
and every completed check. If the clip is replaced or the story is edited,
the existing receipt is invalid and publishing is blocked.

Review the actual source clip; the 2D procedural MP4 is **only a debugging
preview** and cannot be accepted as a professional replacement.

Generated videos may be too large for ordinary GitHub repository commits.
Deploy the vetted clip assets to a controlled production artifact storage
location before enabling automatic editing and publishing. This storage and
ComfyUI GPU are **not yet connected**.

## Quality checklist for Day 1

| Narration | Mandatory visual |
|---|---|
| Max drives at 2:47 AM | Real moving sedan with spinning tires and moving road |
| Engine dies | Visible deceleration, headlight flicker and stopping on highway |
| Ignition fails | Same cabin, dashboard dark, key turned and Biscuit reacts |
| Exits with flashlight | Same parked sedan; door opens; flashlight physically lights roadway |
| Gas station lights | A visible distant real gas station in the correct environment |
| Shadow | Visible movement **behind** locked glass, not in front |
| Knocks and handle turns | Door visibly trembles and handle rotates in close view |

Additional shots will need consistent character reference, vehicle
reference, physics and sound effects. Low-quality assets are rejected,
not inserted to fill time.
