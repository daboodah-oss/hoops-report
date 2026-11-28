#!/usr/bin/env bash
# Commit data/ from a pipeline run.  Route "auto": try a direct push to the run's branch;
# if the push is refused (ruleset requires a PR, or the branch moved), push a dated data
# branch and open a PR that merges itself.  Route "pr": skip the direct push.
set -euo pipefail
git config user.name "hoops-report-bot"
git config user.email "actions@users.noreply.github.com"
git add data/
if git diff --cached --quiet; then echo "no data changes"; exit 0; fi
day=$(date -u +%F)
msg="data: daily update $day"
git commit -q -m "$msg"
base="${GITHUB_REF_NAME}"
if [ "${COMMIT_ROUTE:-auto}" = "auto" ]; then
  if git push origin "HEAD:refs/heads/$base" 2>push.err; then
    echo "::notice::direct push to $base accepted"; exit 0
  fi
  cat push.err
  echo "::warning::direct push to $base refused; using the PR route"
fi
head="data/run-$day-${GITHUB_RUN_ID}"
git push -q origin "HEAD:refs/heads/$head"
url=$(gh pr create --base "$base" --head "$head" --title "$msg" \
  --body "Automated data commit from daily-pipeline run ${GITHUB_SERVER_URL}/${GITHUB_REPOSITORY}/actions/runs/${GITHUB_RUN_ID}.  Tests, box-order check and pipeline already passed in that run.")
echo "opened $url"
if gh pr merge "$url" --merge --delete-branch; then
  echo "::notice::merged $url"
else
  gh pr merge "$url" --merge --auto --delete-branch
  echo "::notice::auto-merge enabled on $url (waiting on required checks or reviews)"
fi
