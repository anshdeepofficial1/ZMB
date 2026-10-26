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
from ai_providers import rewrite_episode  # noqa: E402
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
    """Fixed daily IST slot: prepare one hour early and avoid posting very late."""
    if force: return now
    interval_hours=max(1,int(cfg.get("publish_every_hours",24)))
    days=max(1,int(round(interval_hours/24)))
    prep_hours=max(0,min(interval_hours-1,int(cfg.get("publish_prepare_hours",1))))
    from datetime import time as clock_time
    try:
        hh,mm=str(cfg.get("publish_time_ist","19:00")).split(":",1)
        slot=clock_time(hour=int(hh),minute=int(mm))
    except (TypeError,ValueError): slot=clock_time(hour=19,minute=0)
    hist=state.get("history") or []
    last=hist[-1] if hist else None
    previous=None
    if last:
        raw=last.get("posted_at_ist") or last.get("posted_at_utc")
        previous=_parse_ist_timestamp(raw,now.tzinfo) if raw else None
        if previous is None and last.get("posted_ist_date"):
            try: previous=datetime.fromisoformat(f"{last['posted_ist_date']}T{slot.hour:02d}:{slot.minute:02d}:00").replace(tzinfo=now.tzinfo)
            except (TypeError,ValueError): previous=None
        if previous is None:
            log("[cycle] previous publish timestamp unreadable; skipping schedule decision")
            return None
        target_date=previous.date()+timedelta(days=days)
    else: target_date=now.date()
    target=datetime.combine(target_date,slot,tzinfo=now.tzinfo)
    while previous is not None and target<=previous: target+=timedelta(days=days)
    if now>target+timedelta(hours=1):
        target+=timedelta(days=days)
        log(f"[cycle] publish window missed; next fixed target is {target.isoformat()}")
    prep=target-timedelta(hours=prep_hours)
    if now<prep:
        remaining=prep-now
        log(f"[cycle] next Reel preparation opens in {remaining.total_seconds()/3600:.1f}h; no render yet")
        return None
    if now<target:
        log(f"[cycle] preparation window open; publish target {target.isoformat()}")
        return target
    log(f"[cycle] target passed by {(now-target).total_seconds()/60:.1f} min; publishing within grace window")
    return now

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="render only — koi API call/post nahi")
    ap.add_argument("--stills", action="store_true", help="har line ka ek still frame (turant preview, video nahi)")
    ap.add_argument("--force-publish", action="store_true", help="time/date gate bypass karo")
    ap.add_argument("--prepare-scheduled", action="store_true",
                    help="render and host a Reel now, then queue it for the configured future publish time")
    args = ap.parse_args()

    cfg = load_config()
    state = load_state()
    scn = engine.load_scenarios()
    pending_path = Path(__file__).resolve().parents[1] / "state" / "pending_episode.json"
    pending = None
    if pending_path.exists():
        try:
            pending = json.loads(pending_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise SystemExit(f"[cycle] pending episode file is unreadable: {exc}") from exc
    if args.prepare_scheduled and pending:
        raise SystemExit("[cycle] a pending Reel already exists; refusing to overwrite it")

    token = (os.environ.get("IG_ACCESS_TOKEN") or "").strip()
    ig_user_id = (os.environ.get("IG_USER_ID") or "").strip()

    visual_mode = str(cfg.get("visual_mode", "procedural")).strip().lower()
    if visual_mode in {"ai_storyboard", "ai_video"}:
        log(f"[cycle] remote visual mode '{visual_mode}' is disabled; using the existing local procedural animation engine")
        cfg["visual_mode"] = "procedural"

    # Fail before spending minutes rendering when required publishing credentials are absent.
    if not args.dry_run and not args.prepare_scheduled:
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
    if not args.dry_run and not args.prepare_scheduled and client is not None and ig_user_id:
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

    if args.prepare_scheduled:
        if not (os.environ.get("GITHUB_REPOSITORY") or "").strip():
            raise SystemExit("[cycle] prepare preflight failed: GITHUB_REPOSITORY missing")
        if not ((os.environ.get("GITHUB_TOKEN") or "").strip()
                or (os.environ.get("GH_PAT") or "").strip()):
            raise SystemExit("[cycle] prepare preflight failed: GITHUB_TOKEN/GH_PAT missing")

    now = ist_now()
    today = now.date().isoformat()
    log(f"[cycle] {now.isoformat()} | dry_run={args.dry_run} force={args.force_publish}")

    # --- 1) vote checkpoint (khuli episode ke naye comments padho) ---
    last = state.get("last_episode")
    if (not args.dry_run and not args.prepare_scheduled and not pending
            and client and ig_user_id and last and last.get("vote") and not last.get("closed")):
        votes_mod.tally(client, cfg, state, own_username)
        save_state(state)

    # --- 2) due check ---
    publish_target = None
    if not args.dry_run and not args.prepare_scheduled:
        now = ist_now()
        today = now.date().isoformat()
        if pending:
            publish_target = _parse_ist_timestamp(pending.get("publish_at_ist"), now.tzinfo)
            if publish_target is None:
                raise SystemExit("[cycle] pending Reel has an invalid publish_at_ist timestamp")
            prep_hours = max(0, min(23, int(cfg.get("publish_prepare_hours", 1))))
            prep_start = publish_target - timedelta(hours=prep_hours)
            if now < prep_start:
                remaining = prep_start - now
                log(f"[cycle] queued Reel ready; preparation window opens in {remaining.total_seconds() / 3600:.1f}h")
                return
            if now >= publish_target:
                log(f"[cycle] queued Reel target reached/passed ({publish_target.isoformat()}); publishing now")
                publish_target = now
            else:
                remaining_seconds = (publish_target - now).total_seconds()
                grace_seconds = max(0, int(cfg.get("publish_wait_grace_seconds", 300)))
                if remaining_seconds <= grace_seconds:
                    log(
                        f"[cycle] scheduled time is {remaining_seconds:.0f}s away; "
                        "waiting briefly to publish on the 24-hour target"
                    )
                    time.sleep(max(0, remaining_seconds))
                    publish_target = ist_now()
                else:
                    log(f"[cycle] queued Reel is ready; next publish check at {publish_target.isoformat()}; no runner held open")
                    return
        else:
            publish_target = _publish_target(state, cfg, now, args.force_publish)
            if publish_target is None:
                return

        # Check publishing quota before rendering or publishing; avoid wasting runner minutes
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
                        "skipping publish and waiting for quota reset."
                    )
            if quota_rows:
                log(f"[cycle] publishing quota preflight: {quota_rows}")
        except SystemExit:
            raise
        except Exception as exc:
            log(f"[cycle] quota preflight unavailable (non-fatal): {exc}")

    # --- 3/4) Use queued episode or resolve the story, then render ---
    # If AI generation/rendering fails, do not persist an advanced story node or day.
    pre_generation_state = json.loads(json.dumps(state))
    episode = None
    result = None
    if pending and not args.dry_run and not args.prepare_scheduled:
        episode = pending.get("episode")
        if not isinstance(episode, dict) or not pending.get("video_url"):
            raise SystemExit("[cycle] pending Reel record is missing episode/video_url")
        log(f"[cycle] using queued Reel S{episode.get('season')} D{episode.get('day')} — no rerender")
        result = {"video_path": None}
    else:
        last = state.get("last_episode")
        recap = None
        if last:
            if last.get("vote") and not last.get("closed"):
                if client and ig_user_id and not args.dry_run and not args.prepare_scheduled:
                    votes_mod.tally(client, cfg, state, own_username)
                resolution = engine.advance(state, scn, cfg, last.get("votes"))
            else:
                resolution = engine.advance(state, scn, cfg, None)
            recap = engine.recap_line(resolution)
            if resolution:
                log(f"[cycle] resolution → {resolution}")

        episode = engine.build_episode(state, scn, cfg, recap)
        if bool(cfg.get("ai_story_generation", True)):
            episode = rewrite_episode(episode, log)
        else:
            episode["ai_story"] = {"provider": "local-llama.cpp", "status": "disabled"}
            log("[local-ai] disabled by config; using authored scenario script")
        log(f"[cycle] episode: S{episode['season']} D{episode['day']} "
            f"node={episode['node']} kind={episode['kind']} vote={episode['vote']}")
        if args.stills:
            stills = render.render_stills(cfg, episode)
            log(f"[cycle] stills → {len(stills)} files in out/stills")
            (OUT_DIR / "caption.txt").write_text(episode["caption"] + "\n", encoding="utf-8")
            log("[cycle] dry-run complete: stills only")
            return
        try:
            result = render.render_episode(cfg, episode)
        except Exception:
            state.clear()
            state.update(pre_generation_state)
            save_state(state)
            raise

    # Debug artifacts: upload a rendered file only when this run actually rendered it.
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

    if args.prepare_scheduled:
        from datetime import time as clock_time

        try:
            hour_text, minute_text = str(cfg.get("publish_time_ist", "20:00")).split(":", 1)
            target_date = ist_now().date() + timedelta(days=1)
            target = datetime.combine(
                target_date,
                clock_time(hour=int(hour_text), minute=int(minute_text)),
                tzinfo=ist_now().tzinfo,
            )
        except (TypeError, ValueError):
            raise SystemExit("[cycle] invalid publish_time_ist in config.json")
        media_url = publish.push_media_to_github(result["video_path"], episode["video_name"], cfg)
        if not media_url:
            raise SystemExit("[cycle] public media URL nahi mila while preparing scheduled Reel")
        pending_record = {
            "schema": 1,
            "prepared_at_ist": ist_now().isoformat(),
            "publish_at_ist": target.isoformat(),
            "video_url": media_url,
            "episode": episode,
        }
        pending_path.parent.mkdir(parents=True, exist_ok=True)
        pending_path.write_text(json.dumps(pending_record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        save_state(state)
        log(f"[cycle] QUEUED: S{episode['season']} D{episode['day']} for {target.isoformat()}")
        return

    # --- 5) publish ---
    if client is None or not ig_user_id:
        raise SystemExit("[cycle] IG_ACCESS_TOKEN / IG_USER_ID missing — publish nahi ho sakta")

    media_url = pending.get("video_url") if pending else None
    if not media_url:
        media_url = publish.push_media_to_github(result["video_path"], episode["video_name"], cfg)
    if not media_url:
        raise SystemExit("[cycle] public media URL nahi mila (repo/GITHUB_REPOSITORY check karo)")

    # If this run began in the final-hour window, persist the prepared Reel and exit.
    # The scheduled run at/after the target time publishes the existing hosted file.
    if (not pending and publish_target is not None and publish_target > ist_now()
            and not args.force_publish):
        pending_record = {
            "schema": 1,
            "prepared_at_ist": ist_now().isoformat(),
            "publish_at_ist": publish_target.isoformat(),
            "video_url": media_url,
            "episode": episode,
        }
        pending_path.parent.mkdir(parents=True, exist_ok=True)
        pending_path.write_text(json.dumps(pending_record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        save_state(state)
        log(f"[cycle] QUEUED: S{episode['season']} D{episode['day']} for {publish_target.isoformat()}")
        return

    media_id = publish.publish_reel(client, cfg, ig_user_id, episode, media_url)
    post_url = None
    try:
        details = client.get(media_id, fields="permalink")
        post_url = details.get("permalink")
        if post_url: log(f"[publish] Instagram permalink recorded: {post_url}")
    except Exception as exc:
        log(f"[publish] permalink lookup skipped (non-fatal): {exc}")
    posted_at = ist_now()
    today = posted_at.date().isoformat()
    engine.commit_episode(state, episode, media_id, today, posted_at.isoformat(), post_url=post_url)
    save_state(state)
    if pending and pending_path.exists():
        pending_path.unlink()
        log("[cycle] queued Reel cleared after successful publish")
    log(f"[cycle] SUCCESS: S{episode['season']} D{episode['day']} live (media_id={media_id})")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
        sys.exit(1)
