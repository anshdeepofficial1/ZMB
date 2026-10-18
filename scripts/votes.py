"""Comment votes padho (Instagram Graph API) aur tally karo.

Design: idempotent. `last_episode.voters` = {username: choice_key} — jo user
pehle vote kar chuka, uske naye comments ignore hote hain.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import log  # noqa: E402

# Latin letters/digits/spaces + Devanagari rakhо, baaki punctuation hata do
_CLEAN = re.compile(r"[^\w\s\u0900-\u097F]", re.UNICODE)


def normalize(text: str) -> str:
    text = (text or "").lower().strip()
    text = _CLEAN.sub(" ", text)
    return re.sub(r"\s+", " ", text).strip()


def match_vote(text: str, label_map: dict[str, list[str]]) -> str | None:
    """Comment text ko choice key se match karo. Pehla match jeeta."""
    t = normalize(text)
    if not t:
        return None
    tokens = t.split()
    for key, labels in label_map.items():
        for label in labels:
            if " " in label:
                if label in t:
                    return key
            elif label in tokens:
                return key
    return None


def fetch_comments(client, media_id: str, max_pages: int = 3) -> list[dict]:
    comments: list[dict] = []
    payload = client.get(
        f"{media_id}/comments",
        fields="id,text,username,timestamp",
        limit=50,
    )
    pages = 0
    while True:
        comments.extend(payload.get("data", []))
        pages += 1
        next_url = (payload.get("paging") or {}).get("next")
        if not next_url or pages >= max_pages:
            break
        payload = client.get_next(next_url)
    return comments


def tally(client, cfg: dict, state: dict, own_username: str | None = None) -> dict:
    last = state.get("last_episode")
    if not last or not last.get("vote") or last.get("closed"):
        return dict((last or {}).get("votes", {}))

    own = (own_username or "").lstrip("@").lower()
    label_map = {c["key"]: [str(l).lower() for l in c["labels"]] for c in last["choices"]}
    voters: dict[str, str] = last.setdefault("voters", {})

    try:
        comments = fetch_comments(client, last["media_id"])
    except Exception as exc:  # network/API issue → purana tally wapas
        log(f"[votes] comments fetch failed: {exc}")
        return dict(last.get("votes", {}))

    for comment in comments:
        user = (comment.get("username") or "").strip()
        if not user:
            continue
        if own and user.lower() == own:
            continue
        if user in voters:
            continue
        text = comment.get("text", "")
        # Hamara khud ka CTA first-comment ("VOTE KARO ...") vote count na ho
        if normalize(text).startswith("vote karo"):
            continue
        key = match_vote(text, label_map)
        if key:
            voters[user] = key

    counts: dict[str, int] = {}
    for key in voters.values():
        counts[key] = counts.get(key, 0) + 1
    last["votes"] = counts
    log(f"[votes] media={last['media_id']} comments_seen={len(comments)} tally={counts}")
    return counts
