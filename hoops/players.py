"""Torvik player season file (getadvstats.php).  The JSON has no header row; column
positions below follow the community documentation (toRvik / cbbdata) and are
sanity-checked in the pipeline against team points from the game file."""
import pandas as pd

COLS = {
    0: "player", 1: "team", 2: "conf", 3: "gp", 4: "min_pct", 5: "ortg", 6: "usg",
    7: "efg", 8: "ts", 9: "orb_pct", 10: "drb_pct", 11: "ast_pct", 12: "to_pct",
    13: "ftm", 14: "fta", 15: "ft_pct", 16: "fg2m", 17: "fg2a", 18: "fg2_pct",
    19: "fg3m", 20: "fg3a", 21: "fg3_pct", 22: "blk_pct", 23: "stl_pct", 24: "ftr",
    25: "class", 26: "height", 27: "number", 28: "porpag", 29: "adj_oe", 31: "year",
    32: "pid", 46: "drtg", 50: "bpm", 54: "mpg", 57: "orb_pg", 58: "drb_pg",
    59: "reb_pg", 60: "ast_pg", 61: "stl_pg", 62: "blk_pg", 63: "pts_pg", 64: "role",
}
MIN_ROW_LEN = max(COLS) + 1


def parse_players(rows: list) -> pd.DataFrame:
    short = [r for r in rows if len(r) < MIN_ROW_LEN]
    if short:
        raise ValueError(f"{len(short)} player rows shorter than {MIN_ROW_LEN} fields; layout changed?")
    df = pd.DataFrame([[r[i] for i in COLS] for r in rows], columns=list(COLS.values()))
    df["pts"] = (df.pts_pg * df.gp).round(0)
    # derived totals straight from the counting columns (independent of pts_pg)
    df["pts_from_makes"] = df.ftm + 2 * df.fg2m + 3 * df.fg3m
    return df.sort_values(["team", "pts_pg"], ascending=[True, False]).reset_index(drop=True)


def check_against_games(players: pd.DataFrame, team_games: pd.DataFrame, team: str) -> dict:
    """Sum of players' points (from makes) vs the team's points in the game file.  The
    player file counts non-D1 games too, so the ratio can exceed 1 for some teams."""
    p = players[players.team == team]
    tg = team_games[team_games.team == team]
    return {"team": team, "players": int(len(p)),
            "player_pts_from_makes": float(p.pts_from_makes.sum()),
            "player_pts_from_ppg": float(p.pts.sum()),
            "game_file_pts_d1": float(tg.pts.sum()), "game_file_games_d1": int(len(tg)),
            "player_max_gp": int(p.gp.max()) if len(p) else 0}
