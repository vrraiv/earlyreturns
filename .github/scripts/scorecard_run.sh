#!/usr/bin/env bash
# Daily scorecard refresh on GitHub Actions. Runs every step of src/run_scorecard.py --build, retrying the Wikipedia
# fetches through rate limits until MAX_MINUTES, then runs src/check_scorecard.py. Never touches main: the workflow
# opens a PR with whatever this produced, and a person merges it.
# Writes: ci_out/status (CLEAN|REVIEW|HOLD|FAILED), ci_out/check.txt, ci_out/run.log, ci_out/summary.md
set -uo pipefail
mkdir -p ci_out
LOG=ci_out/run.log
: > "$LOG"
MAX_MINUTES=${MAX_MINUTES:-150}
deadline=$((SECONDS + MAX_MINUTES * 60))
failed_step=""

py() { uv run --locked python "$@" 2>&1 | tee -a "$LOG"; return "${PIPESTATUS[0]}"; }

# attempt NAME RETRY CMD...: run CMD; on failure run RETRY (a space-separated command, or "" for CMD again) every
# RETRY_WAIT s until it passes or MAX_MINUTES is up
attempt() {
  local name=$1 retry=$2; shift 2
  local again
  if [ -n "$retry" ]; then read -r -a again <<< "$retry"; else again=("$@"); fi
  echo "::group::$name"; echo ">> $name" >> "$LOG"
  local start=$SECONDS n=1
  py "$@"; local rc=$?
  while [ $rc -ne 0 ]; do
    if [ $SECONDS -ge $deadline ]; then
      echo "!! $name still failing after $n attempts; out of time" | tee -a "$LOG"
      echo "::endgroup::"; failed_step=$name
      echo "| $name | $n (failed) | $(( (SECONDS - start) / 60 )) |" >> ci_out/steps.md
      return 1
    fi
    echo "!! $name exited $rc (attempt $n); retrying in ${RETRY_WAIT:-300} s" | tee -a "$LOG"
    sleep "${RETRY_WAIT:-300}"; n=$((n + 1))
    py "${again[@]}"; rc=$?
  done
  echo "::endgroup::"
  echo "| $name | $n | $(( (SECONDS - start) / 60 )) |" >> ci_out/steps.md
}

echo "| step | attempts | minutes |" > ci_out/steps.md
echo "|---|---|---|" >> ci_out/steps.md

# A withdrawn or changed call stops results.py by default; here check_scorecard.py judges it instead, and every run goes
# to a PR for a person anyway.
export ALLOW_RESULT_CHANGES=1

attempt "results.py (called winners)" "" src/collect/results.py  && attempt "results_margins.py (vote counts)" "src/collect/results_margins.py resume" src/collect/results_margins.py  && attempt "official_senate.py" "" src/collect/official_senate.py  && attempt "official_house.py" "" src/collect/official_house.py  && attempt "scorecard.py" "" src/model/scorecard.py  && attempt "build.py" "" src/site/build.py

# Linux redraws the share image differently; keep the committed one
git checkout -- site/og.png 2>/dev/null || true

rate_limits=$(grep -c "rate-limited\|Too Many Requests" "$LOG" || true)
if [ -n "$failed_step" ]; then
  echo FAILED > ci_out/status
  echo "Collection stopped at **$failed_step** (see the run log)." > ci_out/check.txt
else
  uv run --locked python src/check_scorecard.py > ci_out/check.txt 2>&1
  case $? in 0) echo CLEAN ;; 2) echo REVIEW ;; *) echo HOLD ;; esac > ci_out/status
fi

{
  echo "**Result: $(cat ci_out/status)**  ·  Wikipedia rate-limit messages: $rate_limits  ·  total $(( SECONDS / 60 )) min"
  echo
  cat ci_out/steps.md
  echo
  grep -h "\[result change\]" "$LOG" | sed 's/^ */- /' | head -40
} > ci_out/summary.md
cat ci_out/summary.md >> "${GITHUB_STEP_SUMMARY:-/dev/null}"
exit 0
