"""Local-only AI refinement for ZMB Stories.

Inference runs inside GitHub Actions via llama.cpp. The model weights are downloaded
as a file; prompts are never sent to a hosted inference endpoint.
"""
from __future__ import annotations
import json
import os
from pathlib import Path
from typing import Any

MODEL_REPO = "Qwen/Qwen2.5-1.5B-Instruct-GGUF"
MODEL_FILE = "qwen2.5-1.5b-instruct-q4_k_m.gguf"
MODEL_REVISION = "91cad51170dc346986eccefdc2dd33a9da36ead9"

def _model_path(Log=print) -> Path:
    explicit = (os.environ.get("ZMB_LOCAL_MODEL_PATH") or "").strip()
    if explicit:
        path = Path(explicit).expanduser()
        if not path.is_file():
            raise FileNotFoundError(f"ZMB_LOCAL_MODEL_PATH does not exist: {path}")
        return path
    from huggingface_hub import hf_hub_download
    Log("[local-ai] resolving cached GGUF weights; inference remains on this runner")
    return Path(hf_hub_download(repo_id=MODEL_REPO, filename=MODEL_FILE, revision=MODEL_REVISION))

def _validate_lines(ep: dict[str, Any], new_lines: Any) -> list[dict[str, Any]]:
    old_lines = ep.get("lines") or []
    if not isinstance(new_lines, list) or len(new_lines) != len(old_lines):
        raise ValueError("local model returned a different number of story beats")
    cleaned = []
    allowed = ("place", "beat", "mood", "time", "cam", "cast", "fx", "zeds")
    for index, item in enumerate(new_lines):
        if not isinstance(item, dict) or not str(item.get("text", "")).strip():
            raise ValueError(f"local model returned an empty narration line at index {index}")
        original = dict(old_lines[index].get("shot") or {})
        proposed = item.get("shot") if isinstance(item.get("shot"), dict) else {}
        shot = dict(original)
        for key in allowed:
            value = proposed.get(key)
            if value is not None and value != "" and value != []:
                shot[key] = value
        if not shot.get("place") or not shot.get("beat"):
            raise ValueError(f"local model returned incomplete shot metadata at index {index}")
        if not isinstance(shot.get("cast", []), list):
            shot["cast"] = original.get("cast", [])
        if not isinstance(shot.get("fx", "none"), str):
            shot["fx"] = original.get("fx", "none")
        cleaned.append({"text": str(item["text"]).strip(), "shot": shot})
    return cleaned

def rewrite_episode(ep: dict[str, Any], Log=print) -> dict[str, Any]:
    """Refine narration and staging with local inference, preserving plot and choices."""
    if os.environ.get("ZMB_LOCAL_AI_ENABLED", "1").strip().lower() in {"0", "false", "no"}:
        result = dict(ep)
        result["ai_story"] = {"provider": "local-llama.cpp", "status": "disabled"}
        Log("[local-ai] disabled; keeping authored scenario dialogue")
        return result
    original_lines = ep.get("lines") or []
    if not original_lines:
        raise RuntimeError("local AI refinement refused: episode has no authored lines")
    payload = {
        "season": ep.get("season"), "day": ep.get("day"), "node": ep.get("node"),
        "kind": ep.get("kind"), "hook": ep.get("hook"), "subtitle": ep.get("subtitle"),
        "lines": original_lines, "choices": ep.get("choices") or [],
    }
    system = (
        "You are the screenplay and shot-staging assistant for ZMB Stories, a cinematic stylized "
        "3D animated zombie-survival Reel. Return ONLY valid JSON with one key 'lines'. Return exactly "
        "the same number of line objects, in the same order. Each has 'text' and 'shot'. Keep story "
        "facts, timeline, named character identities, choices and branching unchanged. Do not add/remove "
        "beats. Make spoken English concise, natural, emotionally specific. Improve visual staging rather "
        "than inventing plot. Shot fields: place (snake_case location), beat (visible action), mood "
        "(calm/tense/danger/hope), time (night/dusk/dawn/day), cam (static/push/pull/panl/panr/tilt/"
        "shake/creep), cast (list of [character, action] pairs; use max, ada, old, zombie, biscuit and "
        "actions idle/walk/run/sneak/shamble/trot/follow/run_dog), fx (short FX name or none), zeds "
        "(integer or null). Preserve existing fields if uncertain. Prefer varied camera language, depth, "
        "readable silhouettes, eyelines, motivated movement and continuity. Max is a young adult survivor "
        "with messy dark hair, charcoal hooded jacket, backpack and brown cargo trousers. Biscuit is a small "
        "tan dog with dark ears. Ada wears practical field clothing. Keep horror non-graphic. Do not put "
        "camera/FX instructions in dialogue. No markdown or commentary."
    )
    try:
        from llama_cpp import Llama
        model_path = _model_path(Log)
        Log(f"[local-ai] running {MODEL_REPO} Q4_K_M locally")
        llm = Llama(model_path=str(model_path), n_ctx=4096,
                    n_threads=max(1, min(4, os.cpu_count() or 2)),
                    n_batch=256, verbose=False)
        response = llm.create_chat_completion(
            messages=[{"role": "system", "content": system},
                      {"role": "user", "content": json.dumps(payload, ensure_ascii=False)}],
            temperature=0.55, top_p=0.85, max_tokens=1500,
            response_format={"type": "json_object"})
        parsed = json.loads(response["choices"][0]["message"]["content"].strip())
        lines = _validate_lines(ep, parsed.get("lines") if isinstance(parsed, dict) else None)
        result = dict(ep)
        result["lines"] = lines
        result["narration"] = [line["text"] for line in lines]
        result["ai_story"] = {"provider": "local-llama.cpp", "model": MODEL_REPO,
                              "quantization": "Q4_K_M", "status": "success"}
        Log(f"[local-ai] refined and validated {len(lines)} beats locally")
        return result
    except Exception as exc:
        result = dict(ep)
        result["ai_story"] = {"provider": "local-llama.cpp", "model": MODEL_REPO,
                              "status": "fallback", "error": type(exc).__name__}
        Log(f"[local-ai] unavailable ({type(exc).__name__}); keeping authored script and local renderer")
        return result

def generate_hf_image(*args, **kwargs) -> None:
    """Disabled: local-only ZMB never calls hosted image inference."""
    raise RuntimeError("Hosted image inference is disabled in ZMB local-only mode")
