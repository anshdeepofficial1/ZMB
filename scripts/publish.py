"""Publish: video ko GitHub media branch par host karo + Instagram REELS post karo.

- Video hosting: `media` branch (orphan, always 1 file, force-push) → raw.githubusercontent.com URL
  Kyun? Instagram Login flavor resumable upload support nahi karta (verified Meta docs),
  aur video URL Meta ko publicly fetch karna hota hai.
- Instagram: container create → status poll (FINISHED) → media_publish → first comment.
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import ApiError, ROOT, log, run  # noqa: E402


def push_media_to_github(video_path: str, name: str, cfg: dict) -> str | None:
    repo = (os.environ.get("GITHUB_REPOSITORY") or "").strip()
    if not repo:
        log("[publish] GITHUB_REPOSITORY set nahi — local mode, upload skip")
        return None

    branch = cfg.get("media_branch", "media")
    origin = run(["git", "remote", "get-url", "origin"], cwd=ROOT).stdout.strip()
    if not origin:
        raise RuntimeError("git remote 'origin' nahi mila")

    tmp = Path(tempfile.mkdtemp(prefix="media_push_"))
    try:
        shutil.copy2(video_path, tmp / name)
        run(["git", "init", "-q"], cwd=tmp)
        run(["git", "config", "user.email", "bot@users.noreply.github.com"], cwd=tmp)
        run(["git", "config", "user.name", "zombie-bot"], cwd=tmp)
        run(["git", "add", name], cwd=tmp)
        run(["git", "commit", "-q", "-m", f"media: {name}"], cwd=tmp)
        run(["git", "push", "--force", origin, f"HEAD:refs/heads/{branch}"], cwd=tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    url = f"https://raw.githubusercontent.com/{repo}/{branch}/{name}"
    log(f"[publish] video public URL: {url}")
    return url


def publish_reel(client, cfg: dict, ig_user_id: str, episode: dict, video_url: str) -> str:
    try:
        limit = client.get(f"{ig_user_id}/content_publishing_limit")
        log(f"[publish] quota check: {limit}")
    except Exception as exc:
        log(f"[publish] quota check skipped: {exc}")

    data = {
        "media_type": "REELS",
        "video_url": video_url,
        "caption": episode["caption"],
        "share_to_feed": "true",
    }
    if cfg.get("ai_disclosure", True):
        data["is_ai_generated"] = "true"

    container = client.post(f"{ig_user_id}/media", **data)
    container_id = container["id"]
    log(f"[publish] container banaya: {container_id}")

    status = None
    for _ in range(30):
        time.sleep(10)
        payload = client.get(container_id, fields="status_code")
        status = payload.get("status_code")
        log(f"[publish] container status: {status}")
        if status == "FINISHED":
            break
        if status in ("ERROR", "EXPIRED"):
            raise ApiError(f"container {status} — video/caption check karo")

    if status != "FINISHED":
        raise ApiError("container 5 minute mein FINISHED nahi hua")

    published = client.post(f"{ig_user_id}/media_publish", creation_id=container_id)
    media_id = published["id"]
    log(f"[publish] LIVE: media_id={media_id}")

    if episode.get("first_comment"):
        try:
            client.post(f"{media_id}/comments", message=episode["first_comment"])
            log("[publish] first comment (vote CTA) post ho gaya")
        except Exception as exc:
            log(f"[publish] first comment fail (non-fatal): {exc}")

    return media_id
