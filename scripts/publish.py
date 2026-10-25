"""Publish: video ko GitHub media branch par host karo + Instagram REELS post karo.

- Video hosting: `media` branch (orphan, always 1 file, force-push) → raw.githubusercontent.com URL
  Kyun? Instagram Login flavor resumable upload support nahi karta (verified Meta docs),
  aur video URL Meta ko publicly fetch karna hota hai.
- Instagram: container create → status poll (FINISHED) → media_publish → first comment.
"""
from __future__ import annotations

import base64
import os
import re
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

        # The temp repository does not inherit checkout's credential helper. Add
        # an in-memory HTTPS auth header for this push; never put tokens in the URL
        # or command line (the latter is included in errors by common.run).
        token = (os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_PAT") or "").strip()
        if not token:
            raise RuntimeError("GitHub push token missing (GITHUB_TOKEN/GH_PAT)")

        header = base64.b64encode(f"x-access-token:{token}".encode("utf-8")).decode("ascii")
        try:
            config_count = max(0, int(os.environ.get("GIT_CONFIG_COUNT", "0")))
        except ValueError:
            config_count = 0
        added_keys = {
            "GIT_CONFIG_COUNT": str(config_count + 1),
            f"GIT_CONFIG_KEY_{config_count}": "http.https://github.com/.extraheader",
            f"GIT_CONFIG_VALUE_{config_count}": f"AUTHORIZATION: basic {header}",
        }
        previous = {key: os.environ.get(key) for key in added_keys}
        try:
            os.environ.update(added_keys)
            run(["git", "push", "--force", origin, f"HEAD:refs/heads/{branch}"], cwd=tmp)
        finally:
            for key, value in previous.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value
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

    caption = str(episode.get("caption") or "").strip()
    if not caption:
        raise RuntimeError("Caption is empty; refusing to publish an unlabelled Reel")
    if len(caption) > 2200:
        raise RuntimeError(f"Caption is too long ({len(caption)} characters; limit is 2200)")
    hashtag_count = len(re.findall(r"(?<!\w)#[\w]+", caption, flags=re.UNICODE))
    if hashtag_count > 5:
        raise RuntimeError(
            f"Caption contains {hashtag_count} hashtags; use 5 or fewer to avoid publishing rejection"
        )
    for choice in episode.get("choices") or []:
        choice_text = str(choice.get("text") or "").strip()
        if choice_text and choice_text not in caption:
            raise RuntimeError(f"Caption is missing choice option: {choice_text}")

    data = {
        "media_type": "REELS",
        "video_url": video_url,
        "caption": caption,
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
    config_issue = published.get("config_issue")
    if config_issue:
        # Meta may publish the Reel while dropping part of the request (for example,
        # a caption failing integrity checks). Log it, but still return the media ID
        # so the caller saves state and does not accidentally publish a duplicate.
        log(f"[publish] WARNING: Instagram returned config_issue={config_issue}")
    log(f"[publish] LIVE: media_id={media_id}")

    if episode.get("first_comment"):
        try:
            client.post(f"{media_id}/comments", message=episode["first_comment"])
            log("[publish] first comment (vote CTA) post ho gaya")
        except Exception as exc:
            log(f"[publish] first comment fail (non-fatal): {exc}")

    return media_id
