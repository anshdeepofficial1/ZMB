"""Long-lived token refresh (hari 1st & 15th chalta hai).

Flow:
  1. Purana 60-day token → naya 60-day token (`refresh_access_token`)
  2. Naya token GitHub Secret `IG_ACCESS_TOKEN` mein automatically update (GH_PAT se)

Agar GH_PAT nahi hai to script fail hoti hai — kyunki naya token store nahi ho payega
aur purana apni original date par expire ho jayega. Is case mein manually
`get_token.py` se naya token lo.
"""
from __future__ import annotations

import base64
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import requests  # noqa: E402

from common import log  # noqa: E402

GRAPH = "https://graph.instagram.com"
GITHUB_API = "https://api.github.com"


def update_repo_secret(repo: str, name: str, value: str, pat: str) -> None:
    from nacl import encoding, public

    headers = {"Authorization": f"Bearer {pat}", "Accept": "application/vnd.github+json"}
    key_resp = requests.get(
        f"{GITHUB_API}/repos/{repo}/actions/secrets/public-key", headers=headers, timeout=30
    )
    key_resp.raise_for_status()
    key_data = key_resp.json()

    pub_key = public.PublicKey(key_data["key"].encode(), encoding.Base64Encoder())
    sealed = public.SealedBox(pub_key).encrypt(value.encode())
    payload = {
        "encrypted_value": base64.b64encode(sealed).decode(),
        "key_id": key_data["key_id"],
    }
    put = requests.put(
        f"{GITHUB_API}/repos/{repo}/actions/secrets/{name}",
        headers=headers, json=payload, timeout=30,
    )
    put.raise_for_status()


def main() -> None:
    token = (os.environ.get("IG_ACCESS_TOKEN") or "").strip()
    if not token:
        raise SystemExit("[token] IG_ACCESS_TOKEN secret missing hai")

    resp = requests.get(
        f"{GRAPH}/refresh_access_token",
        params={"grant_type": "ig_refresh_token", "access_token": token},
        timeout=60,
    )
    data = resp.json()
    if "access_token" not in data:
        raise SystemExit(f"[token] refresh FAILED: {data}")

    new_token = data["access_token"]
    days = int(data.get("expires_in", 0)) // 86400
    log(f"[token] refresh OK — naya token ~{days} din ke liye valid (masked: {new_token[:8]}...)")

    repo = (os.environ.get("GITHUB_REPOSITORY") or "").strip()
    pat = (os.environ.get("GH_PAT") or "").strip()
    if repo and pat:
        update_repo_secret(repo, "IG_ACCESS_TOKEN", new_token, pat)
        log("[token] GitHub secret IG_ACCESS_TOKEN update ho gaya — kuch nahi karna tumhe")
    else:
        raise SystemExit(
            "[token] GH_PAT secret set nahi hai → naya token store NAHI ho paya.\n"
            "        SETUP.md PART B dekho: GH_PAT add karo (recommended), ya manually "
            "get_token.py se naya token generate karke IG_ACCESS_TOKEN update karo."
        )


if __name__ == "__main__":
    main()
