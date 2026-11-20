"""Copy the data files that git does not hold to a backup folder.

Some inputs are kept out of the repo: store-and-link sources (data/linked/), large downloads, pollster PDFs and saved
Wikipedia pages (see .gitignore and DATA.md). They can be fetched again while their sources last, but some sources are
live pages that can change or go away. This script copies every git-ignored file under data/ to a folder outside the
repo, keeping the same paths, so the backup always covers whatever is off-repo at the time it runs.

- The destination is `backup_dir` in .env (or the BACKUP_DIR environment variable), so no private path is committed.
- A file is copied when the backup lacks it or its size or modified time differs. Nothing is ever deleted from the
  backup: a file removed here stays there.
- `.env` itself is not copied (it holds API keys).
- `backup_manifest.json` in the destination lists every file with its size and SHA-256, with the commit backed up from.

Run:  python src/backup_offrepo.py [--dry-run]
Restore: copy the backup's `data` folder over the repo's.
"""
import datetime as dt
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "collect"))
from common import ROOT, env_key  # noqa: E402

SKIP_PARTS = {"__pycache__"}


def off_repo_files():
    out = subprocess.run(["git", "ls-files", "--others", "--ignored", "--exclude-standard", "-z", "--", "data"],
                         cwd=ROOT, capture_output=True, check=True).stdout.decode("utf-8")
    files = [ROOT / f for f in out.split("\0") if f]
    return sorted(f for f in files if f.is_file() and not SKIP_PARTS & set(f.parts))


def sha256(p):
    h = hashlib.sha256()
    with p.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def run(dry=False):
    dest = env_key("backup_dir")
    if not dest:
        raise SystemExit("set backup_dir in .env to the folder that should hold the backup")
    dest = Path(dest)
    if not dest.is_dir():
        raise SystemExit(f"backup folder does not exist: {dest}")
    files = off_repo_files()
    mf = dest / "backup_manifest.json"
    old = json.loads(mf.read_text(encoding="utf-8")).get("files", {}) if mf.exists() else {}
    copied, nbytes, entries = 0, 0, {}
    for f in files:
        rel = f.relative_to(ROOT).as_posix()
        to, st = dest / rel, f.stat()
        same = to.exists() and to.stat().st_size == st.st_size and int(to.stat().st_mtime) == int(st.st_mtime)
        if not same:
            copied, nbytes = copied + 1, nbytes + st.st_size
            if not dry:
                to.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(f, to)
        prev = old.get(rel)
        digest = prev["sha256"] if same and prev and prev.get("bytes") == st.st_size else (None if dry else sha256(f))
        entries[rel] = {"bytes": st.st_size, "sha256": digest}
    total = sum(e["bytes"] for e in entries.values())
    print(f"{len(files)} off-repo files, {total / 1e6:.0f} MB; {'would copy' if dry else 'copied'} {copied} "
          f"({nbytes / 1e6:.0f} MB) to {dest}")
    if dry:
        return
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    kept = {k: v for k, v in old.items() if k not in entries}       # files since removed from the repo folder
    mf.write_text(json.dumps({"backed_up": dt.datetime.now().isoformat(timespec="seconds"), "commit": commit,
                              "files": entries, "no_longer_in_repo_folder": kept}, indent=1), encoding="utf-8")
    bad = [r for r, e in entries.items() if (dest / r).stat().st_size != e["bytes"]]
    if bad:
        raise SystemExit(f"size mismatch after copy: {bad[:5]}")


if __name__ == "__main__":
    run(dry="--dry-run" in sys.argv)
