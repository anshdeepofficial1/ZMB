"""Explicitly install pinned official LTX-Video inside the ZMB workspace.

This is invoked by a human on a CUDA machine and NEVER automatically by
the Instagram posting workflow. It installs code, not a fake GPU.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys

from ltx_local_video import OFFICIAL_LTX_COMMIT, OFFICIAL_LTX_REPO
from visual_manifest import ROOT, VisualContractError


def bootstrap(destination: Path, *, install: bool) -> dict:
    destination = destination.resolve()
    if install:
        destination.parent.mkdir(parents=True, exist_ok=True)
        if not (destination / ".git").exists():
            if destination.exists():
                raise VisualContractError(
                    f"Target already exists but is not a git checkout: {destination}"
                )
            subprocess.run([
                "git", "clone", "--filter=blob:none", "--no-checkout",
                OFFICIAL_LTX_REPO, str(destination),
            ], check=True)
        subprocess.run(
            ["git", "-C", str(destination), "fetch", "--depth", "1",
             "origin", OFFICIAL_LTX_COMMIT],
            check=True,
        )
        subprocess.run(
            ["git", "-C", str(destination), "checkout", "--detach", "FETCH_HEAD"],
            check=True,
        )
        subprocess.run([
            sys.executable, "-m", "pip", "install",
            "-e", str(destination) + "[inference]",
        ], check=True)
    if not (destination / "inference.py").is_file():
        raise VisualContractError(
            f"No LTX code at {destination}; run this tool with --install"
        )
    check = subprocess.run(
        ["git", "-C", str(destination), "rev-parse", "HEAD"],
        text=True, capture_output=True, check=True,
    ).stdout.strip()
    if check != OFFICIAL_LTX_COMMIT:
        raise VisualContractError(
            f"LTX source revision mismatch: {check}; expected {OFFICIAL_LTX_COMMIT}"
        )
    for name in ("ltxv-2b-0.9.8-distilled.yaml", "ltxv-13b-0.9.8-distilled.yaml"):
        if not (destination / "configs" / name).is_file():
            raise VisualContractError(f"Missing official LTX model configuration: {name}")
    return {
        "upstream": OFFICIAL_LTX_REPO, "revision": check,
        "code_installed": True,
        "weights_installed": "resolved and cached by official inference on first GPU run",
        "instagram_publishing": False,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--install", action="store_true",
                    help="Clone pinned source + install inference dependencies (large)")
    ap.add_argument("--verify", action="store_true",
                    help="Only inspect installed source revision, no download")
    ap.add_argument("--ltx-root", type=Path,
                    default=ROOT / ".models" / "LTX-Video")
    args = ap.parse_args()
    if args.install == args.verify:
        ap.error("choose exactly one of --install / --verify")
    print(bootstrap(args.ltx_root, install=args.install))


if __name__ == "__main__":
    main()
