import hashlib
import json
import re
from pathlib import Path

from minibench_harness import seal_harness_config
from minibench_harness.live import (
    build_live_harness_config,
    build_live_rules_artifact,
    build_self_mastery_prereg,
    write_live_prep_artifacts,
)


def test_live_harness_config_seal_pins_prompt_model_retrieval_ducks_and_fixed_point():
    cfg = build_live_harness_config(
        cycle_id='minibench-live-2026w30',
        question_count=60,
        settlement_date='2026-08-01',
        model={'provider': 'openrouter', 'name': 'test-model'},
        prompt='forecast with evidence blocks',
        retrieval={'max_sources': 5, 'search_provider': 'web_search'},
    )
    seal = seal_harness_config(cfg)
    assert cfg['duck_definitions']['base_rate']['definition'] == 'constant_p_0_5_always'
    assert cfg['duck_definitions']['category_prior']['status'] == 'declared_but_disabled_until_category_base_rates_exist'
    assert cfg['duck_definitions']['persistence']['first_forecast_convention'] == 'inherits_base_rate_duck'
    assert cfg['fixed_point']['primary_look'] == 'one_full_cycle_all_resolved_questions'
    assert cfg['fixed_point']['interim_results'] == 'sensitivity_only_no_calibration_claim'
    assert len(cfg['compressor']['prompt_hash']) == 64
    assert seal['config']['model']['name'] == 'test-model'
    assert seal['stopping_law']['primary_evaluation'] == 'fixed_point_only'


def test_self_mastery_prereg_is_hashable_and_pre_contact():
    prereg = build_self_mastery_prereg(
        cycle_id='minibench-live-2026w30',
        predicted_mean_brier_range=[0.18, 0.24],
        predicted_percentile_band=[40, 65],
    )
    expected_hash = hashlib.sha256(json.dumps(prereg['body'], sort_keys=True).encode()).hexdigest()
    assert prereg['artifact'] == 'self_mastery_preregistration'
    assert prereg['sha256'] == expected_hash
    assert prereg['body']['status'] == 'sealed_before_first_live_forecast'
    assert prereg['body']['demo_hygiene'] == 'n2_synthetic_smoke_test_not_track_record'


def test_live_rules_artifact_keeps_confirmed_rules_separate_from_api_discovery_gaps():
    rules = build_live_rules_artifact(
        minibench_page_text='MiniBench is bi-weekly and has 59 Questions Active MiniBench',
        rules_page_text='Bots may not have a human in the loop. Bots must post a comment explaining reasoning alongside each forecast. One prize-eligible bot per user.',
        template_text='METACULUS_TOKEN run_bot_on_tournament.yaml live AIB tournament + MiniBench',
    )
    assert rules['artifact'] == 'metaculus_minibench_live_rules_receipt'
    assert rules['confirmed']['active_minibench_question_count'] == 59
    assert 'no_human_in_loop' in rules['confirmed']['rules']
    assert 'comments_required' in rules['confirmed']['rules']
    assert rules['api_discovery']['current_tournament_id']['status'] == 'not_visible_in_public_page_extract'
    assert rules['api_discovery']['metaculus_token']['storage_policy'] == 'environment_or_private_ignored_file_only_never_commit'


def test_write_live_prep_artifacts_writes_manifest_and_never_writes_token(tmp_path):
    result = write_live_prep_artifacts(
        tmp_path,
        live_rules_inputs={
            'minibench_page_text': 'Active MiniBench 59 Questions',
            'rules_page_text': 'No human in the loop. Bots must post a comment explaining reasoning alongside each forecast. One prize-eligible bot per user.',
            'template_text': 'METACULUS_TOKEN live AIB tournament + MiniBench',
        },
        cycle_id='minibench-live-2026w30',
    )
    assert (tmp_path/'live_config_seal.json').exists()
    assert (tmp_path/'self_mastery_prereg.json').exists()
    assert (tmp_path/'live_rules_receipt.json').exists()
    assert (tmp_path/'manifest.json').exists()
    manifest = json.loads((tmp_path/'manifest.json').read_text())
    seal = json.loads((tmp_path/'live_config_seal.json').read_text())
    assert seal['config']['fixed_point']['question_count'] == 59
    assert 'live_config_seal' in manifest['artifacts']
    assert 'self_mastery_prereg' in manifest['artifacts']
    all_text = ''.join(p.read_text() for p in tmp_path.glob('*.json'))
    assert 'REAL_TOKEN_PREFIX_SHOULD_NOT_APPEAR' not in all_text
    assert not re.search(r'(?i)(metaculus[_-]?token|token)[^\n]{0,80}[a-f0-9]{40}', all_text)
    assert result['status'] == 'sealed_before_first_live_forecast'
