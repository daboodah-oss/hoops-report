# hoops-report
College basketball ratings and analysis page (hoops.daboodah.com) - own Torvik-style adjusted efficiency engine, IU-centered

- Design brief: `docs/design-brief.md` · feasibility: `docs/feasibility-verdict.md` · engine validation: `docs/engine-validation.md`

## Run it

```bash
pip install -r requirements.txt
python -m pytest -q
python scripts/run_pipeline.py              # current season; builds prior seasons from cache if missing
python scripts/run_pipeline.py --season 2025  # validation season (exit 1 if outside the acceptance band)
python scripts/calibrate.py                 # refit shrinkage on 2024-25, holdout 2025-26
```

## Layout

| Path | What |
|---|---|
| `hoops/config.py` | every constant: URLs, HCA 3.0, Barthag 11.5, prior fade 27 games, shrink 0.889, acceptance band |
| `hoops/ingest.py` | polite cached downloads (UA, 3 s between hits, at most daily; finished seasons never re-fetched) |
| `hoops/parse.py` | Torvik gamestats parser + **box-score-order regression test** (build refuses on failure) |
| `hoops/engine.py` | possessions, damped opponent/venue adjustment loop, flat prior blend, shrinkage, Barthag |
| `hoops/validate.py` | comparison vs Torvik published ratings, shrink fit, prior predictive check |
| `hoops/players.py` | Torvik player season file |
| `hoops/espn.py` | ESPN play-by-play scoring progression for IU games (GameTracker) |
| `data/<season>/ratings.csv` | one row per D1 team, rank order.  `AdjOE/AdjDE/AdjEM/Barthag` are published (shrunk); `*_u` are unshrunk and feed next season's prior |
| `data/<season>/validation.json` | vs Torvik for that season |
| `data/<current>/team_games.csv` | per team-game raw and game-level adjusted efficiency (the game-by-game graphs) |
| `data/<current>/games.csv` | tidy per-game box scores |
| `data/<current>/players.csv` | per-player season stats, all D1 |
| `data/<current>/gametracker/` | one JSON per completed IU game + `index.json` |
| `data/raw/` | download cache, gitignored |

Every run recomputes the full season from scratch.  The daily workflow (`.github/workflows/pipeline.yml`) is manual-trigger only until the page exists (brief build step 5).

Graduation path if Torvik's files become unavailable: build the same box scores from ESPN/NCAA feeds (sportsdataverse/hoopR); the engine only needs the `games` table.  Not built in v1.
