# Engine v1: build notes and validation

**Built:** Nov 24-25, 2026 · **Scope:** data pipeline + ratings engine only (page is a later pass)

## Acceptance band (brief section 5), 2024-25 vs Torvik finals: PASSED

| Measure | Band | Prototype (Nov 21) | Engine v1 |
|---|---|---|---|
| Spearman, AdjEM | ≥ 0.98 | 0.991 | **0.993** |
| Top-30 mean abs rank diff | ≤ 3 | 1.9 | **1.9** (29 of 30 overlap) |
| Indiana | within 10 places | #45 vs #50 | **#49 vs #50** |
| Mean abs rank diff, all 364 | (none) | 10.0 | 8.8 |
| AdjEM spread (sd) ours vs Torvik | (none) | wide (Duke +45.6 vs +38.6) | 12.68 vs 12.74 |
| AdjEM mean abs error vs Torvik | (none) | n/a | 1.16 |
| Indiana AdjO / AdjD / AdjEM | (none) | 116.0 / 95.0 / +21.0 | 113.8 / 98.6 / +15.2 (Torvik 113.1 / 97.7 / +15.4) |

Torvik "rank" is his published (Barthag-order) rank column, as in the feasibility check.  Source of truth: `data/2025/validation.json`.

### Other seasons (report only; band enforced on 2024-25)

| Season | Spearman | Top-30 diff | Indiana ours vs Torvik | Note |
|---|---|---|---|---|
| 2023-24 (2024) | 0.993 | 3.23 | #100 vs #83 | first season in the chain, built **without** a prior |
| 2025-26 (2026) | 0.992 | 2.33 | #40 vs #32 | shrinkage holdout season: sd 13.11 vs 13.19 |
| 2026-27 (2027), through Nov 24 | 0.939 | 8.2 | #35 vs #29 | early season, see below |

## What changed from the prototype

1. **Defensive home-court sign fixed.**  The prototype subtracted HCA from home defense when it should add it back (a home defense is *expected* to allow HCA fewer points per 100, so the observed number flatters it).  The bug inflated defense for teams with home-heavy schedules.  Fixing it alone moved 2024-25 from Spearman 0.991 to 0.993 and Indiana from #45 to #49.  `tests/test_engine.py` recovers known ratings from synthetic unbalanced-venue games and fails under the old sign.
2. **Level pinned every iteration.**  The model only fixes ratings up to a common shift (all AdjOE +c, all AdjDE −c fit the games equally), so each iteration re-centres game-weighted mean AdjOE and AdjDE on the league average.  Without it the prior-blended loop crawled and hit the 2000-iteration cap; with it, about 150 iterations to 1e-6.
3. **Flat preseason prior** (ruling Nov 22): last season's final *unshrunk* ratings, as deviations from last season's league average, re-centred on this season's.  Blended inside the loop with weight `max(0, 1 − games/27)`, so opponents are judged by blended ratings too.  Teams new to D1 (2027: West Florida) get the O/D split of teams near the 10th percentile of last year's AdjEM.
4. **Shrinkage calibration:** published AdjOE/AdjDE = avg + 0.889 × (unshrunk − avg).  Fitted by least squares on 2024-25 (`scripts/calibrate.py`), holdout-checked on 2025-26.  The loop and next year's prior run unshrunk, so nothing is shrunk twice.

## Does the prior help?  Out-of-sample check

Rate on games before a cutoff, predict margin per 100 possessions of every later game (`hoops/validate.py: predictive_check`):

| Season, cutoff | MAE with prior | MAE no prior |
|---|---|---|
| 2024-25, Nov 20 | **14.81** | 18.63 |
| 2024-25, Dec 1 | **14.38** | 15.19 |
| 2024-25, Dec 20 | 14.15 | 14.11 |
| 2024-25, Jan 15 | 13.56 | 13.49 |
| 2025-26, Nov 20 | **15.19** | 16.11 |
| 2025-26, Dec 1 | **14.71** | 15.13 |
| 2025-26, Dec 20 | **14.27** | 14.50 |

The prior earns its keep in November and early December and is neutral by mid-season.  By late December the flat, unregressed prior is very slightly over-weighted.  That points straight at the v1.1 item already on the list (returning production) or a one-knob alternative: regress the prior part-way to the mean.

## Early-season gap vs Torvik (current season)

Through Nov 24 (about 5 games per team) we sit at Spearman 0.94 vs Torvik's live ratings, below the band.  Expected: Torvik's early-season numbers are driven by a returning-production/recruiting prior, ours by a flat one.  The brief's success criterion "stay within the acceptance band all season" will not hold in November with a flat prior; it should hold once the prior has faded (the finished seasons all pass).  `data/2027/validation.json` is rewritten every run, so the gap can be watched closing.

## Source verification (brief section 3: "first build task")

- **Torvik player file** (`getadvstats.php?year=YYYY&json=1`): **works**.  No header row; 4,863 player rows for 2026-27; column positions in `hoops/players.py`.  Cross-check: Indiana's 13 players sum to **527 points**, identical to Indiana's total in the game file (6 games).  The fallback (box-score aggregation) is not needed.
- **ESPN play-by-play** (`site.api.espn.com/.../summary?event=ID`, keyless JSON): **works** without hoopR/sportsdataverse.  All 6 completed IU games verified: last scoring play equals the final score, scores never decrease.  One feed quirk handled: plays sharing a clock second can be listed out of order (Kentucky, 16:38, 2nd half); they are ordered by cumulative score within the second.  GameTracker can be promised on the page.

## Box-score-order regression test

`hoops/parse.py: check_box_order` runs on every row of every pull and the pipeline refuses to build if any row fails.  Every season so far: 0 mismatches, and exactly half the rows (one per game) would be wrong under a naive per-row reading, which proves the test still bites on live data.  Unit tests in `tests/test_parse.py` use 8 real 2024-25 rows and synthetic corruptions.
