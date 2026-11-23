"""Shared download helpers: every raw file lands in data/raw/<source>/<date>/ with a manifest."""
import datetime as dt
import json
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw"
TODAY = dt.date.today().isoformat()
UA = "earlyreturns-research/0.1 (personal election forecasting project; https://earlyreturns.vikramrai.com; https://github.com/vrraiv/earlyreturns)"

SESSION = requests.Session()
SESSION.headers["User-Agent"] = UA


def raw_dir(source: str) -> Path:
    d = RAW / source / TODAY
    d.mkdir(parents=True, exist_ok=True)
    return d


def _log(d: Path, name: str, url: str, nbytes: int):
    mf = d / "manifest.json"
    m = json.loads(mf.read_text()) if mf.exists() else {}
    m[name] = {"url": url, "retrieved": dt.datetime.now().isoformat(timespec="seconds"), "bytes": nbytes}
    mf.write_text(json.dumps(m, indent=2))


def fetch(source: str, name: str, url: str, params=None, headers=None, retries=3, skip_existing=True, timeout=120) -> Path:
    d = raw_dir(source)
    out = d / name
    if skip_existing and out.exists() and out.stat().st_size > 0:
        return out
    last = None
    for i in range(retries):
        try:
            r = SESSION.get(url, params=params, headers=headers, timeout=timeout)
            r.raise_for_status()
            if not r.content:   # some hosts answer blocked clients with an empty 200 (Clarity, to GitHub's runners)
                raise RuntimeError("empty response")
            out.write_bytes(r.content)
            _log(d, name, r.url, len(r.content))
            return out
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(2 * (i + 1))
    raise RuntimeError(f"failed {url}: {last}")


# Store-and-link sources (DATA.md, "Linked sources"): free to use with credit, but they ask that whole tables not be
# reproduced. Raw copies go to data/linked/<source>/<date>/ (gitignored); data/linked/manifest.json (committed) records
# every fetch, so anyone can rebuild the store from the source. Only derived tables are committed.
LINKED = ROOT / "data" / "linked"


def gsheet_csv(sheet_id: str, gid) -> str:
    """CSV export URL for one tab of a public Google Sheet."""
    return f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid}"


def fetch_linked(source: str, name: str, url: str, page: str, meta=None, skip_existing=True, timeout=120) -> Path:
    """Fetch a store-and-link file into data/linked/<source>/<date>/<name> and record it in the committed manifest.
    page: the source's own page, which DATA.md and the site link to in place of our copy. meta: e.g. sheet id and tab."""
    import hashlib
    d = LINKED / source / TODAY
    out = d / name
    if not (skip_existing and out.exists() and out.stat().st_size > 0):
        r = SESSION.get(url, timeout=timeout)
        r.raise_for_status()
        if not r.content or r.content.lstrip()[:15].lower().startswith((b"<!doctype", b"<html")):
            raise RuntimeError(f"not a data file: {url}")   # a private or moved sheet answers with a sign-in page
        d.mkdir(parents=True, exist_ok=True)
        out.write_bytes(r.content)
    mf = LINKED / "manifest.json"
    m = json.loads(mf.read_text(encoding="utf-8")) if mf.exists() else {}
    m.setdefault(source, {})[f"{TODAY}/{name}"] = {
        "url": url, "page": page, **(meta or {}), "retrieved": dt.datetime.now().isoformat(timespec="seconds"),
        "bytes": out.stat().st_size, "sha256": hashlib.sha256(out.read_bytes()).hexdigest()}
    mf.write_text(json.dumps(m, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return out


def latest_linked(source: str, name: str) -> Path:
    """Most recent store copy of a linked-source file; says how to rebuild the store if it is missing."""
    cands = sorted((LINKED / source).glob(f"*/{name}"))
    if not cands:
        raise FileNotFoundError(f"data/linked/{source}/*/{name} is not in the local store (it is gitignored); "
                                f"run the source's collector to fetch it")
    return cands[-1]


def latest(source: str, name: str) -> Path:
    """Most recent raw copy of a file."""
    cands = sorted((RAW / source).glob(f"*/{name}"))
    if not cands:
        raise FileNotFoundError(f"{source}/{name}")
    return cands[-1]


def env_key(name: str, default=None):
    """Read a key from .env (falls back to .env.txt, which Windows Notepad sometimes creates). Never printed."""
    import os
    if os.environ.get(name.upper()):
        return os.environ[name.upper()]
    for fn in (".env", ".env.txt"):
        f = ROOT / fn
        if f.exists():
            for line in f.read_text(encoding="utf-8-sig").splitlines():
                if "=" in line and not line.strip().startswith("#"):
                    k, v = line.split("=", 1)
                    if k.strip().lower() == name.lower():
                        return v.strip().strip('"').strip("'")
    return default
