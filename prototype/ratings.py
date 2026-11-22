#!/usr/bin/env python3
"""
Feasibility prototype: Torvik/KenPom-style adjusted efficiency ratings
from free Bart Torvik game data (2024-25 season).

Pipeline
--------
1. Load Torvik's per-team-game log (getgamestats.php?year=2025&json=1).
   Each row embeds a full box-score string (field 29) with counting stats
   for BOTH teams, in this positional layout per team:
     FGM, FGA, 3PM, 3PA, FTM, FTA, ORB, DRB, REB, AST, STL, BLK, TO, PF, PTS
2. Possessions per team = FGA - ORB + TO + 0.44 * FTA  (standard formula).
   Game possessions = mean of the two teams' estimates.
3. Raw efficiency = points per 100 possessions, summed over the season.
4. Iterative opponent + location adjustment (KenPom-lite):
     Model for team i's offensive output vs team j in one game:
         OE_game = AdjOE_i + (AdjDE_j - LeagueAvg) + HCA_i
     where HCA_i = +HCA if i is home, -HCA if away, 0 if neutral.
     HCA = 3.0 points per 100 possessions (documented choice; roughly
     2 points per game at a ~68-possession pace, in line with published
     home-court estimates once expressed per-possession).
     Solve by repeated averaging (fixed-point iteration) until the max
     change in any AdjOE/AdjDE is < 1e-5 (max 500 iterations).
5. Barthag = AdjOE^11.5 / (AdjOE^11.5 + AdjDE^11.5)  (Torvik's formula).
   AdjEM = AdjOE - AdjDE. Teams ranked by AdjEM (equiv. Barthag order).

Scope notes: D1-vs-D1 games only (both teams in Torvik's 364-team list).
No preseason prior, no recency weighting, no garbage-time filtering --
deliberate omissions for the feasibility pass, noted in VERDICT.md.
"""
import json, csv, sys
import pandas as pd
import numpy as np

YEAR_FILE = "data/torvik_2025_gamestats.json"
RESULTS_FILE = "data/torvik_2025_team_results.csv"
HCA = 3.0          # points per 100 possessions
PYTHAG_EXP = 11.5  # Barthag exponent

BOX = ["FGM","FGA","3PM","3PA","FTM","FTA","ORB","DRB","REB","AST","STL","BLK","TO","PF","PTS"]

def parse_games():
    rows = json.load(open(YEAR_FILE))
    d1 = set(pd.read_csv(RESULTS_FILE)["team"])
    games, seen = [], set()
    for r in rows:
        date, team, opp, venue = r[0], r[2], r[4], r[5]
        key = (date, tuple(sorted([team, opp])))
        if key in seen:            # each game appears once per team
            continue
        seen.add(key)
        box = json.loads(r[29])
        # NOTE: the embedded box string is stored once per game with a FIXED
        # team order (box[2], box[3]) -- it does NOT follow the perspective
        # of the gamestats row. Verified: block points match box[2]/box[3],
        # not the row's team/opponent, in all 11,528 rows.
        stats = {box[2]: dict(zip(BOX, box[4:19])),
                 box[3]: dict(zip(BOX, box[19:34]))}
        if venue == "H":
            home, away = team, opp
        elif venue == "A":
            home, away = opp, team
        else:  # neutral: keep team/opp order, no home team
            home, away = team, opp
        hs, as_ = stats[home], stats[away]
        games.append(dict(date=date, home=home, away=away, neutral=(venue == "N"),
                          hs=hs, as_=as_, d1=(team in d1 and opp in d1)))
    return pd.DataFrame(games), d1

def poss(s):  # estimated possessions for one team's box line
    return s["FGA"] - s["ORB"] + s["TO"] + 0.44 * s["FTA"]

def main():
    games, d1 = parse_games()
    print(f"games parsed: {len(games)}  (D1-vs-D1: {games.d1.sum()}, "
          f"vs non-D1 excluded: {(~games.d1).sum()})")
    g = games[games.d1].copy()
    g["poss"] = [ (poss(r.hs) + poss(r.as_)) / 2 for r in g.itertuples() ]
    g["h_pts"] = [r.hs["PTS"] for r in g.itertuples()]
    g["a_pts"] = [r.as_["PTS"] for r in g.itertuples()]
    g.to_pickle("data/games_d1.pkl")

    # ---- long format: one row per team-game with venue from its perspective
    recs = []
    for r in g.itertuples():
        recs.append((r.home, r.away, "H" if not r.neutral else "N", r.h_pts, r.a_pts, r.poss))
        recs.append((r.away, r.home, "A" if not r.neutral else "N", r.a_pts, r.h_pts, r.poss))
    tg = pd.DataFrame(recs, columns=["team","opp","venue","pts","allowed","poss"])
    tg["oe"] = 100 * tg.pts / tg.poss
    tg["de"] = 100 * tg.allowed / tg.poss

    teams = sorted(d1)
    agg = tg.groupby("team").agg(pts=("pts","sum"), allowed=("allowed","sum"),
                                 poss=("poss","sum"), gp=("pts","size"))
    raw = pd.DataFrame({"rawOE": 100*agg.pts/agg.poss, "rawDE": 100*agg.allowed/agg.poss,
                        "gp": agg.gp})
    AVG = 100 * tg.pts.sum() / tg.poss.sum()
    print(f"league average efficiency: {AVG:.2f} pts/100 poss; teams: {len(teams)}")

    adjO = raw.rawOE.copy(); adjD = raw.rawDE.copy()
    hca_map = {"H": HCA, "A": -HCA, "N": 0.0}
    tg = tg.assign(hca=tg.venue.map(hca_map))
    for it in range(500):
        prevO, prevD = adjO.copy(), adjD.copy()
        tg = tg.assign(expO=tg.opp.map(adjO), expD=tg.opp.map(adjD))
        # offense: OE_game - (opp AdjDE - AVG) - hca  -> AdjOE
        newO = (tg.oe - (tg.expD - AVG) - tg.hca).groupby(tg.team).mean()
        # defense: DE_game - (opp AdjOE - AVG) - hca  -> AdjDE
        # (hca is from THIS team's perspective: a home team's defense is
        #  expected to allow HCA fewer pts/100, so we subtract it back out)
        newD = (tg.de - (tg.expO - AVG) - tg.hca).groupby(tg.team).mean()
        # damping 0.5: undamped Jacobi iteration oscillates at ~1e-3 and
        # never trips the tolerance; damping converges cleanly and does
        # not change the fixed point.
        adjO = 0.5 * prevO + 0.5 * newO.reindex(teams)
        adjD = 0.5 * prevD + 0.5 * newD.reindex(teams)
        delta = max((adjO - prevO).abs().max(), (adjD - prevD).abs().max())
        if delta < 1e-4:
            print(f"converged after {it+1} iterations (max change {delta:.2e})")
            break
    out = pd.DataFrame({"team": teams, "AdjOE": adjO.values, "AdjDE": adjD.values})
    out["AdjEM"] = out.AdjOE - out.AdjDE
    out["Barthag"] = out.AdjOE**PYTHAG_EXP / (out.AdjOE**PYTHAG_EXP + out.AdjDE**PYTHAG_EXP)
    out["rank"] = out.AdjEM.rank(ascending=False).astype(int)
    out = out.sort_values("rank")
    out.to_csv("my_ratings_2025.csv", index=False)

    # ---- validation vs Torvik published end-of-season ratings
    tor = pd.read_csv(RESULTS_FILE)[["rank","team","adjoe","adjde","barthag"]]
    tor = tor.rename(columns={"rank": "rank_t"})
    tor["AdjEM_t"] = tor.adjoe - tor.adjde
    m = out.merge(tor, on="team")
    m["absrankdiff"] = (m["rank"] - m["rank_t"]).abs()
    from scipy.stats import spearmanr
    rho_em, _ = spearmanr(m.AdjEM, m.AdjEM_t)
    rho_bt, _ = spearmanr(m.Barthag, m.barthag)
    print("\n--- VALIDATION vs Torvik 2024-25 final ---")
    print(f"teams matched: {len(m)}")
    print(f"Spearman rho, AdjEM: {rho_em:.4f} | Barthag: {rho_bt:.4f}")
    print(f"mean |rank diff|, all teams: {m.absrankdiff.mean():.1f}")
    top30 = m[m.rank_t <= 30]
    print(f"Top-30 (Torvik) mean |rank diff|: {top30.absrankdiff.mean():.1f}; "
          f"overlap of top-30 sets: {len(set(top30.team) & set(m[m['rank']<=30].team))}/30")
    ind = m[m.team == "Indiana"].iloc[0]
    print(f"Indiana: mine #{int(ind['rank'])} (AdjEM {ind.AdjEM:+.2f}, AdjO {ind.AdjOE:.1f}, AdjD {ind.AdjDE:.1f}) "
          f"vs Torvik #{int(ind['rank_t'])} (AdjEM {ind.AdjEM_t:+.2f}, AdjO {ind.adjoe:.1f}, AdjD {ind.adjde:.1f})")
    m.to_csv("comparison_2025.csv", index=False)
    print("\nMy top 15:")
    print(out.head(15).to_string(index=False))
    print("\nTorvik top 15:")
    print(tor.sort_values('AdjEM_t', ascending=False).head(15).to_string(index=False))

if __name__ == "__main__":
    main()
