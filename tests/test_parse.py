"""Box-score-order regression test (design brief: MUST be kept) plus parser basics."""
import copy
import json
from pathlib import Path

import pytest

from hoops import parse

FIX = Path(__file__).parent / "fixtures" / "gamestats_2025_sample.json"


@pytest.fixture
def rows():
    return json.loads(FIX.read_text())


def test_box_order_check_passes_on_real_rows(rows):
    rep = parse.check_box_order(rows)
    assert rep["mismatches"] == 0
    # half the rows sit "behind" the box's fixed order: a per-row reading would be wrong
    assert rep["naive_reading_wrong"] == len(rows) // 2


def test_box_order_check_catches_a_swapped_box(rows):
    bad = copy.deepcopy(rows)
    # keep team names in fixed order but swap the stat blocks: stats now belong to the wrong team
    for r in bad:
        box = json.loads(r[29])
        box[4:19], box[19:34] = box[19:34], box[4:19]
        r[29] = json.dumps(box)
    with pytest.raises(parse.BoxOrderError):
        parse.check_box_order(bad)


def test_box_order_check_catches_a_foreign_team(rows):
    bad = copy.deepcopy(rows)
    box = json.loads(bad[0][29]); box[2] = "Not A Team"; bad[0][29] = json.dumps(box)
    with pytest.raises(parse.BoxOrderError):
        parse.check_box_order(bad)


def test_parser_assigns_stats_to_the_right_team(rows):
    teams = {r[2] for r in rows} | {r[4] for r in rows}
    g = parse.parse_games(rows, teams)
    assert len(g) == len(rows) // 2                     # one row per game
    for r in rows:
        tpts, opts = parse.team_points_from_result(r[6])
        team, opp = r[2], r[4]
        m = g[((g.home == team) & (g.away == opp)) | ((g.home == opp) & (g.away == team))]
        assert len(m) == 1
        m = m.iloc[0]
        mine = m.h_PTS if m.home == team else m.a_PTS
        theirs = m.a_PTS if m.home == team else m.h_PTS
        assert (mine, theirs) == (tpts, opts)
        if r[5] == "H":
            assert m.home == team and not m.neutral
        if r[5] == "N":
            assert m.neutral


def test_result_string():
    assert parse.team_points_from_result("L, 94-59") == (59, 94)
    assert parse.team_points_from_result("W, 81-60") == (81, 60)
    assert parse.team_points_from_result("W, 60-81") == (81, 60)   # order-agnostic


def test_possessions_formula(rows):
    g = parse.parse_games(rows, {r[2] for r in rows} | {r[4] for r in rows})
    r = g.iloc[0]
    assert r.h_poss == pytest.approx(r.h_FGA - r.h_ORB + r.h_TO + 0.44 * r.h_FTA)
    assert r.poss == pytest.approx((r.h_poss + r.a_poss) / 2)


def test_dates_both_formats():
    assert parse._date("12/9/24") == "2024-12-09"
    assert parse._date("12/21/2023") == "2023-12-21"
