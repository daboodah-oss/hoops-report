"""Engine recovers known ratings from noise-free synthetic games."""
import itertools

import numpy as np
import pandas as pd
import pytest

from hoops import config, engine, espn

AVG = 105.0


def synth(n=12, seed=0, home_bias=True):
    rng = np.random.default_rng(seed)
    teams = [f"T{i:02d}" for i in range(n)]
    O = pd.Series(AVG + rng.normal(0, 8, n), index=teams)
    D = pd.Series(AVG + rng.normal(0, 8, n), index=teams)
    O += AVG - O.mean(); D += AVG - D.mean()          # double round robin -> equal gp, mean = AVG
    recs = []
    for k, (a, b) in enumerate(itertools.permutations(teams, 2)):
        # unbalanced venues on purpose: low-index teams host more, some games neutral
        neutral = (k % 5 == 0)
        home, away = (a, b) if (not home_bias or a < b or neutral) else (b, a)
        h = 0.0 if neutral else config.HCA
        poss = 70.0
        h_oe = O[home] + D[away] - AVG + h
        a_oe = O[away] + D[home] - AVG - h
        recs.append(dict(date="2025-01-01", home=home, away=away, neutral=neutral, d1=True,
                         poss=poss, h_PTS=h_oe * poss / 100, a_PTS=a_oe * poss / 100))
    return pd.DataFrame(recs), teams, O, D


def test_recovers_true_ratings_with_unbalanced_home_games():
    g, teams, O, D = synth()
    r = engine.rate(g, teams, None, shrink=1.0).ratings.set_index("team")
    # league avg in the engine is pts/poss over all games; equals AVG here by construction
    assert np.allclose(r.AdjOE_u[teams], O[teams], atol=1e-3)
    assert np.allclose(r.AdjDE_u[teams], D[teams], atol=1e-3)   # fails with the prototype's -hca sign


def test_shrink_scales_deviation_only():
    g, teams, O, D = synth()
    r = engine.rate(g, teams, None, shrink=0.8).ratings.set_index("team")
    assert np.allclose(r.AdjOE - r.league_avg, 0.8 * (r.AdjOE_u - r.league_avg))
    assert r.Barthag.between(0, 1).all()
    assert list(r.sort_values("rank").index) == list(r.sort_values("AdjEM", ascending=False).index)


def test_prior_only_when_no_games_and_fades_out():
    g, teams, O, D = synth()
    prev = pd.DataFrame({"team": teams, "AdjOE_u": AVG + 10, "AdjDE_u": AVG - 10, "league_avg": AVG})
    prior = engine.build_prior(prev, teams)
    none = engine.rate(g.iloc[:0], teams, prior, shrink=1.0).ratings
    assert np.allclose(none.AdjOE_u - none.AdjDE_u, 20.0)       # no games: pure prior
    full = engine.rate(g, teams, prior, shrink=1.0, fade_games=5).ratings.set_index("team")
    assert (full.prior_weight == 0).all()                       # 22 games > 5: prior gone
    assert np.allclose(full.AdjOE_u[teams], O[teams], atol=1e-3)


def test_new_team_gets_low_prior():
    prev = pd.DataFrame({"team": [f"T{i}" for i in range(40)], "AdjOE_u": np.linspace(95, 125, 40),
                         "AdjDE_u": AVG, "league_avg": AVG})
    p = engine.build_prior(prev, list(prev.team) + ["Newcomer"])
    assert not p.loc["Newcomer", "has_prior"]
    assert p.loc["Newcomer", "pO"] < p.pO.median()


@pytest.mark.parametrize("period,clock,t", [(1, "20:00", 0), (1, "0:00", 1200), (2, "10:00", 1800),
                                            (3, "5:00", 2400), (3, "0:00", 2700), (4, "2:30", 2850)])
def test_clock_seconds(period, clock, t):
    assert espn.clock_seconds(period, clock) == t
