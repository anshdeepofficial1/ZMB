# ZMB Stories — Local-only AI pipeline

## Architecture

ZMB uses a small, quantized Qwen2.5-1.5B-Instruct GGUF model for **local text inference inside the standard GitHub-hosted Ubuntu runner**. The pinned model revision is Apache-2.0 licensed. The workflow downloads the model file from the upstream model repository and caches it between runs. Downloading model weights is not inference: episode prompts and story content are passed to llama.cpp running on the Actions machine, not to a hosted inference API.

The local model can improve:
- concise spoken narration and emotional beats;
- shot descriptions, staging, camera intent, and continuity;
- character movement instructions and supported atmosphere/FX metadata.

It cannot generate new photorealistic/3D video footage on a standard CPU runner. The existing ZMB procedural SVG character rigs, layered scene backgrounds, camera presets, frame rasterizer, FFmpeg compositor, narration, captions, and title/vote cards remain the animation engine. The existing Instagram Graph API publishing flow and 7:00 PM IST schedule remain in place.

## Runtime and caching

- Model: `Qwen/Qwen2.5-1.5B-Instruct-GGUF`
- Quantization: `Q4_K_M`, about 1.04 GiB
- Runtime: `llama-cpp-python` on CPU
- Model revision: `91cad51170dc346986eccefdc2dd33a9da36ead9`
- Cache: GitHub Actions cache at `~/.cache/huggingface/hub`
- No `HF_TOKEN`, `POLLINATIONS_KEY`, hosted chat inference, hosted image inference, or hosted video inference is required by the production workflow.

The first run downloads the model weights and will take longer; subsequent runs can reuse the cache. GitHub-hosted runner caches are best-effort and may be evicted. If the cache is unavailable, the workflow downloads the same pinned model again.

## Failure behaviour

- The model output must be valid JSON with the same number and order of story beats.
- The story graph, choice keys, and branch destinations are not rewritten by the model.
- Existing shot fields are retained when the model omits or returns invalid optional fields.
- If the model cannot load or inference fails, the authored scenario and local procedural renderer are used. Episode metadata reports `ai_story.status=fallback`; this is not reported as a successful AI generation.
- Remote visual modes from older configuration files are disabled and forced back to the existing local procedural renderer.

## Free-tier trade-offs

This uses standard GitHub-hosted runners and does not require a paid GPU runner or inference credits. CPU generation will be slower than a hosted GPU model, and the model improves text and shot instructions rather than synthesizing new video footage. The existing animation engine is preserved and remains responsible for all rendered pixels.

## Test before production

1. Run the `Validate Python and Scheduler` workflow and confirm the local-AI tests pass.
2. Use **Actions → Episode Cycle → Run workflow → Dry run** to render without publishing.
3. Download the `reel-debug` artifact and review the MP4 and `episode.json`.
4. Check the dashboard's AI health entry. A fallback status means local inference did not run successfully.
5. Leave Instagram credentials and publishing schedule unchanged unless you intentionally want to change posting behaviour.

Do not put tokens into the repository or logs. Instagram publishing still requires the existing Instagram and GitHub secrets; these are separate from AI inference.
