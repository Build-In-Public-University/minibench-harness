import hashlib
import json

from minibench_harness import (
    build_settlement_calendar,
    mint_forecast_artifact,
    seal_harness_config,
    settle_forecast,
)


def test_seal_harness_config_is_content_addressed_and_contains_stopping_law():
    config = {
        'cycle_id': 'minibench-2026w30',
        'question_source': 'MiniBench external notary',
        'fixed_point': {'question_count': 60, 'settlement_date': '2026-08-01'},
        'compressor': {'id': 'marvin-b2a-forecast-v0', 'version': '0.1.0'},
    }
    seal = seal_harness_config(config)
    expected_hash = hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()
    assert seal['artifact'] == 'minibench_harness_config_seal'
    assert seal['sha256'] == expected_hash
    assert seal['stopping_law']['optional_stopping_forbidden'] is True
    assert seal['stopping_law']['primary_evaluation'] == 'fixed_point_only'
    assert seal['stopping_law']['interim_results'] == 'sensitivity_only_no_promotion'


def test_mint_forecast_artifact_contains_required_b2a_fields_and_null_ducks():
    config = {'cycle_id': 'minibench-2026w30', 'fixed_point': {'question_count': 60}}
    seal = seal_harness_config(config)
    question = {
        'url': 'https://example.test/q/1',
        'text': 'Will the notary resolve this true?',
        'cutoff': '2026-07-20T00:00:00Z',
        'retrieved_evidence': [{'url': 'https://evidence.test/a', 'retrieved_at': '2026-07-18T00:00:00Z'}],
    }
    compressor = {'id': 'marvin-b2a-forecast-v0', 'version': '0.1.0', 'prompt': 'forecast strictly'}
    forecast = mint_forecast_artifact(question, seal, compressor, prediction=0.62, submitted_at='2026-07-18T12:00:00Z')
    assert forecast['artifact'] == 'minibench_forecast'
    assert len(forecast['question_hash']) == 64
    assert forecast['question_url'] == question['url']
    assert forecast['blocks'][0]['role'] == 'evidence_retrieved'
    assert forecast['blocks'][0]['cutoff'] == question['cutoff']
    assert forecast['compressor']['prompt_hash'] == hashlib.sha256(compressor['prompt'].encode()).hexdigest()
    assert forecast['input_blocks'] == [{'role': 'sealed_harness_config', 'sha256': seal['sha256']}]
    assert forecast['prediction'] == 0.62
    assert forecast['submitted_at'] == '2026-07-18T12:00:00Z'
    assert set(forecast['null_ducks']) == {'base_rate', 'persistence'}
    assert forecast['settlement'] is None


def test_settle_forecast_preserves_outcome_and_scores_bilingually_against_null_ducks():
    seal = seal_harness_config({'cycle_id': 'x'})
    forecast = mint_forecast_artifact(
        {'url': 'https://example.test/q/2', 'text': 'Will X happen?', 'cutoff': '2026-07-20T00:00:00Z', 'retrieved_evidence': []},
        seal,
        {'id': 'c', 'version': '0', 'prompt': 'p'},
        prediction=0.70,
        submitted_at='2026-07-18T12:00:00Z',
    )
    settled = settle_forecast(forecast, {'resolved_at': '2026-08-01T00:00:00Z', 'outcome': 1, 'notary_url': 'https://notary.test/q/2'})
    assert settled['settlement']['resolved'] is True
    assert settled['settlement']['outcome'] == 1
    assert settled['settlement']['brier'] == 0.09
    assert settled['settlement']['binary_log_loss_proxy'] == 0.3567
    assert 'Venue score is peer-relative; internal proxies are absolute' in settled['settlement']['scoring_note']
    assert settled['settlement']['vs_ducks']['base_rate']['brier']['beat'] is True
    assert settled['settlement']['vs_ducks']['base_rate']['binary_log_loss_proxy']['beat'] is True
    assert settled['settlement']['vs_ducks']['persistence']['brier']['beat'] is True
    assert settled['settlement']['notary_url'] == 'https://notary.test/q/2'


def test_settlement_calendar_lists_four_clocks_and_forbidden_actions():
    calendar = build_settlement_calendar([
        {'stream': 'minibench_forecasting_resolutions', 'next_settlement': '2026-08-01', 'resolves': 'cycle brier vs ducks'},
        {'stream': 'atlas_future_windows', 'next_settlement': 'after 251 future windows and 74 positives', 'resolves': 'arena v2 fixed point'},
        {'stream': 'twitter_funnel_t30_settlement', 'next_settlement': 'T+30 from first sealed post', 'resolves': 'funnel stage rates'},
        {'stream': 'raw_text_corpus_work', 'next_settlement': 'rolling receipts', 'resolves': 'substrate coverage, not model promotion'},
    ])
    assert calendar['artifact'] == 'settlement_calendar'
    assert len(calendar['streams']) == 4
    assert calendar['forbidden_until_settlement']['minibench_forecasting_resolutions'] == 'no calibration claim from interim drips'
    assert calendar['forbidden_until_settlement']['atlas_future_windows'] == 'no arena v2 promotion before fixed point'
    assert calendar['forbidden_until_settlement']['raw_text_corpus_work'] == 'no promotion-grade census claim without raw text evidence blocks'
