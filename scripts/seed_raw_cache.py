#!/usr/bin/env python3
"""Seed data/raw/ from the `raw-cache` branch before the pipeline runs (GitHub Actions step).

    python scripts/seed_raw_cache.py [remote]      # default origin

Missing branch or a different season: prints a notice and exits 0 (the pipeline then tries
a direct fetch).  Checksum mismatch: exits 1.  Freshness is not judged here: each file gets
its real fetch time as mtime and ingest.fetch applies the usual CACHE_MAX_AGE_H rule.
"""
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hoops import config, rawcache  # noqa: E402


def git(*args) -> bytes:
    return subprocess.run(["git", "-C", str(config.ROOT), *args], capture_output=True, check=True).stdout


def main(remote: str = "origin"):
    try:
        git("fetch", "-q", "--depth=1", remote, rawcache.BRANCH)
    except subprocess.CalledProcessError:
        print(f"::notice::no {rawcache.BRANCH} branch on origin; pipeline will fetch Torvik directly")
        return
    manifest = json.loads(git("show", f"FETCH_HEAD:{rawcache.MANIFEST}"))
    season = config.current_season()
    if manifest.get("season") != season:
        print(f"::warning::{rawcache.BRANCH} holds season {manifest.get('season')}, need {season}; not seeding")
        return
    print(f"{rawcache.BRANCH}: collected {manifest['collected_utc']} by {manifest['collector']}")
    try:
        for line in rawcache.install(manifest, lambda n: git("show", f"FETCH_HEAD:{n}"), config.RAW):
            print("  " + line)
    except ValueError as e:
        sys.exit(f"::error::{e}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "origin")
