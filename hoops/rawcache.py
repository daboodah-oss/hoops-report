"""Collected Torvik files: the bridge between a collector on a network Torvik accepts and the
GitHub Actions pipeline (Torvik returns 403 to Actions egress IPs).

The collector (scripts/collect_torvik.py) downloads the three Torvik files through
ingest.fetch (same cache, polite delay and identifying user agent as the pipeline) and
commits them, plus manifest.json, to the `raw-cache` branch.  The workflow seeds data/raw/
from that branch (scripts/seed_raw_cache.py) before the pipeline runs.

Seeding sets each file's mtime to the time the collector actually fetched it, so
ingest.fetch's normal freshness rule decides: a copy younger than CACHE_MAX_AGE_H is used,
an older one triggers a direct fetch (which fails loudly while the block holds).  Bytes are
verified against the manifest's sha256, so the pipeline reads exactly what Torvik served.
"""
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from . import config

BRANCH = "raw-cache"
MANIFEST = "manifest.json"
SEEDED = "_collected.json"      # copy of the manifest left in data/raw/ for provenance


def torvik_files(year: int) -> dict[str, str]:
    """name in data/raw/ -> source URL, for the files the current-season run reads."""
    return {
        f"torvik_{year}_gamestats.json": config.TORVIK_GAMESTATS.format(year=year),
        f"torvik_{year}_team_results.csv": config.TORVIK_TEAM_RESULTS.format(year=year),
        f"torvik_{year}_players.json": config.TORVIK_PLAYERS.format(year=year),
    }


def sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, timezone.utc).isoformat(timespec="seconds")


def build_manifest(year: int, paths: dict[str, Path], label: str) -> dict:
    files = {}
    for name, url in torvik_files(year).items():
        p = paths[name]
        body = p.read_bytes()
        files[name] = {"url": url, "fetched_utc": iso(p.stat().st_mtime),
                       "bytes": len(body), "sha256": sha256(body)}
    return {"season": year, "collector": label, "user_agent": config.USER_AGENT,
            "collected_utc": iso(datetime.now(timezone.utc).timestamp()), "files": files}


def install(manifest: dict, read_blob, raw_dir: Path) -> list[str]:
    """Write each manifest file into raw_dir with its fetch time as mtime.

    read_blob(name) -> bytes.  Raises ValueError on a checksum mismatch.  A local file
    that is already newer than the collected copy is left alone.  Returns log lines.
    """
    raw_dir.mkdir(parents=True, exist_ok=True)
    log = []
    for name, f in manifest["files"].items():
        ts = datetime.fromisoformat(f["fetched_utc"]).timestamp()
        dest = raw_dir / name
        if dest.exists() and dest.stat().st_mtime >= ts:
            log.append(f"{name}: local copy is newer, kept")
            continue
        body = read_blob(name)
        if sha256(body) != f["sha256"] or len(body) != f["bytes"]:
            raise ValueError(f"{name}: collected bytes do not match manifest checksum")
        tmp = dest.with_suffix(dest.suffix + ".part")
        tmp.write_bytes(body)
        tmp.replace(dest)
        os.utime(dest, (ts, ts))
        age_h = (datetime.now(timezone.utc).timestamp() - ts) / 3600
        log.append(f"{name}: seeded, fetched {f['fetched_utc']} ({age_h:.1f} h ago, "
                   f"{'fresh' if age_h < config.CACHE_MAX_AGE_H else 'STALE, direct fetch will be tried'})")
    (raw_dir / SEEDED).write_text(json.dumps(manifest, indent=2) + "\n")
    return log


def provenance(raw_dir: Path, names: list[str]) -> dict:
    """Per input file: when it was fetched, its sha256, and whether it came from the collector."""
    seeded = {}
    if (raw_dir / SEEDED).exists():
        seeded = json.loads((raw_dir / SEEDED).read_text()).get("files", {})
    out = {}
    for name in names:
        p = raw_dir / name
        if not p.exists():
            continue
        digest = sha256(p.read_bytes())
        via = "collector" if seeded.get(name, {}).get("sha256") == digest else "direct"
        out[name] = {"fetched_utc": iso(p.stat().st_mtime), "sha256": digest, "via": via}
    return out
