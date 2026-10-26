"""Story engine: vote resolution, plot advancement, episode building.

Pure logic — koi network call nahi. Isliye locally selftest ho sakta hai:
    python scripts/engine.py --selftest
"""
from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import SCENARIOS_PATH, load_config, load_json, log  # noqa: E402


def load_scenarios() -> dict:
    scn = load_json(SCENARIOS_PATH)
    if not scn or "arcs" not in scn:
        raise RuntimeError(f"scenarios.json invalid: {SCENARIOS_PATH}")
    return scn


def clamp(value: int) -> int:
    return max(0, min(100, int(value)))


def apply_effects(state: dict, effects: dict | None) -> None:
    if not effects:
        return
    stats = state.setdefault("stats", {})
    for key, delta in effects.items():
        stats[key] = clamp(stats.get(key, 50) + int(delta))


def find_choice(node: dict, key: str) -> dict:
    for choice in node.get("choices", []):
        if choice["key"] == key:
            return choice
    raise KeyError(f"choice '{key}' not in node")


def substitute(text: str, state: dict) -> str:
    return (
        str(text)
        .replace("{location}", state.get("location", "somewhere on the road"))
        .replace("{season}", str(state.get("season", 1)))
    )


def advance(state: dict, scn: dict, cfg: dict, votes: dict | None = None) -> dict | None:
    """Last episode ko resolve karo: winner decide, effects apply, next node set.

    Returns resolution dict (recap ke liye) ya None agar kuch nahi tha.
    """
    last = state.get("last_episode")
    if not last:
        return None

    arc = scn["arcs"][state["arc"]]
    node = arc["nodes"][last["node"]]
    kind = node.get("kind", "story")
    res: dict = {"node_id": last["node"], "kind": kind}

    if kind in ("vote", "ending"):
        counts = {k: int(v) for k, v in (votes or {}).items()}
        total = sum(counts.values())
        keys = [c["key"] for c in node["choices"]]
        default_key = node.get("default") or keys[0]

        if total < int(cfg.get("min_votes", 10)):
            winner = default_key
            res["fallback"] = True
        elif len(keys) == 1:
            winner = keys[0]
        else:
            ranked = sorted(keys, key=lambda k: (-counts.get(k, 0), k != default_key))
            winner = ranked[0] if counts.get(ranked[0], 0) > counts.get(ranked[1], 0) else default_key

        choice = find_choice(node, winner)
        res.update(
            winner=winner,
            winner_text=choice.get("text", winner),
            pct=round(100 * counts.get(winner, 0) / total) if total else 0,
            total=total,
        )
        apply_effects(state, choice.get("effects"))

        if choice.get("next_arc"):
            nxt = choice["next_arc"]
            if nxt not in scn.get("arcs", {}):
                # Agla season abhi likha nahi gaya — ending par ruk jao
                res["awaiting_arc"] = nxt
                state["node"] = last["node"]
                last["closed"] = True
                return res
            state["arc"] = nxt
            state["season"] = int(state.get("season", 1)) + 1
            if choice.get("location_text"):
                state["location"] = choice["location_text"]
            state["node"] = scn["arcs"].get(nxt, {}).get("start", "intro")
            state["stats"] = {k: int(v) for k, v in cfg.get("stats_reset", state.get("stats", {})).items()}
        else:
            state["node"] = choice["next"]
    else:
        apply_effects(state, node.get("effects"))
        nxt = node.get("next")
        if not nxt:
            raise RuntimeError(f"story node '{last['node']}' has no 'next'")
        state["node"] = nxt

    last["closed"] = True
    return res


def recap_line(res: dict | None) -> str | None:
    if not res:
        return None
    if res.get("awaiting_arc"):
        return "That is the end of the season. The next one is being written right now."
    if res.get("fallback") or int(res.get("total", 0)) <= 0:
        return "Not enough votes came in, so the story chose its own path. Comment to decide next time."
    return f"Last time, {res['pct']} percent of you said: {res['winner_text']}."


def pick_hashtags(cfg: dict, state: dict) -> list[str]:
    pool = list(cfg.get("hashtag_pool", []))
    count = int(cfg.get("hashtags_per_post", 5))
    recent = set(state.get("recent_hashtags", []))
    fresh = [h for h in pool if h not in recent]
    rng = random.Random(f"{state.get('season')}-{state.get('day')}")
    rng.shuffle(fresh)
    picked = fresh[:count]
    if len(picked) < count:
        rest = [h for h in pool if h not in picked]
        rng.shuffle(rest)
        picked += rest[: count - len(picked)]
    state["recent_hashtags"] = (state.get("recent_hashtags", []) + picked)[-len(pool):]
    return picked


def build_caption(cfg: dict, state: dict, node: dict, choices: list[dict], hashtags: list[str], recap: str | None) -> str:
    lines = [substitute(node.get("hook", ""), state), ""]
    if recap:
        lines += [recap, ""]
    if choices:
        for i, choice in enumerate(choices, start=1):
            lines.append(f"{i}\ufe0f\u20e3 {choice['text']}")
        handle = str(cfg.get("handle") or "@zmbstories").strip()
        if handle and not handle.startswith("@"):
            handle = "@" + handle
        lines += [
            "",
            cfg.get("cta_vote", "Comment 1 or 2. The winning choice shapes the next episode."),
            f"Follow {handle} for the next episode." if handle else "Follow for the next episode.",
        ]
    else:
        lines += [cfg.get("cta_story", "Follow @zmbstories to find out what happens next.")]
    lines += ["", cfg.get("fiction_disclaimer", "A fictional animated story."), "", " ".join(hashtags)]
    caption = "\n".join(line for line in lines if line is not None).strip()
    return caption[:2190] + "\u2026" if len(caption) > 2200 else caption


def first_comment(choices: list[dict]) -> str | None:
    if not choices:
        return None
    parts = [f"{i} = {c['text']}" for i, c in enumerate(choices, start=1)]
    return "VOTE KARO \U0001f447 " + "  |  ".join(parts)


def build_episode(state: dict, scn: dict, cfg: dict, recap: str | None = None) -> dict:
    arc_id = state["arc"]
    arc = scn["arcs"][arc_id]
    node_id = state["node"]
    node = arc["nodes"][node_id]
    day = int(state.get("day", 0)) + 1
    season = int(state.get("season", 1))

    raw_lines = node.get("lines") or []
    lines: list[dict] = []
    if recap:
        lines.append({"text": substitute(recap, state),
                      "shot": dict((raw_lines[0].get("shot") if raw_lines else {}) or {})})
    for ln in raw_lines:
        lines.append({
            "text": substitute(ln.get("text", ""), state),
            "shot": substitute_shots(ln.get("shot", {}), state),
        })

    vote = node.get("kind") in ("vote", "ending")
    choices: list[dict] = []
    if vote:
        choices = [
            {
                "key": c["key"],
                "text": substitute(c.get("text", c["key"]), state),
                "labels": [str(l).lower() for l in c.get("labels", [c["key"]])],
                "next_arc": c.get("next_arc"),
                "next": c.get("next"),
            }
            for c in node["choices"]
        ]

    hashtags = pick_hashtags(cfg, state)
    return {
        "season": season,
        "day": day,
        "arc": arc_id,
        "arc_title": arc.get("title", f"Season {season}"),
        "node": node_id,
        "kind": node.get("kind", "story"),
        "subtitle": substitute(node.get("subtitle", arc.get("title", "")), state),
        "hook": substitute(node.get("hook", ""), state),
        "lines": lines,
        "narration": [ln["text"] for ln in lines],
        "ending": substitute_shots(node.get("ending") or {}, state) or None,
        "title_card": bool(day == 1 or node_id == arc.get("start")),
        "vote": vote,
        "choices": choices,
        "stats": dict(state.get("stats", {})),
        "stats_labels": dict(cfg.get("stats_labels", {})),
        "handle": cfg.get("handle", ""),
        "visual_mode_requested": cfg.get("visual_mode", "procedural"),
        "video_name": f"reel_s{season}_d{day:03d}.mp4",
        "caption": build_caption(cfg, state, node, choices, hashtags, recap),
        "first_comment": first_comment(choices),
        "hashtags": hashtags,
    }


def substitute_shots(value, state: dict):
    """Shot trees ke andar {location} jaise placeholders replace karo."""
    if isinstance(value, str):
        return substitute(value, state)
    if isinstance(value, list):
        return [substitute_shots(v, state) for v in value]
    if isinstance(value, dict):
        return {k: substitute_shots(v, state) for k, v in value.items()}
    return value


def commit_episode(
    state: dict, episode: dict, media_id: str, ist_date: str,
    posted_at_ist: str | None = None, post_url: str | None = None
) -> None:
    state["day"] = episode["day"]
    state.setdefault("history", []).append({
        "season": episode["season"],
        "day": episode["day"],
        "arc": episode["arc"],
        "node": episode["node"],
        "kind": episode["kind"],
        "media_id": media_id,
        "video": episode["video_name"],
        "posted_ist_date": ist_date,
        "posted_at_ist": posted_at_ist,
        "post_url": post_url,
        "visual_mode_requested": episode.get("visual_mode_requested", "procedural"),
        "visual_mode_used": episode.get("visual_mode_used", episode.get("visual_mode_requested", "procedural")),
        "ai_story": episode.get("ai_story"),
    })
    state["last_episode"] = {
        "media_id": media_id,
        "posted_at_ist": posted_at_ist,
        "post_url": post_url,
        "visual_mode_requested": episode.get("visual_mode_requested", "procedural"),
        "visual_mode_used": episode.get("visual_mode_used", episode.get("visual_mode_requested", "procedural")),
        "ai_story": episode.get("ai_story"),
        "node": episode["node"],
        "kind": episode["kind"],
        "vote": episode["vote"],
        "choices": [
            {"key": c["key"], "text": c["text"], "labels": c["labels"]}
            for c in episode["choices"]
        ],
        "votes": {},
        "voters": {},
        "closed": False,
    }


def selftest() -> None:
    cfg = load_config()
    scn = load_scenarios()
    state = {
        "schema": 2, "season": 1, "day": 0, "arc": "road", "node": "intro",
        "location": "the empty highway", "stats": dict(cfg.get("stats_reset", {})),
        "history": [], "last_episode": None, "recent_hashtags": [],
    }
    for step in range(14):
        ep = build_episode(state, scn, cfg, None)
        keys = [c["key"] for c in ep["choices"]]
        log(f"[selftest] S{ep['season']} D{ep['day']:>2} node={ep['node']:<16} vote={ep['vote']} choices={keys}")
        commit_episode(state, ep, f"fake_{step}", "2026-01-01")
        if state["last_episode"]["choices"]:
            fake = {c["key"]: 12 - i * 5 for i, c in enumerate(state["last_episode"]["choices"])}
        else:
            fake = {}
        res = advance(state, scn, cfg, fake)
        if res:
            log(f"[selftest]     -> resolved: {res}")
    log("[selftest] OK — branching logic working")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()
    if args.selftest:
        selftest()
    else:
        log("Use --selftest, ya run_cycle.py use karo.")
