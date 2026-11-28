#!/usr/bin/env python3
"""Daily pipeline: collect -> regression-test -> rate -> validate -> write data/<season>/.

    python scripts/run_pipeline.py                 # current season (prior seasons built from cache if missing)
    python scripts/run_pipeline.py --season 2025   # a finished season (validation run)

Every run recomputes the whole season from scratch.  Finished seasons read cached raw
files without re-downloading.  Exit code 1 if the box-order regression test fails, or
if the validation season (2024-25) misses the acceptance band.  Other seasons report only.
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd  # noqa: E402

from hoops import config, engine, espn, ingest, parse, players, rawcache, validate  # noqa: E402

FIRST_SEASON = 2024   # oldest season we build; it runs without a prior


def _round(df, nd=4):
    return df.round({c: nd for c in df.select_dtypes("float").columns})


def run_season(year: int, current: int, log=print) -> dict:
    finished = year < current
    refresh = not finished
    sd = config.season_dir(year)

    rows = ingest.torvik_gamestats(year, refresh)
    box_report = parse.check_box_order(rows)          # raises BoxOrderError -> no build
    log(f"[{year}] box-order regression test: {box_report}")
    torvik = parse.team_results(ingest.torvik_team_results(year, refresh))
    teams = sorted(torvik.team)
    games = parse.parse_games(rows, set(teams))

    prior_src = None
    if year > FIRST_SEASON:
        prev_path = config.DATA / str(year - 1) / "ratings.csv"
        if not prev_path.exists():
            log(f"[{year}] prior season ratings missing; building {year - 1} first")
            run_season(year - 1, current, log)
        prior_src = pd.read_csv(prev_path)
    prior = engine.build_prior(prior_src, teams) if prior_src is not None else None
    res = engine.rate(games, teams, prior)
    log(f"[{year}] {int(games.d1.sum())} D1 games, {len(teams)} teams, league avg "
        f"{res.league_avg:.2f}, converged in {res.iterations} iterations (max change {res.max_change:.1e})")

    ratings = res.ratings.merge(torvik[["team", "conf"]], on="team", how="left")
    cols = ["rank", "team", "conf", "gp", "W", "L", "AdjOE", "AdjDE", "AdjEM", "Barthag",
            "rawOE", "rawDE", "pace", "prior_weight", "has_prior", "AdjOE_u", "AdjDE_u", "league_avg"]
    _round(ratings[cols]).to_csv(sd / "ratings.csv", index=False)

    rep, comp = validate.compare(res.ratings, torvik)
    rep["season"], rep["finished"] = year, finished
    (sd / "validation.json").write_text(json.dumps(rep, indent=2) + "\n")
    log(f"[{year}] vs Torvik: spearman {rep['spearman_adjem']:.4f}, top-30 diff "
        f"{rep['top30_mean_abs_rank_diff']:.2f}, Indiana {rep.get('indiana')}, passed={rep['passed']}")

    meta = {"season": year, "built_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "games_d1": int(games.d1.sum()), "teams": len(teams),
            "last_game_date": games.date.max() if len(games) else None,
            "league_avg": round(res.league_avg, 4), "iterations": res.iterations,
            "box_order_check": box_report,
            "engine": {"hca": config.HCA, "barthag_exp": config.PYTHAG_EXP, "shrink": config.SHRINK,
                       "prior": "flat, last season final (unshrunk)", "prior_fade_games": config.PRIOR_FADE_GAMES,
                       "prior_season": year - 1 if prior_src is not None else None},
            "sources": {"games": config.TORVIK_GAMESTATS.format(year=year),
                        "validation": config.TORVIK_TEAM_RESULTS.format(year=year)}}

    if not finished:
        # detail tables for the page (current season only, to keep the repo light)
        _round(games).to_csv(sd / "games.csv", index=False)
        tg = res.team_games[["date", "team", "opp", "venue", "pts", "allowed", "poss", "oe", "de",
                             "adj_oe_pub", "adj_de_pub"]].rename(
            columns={"adj_oe_pub": "adj_oe", "adj_de_pub": "adj_de"})
        _round(tg, 2).to_csv(sd / "team_games.csv", index=False)

        prow = ingest.torvik_players(year, refresh)
        pl = players.parse_players(prow)
        pl.to_csv(sd / "players.csv", index=False)
        meta["players"] = {"rows": len(pl), "source": config.TORVIK_PLAYERS.format(year=year),
                           "check_center_team": players.check_against_games(pl, res.team_games, config.CENTER_TEAM)}
        log(f"[{year}] players: {meta['players']['check_center_team']}")

        gt_dir = sd / "gametracker"
        gt_dir.mkdir(exist_ok=True)
        index = []
        for ev in espn.completed_events(year):
            prog = espn.scoring_progression(ev["id"])
            (gt_dir / f"{ev['id']}.json").write_text(json.dumps(prog, separators=(",", ":")) + "\n")
            index.append({**ev, **prog["verified"], "score": {k: v["score"] for k, v in prog["teams"].items()}})
        (gt_dir / "index.json").write_text(json.dumps(index, indent=1) + "\n")
        bad = [e["id"] for e in index if not (e["final_score_matches"] and e["monotonic"])]
        meta["gametracker"] = {"games": len(index), "unverified": bad}
        log(f"[{year}] gametracker: {len(index)} IU games, unverified={bad}")

    # freshness proof: when each Torvik input was fetched, its checksum, collector or direct
    meta["inputs"] = rawcache.provenance(config.RAW, list(rawcache.torvik_files(year)))
    (sd / "meta.json").write_text(json.dumps(meta, indent=2) + "\n")
    if year == config.VALIDATION_SEASON and not rep["passed"]:
        raise SystemExit(f"[{year}] FAILED acceptance band: {rep['accept']}")
    return rep


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", type=int, default=config.current_season())
    a = ap.parse_args()
    try:
        run_season(a.season, config.current_season())
    except parse.BoxOrderError as e:
        sys.exit(f"BOX-ORDER REGRESSION TEST FAILED, build refused: {e}")


if __name__ == "__main__":
    main()
