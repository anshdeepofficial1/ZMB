"""Main orchestrator — daytime vote checks + final-hour daily publishing window.

Cycle:
  1. Agar koi episode khuli hai (vote open) → comments se tally (checkpoint)
  2. Agar aaj post nahi hua + publish hour aaya → votes resolve → advance
  3. Nayi episode banao (engine) → video render (render.py)
  4. Video host karo (GitHub media branch) → Instagram par REELS publish
  5. State save (workflow ise commit karta hai)

Local testing:
    python scripts/run_cycle.py --dry-run          # sirf render, koi post nahi
    python scripts/run_cycle.py --dry-run --force-publish
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import traceback
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import engine  # noqa: E402
import publish  # noqa: E402
import render  # noqa: E402
import votes as votes_mod  # noqa: E402
from common import OUT_DIR, GraphClient, ist_now, load_config, load_state, log, save_state  # noqa: E402


def _parse_ist_timestamp(value: str, tzinfo) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=tzinfo)
        return parsed.astimezone(tzinfo)
    except (TypeError, ValueError):
        return None


def _publish_target(state: dict, cfg: dict, now: datetime, force: bool) -> datetime | None:
    """Schedule the first post at the configured local time; later posts at 24h cadence.

    The workflow starts preparation once the previous post is 23h old, then renders
    and hosts the video before waiting for the 24h target. This keeps the heavy work
    inside the final hour and prevents a run at a random checkpoint from posting.
    """
    if force:
        return now

    interval_hours = max(1, int(cfg.get("publish_every_hours", 24)))
    prepare_hours = max(0, min(interval_hours - 1, int(cfg.get("publish_prepare_hours", 1))))
    history = state.get("history") or []
    last_item = history[-1] if history else None

    if last_item:
        raw_timestamp = last_item.get("posted_at_ist") or last_item.get("posted_at_utc")
        previous = _parse_ist_timestamp(raw_timestamp, now.tzinfo) if raw_timestamp else None
        if previous is None and last_item.get("posted_ist_date"):
            # Backward-compatible fallback for older state records that saved only
            # the date. Assume the configured daily posting time for that old post.
            try:
                hour_text, minute_text = str(cfg.get("publish_time_ist", "20:00")).split(":", 1)
                previous = datetime.fromisoformat(
                    f"{last_item['posted_ist_date']}T{int(hour_text):02d}:{int(minute_text):02d}:00"
                ).replace(tzinfo=now.tzinfo)
            except (TypeError, ValueError):
                previous = None

        if previous is None:
            log("[cycle] cannot parse previous publish time; safe fallback is next configured posting window")
            return None

        target = previous + timedelta(hours=interval_hours)
        earliest_start = target - timedelta(hours=prepare_hours)
        if now < earliest_start:
            remaining = earliest_start - now
            log(f"[cycle] next Reel preparation opens in {remaining.total_seconds() / 3600:.1f}h; no render yet")
            return None
        if now < target:
            log(f"[cycle] inside final {prepare_hours}h preparation window; target publish time {target.isoformat()}")
            return target
        log(f"[cycle] target time passed by {(now - target).total_seconds() / 60:.1f} min; publishing as soon as ready")
        return now

    # Initial launch: use a fixed, researched baseline rather than posting at the
    # first arbitrary workflow checkpoint. Once history exists, preserve 24h cadence.
    try:
        hour_text, minute_text = str(cfg.get("publish_time_ist", "20:00")).split(":", 1)
        target = now.replace(
            hour=int(hour_text), minute=int(minute_text), second=0, microsecond=0
        )
    except (TypeError, ValueError):
        target = now.replace(hour=20, minute=0, second=0, microsecond=0)

    prep_start = target - timedelta(hours=prepare_hours)
    if now < prep_start:
        log(f"[cycle] first-post preparation opens at {prep_start.isoformat()}; no render yet")
        return None
    if now > target + timedelta(hours=1):
        log(f"[cycle] first-post window for today was missed; will try tomorrow near {cfg.get('publish_time_ist', '20:00')} IST")
        return None
    return target if now < target else now


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="render only — koi API call/post nahi")
    ap.add_argument("--stills", action="store_true", help="har line ka ek still frame (turant preview, video nahi)")
    ap.add_argument("--force-publish", action="store_true", help="time/date gate bypass karo")
    args = ap.parse_args()

    cfg = load_config()
    state = load_state()
    scn = engine.load_scenarios()

    token = (os.environ.get("IG_ACCESS_TOKEN") or "").strip()
    ig_user_id = (os.environ.get("IG_USER_ID") or "").strip()

    # Fail before spending minutes rendering when required publishing credentials are absent.
    if not args.dry_run:
        missing = []
        if not token:
            missing.append("IG_ACCESS_TOKEN")
        if not ig_user_id:
            missing.append("IG_USER_ID")
        if os.environ.get("GITHUB_REPOSITORY") and not (
            os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_PAT")
        ):
            missing.append("GITHUB_TOKEN/GH_PAT")
        if missing:
            raise SystemExit(
                "[cycle] preflight failed before rendering: missing " + ", ".join(missing)
            )

    client = GraphClient(token) if token else None

    own_username = (os.environ.get("IG_USERNAME") or "").strip() or None
    if not args.dry_run and client is not None and ig_user_id:
        # Validate the token/account before paying the render cost.
        try:
            profile = client.get("me", fields="user_id,username")
        except Exception as exc:
            raise SystemExit(
                "[cycle] Instagram credential preflight failed before rendering: "
                + str(exc)
            ) from exc

        profile_id = str(profile.get("user_id") or "").strip()
        if profile_id and profile_id != ig_user_id:
            raise SystemExit(
                "[cycle] IG_USER_ID does not match the account returned by IG_ACCESS_TOKEN; "
                "refusing to publish to the wrong account."
            )
        if not own_username:
            own_username = profile.get("username")



    now = ist_now()
    today = now.date().isoformat()
    log(f"[cycle] {now.isoformat()} | dry_run={args.dry_run} force={args.force_publish}")

    # --- 1) vote checkpoint (khuli episode ke naye comments padho) ---
    last = state.get("last_episode")
    if (not args.dry_run and client and ig_user_id
            and last and last.get("vote") and not last.get("closed")):
        votes_mod.tally(client, cfg, state, own_username)
        save_state(state)

    # --- 2) due check ---
    publish_target = None
    if not args.dry_run:
        now = ist_now()
        today = now.date().isoformat()
        publish_target = _publish_target(state, cfg, now, args.force_publish)
        if publish_target is None:
            return

        # Check publishing quota before rendering; avoid wasting runner minutes
        # if the account has already exhausted the API publishing window.
        try:
            quota_payload = client.get(f"{ig_user_id}/content_publishing_limit")
            quota_rows = quota_payload.get("data") or []
            for quota_row in quota_rows:
                usage = int(quota_row.get("quota_usage", 0) or 0)
                total = int(quota_row.get("quota_total", 0) or 0)
                if total > 0 and usage >= total:
                    raise SystemExit(
                        f"[cycle] publishing quota exhausted ({usage}/{total}); "
                        "skipping render and waiting for quota reset."
                    )
            if quota_rows:
                log(f"[cycle] publishing quota preflight: {quota_rows}")
        except SystemExit:
            raise
        except Exception as exc:
            # Quota read can be transient; publish_reel performs a second check.
            log(f"[cycle] quota preflight unavailable (non-fatal): {exc}")

    # --- 3) pichhli episode resolve karo + agla node set karo ---
    last = state.get("last_episode")
    recap = None
    if last:
        if last.get("vote") and not last.get("closed"):
            if client and ig_user_id and not args.dry_run:
                votes_mod.tally(client, cfg, state, own_username)
            resolution = engine.advance(state, scn, cfg, last.get("votes"))
        else:
            resolution = engine.advance(state, scn, cfg, None)
        recap = engine.recap_line(resolution)
        if resolution:
            log(f"[cycle] resolution → {resolution}")

    # --- 4) episode banao + render ---
    episode = engine.build_episode(state, scn, cfg, recap)
    log(f"[cycle] episode: S{episode['season']} D{episode['day']} "
        f"node={episode['node']} kind={episode['kind']} vote={episode['vote']}")
    if args.stills:
        stills = render.render_stills(cfg, episode)
        log(f"[cycle] stills → {len(stills)} files in out/stills")
        (OUT_DIR / "caption.txt").write_text(episode["caption"] + "\n", encoding="utf-8")
        log("[cycle] dry-run complete: stills only")
        return
    result = render.render_episode(cfg, episode)

    # debug artifacts (workflow inhe artifact ke roop mein upload karta hai)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "episode.json").write_text(
        json.dumps(episode, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (OUT_DIR / "caption.txt").write_text(episode["caption"] + "\n", encoding="utf-8")

    if args.dry_run:
        print("\n================ CAPTION ================")
        print(episode["caption"])
        print("=========================================")
        log(f"[cycle] dry-run complete: {result['video_path']}")
        return

    # --- 5) publish ---
    if client is None or not ig_user_id:
        raise SystemExit("[cycle] IG_ACCESS_TOKEN / IG_USER_ID missing — publish nahi ho sakta")

    media_url = publish.push_media_to_github(result["video_path"], episode["video_name"], cfg)
    if not media_url:
        raise SystemExit("[cycle] public media URL nahi mila (repo/GITHUB_REPOSITORY check karo)")

    # Video is already rendered and hosted before the deadline. For scheduled runs,
    # hold the job until the 24h publish target; manual force-publish remains immediate.
    if publish_target is not None and not args.force_publish:
        wait_seconds = (publish_target - ist_now()).total_seconds()
        if wait_seconds > 0:
            log(f"[cycle] Reel prepared and hosted; waiting {wait_seconds / 60:.1f} min for planned publish time")
            time.sleep(wait_seconds)

    media_id = publish.publish_reel(client, cfg, ig_user_id, episode, media_url)

    # --- 6) state save ---
    posted_at = ist_now()
    today = posted_at.date().isoformat()
    engine.commit_episode(state, episode, media_id, today, posted_at.isoformat())
    save_state(state)
    log(f"[cycle] SUCCESS: S{episode['season']} D{episode['day']} live (media_id={media_id})")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
        sys.exit(1)
