"""Adjusted efficiency engine.

Model, per game, for team i (offense) against team j (defense):
    OE_ij = AdjOE_i + (AdjDE_j - AVG) + h_i          h_i = +HCA home, -HCA away, 0 neutral
    DE_ij = AdjDE_i + (AdjOE_j - AVG) - h_i          (a home team's defense allows HCA fewer)
Solved by damped fixed-point iteration: each team's data estimate is the mean over
its games of the opponent- and venue-corrected game efficiency.

Flat preseason prior (brief ruling Nov 22): last season's final (unshrunk) ratings,
re-centred on this season's league average, blended inside the loop with weight
w = max(0, 1 - games / PRIOR_FADE_GAMES), so opponents are judged by blended
ratings too.  The prior is gone by game 27.

Level: ratings are re-centred every iteration so the game-weighted mean AdjOE and
AdjDE equal the league average (the model alone leaves that common shift free).

Shrinkage: published AdjOE/AdjDE = AVG + SHRINK * (rating - AVG).  The loop runs on
the unshrunk scale (that is the fixed point of the model); shrinkage only maps it
onto a spread comparable to published ratings.  Next season's prior uses the
unshrunk values so nothing is shrunk twice.
"""
from dataclasses import dataclass

import numpy as np
import pandas as pd

from . import config


def long_format(games: pd.DataFrame) -> pd.DataFrame:
    """Two rows per game, one from each team's perspective."""
    g = games[games.d1]
    base = dict(date=g.date.values, poss=g.poss.values, neutral=g.neutral.values)
    home = pd.DataFrame(dict(base, team=g.home.values, opp=g.away.values,
                             venue=np.where(g.neutral, "N", "H"),
                             pts=g.h_PTS.values, allowed=g.a_PTS.values))
    away = pd.DataFrame(dict(base, team=g.away.values, opp=g.home.values,
                             venue=np.where(g.neutral, "N", "A"),
                             pts=g.a_PTS.values, allowed=g.h_PTS.values))
    tg = pd.concat([home, away], ignore_index=True).sort_values(["team", "date"])
    tg["oe"] = 100 * tg.pts / tg.poss
    tg["de"] = 100 * tg.allowed / tg.poss
    tg["hca"] = tg.venue.map({"H": config.HCA, "A": -config.HCA, "N": 0.0})
    return tg.reset_index(drop=True)


@dataclass
class Result:
    ratings: pd.DataFrame       # one row per team, published + unshrunk values
    team_games: pd.DataFrame    # per team-game, with game-level adjusted efficiencies
    league_avg: float
    iterations: int
    max_change: float


def build_prior(prev: pd.DataFrame | None, teams: list[str]) -> pd.DataFrame:
    """Prior as deviations from last season's league average.
    prev needs columns team, AdjOE_u, AdjDE_u, league_avg (unshrunk engine output)."""
    if prev is None:
        return pd.DataFrame({"pO": 0.0, "pD": 0.0, "has_prior": False}, index=teams)
    avg = float(prev.league_avg.iloc[0])
    p = prev.set_index("team")
    dO, dD = p.AdjOE_u - avg, p.AdjDE_u - avg
    em = dO - dD
    cut = em.quantile(config.NEW_TEAM_PRIOR_PCTILE)
    # new-to-D1 teams: borrow the O/D split of teams near that percentile
    near = (em - cut).abs().nsmallest(15).index
    out = pd.DataFrame({"pO": dO.reindex(teams), "pD": dD.reindex(teams)})
    out["has_prior"] = out.pO.notna()
    out["pO"] = out.pO.fillna(dO[near].mean())
    out["pD"] = out.pD.fillna(dD[near].mean())
    return out


def rate(games: pd.DataFrame, teams: list[str], prior: pd.DataFrame | None = None,
         shrink: float = config.SHRINK, fade_games: float = config.PRIOR_FADE_GAMES,
         hca: float | None = None) -> Result:
    tg = long_format(games)
    if hca is not None:
        tg["hca"] = tg.venue.map({"H": hca, "A": -hca, "N": 0.0})
    tg = tg[tg.team.isin(teams) & tg.opp.isin(teams)].reset_index(drop=True)
    avg = 100 * tg.pts.sum() / tg.poss.sum() if len(tg) else 100.0
    gp = tg.groupby("team").size().reindex(teams, fill_value=0)

    if prior is None:
        prior = build_prior(None, teams)
        w = pd.Series(0.0, index=teams)
    else:
        w = (1 - gp / fade_games).clip(lower=0.0)
    priorO, priorD = avg + prior.pO.reindex(teams), avg + prior.pD.reindex(teams)

    agg = tg.groupby("team")[["pts", "allowed", "poss"]].sum().reindex(teams)
    rawO = (100 * agg.pts / agg.poss)
    rawD = (100 * agg.allowed / agg.poss)
    adjO = (w * priorO + (1 - w) * rawO.fillna(avg)).where(gp > 0, priorO)
    adjD = (w * priorD + (1 - w) * rawD.fillna(avg)).where(gp > 0, priorD)

    team_idx = pd.Index(teams)
    ti, oi = team_idx.get_indexer(tg.team), team_idx.get_indexer(tg.opp)
    oe, de, h = tg.oe.values, tg.de.values, tg.hca.values
    n = np.bincount(ti, minlength=len(teams)).astype(float)
    wv, pOv, pDv = w.values, priorO.values, priorD.values
    O, D = adjO.values.copy(), adjD.values.copy()
    it, delta = 0, np.inf
    for it in range(1, config.MAX_ITER + 1):
        gO = oe - (D[oi] - avg) - h            # game-level adjusted offense
        gD = de - (O[oi] - avg) + h            # game-level adjusted defense
        with np.errstate(invalid="ignore", divide="ignore"):
            dO = np.bincount(ti, gO, len(teams)) / n
            dD = np.bincount(ti, gD, len(teams)) / n
        newO = np.where(n > 0, wv * pOv + (1 - wv) * dO, pOv)
        newD = np.where(n > 0, wv * pDv + (1 - wv) * dD, pDv)
        newO = config.DAMPING * O + (1 - config.DAMPING) * newO
        newD = config.DAMPING * D + (1 - config.DAMPING) * newD
        # The model only identifies ratings up to a common shift (every AdjOE +c, every
        # AdjDE -c fits the games equally well), so pin the level: game-weighted mean
        # AdjOE and AdjDE both equal the league average.  Without this, a fading prior
        # anchors that free direction only weakly and the loop crawls instead of converging.
        if n.sum() > 0:
            newO -= (n @ newO) / n.sum() - avg
            newD -= (n @ newD) / n.sum() - avg
        delta = max(np.abs(newO - O).max(), np.abs(newD - D).max())
        O, D = newO, newD
        if delta < config.TOL:
            break

    tg["adj_oe"] = oe - (D[oi] - avg) - h
    tg["adj_de"] = de - (O[oi] - avg) + h
    tg["adj_oe_pub"] = avg + shrink * (tg.adj_oe - avg)
    tg["adj_de_pub"] = avg + shrink * (tg.adj_de - avg)

    wins = (tg.pts > tg.allowed).groupby(tg.team).sum().reindex(teams, fill_value=0)
    r = pd.DataFrame({"team": teams, "gp": gp.values,
                      "W": wins.values.astype(int), "L": (gp - wins).values.astype(int),
                      "AdjOE_u": O, "AdjDE_u": D,
                      "rawOE": rawO.values, "rawDE": rawD.values,
                      "pace": (agg.poss / gp.replace(0, np.nan)).values,
                      "prior_weight": w.values, "has_prior": prior.has_prior.reindex(teams).values})
    r["AdjOE"] = avg + shrink * (r.AdjOE_u - avg)
    r["AdjDE"] = avg + shrink * (r.AdjDE_u - avg)
    r["AdjEM"] = r.AdjOE - r.AdjDE
    r["Barthag"] = barthag(r.AdjOE, r.AdjDE)
    r["rank"] = r.AdjEM.rank(ascending=False, method="min").astype(int)
    r["league_avg"] = avg
    r = r.sort_values("rank").reset_index(drop=True)
    return Result(r, tg, avg, it, float(delta))


def barthag(o, d, exp: float = config.PYTHAG_EXP):
    return o ** exp / (o ** exp + d ** exp)
