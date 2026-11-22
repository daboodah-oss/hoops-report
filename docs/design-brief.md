# Design Brief — College Basketball Ratings & Analysis Page (working title: "Hoops Report")

**Drafted:** Sat Nov 21, 2026 · **Status:** APPROVED Nov 22, 2026 — all four open questions ruled (name: hoops.daboodah.com; lane: Claude builds engine/pipeline, Budzilla page loop; Fable: skipped; prior: flat for v1)
**Basis:** Nov 19 voice-call design conversation + Nov 21 feasibility check (VERDICT.md in this folder — prototype reproduced Torvik's 2024-25 final rankings at Spearman 0.991, top-30 within 1.9 places, Indiana #45 ours vs #50 his)

---

## 1. What this is

A college basketball analysis site in the football-report family (IU Report, ND Report, College Football): a documented repo, a scheduled pipeline on GitHub's computers, a static page on GitHub Pages. Any of Jeff's three assistants can pick it up cold from the repo docs.

The difference from the football pages: this one runs **our own ratings engine** — Torvik/KenPom-style adjusted efficiency, computed by us from public box scores — instead of only displaying someone else's numbers. IU is the default center team, but the engine covers all of D1.

## 2. V1 scope (deliberately small — the anti-rabbit-hole clause)

**In v1:**
1. **Ratings engine**
   - Possessions: FGA − ORB + TO + 0.44·FTA (game pace = mean of the two teams' estimates)
   - Raw efficiency per 100 possessions, offense and defense
   - Iterative opponent + location adjustment loop (home court ≈ 3.0 pts/100 poss, damped until convergence)
   - Outputs per team: AdjOE, AdjDE, AdjEM, Barthag (exponent 11.5), rank
   - Preseason prior: last season's final ratings blended in, fading as games accumulate (KenPom-style, gone by ~game 27). Returning-production weighting is a v1 stretch item, not a requirement — a flat team prior is acceptable for v1.
   - Shrinkage calibration so our AdjEM spread is comparable to published ratings (prototype ran wide: Duke +45.6 vs Torvik +38.6)
2. **The page**
   - IU front and center by default: season ratings card, game-by-game efficiency graph (the visual language of the football pages)
   - Compare picker: any D1 team(s) charted against IU (or against each other), game-by-game lines
   - Full ratings table: all ~364 teams, sortable, in rank order by default
   - Player layer: per-team player stats table (season totals/rates), drill-down from the team view — display only, no player ratings engine in v1
   - Game log per team: opponent, result, game efficiency splits
   - **GameTracker chart, IU games only (added by Jeff, Nov 21):** for each IU game, a scoring-progression line graph — game clock on the x-axis, score/margin on the y-axis — on the game's drill-down, built from ESPN play-by-play (every scoring play carries a clock time). Post-game only: it lands with the daily update. Live in-game tracking is NOT in v1 (the pipeline is a daily build, not a live feed). Scope is IU games only to bound the data work; widening to more teams is a later call based on use.
   - "Go deeper" links section near the bottom: KenPom, Bart Torvik, EvanMiya, Haslametrics, Hoop Explorer, NCAA NET, Sports Reference; Sagarin listed as historical only (ratings ended 2023). Links only — no scraping or replicating their presentation.
3. **Pipeline**
   - Daily GitHub Actions run (collect → build → Pages), same pattern as iu-qb-report / college-football, including the render-verification QA step before calling a build good
   - Data source v1: Bart Torvik's published game files (free, no key; daily pull, cached, polite rate). The parser MUST keep the feasibility regression test: the embedded box score is stored once per game in fixed team order — reading it per-row silently swaps every game's stats.
   - Every run recomputes the full season from scratch (seconds of compute; no incremental state to corrupt)

**Explicitly NOT in v1:**
- Game predictions / win probabilities for upcoming games (Barthag vs an average team is a rating, not a matchup prediction — page copy must not blur this)
- AI analysis layer (summaries, matchup insights, what-ifs) — v2, after the base numbers have a season of being checked against reality
- Alternative/experimental rating schemes side-by-side — v2+
- Betting lines, odds, or picks
- Women's basketball (separate conversation if ever)

## 3. Data notes

- Torvik game file fields verified Nov 21: date, teams, venue H/A/N (incl. neutral), score, full box score (FGA, ORB, TO, FTA all present). 2024-25: 5,764 games, 364 teams.
- Current season file exists at the same pattern (year=2026 for 2025-26), so the site can go live in-season and the prior fades naturally.
- Graduation path if Torvik's files ever become unavailable or terms change: build box scores from ESPN/NCAA feeds via sportsdataverse/hoopR — same counting stats, engine unchanged. Noted in repo docs, not built in v1.
- Player stats source (Torvik player file) was identified but NOT tested in the feasibility check — first build task is verifying it; fallback is per-game box-score aggregation from the game file we already pull.
- GameTracker source (ESPN play-by-play via sportsdataverse/hoopR) likewise identified but NOT tested — a build task verifies it on a completed IU game before the chart is promised on the page; the Torvik game file alone cannot produce it (no clock times).

## 4. Page design principles

- Same family look and QA bar as the football reports: sticky header with scroll-margin on anchors, no pill styling on non-interactive elements, works at phone / iPad / desktop widths, renders verified in jsdom before push (per the standing QA checklist in AGENTS.md)
- Leaderboards always in rank order
- Every number on the page traceable to the engine output in the repo (data files committed alongside the build, like the football repos)
- A short "How these numbers work" section on the page itself: possessions, adjustment loop, Barthag, the prior and its fade — in plain words, the way it was explained on the Nov 19 call. This is part of the fun Jeff asked for, not documentation garnish.

## 5. Build order

1. Repo created (daboodah-oss), branch protection Tier 1 applied immediately, this brief committed to `docs/` on main
2. Data ingest + parser with regression tests
3. Engine v1: adjustment loop + prior + shrinkage calibration; validated against Torvik 2024-25 finals (acceptance: Spearman ≥ 0.98, top-30 mean rank diff ≤ 3, Indiana within 10 places) and then run on the current season
4. Page build + QA pass
5. Daily schedule on; soak for a week of daily runs before calling it live

## 6. Open questions for Jeff (rulings needed before build)

1. **Name / address: RULED Nov 21 — `hoops.daboodah.com`.**
2. **Build lane: RULED Nov 21 — Claude builds the engine/pipeline in a Claude Code cloud session from this brief in the repo; Budzilla reviews and runs the page iterate loop with Jeff.**
3. **Fable review: RULED Nov 22 — skipped. Straight to build; the feasibility verdict stands as the design check.**
4. **Prior strength: RULED Nov 22 — flat prior for v1 (last year's final rating, simple fade). Returning production is the first v1.1 item; if its design is taken up, that piece alone gets a Fable adversarial pass (Jeff's question, Nov 22), scoped to the prior spec only.**

## 7. Success criteria

- Daily page updates land without manual steps (Jeff's only step is approvals)
- Our ratings stay within the acceptance band of published ratings all season
- Jeff actually uses the compare picker during games — the real test, same as the football pages
