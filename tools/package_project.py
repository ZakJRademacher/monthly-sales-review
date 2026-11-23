"""Build a portable bundle and hash the exact packaged bytes."""
import argparse
import hashlib
import json
import os
import sys
import uuid
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
PROJECT = "monthly-sales-automation"
BUNDLE = "monthly-sales-automation-portfolio.zip"
PREFIX = "monthly-sales-automation"


def build(root=ROOT):
    root = Path(root).resolve()
    folders = ["src","sql","tools","tests","docs","deliverables","evidence","powerbi","data/incoming",".github",
               "presentation", "tableau", "powerbi-rebuild", "web"]
    files = {}
    for folder in folders:
        for path in (root/folder).rglob("*"):
            rel = path.relative_to(root)
            if (not path.is_file() or any(part in {"__pycache__", ".pbi", "node_modules", ".git"} for part in rel.parts)
                or any(part.startswith(("latest_", "staging_", ".staging_", "~$")) for part in rel.parts)
                or path.suffix in {".pyc", ".zip"} or path.name.endswith(".inspect.ndjson")
                or path.name == "package-manifest.json"):
                continue
            files[rel.as_posix()] = path.read_bytes()
    root_names = {"README.md","LICENSE","NOTICE",".gitignore",".gitattributes","refresh.py","release.json","design-tokens.json"}
    for path in root.iterdir():
        if path.is_file() and (path.name in root_names or path.name.startswith("requirements") and path.suffix==".txt"):
            files[path.name] = path.read_bytes()
    for name in ["data/LICENSE","data/notes/review_notes.example.csv"]:
        path = root/name
        if path.is_file():
            files[name] = path.read_bytes()
    if "README.md" not in files:
        raise ValueError("Incomplete package inputs")
    release = json.loads(files.get("release.json", b"{}"))
    manifest = {
        "package_schema": 2,
        "project": PROJECT,
        "release": release,
        "results_layout": "Included input deliveries and validated Power BI sample",
        "files": [{"path": name, "bytes": len(content), "sha256": hashlib.sha256(content).hexdigest()} for name, content in sorted(files.items())],
        "omitted": ["raw downloads","generated databases","complete row-level outputs","private review notes","local caches","older ZIPs"],
        "rebuild": "See README.md and docs",
    }
    manifest_bytes = (json.dumps(manifest, indent=2)+"\n").encode("utf-8")
    files["docs/package-manifest.json"] = manifest_bytes
    target = root/BUNDLE
    pending = root/(BUNDLE+"."+uuid.uuid4().hex+".tmp")
    try:
        with zipfile.ZipFile(pending, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            for name, content in sorted(files.items()):
                info = zipfile.ZipInfo(PREFIX+"/"+name, (1980,1,1,0,0,0))
                info.compress_type = zipfile.ZIP_DEFLATED
                archive.writestr(info, content)
        with zipfile.ZipFile(pending) as archive:
            if archive.testzip() is not None:
                raise ValueError("Package integrity check failed")
            for record in manifest["files"]:
                content = archive.read(PREFIX+"/"+record["path"])
                if hashlib.sha256(content).hexdigest() != record["sha256"]:
                    raise ValueError("Packaged file differs from its manifest")
        (root/"docs").mkdir(exist_ok=True)
        (root/"docs/package-manifest.json").write_bytes(manifest_bytes)
        os.replace(pending, target)
    finally:
        if pending.exists():
            pending.unlink()
    return {"zip": str(target), "files": len(files), "sha256": hashlib.sha256(target.read_bytes()).hexdigest(), "manifest_verified": True}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    print(json.dumps(build(), indent=2))
