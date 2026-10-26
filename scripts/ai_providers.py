"""Optional hosted AI adapters for ZMB Stories.

Hosted model calls are opt-in via secrets. Nothing here fabricates an AI result:
provider errors are surfaced to the caller and production rendering must stop.
"""
from __future__ import annotations

import json
import os
import time
from typing import Any

import requests

HF_CHAT_URL = "https://router.huggingface.co/v1/chat/completions"
DEFAULT_STORY_MODEL = "Qwen/Qwen2.5-7B-Instruct"
DEFAULT_IMAGE_MODEL = "black-forest-labs/FLUX.1-schnell"


def _token() -> str:
    return (os.environ.get("HF_TOKEN") or "").strip()


def rewrite_episode(ep: dict[str, Any], Log=print) -> dict[str, Any]:
    """Improve dialogue and shot descriptions without changing story graph choices."""
    token = _token()
    if not token:
        Log("[ai-story] HF_TOKEN not configured; keeping authored scenario dialogue.")
        return ep
    model = os.environ.get("HF_STORY_MODEL", DEFAULT_STORY_MODEL).strip()
    original_lines = ep.get("lines") or []
    if not original_lines:
        raise RuntimeError("AI story generation refused: episode has no authored lines")
    request_payload = {
        "season": ep.get("season"), "day": ep.get("day"), "node": ep.get("node"),
        "kind": ep.get("kind"), "hook": ep.get("hook"), "subtitle": ep.get("subtitle"),
        "lines": original_lines, "choices": ep.get("choices") or [],
    }
    system = (
        "You are the screenwriter for ZMB Stories, a cinematic 3D animated zombie-survival short. "
        "Return only valid JSON with keys lines. lines must contain exactly the same number of objects "
        "as input; each object has text (spoken English, concise, vivid, natural) and shot (object with "
        "place, beat, mood, time, cam). Preserve the plot facts, character identities, timeline, and "
        "the meaning/order of all audience choices. Do not invent new choices or change branching. "
        "Max is a young adult survivor with messy dark hair, charcoal hooded jacket and backpack; "
        "Biscuit is his small tan dog with dark ears; Ada is a capable young woman. Non-graphic horror. "
        "Aim for 65-90 spoken words across the episode, with a strong opening and cliffhanger. "
        "Each line should fit a short narrated shot. Do not add markdown."
    )
    body = {
        "model": model, "temperature": 0.7, "max_tokens": 1800,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": json.dumps(request_payload, ensure_ascii=False)},
        ],
    }
    last_error = None
    for attempt in range(3):
        try:
            response = requests.post(
                HF_CHAT_URL, headers={"Authorization": "Bearer " + token,
                "Content-Type": "application/json"}, json=body, timeout=(20, 120))
            if response.status_code >= 400:
                raise RuntimeError("Hugging Face story API HTTP " + str(response.status_code))
            data = response.json()
            content = data["choices"][0]["message"]["content"].strip()
            if content.startswith("```"):
                content = content.split("\n", 1)[1].rsplit("```", 1)[0].strip()
            parsed = json.loads(content)
            new_lines = parsed.get("lines")
            if not isinstance(new_lines, list) or len(new_lines) != len(original_lines):
                raise ValueError("model returned a different number of story lines")
            clean = []
            for i, item in enumerate(new_lines):
                if not isinstance(item, dict) or not str(item.get("text", "")).strip():
                    raise ValueError("model returned an empty narration line")
                shot = item.get("shot")
                if not isinstance(shot, dict):
                    shot = {}
                old_shot = original_lines[i].get("shot") or {}
                merged = {key: shot.get(key, old_shot.get(key)) for key in
                          ("place", "beat", "mood", "time", "cam")}
                if not merged.get("place") or not merged.get("beat"):
                    raise ValueError("model returned incomplete shot metadata")
                clean.append({"text": str(item["text"]).strip(), "shot": merged})
            result = dict(ep)
            result["lines"] = clean
            result["narration"] = [line["text"] for line in clean]
            result["ai_story"] = {"provider": "huggingface", "model": model, "status": "success"}
            Log("[ai-story] generated and validated " + str(len(clean)) + " narration beats via " + model)
            return result
        except Exception as exc:
            last_error = exc
            Log("[ai-story] attempt " + str(attempt + 1) + "/3 failed: " + type(exc).__name__)
            if attempt < 2:
                time.sleep(2 + attempt * 3)
    raise RuntimeError("AI story generation failed after 3 attempts; refusing to silently publish an ungenerated script") from last_error


def generate_hf_image(prompt: str, path, seed: int) -> None:
    """Generate one image through HF Inference Providers. Requires optional SDK."""
    token = _token()
    if not token:
        raise RuntimeError("HF_TOKEN is not configured")
    from huggingface_hub import InferenceClient
    model = os.environ.get("HF_IMAGE_MODEL", DEFAULT_IMAGE_MODEL).strip()
    client = InferenceClient(provider="auto", api_key=token, timeout=240)
    image = client.text_to_image(prompt, model=model, width=720, height=1280, seed=seed)
    if image is None or getattr(image, "size", (0, 0))[0] < 256:
        raise RuntimeError("Hugging Face returned an invalid image")
    image.save(path, format="JPEG", quality=94, optimize=True)
