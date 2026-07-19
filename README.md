# MiniBench Harness

B2A forecasting harness for MiniBench-style external-notary questions.

This is the first future-evidence pipe after the Atlas arena constitution. It does not claim calibration yet. It writes the artifacts that will let calibration happen later without optional stopping.

## What it emits

A cycle writes:

```text
config_seal.json
forecasts.jsonl
settlements.jsonl
settlement_calendar.json
cycle_summary.json
```

Forecast artifact shape:

```text
question_hash
question_url
blocks: cutoff-stamped evidence retrieved
compressor: id, version, prompt_hash
input_blocks: sealed_harness_config hash
prediction
submitted_at
null_ducks: base_rate, persistence
settlement: null until resolved
```

Settlement preserves outcomes uncompressed and scores against ducks:

```text
settlement.outcome
settlement.brier
settlement.vs_ducks.base_rate
settlement.vs_ducks.persistence
```

## Stopping law

The harness config seal includes:

```text
optional_stopping_forbidden: true
primary_evaluation: fixed_point_only
interim_results: sensitivity_only_no_promotion
```

Do not claim calibration from interim drips. MiniBench gets the same law as Atlas future windows.

## Demo run

From this repo:

```bash
python3 -m pytest tests -q
PYTHONPATH=src python3 -m minibench_harness.cli demo-cycle --out artifacts/demo-cycle
```

Or after editable install:

```bash
python3 -m pip install -e .
/Library/Frameworks/Python.framework/Versions/3.11/bin/minibench-harness demo-cycle --out artifacts/demo-cycle
```

Note: on this machine the console script installs outside PATH, so the absolute path above is the verified command.

## Current verification

```text
pytest: 5 passed
CLI demo emitted: config_seal.json, forecasts.jsonl, settlements.jsonl, settlement_calendar.json, cycle_summary.json
```

## Next real integration

Replace the demo questions with the actual MiniBench question source and external notary submission/resolution adapters. Keep the artifact contract stable while swapping transport.

## Live prep receipt — sealed before first live forecast

Artifacts:

```text
artifacts/live-prep/live_config_seal.json
artifacts/live-prep/self_mastery_prereg.json
artifacts/live-prep/live_rules_receipt.json
artifacts/live-prep/manifest.json
artifacts/live-prep/source_extracts.json
```

Status:

```text
sealed_before_first_live_forecast
```

Live page extract:

```text
active_minibench_question_count: 59
```

Fixed point:

```text
primary_look: one_full_cycle_all_resolved_questions
question_count: 59
interim_results: sensitivity_only_no_calibration_claim
```

Duck definitions:

```text
base_rate: constant_p_0_5_always
category_prior: declared but disabled until category base rates exist
persistence: previous forecast probability when available; first forecast inherits base-rate duck
```

Self-mastery prereg:

```text
predicted_mean_brier_range: [0.18, 0.24]
predicted_percentile_band: [40, 65]
status: sealed_before_first_live_forecast
```

Confirmed public rules from extracted pages:

```text
no_human_in_loop
comments_required
one_prize_eligible_bot_per_user_or_team
code_or_description_disclosure_required
```

Discovery gaps before live operation:

```text
current_tournament_id: not_visible_in_public_page_extract
participation_survey_requirement: not_confirmed_in_extracted_public_rules
public API discovery attempt: 403 on unauthenticated endpoints
```

Token policy:

```text
METACULUS_TOKEN from environment or private ignored file only; never commit
```

Demo hygiene:

```text
The n=2 synthetic demo cycle is a plumbing smoke test, not a track record.
Mean Brier 0.125 and ducks beaten 2-of-2 are not evidence of forecasting skill.
```

## FutureEval receipt — public scoreboard and failure map

Source:

```text
https://www.metaculus.com/futureeval/
```

Artifact:

```text
artifacts/live-prep/futureeval_receipt.json
artifacts/live-prep/futureeval_source_extract.json
```

Current public coordinate system from extracted page:

```text
Metaculus Pro Forecasters: 35.90
Metaculus Community: 25.96
Best model: Gemini 3.1 Pro High, 19.84
Pro minus best-model gap: 16.06
Gap as fraction of best-model score: 0.8095
Summer 2026 bot tournament: LIVE, $58,000
Pros won every season so far: true
```

Scoring warning:

```text
Venue score basis: unified forecasting score based on log scores.
Internal settlement records therefore keep both Brier and binary_log_loss_proxy.
Brier is diagnostic; log-score currency is what the venue rewards/punishes.
```

Published failure-mode checks added to the harness frame:

```text
status_quo_bias -> persistence_duck
self_retrieval_failure -> verify self-referential claims against fetched evidence before submission
historical_seasonality_over_anchor -> force current-evidence vs historical-pattern contrast block
```

Claim language:

```text
cycle_one: calibration_data_not_track_record
unit_of_claim: season_over_season_hash_committed_process_trajectory
leaderboard_claim: placement_is_secondary_to_derivative_process_improvement
```

Interpretation:

```text
The board is not saturated. Frontier models cluster below Pros; the gap is process-shaped.
The first entry benchmarks the loop, not the launch.
```

## Metaculus read-only discovery receipt

Artifact:

```text
artifacts/metaculus-discovery/discovery_summary.json
artifacts/metaculus-discovery/manifest.json
```

Status:

```text
partial_complete_no_submission
```

Resolved:

```text
API auth works
bot-testing-area slug: bot-testing-area
bot-testing-area open posts: 7
current MiniBench public URL: https://www.metaculus.com/tournament/minibench/
/aib/minibench/ page hash recorded
```

Unresolved:

```text
current_minibench_numeric_project_id: not_resolved_from_api_yet
api_filter_for_current_minibench_posts: not_resolved; tournaments=minibench returned zero, project param was broad
participation_survey_state: not_confirmed_by_api
current_cycle_enterability: not_confirmed_by_api
```

Important:

```text
No forecast submission endpoint was called.
No token was written to artifacts.
```

## Metaculus fresh-token and cycle-slug probe

Artifact:

```text
artifacts/metaculus-discovery/fresh_token_cycle_probe.json
```

Status:

```text
complete_no_submission
```

Fresh token health:

```text
bot-testing-area authenticated GET: 200
result_count: 1
body_sha256: e0b04321d1b4af49c66c2546a59aae01d07ab60f6c3c5adf84eb8c9cb508ffde
```

Cycle-slug hypothesis:

```text
?tournaments=minibench-2026-06-29: 0 useful posts
?tournaments=minibench-2026-06-15: 0 useful posts
?tournaments=minibench-2026-07-13: 0 useful posts
?projects=<cycle slug>: broad/generic results, not MiniBench-specific
```

Conclusion:

```text
fresh token works for read-only API
cycle-slug API filter did not close the MiniBench discovery gap
bot-template internals resolved the transport seam and payload shapes
no forecast submission endpoint was called
```

## Metaculus transport adapter — dry-run only by default

Source facts from `Metaculus/metac-bot-template` no-framework reference:

```text
GET  /api/posts/?tournaments=<id>&statuses=open&limit=<n>
POST /api/questions/forecast/
POST /api/comments/create/
BOT_TESTING_AREA_ID = bot-testing-area
CURRENT_MINIBENCH_ID = minibench
```

Implemented adapter:

```text
src/minibench_harness/metaculus_transport.py
```

Verified dry-run artifact:

```text
artifacts/metaculus-discovery/bot_testing_area_dry_run_packet.json
```

Current status:

```text
bot-testing-area authenticated read-only list: works
read_only_question_count: 4
forecast payload shape: constructed
comment payload shape: constructed
submit path guard: requires explicit allow_submit=True
bot-testing-area POST smoke: completed
MiniBench/live submission: not attempted
```

POST smoke receipt:

```text
artifacts/metaculus-discovery/bot_testing_area_post_smoke_receipt.json
```

POST smoke result:

```text
target: bot-testing-area
post_id: 43327
question_id: 43332
probability_yes: 0.50
forecast endpoint status: 201
comment endpoint status: 201
readback status: 200
```

Important:

```text
The adapter is dry-run/no-submit by default.
A real bot-testing-area smoke forecast/comment was submitted after explicit approval.
No real MiniBench forecast has been submitted.
The urllib transport needs an explicit User-Agent; default urllib was rejected with HTTP 403.
```

