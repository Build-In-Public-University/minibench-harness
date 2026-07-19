from minibench_harness.futureeval import build_futureeval_receipt


def test_futureeval_receipt_records_leaderboard_gap_and_process_claim():
    text = '''
    Uses our unified forecasting score based on log scores. Updates daily.
    35.90 Metaculus Pro Forecasters
    25.96 Metaculus Community
    19.84 Gemini 3.1 Pro High
    Bot tournaments Summer 2026 $58,000 LIVE
    Pros vs. Bots Metaculus Pro Forecasters won every season so far.
    '''
    receipt = build_futureeval_receipt(text)
    assert receipt['artifact'] == 'futureeval_public_scoreboard_receipt'
    assert receipt['leaderboard']['metaculus_pro_forecasters'] == 35.90
    assert receipt['leaderboard']['metaculus_community'] == 25.96
    assert receipt['leaderboard']['best_model'] == {'name': 'Gemini 3.1 Pro High', 'score': 19.84}
    assert receipt['derived']['pro_minus_best_model_gap'] == 16.06
    assert receipt['derived']['gap_as_fraction_of_best_model_score'] == 0.8095
    assert receipt['scoring']['venue_score_basis'] == 'unified_forecasting_score_based_on_log_scores'
    assert receipt['claim_language']['cycle_one'] == 'calibration_data_not_track_record'
    assert receipt['claim_language']['unit_of_claim'] == 'season_over_season_hash_committed_process_trajectory'


def test_futureeval_receipt_turns_published_bot_failures_into_harness_checks():
    text = '''
    Bots weighted the status quo outcome more heavily.
    Bots failed to find their current rank and were optimistic about AI progress.
    Bots correctly anticipated that the dramatic July spike might continue rather than following the historical seasonal decline pattern.
    '''
    receipt = build_futureeval_receipt(text)
    checks = receipt['published_failure_mode_checks']
    assert checks['status_quo_bias']['baseline_mapping'] == 'persistence_duck'
    assert checks['self_retrieval_failure']['harness_check'] == 'verify_self_referential_claims_against_fetched_evidence_before_submission'
    assert checks['historical_seasonality_over_anchor']['harness_check'] == 'force_current_evidence_vs_historical_pattern_contrast_block'
