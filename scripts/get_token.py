"""One-time helper: Instagram Login OAuth se long-lived (60-day) token lo.

Usage:
    # Step 1 — authorize URL print karo, browser mein kholo
    python scripts/get_token.py --app-id <APP_ID> --app-secret <APP_SECRET>

    # Step 2 — redirect URL se `code` copy karke
    python scripts/get_token.py --app-id <APP_ID> --app-secret <APP_SECRET> --code <CODE>

Output: IG_ACCESS_TOKEN + IG_USER_ID — GitHub repo secrets mein daalo.
"""
from __future__ import annotations

import argparse
import sys
import urllib.parse

import requests

GRAPH_VERSION = "v25.0"
SCOPES = "instagram_business_basic,instagram_business_content_publish,instagram_business_manage_comments"


def start_flow(app_id: str, redirect_uri: str) -> None:
    params = {
        "client_id": app_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": SCOPES,
    }
    url = "https://www.instagram.com/oauth/authorize?" + urllib.parse.urlencode(params)
    print("1) Ye URL browser mein kholo aur account se Approve karo:\n")
    print(url)
    print(
        "\n2) Approve ke baad redirect hoga (page error de sakta hai — bilkul normal).\n"
        "   URL bar se `code=` ke baad wali value copy karo.\n"
        "3) Phir chalao:\n"
        f"   python scripts/get_token.py --app-id {app_id} --app-secret <SECRET> --code <CODE>\n"
    )


def finish(app_secret: str, short_token: str) -> None:
    """Short-lived token → 60-day long-lived token + account info print."""
    # short-lived → long-lived (60 days)
    resp2 = requests.get(
        "https://graph.instagram.com/access_token",
        params={
            "grant_type": "ig_exchange_token",
            "client_secret": app_secret,
            "access_token": short_token,
        },
        timeout=60,
    )
    data2 = resp2.json()
    if "access_token" not in data2:
        raise SystemExit(
            f"[token] short→long exchange FAILED: {data2}\n"
            "        Note: ek short token sirf EK BAAR exchange ho sakta hai.\n"
            "        Dashboard se fresh token generate karke dubara try karo."
        )
    long_token = data2["access_token"]
    days = int(data2.get("expires_in", 0)) // 86400

    # account info (IG user id + username)
    me = requests.get(
        f"https://graph.instagram.com/{GRAPH_VERSION}/me",
        params={"fields": "id,user_id,username", "access_token": long_token},
        timeout=60,
    ).json()
    ig_user_id = me.get("user_id") or me.get("id")
    username = me.get("username", "?")

    print("\n=========== GitHub Repo Secrets mein daalo ===========")
    print(f"IG_ACCESS_TOKEN={long_token}")
    print(f"IG_USER_ID={ig_user_id}")
    print(f"IG_USERNAME={username}   (optional — own comments filter ke liye)")
    print("======================================================")
    print(f"\nAccount: @{username} | Token valid: ~{days} din (auto-refresh workflow sambhal lega)")


def exchange(app_id: str, app_secret: str, redirect_uri: str, code: str) -> None:
    # 1) code → short-lived token (~1 hour)
    resp = requests.post(
        "https://api.instagram.com/oauth/access_token",
        data={
            "client_id": app_id,
            "client_secret": app_secret,
            "grant_type": "authorization_code",
            "redirect_uri": redirect_uri,
            "code": code,
        },
        timeout=60,
    )
    data = resp.json()
    if "access_token" not in data:
        raise SystemExit(f"[token] code exchange FAILED: {data}")
    finish(app_secret, data["access_token"])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--app-id", default=None)
    ap.add_argument("--app-secret", required=True)
    ap.add_argument("--redirect-uri", default="https://localhost/")
    ap.add_argument("--code", default=None)
    ap.add_argument("--short-token", default=None,
                    help="Dashboard se mila short-lived token → 60-day long-lived banao")
    args = ap.parse_args()

    if args.short_token:
        finish(args.app_secret, args.short_token)
    elif args.code:
        if not args.app_id:
            raise SystemExit("--code ke saath --app-id bhi chahiye")
        exchange(args.app_id, args.app_secret, args.redirect_uri, args.code)
    else:
        if not args.app_id:
            raise SystemExit("--app-id chahiye (ya --short-token use karo)")
        start_flow(args.app_id, args.redirect_uri)


if __name__ == "__main__":
    main()
