# Brief: make the daily pipeline's Torvik fetch survive GitHub Actions

Status: queued 2026-11-28.  Owner lane: Claude (pipeline code).  Budzilla diagnosed and is running a manual stopgap; this brief is the durable fix.

## The problem, verified 2026-11-27/28

Bart Torvik's site returns **403 Forbidden** to this repo's GitHub Actions runners.  Evidence:

- Two `workflow_dispatch` runs (2026-11-28T04:35Z and 04:54Z, runs 46108295093 and 46109653429) both failed at the first fetch in `hoops/ingest.py`: `requests.exceptions.HTTPError: 403 Client Error: Forbidden for url: https://barttorvik.com/getgamestats.php?year=2027&json=1`.  Tests passed; the commit step never ran.
- The same URL returns **200** from other networks (Budzilla's VM), with every user agent tried: curl default, `python-requests`, a Chrome UA, and the pipeline's own `config.USER_AGENT`.  The URL, the file, and the user agent are all fine.  The block is specific to the Actions egress IPs (shared datacenter addresses; possibly rate-based, possibly a range block; duration unknown).
- The daily schedule (06:17 ET) will keep failing while the block holds.  The soak week cannot complete until this is fixed.

## Stopgap in place (not the fix)

Budzilla runs `scripts/run_pipeline.py` locally (this network reaches Torvik), then pushes the resulting `data/<season>/` files to main via branch, PR, and merge, exactly the outputs the bot would commit.  First stopgap run: 2026-11-28, data through 2026-11-27, Indiana 8-0.  This is manual and must not become the standing design.

## What the fix must achieve

1. A `workflow_dispatch` run on GitHub Actions completes end to end and commits fresh data, with Torvik still blocking direct fetches from Actions IPs.  Two consecutive scheduled runs must also succeed.
2. Fetch layer only: for identical inputs, ratings outputs must be byte-identical to today's pipeline.  No engine, parser, or data-layout changes.
3. Stay polite and honest with Torvik: keep the cache, the polite delay, and an identifying user agent.  Do not evade with browser-UA spoofing or proxy rotation designed to look like someone else.  A relay that fetches once, under our own identity, from a network Torvik accepts, is fine.
4. Keep every existing gate: the box-order regression test, the pytest suite, and the validation band must still run and still be able to fail the build.

## Design space (Claude's call, Jeff approves the choice)

- **Split collect from compute.**  A collector on a network Torvik accepts (candidates: Budzilla's VM, Jeff's NAS) fetches the three Torvik files on a schedule and lands them where the Actions workflow can consume them (for example, committed to a `raw-cache` branch, or uploaded as a workflow artifact by an API-triggered run).  The Actions pipeline prefers the collected copies and falls back to a direct fetch.  Raw files are currently gitignored (`data/raw/`); the design must state where collected files live and how freshness is proven (the pipeline already stamps `meta.json`).
- **Long-backoff retry** in `_get` is acceptable as a supplement, not as the fix: an IP block does not clear in seconds, and one runner keeps one IP for the whole job.
- **Alternate Torvik endpoints** (a mirror or CDN host for the same files) may be checked, but do not depend on an undocumented endpoint without a fallback.

## Second latent issue to verify while you are in there

The workflow's Commit data step pushes directly to `main` with the `GITHUB_TOKEN`, while this repo has a Tier 1 ruleset (PR required before merging).  No run has reached the commit step yet, so whether the bot push is exempt is untested.  Verify it.  If the push is rejected, change the commit step to push a dated data branch and open a PR that auto-merges (the route Budzilla's stopgap pushes already prove works), and note the change in the PR for this fix.

## Acceptance

- A dispatched run succeeds end to end on Actions and the committed data matches a local run over the same inputs.
- The next two scheduled runs succeed without intervention.
- A short note in this repo's docs records the chosen design, so any of Jeff's assistants can run the pipeline cold.
