#!/usr/bin/env python3
"""Fit the shrinkage factor on a finished season (default 2025 = 2024-25) and check it on
a holdout season (default 2026).  Prints the value to paste into hoops/config.py SHRINK.
Uses the cached raw files under data/raw/ (run run_pipeline.py --season N first)."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import pandas as pd  # noqa: E402

from hoops import config, engine, ingest, parse, validate  # noqa: E402


def season(year):
    rows = ingest.torvik_gamestats(year, refresh=False)
    parse.check_box_order(rows)
    tor = parse.team_results(ingest.torvik_team_results(year, refresh=False))
    teams = sorted(tor.team)
    prev = config.DATA / str(year - 1) / "ratings.csv"
    prior = engine.build_prior(pd.read_csv(prev), teams) if prev.exists() else None
    return parse.parse_games(rows, set(teams)), teams, prior, tor


ap = argparse.ArgumentParser()
ap.add_argument("--fit", type=int, default=2025)
ap.add_argument("--holdout", type=int, default=2026)
a = ap.parse_args()
g, teams, prior, tor = season(a.fit)
k = validate.fit_shrink(engine.rate(g, teams, prior, shrink=1.0).ratings, tor)
print(f"fitted SHRINK on {a.fit}: {k:.3f}")
for y in (a.fit, a.holdout):
    g, teams, prior, tor = season(y)
    for label, s in (("unshrunk", 1.0), ("shrunk", k)):
        rep, _ = validate.compare(engine.rate(g, teams, prior, shrink=s).ratings, tor)
        print(f"{y} {label:8s} sd ours {rep['adjem_sd_ours']:.2f} vs torvik {rep['adjem_sd_torvik']:.2f}, "
              f"AdjEM MAE {rep['adjem_mae']:.2f}, spearman {rep['spearman_adjem']:.4f}")
