"""Torvik gamestats parser.

Each gamestats row is one TEAM-GAME (so each game appears twice).  Field 29 is an
embedded JSON box score covering BOTH teams.  CRITICAL GOTCHA (feasibility check,
Nov 21): that box string is stored once per game in a FIXED team order
(box[2] then box[3]); it does NOT follow the perspective of the row it sits in.
Reading it per-row silently swaps every game's stats and the ratings come out as
noise (Spearman ~ 0).  `check_box_order` is the regression test that guards this
and the pipeline refuses to build if it fails.
"""
import json
import re
from datetime import datetime

import pandas as pd

BOX = ["FGM", "FGA", "3PM", "3PA", "FTM", "FTA", "ORB", "DRB", "REB",
       "AST", "STL", "BLK", "TO", "PF", "PTS"]
_RESULT = re.compile(r"^\s*([WL])\s*,\s*(\d+)\s*-\s*(\d+)")


class BoxOrderError(ValueError):
    """The embedded box score did not line up with the row's result string."""


def _date(s: str) -> str:
    for fmt in ("%m/%d/%y", "%m/%d/%Y"):
        try:
            return datetime.strptime(s, fmt).date().isoformat()
        except ValueError:
            pass
    raise ValueError(f"unparseable date {s!r}")


def _box(row) -> dict:
    box = json.loads(row[29])
    return {box[2]: {k: float(v) for k, v in zip(BOX, box[4:19])},
            box[3]: {k: float(v) for k, v in zip(BOX, box[19:34])}}


def team_points_from_result(result: str) -> tuple[int, int]:
    """(team pts, opp pts) from Torvik's result string, e.g. 'L, 94-59' -> (59, 94)."""
    m = _RESULT.match(result)
    if not m:
        raise ValueError(f"unparseable result {result!r}")
    wl, a, b = m.group(1), int(m.group(2)), int(m.group(3))
    hi, lo = max(a, b), min(a, b)
    return (hi, lo) if wl == "W" else (lo, hi)


def check_box_order(rows: list) -> dict:
    """Regression test: for EVERY row, box points keyed by the box's own team names
    must equal the row's result string, and the box's two teams must be the row's
    team and opponent.  Also counts how many rows a naive per-row reading would get
    wrong, to prove the test still has teeth on this data.  Raises BoxOrderError."""
    bad, naive_wrong, ties = [], 0, 0
    for i, r in enumerate(rows):
        team, opp = r[2], r[4]
        box = json.loads(r[29])
        tpts, opts = team_points_from_result(r[6])
        if tpts == opts:
            ties += 1
        stats = _box(r)
        if set(stats) != {team, opp}:
            bad.append((i, "teams", team, opp, box[2], box[3]))
            continue
        if (stats[team]["PTS"], stats[opp]["PTS"]) != (tpts, opts):
            bad.append((i, "points", team, opp, r[6]))
        # naive reading: first block = this row's team
        if float(box[18]) != tpts:
            naive_wrong += 1
    report = dict(rows=len(rows), mismatches=len(bad), naive_reading_wrong=naive_wrong)
    if bad:
        raise BoxOrderError(f"{len(bad)} of {len(rows)} rows fail the box-order check; first: {bad[:3]}")
    return report


def parse_games(rows: list, d1: set[str]) -> pd.DataFrame:
    """One row per game (deduplicated), home/away resolved, box stats for both sides."""
    games, seen = [], set()
    for r in rows:
        date, team, opp, venue = _date(r[0]), r[2], r[4], r[5]
        key = (date, *sorted((team, opp)))
        if key in seen:
            continue
        seen.add(key)
        stats = _box(r)
        if venue == "A":
            home, away = opp, team
        else:                    # 'H', or 'N' (keep row order, no home team)
            home, away = team, opp
        rec = dict(date=date, home=home, away=away, neutral=venue == "N",
                   d1=(home in d1 and away in d1))
        for side, t in (("h", home), ("a", away)):
            for k in BOX:
                rec[f"{side}_{k}"] = stats[t][k]
        games.append(rec)
    g = pd.DataFrame(games).sort_values(["date", "home"]).reset_index(drop=True)
    g["h_poss"] = possessions(g, "h")
    g["a_poss"] = possessions(g, "a")
    g["poss"] = (g.h_poss + g.a_poss) / 2      # game pace = mean of the two estimates
    return g


def possessions(g: pd.DataFrame, side: str):
    """FGA - ORB + TO + 0.44*FTA for one side of each game."""
    return g[f"{side}_FGA"] - g[f"{side}_ORB"] + g[f"{side}_TO"] + 0.44 * g[f"{side}_FTA"]


def team_results(path) -> pd.DataFrame:
    """Torvik's team_results.csv, with the duplicated 'rank' header disambiguated."""
    t = pd.read_csv(path)
    t = t.rename(columns={"rank": "torvik_rank"})
    keep = ["torvik_rank", "team", "conf", "record", "adjoe", "adjde", "barthag", "adjt"]
    return t[[c for c in keep if c in t.columns]]
