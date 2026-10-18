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
    short_token = data["access_token"]

    # 2) short-lived → long-lived (60 days)
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
    long_token = data2.get("access_token", short_token)
    days = int(data2.get("expires_in", 0)) // 86400

    # 3) account info (IG user id + username)
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


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--app-id", required=True)
    ap.add_argument("--app-secret", required=True)
    ap.add_argument("--redirect-uri", default="https://localhost/")
    ap.add_argument("--code", default=None)
    args = ap.parse_args()

    if not args.code:
        start_flow(args.app_id, args.redirect_uri)
    else:
        exchange(args.app_id, args.app_secret, args.redirect_uri, args.code)


if __name__ == "__main__":
    main()
