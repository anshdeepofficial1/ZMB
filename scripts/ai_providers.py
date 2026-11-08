"""Offline script refinement for ZMB Stories: suggestions NEVER override filmed lines.

A small local LLM can brainstorm concise narration, but a changed voice-over
without a changed visual is a story-fidelity defect. Therefore auto-publishing
always renders the **authored and reviewed** lines, not free-form AI text.
"""
from __future__ import annotations

import copy
import json
import os
from pathlib import Path
from typing import Any

MODEL_REPO = "Qwen/Qwen2.5-1.5B-Instruct-GGUF"
MODEL_FILE = "qwen2.5-1.5b-instruct-q4_k_m.gguf"
MODEL_REVISION = "91cad51170dc346986eccefdc2dd33a9da36ead9"

ROOT = Path(__file__).resolve().parents[1]
SHOT_DIRECTIONS = ROOT / "content" / "shot_directions.json"


def _model_path(Log=print) -> Path:
    explicit = (os.environ.get("ZMB_LOCAL_MODEL_PATH") or "").strip()
    if explicit:
        path = Path(explicit).expanduser()
        if not path.is_file():
            raise FileNotFoundError(f"ZMB_LOCAL_MODEL_PATH does not exist: {path}")
        return path
    from huggingface_hub import hf_hub_download
    Log("[local-ai] resolving local model cache; prompts stay on this machine")
    return Path(hf_hub_download(repo_id=MODEL_REPO, filename=MODEL_FILE, revision=MODEL_REVISION))


def _directions_for_episode(ep: dict[str, Any]) -> list[dict[str, Any]]:
    lines = ep.get("lines") or []
    try:
        direction_index = json.loads(SHOT_DIRECTIONS.read_text(encoding="utf-8"))["arcs"]
        directions = direction_index[ep["arc"]][ep["node"]]
    except (OSError, KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"no approved shot direction source for this episode: {exc}") from exc
    if len(directions) != len(lines):
        raise ValueError(
            f"narration/visual count mismatch: {len(lines)} lines "
            f"but {len(directions)} physical shots"
        )
    return directions


def _validate_lines(ep: dict[str, Any], new_lines: Any) -> list[dict[str, Any]]:
    """Validate candidate text count, preserve all original renderer metadata."""
    authored = ep.get("lines") or []
    if not isinstance(new_lines, list) or len(new_lines) != len(authored):
        raise ValueError("local model returned a different number of story beats")
    cleaned = []
    for i, proposal in enumerate(new_lines):
        text = proposal.get("text") if isinstance(proposal, dict) else proposal
        if not isinstance(text, str) or not text.strip():
            raise ValueError(f"local model returned an empty narration line at index {i}")
        text = text.strip()
        if len(text) > 245:
            raise ValueError(f"local model returned overlong narration at index {i}")
        # NEVER let the model invent a cast/action/camera or silently rewrite
        # any shot fields; those require explicit physical image/video review.
        cleaned.append({
            "text": text,
            "shot": copy.deepcopy(authored[i].get("shot") or {}),
        })
    return cleaned


def rewrite_episode(ep: dict[str, Any], Log=print) -> dict[str, Any]:
    """Generate alternative narration for HUMAN REVIEW, not automatic release.

    Return the original episode untouched with proposals stored separately.
    Even a successful model call cannot modify the video voice-over without
    corresponding reviewed shot assets and new approval receipts.
    """
    result = copy.deepcopy(ep)
    if os.environ.get("ZMB_LOCAL_AI_ENABLED", "1").strip().lower() in {
        "0", "false", "no"
    }:
        result["ai_story"] = {"provider": "local-llama.cpp", "status": "disabled"}
        Log("[local-ai] disabled; preserving the authored visual script")
        return result
    authored = ep.get("lines") or []
    if not authored:
        raise RuntimeError("local AI proposal refused: episode has no authored lines")
    try:
        directions = _directions_for_episode(ep)
        payload = {
            "arc": ep.get("arc"), "node": ep.get("node"),
            "hook": ep.get("hook"), "choices": [
                str(c.get("text", "")) for c in ep.get("choices") or []
            ],
            "lines": [
                {
                    "index": i, "original": line["text"],
                    "visible_action": directions[i]["action"],
                    "physical_props": directions[i]["props"],
                    "cast": [pair[0] for pair in line.get("shot", {}).get("cast") or []],
                }
                for i, line in enumerate(authored)
            ],
        }
        system = (
            "You are a professional English horror-film dialogue editor. Return "
            "ONLY one JSON object with 'lines': an array of objects with 'text'. "
            "Exactly one concise spoken narration line per provided scene; "
            "preserve original scene sequence, named cast, literal physical "
            "actions, objects, timing, place, cause-and-effect and viewer "
            "choices. The visible_action and physical_props are fixed and "
            "CANNOT be changed. No invented vehicle, threat, character, "
            "movement or location; no vote statistics, camera notes, markdown, "
            "intro announcements, emojis or direct engagement prompts. "
            "Write natural suspenseful English without overexplaining."
        )
        from llama_cpp import Llama
        model_path = _model_path(Log)
        Log(f"[local-ai] suggesting script alternatives with {MODEL_REPO} locally")
        llm = Llama(
            model_path=str(model_path), n_ctx=4096,
            n_threads=max(1, min(4, os.cpu_count() or 2)),
            n_batch=256, verbose=False,
        )
        text_payload = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        max_tokens = 1100
        tokenizer = getattr(llm, "tokenize", None)
        if callable(tokenizer):
            # Leave room for chat framing and system instructions; avoid the
            # historical n_ctx overflow ValueError after model downloads.
            try:
                tokens = tokenizer((system + text_payload).encode("utf-8"))
                if isinstance(tokens, (list, tuple)):
                    max_tokens = max(256, min(1100, 4096 - len(tokens) - 350))
            except Exception:
                pass
        if max_tokens < 300:
            raise ValueError("story prompt too long for Qwen context window")
        response = llm.create_chat_completion(
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": text_payload},
            ],
            temperature=0.25, top_p=0.8, max_tokens=max_tokens,
            response_format={"type": "json_object"},
        )
        raw = response["choices"][0]["message"]["content"]
        parsed = json.loads(raw.strip())
        proposals = _validate_lines(
            ep, parsed.get("lines") if isinstance(parsed, dict) else None
        )
        result["ai_story"] = {
            "provider": "local-llama.cpp", "model": MODEL_REPO,
            "quantization": "Q4_K_M", "status": "review_required",
            "suggestions": [line["text"] for line in proposals],
            "note": "PROPOSALS ONLY; voice/video remain the authored approved script",
        }
        Log(f"[local-ai] {len(proposals)} candidate lines saved for review; "
            "published narration NOT changed")
        return result
    except Exception as exc:
        result["ai_story"] = {
            "provider": "local-llama.cpp", "model": MODEL_REPO,
            "status": "fallback", "error": type(exc).__name__,
        }
        Log(
            f"[local-ai] proposal unavailable ({type(exc).__name__}): "
            f"{str(exc)[:220]}; authored narration preserved"
        )
        return result


def generate_hf_image(*args, **kwargs) -> None:
    """Hosted image inference remains disabled."""
    raise RuntimeError("Hosted image inference is disabled in ZMB local-only mode")
