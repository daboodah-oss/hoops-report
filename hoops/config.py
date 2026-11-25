"""Constants, paths and source URLs.  Every tunable lives here so a run is reproducible."""
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
RAW = DATA / "raw"            # download cache (gitignored)

# ---- sources (free, no key).  Torvik "year" = the spring of the season (2027 = 2026-27).
TORVIK_GAMESTATS = "https://barttorvik.com/getgamestats.php?year={year}&json=1"
TORVIK_TEAM_RESULTS = "https://barttorvik.com/{year}_team_results.csv"
TORVIK_PLAYERS = "https://barttorvik.com/getadvstats.php?year={year}&json=1"
ESPN_SCHEDULE = ("https://site.api.espn.com/apis/site/v2/sports/basketball/"
                 "mens-college-basketball/teams/{team_id}/schedule?season={year}")
ESPN_SUMMARY = ("https://site.api.espn.com/apis/site/v2/sports/basketball/"
                "mens-college-basketball/summary?event={event_id}")
USER_AGENT = "hoops-report-pipeline/1.0 (daily cached pull; github.com/daboodah-oss/hoops-report)"
POLITE_DELAY_S = 3.0          # pause between requests to the same host
CACHE_MAX_AGE_H = 20          # re-download a cached file at most about once a day

# ---- engine
HCA = 3.0                     # home court, points per 100 possessions
PYTHAG_EXP = 11.5             # Barthag exponent (Torvik)
DAMPING = 0.5                 # undamped iteration oscillates; 0.5 converges to the same fixed point
TOL = 1e-6
MAX_ITER = 2000
PRIOR_FADE_GAMES = 27         # flat prior weight = max(0, 1 - games_played / 27)
NEW_TEAM_PRIOR_PCTILE = 0.10  # teams with no prior season: prior = this percentile of last year's AdjEM
# Shrinkage applied to published AdjOE/AdjDE deviations from league average.
# Calibrated on 2024-25 vs Torvik finals (scripts/calibrate.py); holdout-checked on 2025-26.
SHRINK = 0.889

# ---- validation acceptance band (design brief, section 5), enforced on the validation season
VALIDATION_SEASON = 2025      # 2024-25
ACCEPT_SPEARMAN = 0.98
ACCEPT_TOP30_MEAN_RANK_DIFF = 3.0
ACCEPT_INDIANA_PLACES = 10

CENTER_TEAM = "Indiana"
ESPN_CENTER_TEAM_ID = 84      # Indiana Hoosiers on ESPN


def current_season(today: date | None = None) -> int:
    """Torvik season year: Aug-Dec belong to next spring's season."""
    t = today or date.today()
    return t.year + 1 if t.month >= 8 else t.year


def season_dir(year: int) -> Path:
    d = DATA / str(year)
    d.mkdir(parents=True, exist_ok=True)
    return d
