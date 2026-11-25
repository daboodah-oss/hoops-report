"""Polite, cached downloads.  One file per (source, year); re-fetched at most once per CACHE_MAX_AGE_H."""
import json
import time
from pathlib import Path

import requests

from . import config

_last_hit: dict[str, float] = {}


def _get(url: str) -> bytes:
    host = url.split("/")[2]
    wait = config.POLITE_DELAY_S - (time.time() - _last_hit.get(host, 0))
    if wait > 0:
        time.sleep(wait)
    for attempt in range(4):
        try:
            r = requests.get(url, headers={"User-Agent": config.USER_AGENT}, timeout=60)
            _last_hit[host] = time.time()
            r.raise_for_status()
            return r.content
        except requests.RequestException:
            if attempt == 3:
                raise
            time.sleep(2 ** (attempt + 1))
    raise RuntimeError("unreachable")


def fetch(url: str, name: str, refresh: bool = True) -> Path:
    """Download url to data/raw/name unless a fresh-enough copy exists.

    refresh=False uses any cached copy regardless of age (finished seasons never change).
    """
    config.RAW.mkdir(parents=True, exist_ok=True)
    path = config.RAW / name
    if path.exists():
        age_h = (time.time() - path.stat().st_mtime) / 3600
        if not refresh or age_h < config.CACHE_MAX_AGE_H:
            return path
    body = _get(url)
    tmp = path.with_suffix(path.suffix + ".part")
    tmp.write_bytes(body)
    tmp.replace(path)
    return path


def torvik_gamestats(year: int, refresh: bool = True) -> list:
    p = fetch(config.TORVIK_GAMESTATS.format(year=year), f"torvik_{year}_gamestats.json", refresh)
    return json.loads(p.read_text())


def torvik_team_results(year: int, refresh: bool = True) -> Path:
    return fetch(config.TORVIK_TEAM_RESULTS.format(year=year), f"torvik_{year}_team_results.csv", refresh)


def torvik_players(year: int, refresh: bool = True) -> list:
    p = fetch(config.TORVIK_PLAYERS.format(year=year), f"torvik_{year}_players.json", refresh)
    return json.loads(p.read_text())


def espn_json(url: str, name: str, refresh: bool = True) -> dict:
    return json.loads(fetch(url, name, refresh).read_text())
