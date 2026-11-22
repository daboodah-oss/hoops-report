# Feasibility verdict — own college basketball ratings engine

**Date:** Sat Nov 21, 2026 · **Test season:** 2024-25 (Torvik "2025")
**Verdict: FEASIBLE. The base engine works with free data, today, in ~150 lines of Python.**

## What was actually done

- **Data source (free, no key, no login): Bart Torvik's own published files.**
  - Game log: `https://barttorvik.com/getgamestats.php?year=2025&json=1`
    — 11,528 team-game rows = **5,764 games, 364 D1 teams**. Each row carries
    date, team, opponent, conference, venue (H/A/N), result/score, and an
    embedded full box-score string for both teams (FGM, FGA, 3PM, 3PA, FTM,
    FTA, ORB, DRB, REB, AST, STL, BLK, TO, PF, PTS). Everything the
    possession formula needs is present.
  - Validation targets: `https://barttorvik.com/2025_team_results.csv`
    — Torvik's final 2024-25 AdjOE / AdjDE / Barthag for all 364 teams.
- **Engine** (`ratings.py`, runs in ~2 seconds):
  possessions = FGA − ORB + TO + 0.44·FTA (game pace = mean of the two
  teams' estimates; actual mean 67.9 poss/game) → raw efficiency per 100 →
  iterative opponent + location adjustment (home court = 3.0 pts/100 poss,
  damped fixed-point iteration, converged in 100 iterations) → Barthag with
  Torvik's 11.5 exponent.

## How close we landed vs Torvik's published final ratings

| Measure | Result |
|---|---|
| Spearman rank correlation, AdjEM | **0.991** |
| Spearman rank correlation, Barthag | **0.991** |
| Pearson correlation, AdjEM | 0.992 |
| Mean absolute rank difference, all 364 teams | 10.0 places |
| Top-30: mean absolute rank difference | **1.9 places** |
| Top-30 overlap | **29 of 30** (mine has Connecticut, his has Oregon) |
| Top 5 | Duke, Houston, Auburn, Florida, Tennessee — same five as Torvik, near-identical order |
| **Indiana** | **Mine #45** (AdjO 116.0, AdjD 95.0, AdjEM +21.0) vs **Torvik #50** (113.1 / 97.7 / +15.4) |

One systematic difference: my AdjEM *spread* is wider than Torvik's
(e.g. Duke +45.6 vs his +38.6). Rankings are nearly identical; the levels
differ because Torvik shrinks toward preseason priors and applies
game-level weighting we deliberately omitted. If we ever publish numbers
side-by-side with his, a light shrinkage factor closes most of that gap.

## Gotchas found (the useful kind)

- The gamestats embedded box score is stored **once per game in a fixed
  team order** — it does not follow the row's perspective. Assuming it did
  silently swapped every game's stats and produced garbage rankings
  (Spearman ≈ 0). Caught by cross-checking box-score points against each
  row's result string (11,528/11,528 rows confirm the fixed order).
  Any production parser must keep that regression test.
- Undamped adjustment iteration oscillates at ~1e-3 forever; damping 0.5
  converges cleanly to the same fixed point.

## Gaps / deliberate omissions in this prototype

- **No preseason prior** (Torvik/KenPom blend one in, fading over ~20+
  games). End-of-season numbers barely notice; early-season numbers would
  bounce exactly as Jeff predicted in the Nov 19 call. This is the single
  biggest piece to add for a live site.
- **No recency weighting, no garbage-time filtering, no injury/availability
  adjustment** — all refinements Torvik applies; none changed the ranking
  story materially here.
- **Neutral-site flag** comes straight from Torvik's venue field (1,478 of
  11,528 team-games) — reliable in this source.
- **D1-only:** this source is already D1-only (all 5,764 games are
  D1-vs-D1), so no filtering was needed; games vs non-D1 schools simply
  aren't in the file, which slightly understates cupcake-game volume vs
  KenPom's universe.
- **Data license/etiquette:** Torvik's files are publicly downloadable and
  are the de-facto community source (sportsdataverse documents them), but
  they are *his* compilation. A production site should either keep pulling
  politely (daily, cached, not hammering) or graduate to building box
  scores from ESPN/NCAA feeds via sportsdataverse/hoopR, which expose the
  same counting stats. The engine doesn't care which feed fills the table.
- Current-season (2025-26) files exist at the same URLs with year=2026,
  so a live site can start now and blend the prior in as games accumulate.

## What a production pipeline would need (rough)

1. **Daily ingest** (GitHub Actions cron, same pattern as the football
   reports): pull the current-year gamestats file, parse, regression-test
   the box-score order, store a tidy games table in the repo.
2. **Ratings job**: this script, plus (a) preseason prior from last year's
   final ratings + returning-production if we want early-season stability,
   (b) optional recency weighting, (c) shrinkage calibration vs Torvik.
   Runtime is seconds; the whole season recomputes from scratch daily.
3. **Outputs**: ratings table + per-team game-by-game efficiency series
   (the graphs Jeff wants), compare-picker data for any two teams, player
   stats layer (Torvik publishes a player file at the same host —
   `getadvstats.php` — not tested here).
4. **Page**: one more repo in the football-report family
   (collect → build → GitHub Pages), IU as the default center team.

**Bottom line for Jeff:** the math is real, the data is free, and a
weekend-grade prototype already reproduces Torvik's rankings to within
a couple of places where it matters. The rabbit-hole risk is not the
engine — it's the extras (priors, predictions, AI layer). Build the base
first, exactly as scoped.
