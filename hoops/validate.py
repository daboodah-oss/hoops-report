"""Compare engine output against Torvik's published ratings for the same season."""
import numpy as np
import pandas as pd
from scipy.stats import pearsonr, spearmanr

from . import config


def compare(ours: pd.DataFrame, torvik: pd.DataFrame) -> tuple[dict, pd.DataFrame]:
    t = torvik.copy()
    t["AdjEM_t"] = t.adjoe - t.adjde
    t["rank_t_em"] = t.AdjEM_t.rank(ascending=False, method="min").astype(int)
    m = ours.merge(t, on="team", how="inner")
    m["rankdiff"] = (m["rank"] - m["torvik_rank"]).abs()
    top30 = m[m.torvik_rank <= 30]
    ind = m[m.team == config.CENTER_TEAM]
    rep = {
        "teams_matched": int(len(m)),
        "spearman_adjem": float(spearmanr(m.AdjEM, m.AdjEM_t)[0]),
        "spearman_barthag": float(spearmanr(m.Barthag, m.barthag)[0]),
        "pearson_adjem": float(pearsonr(m.AdjEM, m.AdjEM_t)[0]),
        "mean_abs_rank_diff_all": float(m.rankdiff.mean()),
        "top30_mean_abs_rank_diff": float(top30.rankdiff.mean()),
        "top30_overlap": int(len(set(top30.team) & set(m[m["rank"] <= 30].team))),
        "adjem_sd_ours": float(m.AdjEM.std()),
        "adjem_sd_torvik": float(m.AdjEM_t.std()),
        "adjem_mae": float((m.AdjEM - m.AdjEM_t).abs().mean()),
    }
    if len(ind):
        i = ind.iloc[0]
        rep["indiana"] = {"ours_rank": int(i["rank"]), "torvik_rank": int(i.torvik_rank),
                          "ours": [round(i.AdjOE, 1), round(i.AdjDE, 1), round(i.AdjEM, 1)],
                          "torvik": [round(i.adjoe, 1), round(i.adjde, 1), round(i.AdjEM_t, 1)]}
    rep["accept"] = {
        "spearman>=%.2f" % config.ACCEPT_SPEARMAN: rep["spearman_adjem"] >= config.ACCEPT_SPEARMAN,
        "top30<=%.1f" % config.ACCEPT_TOP30_MEAN_RANK_DIFF:
            rep["top30_mean_abs_rank_diff"] <= config.ACCEPT_TOP30_MEAN_RANK_DIFF,
        "indiana<=%d" % config.ACCEPT_INDIANA_PLACES:
            bool(len(ind)) and abs(rep["indiana"]["ours_rank"] - rep["indiana"]["torvik_rank"])
            <= config.ACCEPT_INDIANA_PLACES,
    }
    rep["passed"] = all(rep["accept"].values())
    return rep, m.sort_values("rank")


def fit_shrink(ours_u: pd.DataFrame, torvik: pd.DataFrame) -> float:
    """Least-squares k so that k * (our unshrunk AdjEM, centred) ~ Torvik AdjEM (centred)."""
    m = ours_u.merge(torvik, on="team")
    x = (m.AdjOE_u - m.AdjDE_u); x = x - x.mean()
    y = (m.adjoe - m.adjde); y = y - y.mean()
    return float((x * y).sum() / (x * x).sum())


def predictive_check(games: pd.DataFrame, teams, prior, cutoff: str, rate_fn) -> dict:
    """Out-of-sample sanity check of the prior: rate on games before `cutoff`, predict the
    margin per 100 possessions of every later game, report MAE with and without prior."""
    before, after = games[games.date < cutoff], games[(games.date >= cutoff) & games.d1]
    out = {}
    for label, p in (("with_prior", prior), ("no_prior", None)):
        r = rate_fn(before, teams, p, shrink=1.0).ratings.set_index("team")
        hca = np.where(after.neutral, 0.0, config.HCA)
        pred = (r.AdjEM.reindex(after.home).values - r.AdjEM.reindex(after.away).values) + 2 * hca
        actual = 100 * (after.h_PTS - after.a_PTS) / after.poss
        ok = ~np.isnan(pred)
        out[label] = {"mae_per100": float(np.abs(pred[ok] - actual.values[ok]).mean()),
                      "winner_correct": float(((pred[ok] > 0) == (actual.values[ok] > 0)).mean()),
                      "games": int(ok.sum())}
    out["cutoff"] = cutoff
    return out
