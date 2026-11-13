"""Inventory an untrusted ZIP; never extract or execute archive content."""
import hashlib
import json
import sys
import zipfile
from pathlib import Path, PurePosixPath

p = Path(sys.argv[1])
with zipfile.ZipFile(p) as z:
    infos = z.infolist()
    if len(infos) > 5000 or sum(i.file_size for i in infos) > 150_000_000:
        raise ValueError("Archive exceeds inspection budget")
    names = [i.filename for i in infos]
    if any(PurePosixPath(n).is_absolute() or ".." in PurePosixPath(n).parts or "\\" in n for n in names):
        raise ValueError("Unsafe archive path")
    skills = [i for i in infos if PurePosixPath(i.filename).name == "SKILL.md"]
    if not skills:
        raise ValueError("SKILL.md missing")
    markers = {}
    for i in skills:
        if i.file_size > 200_000:
            raise ValueError("Oversized skill document")
        s = z.read(i).decode("utf-8", errors="replace").lower()
        markers[i.filename] = {term: term in s for term in ("2d", "3d", "ffmpeg", "chrome", "python", "node", "remotion", "elevenlabs", "edge-tts", "api key", "setup.sh")}
    print(json.dumps({
        "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
        "entries": len(names), "files": names,
        "skill_requirement_markers": markers,
        "license_files": [n for n in names if PurePosixPath(n).name.lower().startswith(("license", "copying"))],
        "executed": False, "requires_manual_code_and_license_review": True
    }, indent=2))
