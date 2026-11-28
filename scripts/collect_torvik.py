#!/usr/bin/env python3
"""Collector: fetch the current season's three Torvik files and commit them to `raw-cache`.

Run from a clone of this repo on a network Torvik accepts (not GitHub Actions), with push
access to origin, shortly before the daily workflow (06:17 ET):

    python scripts/collect_torvik.py                  # current season, label "external"
    python scripts/collect_torvik.py --label vm --dry-run

Downloads go through hoops.ingest.fetch: same 20 h cache, 3 s polite delay and identifying
user agent as the pipeline, one pull per file per day.  The branch is written with git
plumbing (hash-object / mktree / commit-tree), so the clone's working tree and current
branch are untouched.  Each commit replaces the tree: the branch tip holds only the latest
files plus manifest.json.
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hoops import config, ingest, rawcache  # noqa: E402


def git(*args, inp: bytes | None = None) -> str:
    r = subprocess.run(["git", "-C", str(config.ROOT), *args], input=inp,
                       capture_output=True, check=True)
    return r.stdout.decode().strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", type=int, default=config.current_season())
    ap.add_argument("--label", default="external", help="collector name recorded in the manifest")
    ap.add_argument("--remote", default="origin")
    ap.add_argument("--dry-run", action="store_true", help="fetch and build the commit, do not push")
    a = ap.parse_args()

    paths = {name: ingest.fetch(url, name, refresh=True)
             for name, url in rawcache.torvik_files(a.season).items()}
    manifest = rawcache.build_manifest(a.season, paths, a.label)
    mbytes = (json.dumps(manifest, indent=2) + "\n").encode()

    entries = [(rawcache.MANIFEST, git("hash-object", "-w", "--stdin", inp=mbytes))]
    entries += [(n, git("hash-object", "-w", str(p))) for n, p in paths.items()]
    tree = git("mktree", inp="".join(f"100644 blob {sha}\t{n}\n" for n, sha in sorted(entries)).encode())

    parent = []
    try:
        git("fetch", "-q", "--depth=1", a.remote, rawcache.BRANCH)
        parent = ["-p", git("rev-parse", "FETCH_HEAD")]
    except subprocess.CalledProcessError:
        print(f"{rawcache.BRANCH} not on {a.remote} yet; creating it")
    msg = f"raw: torvik {a.season} collected {manifest['collected_utc']} ({a.label})"
    commit = git("-c", "user.name=hoops-report-collector", "-c", "user.email=collector@users.noreply.github.com",
                 "commit-tree", tree, *parent, "-m", msg)

    for n, f in manifest["files"].items():
        print(f"{n}: {f['bytes']} bytes, fetched {f['fetched_utc']}, sha256 {f['sha256'][:12]}")
    if a.dry_run:
        print(f"dry run: built {commit}, not pushed")
        return
    git("push", "-q", a.remote, f"{commit}:refs/heads/{rawcache.BRANCH}")
    print(f"pushed {commit[:12]} to {a.remote}/{rawcache.BRANCH}")


if __name__ == "__main__":
    main()
