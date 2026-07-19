from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .core import seal_harness_config


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha(obj: Any) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def _write_json(path: Path, obj: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + '\n')


def build_live_harness_config(
    cycle_id: str,
    question_count: int,
    settlement_date: str,
    model: dict[str, Any],
    prompt: str,
    retrieval: dict[str, Any],
) -> dict[str, Any]:
    return {
        'artifact': 'minibench_live_harness_config',
        'cycle_id': cycle_id,
        'model': dict(model),
        'retrieval': dict(retrieval),
        'compressor': {
            'id': 'marvin-b2a-forecast-v0',
            'version': '0.1.0',
            'prompt_hash': hashlib.sha256(prompt.encode()).hexdigest(),
            'prompt_text': prompt,
        },
        'duck_definitions': {
            'base_rate': {
                'definition': 'constant_p_0_5_always',
                'reason': 'arbitrary binary questions have no trustworthy global live class rate before category priors are sealed',
            },
            'category_prior': {
                'status': 'declared_but_disabled_until_category_base_rates_exist',
                'definition': 'fixed prior by question category, enabled only after category mapping and prior table are sealed before forecasts',
            },
            'persistence': {
                'definition': 'previous forecast probability for the same question when available',
                'first_forecast_convention': 'inherits_base_rate_duck',
            },
        },
        'fixed_point': {
            'question_count': int(question_count),
            'settlement_date': settlement_date,
            'primary_look': 'one_full_cycle_all_resolved_questions',
            'interim_results': 'sensitivity_only_no_calibration_claim',
        },
        'competitor_clock': {
            'pin_timestamp_source': 'live_config_seal.sealed_at_utc',
            'evaluation_window_starts': 'strictly_after_config_seal_hash_lands_in_manifest',
            'quiet_upgrade_policy': 'any prompt/model/retrieval/duck change after live forecasts exist is a new competitor',
        },
        'token_policy': 'METACULUS_TOKEN from environment or private ignored file only; never commit',
    }


def build_self_mastery_prereg(
    cycle_id: str,
    predicted_mean_brier_range: list[float],
    predicted_percentile_band: list[int],
) -> dict[str, Any]:
    body = {
        'cycle_id': cycle_id,
        'status': 'sealed_before_first_live_forecast',
        'predicted_mean_brier_range': predicted_mean_brier_range,
        'predicted_percentile_band': predicted_percentile_band,
        'interpretation': 'self-mastery band for first real MiniBench cycle; not adjusted after seeing questions or outcomes',
        'demo_hygiene': 'n2_synthetic_smoke_test_not_track_record',
    }
    return {
        'artifact': 'self_mastery_preregistration',
        'sealed_at_utc': _now(),
        'body': body,
        'sha256': _sha(body),
    }


def _extract_question_count(text: str) -> int | None:
    m = re.search(r'(\d+)\s+Questions', text or '')
    return int(m.group(1)) if m else None


def build_live_rules_artifact(minibench_page_text: str, rules_page_text: str, template_text: str) -> dict[str, Any]:
    rules = []
    rules_text = rules_page_text.lower()
    if 'human in the loop' in rules_text:
        rules.append('no_human_in_loop')
    if 'comment' in rules_text and 'forecast' in rules_text:
        rules.append('comments_required')
    if 'one prize-eligible bot' in rules_text or 'one active metaculus bot user id' in rules_text:
        rules.append('one_prize_eligible_bot_per_user_or_team')
    if 'description of how their bot works' in rules_text or 'actual code' in rules_text:
        rules.append('code_or_description_disclosure_required')
    return {
        'artifact': 'metaculus_minibench_live_rules_receipt',
        'retrieved_at_utc': _now(),
        'sources': {
            'minibench': 'https://www.metaculus.com/aib/minibench/',
            'contest_rules': 'https://www.metaculus.com/aib/contest-rules/',
            'bot_template': 'https://github.com/Metaculus/metac-bot-template',
        },
        'confirmed': {
            'minibench_biweekly': 'bi-weekly' in (minibench_page_text or '').lower(),
            'active_minibench_question_count': _extract_question_count(minibench_page_text),
            'rules': sorted(set(rules)),
            'template_mentions_live_minibench': 'MiniBench' in template_text and 'METACULUS_TOKEN' in template_text,
        },
        'api_discovery': {
            'current_tournament_id': {
                'status': 'not_visible_in_public_page_extract',
                'next_step': 'discover via Metaculus API or authenticated tournament metadata before submission',
            },
            'participation_survey_requirement': {
                'status': 'not_confirmed_in_extracted_public_rules',
                'note': 'User flagged survey requirement; verify on live participate/rules page before prize-eligible operation.',
            },
            'metaculus_token': {
                'storage_policy': 'environment_or_private_ignored_file_only_never_commit',
                'provided_in_chat': True,
                'written_to_repo': False,
            },
        },
    }


def write_live_prep_artifacts(out_dir: str | Path, live_rules_inputs: dict[str, str], cycle_id: str) -> dict[str, Any]:
    out = Path(out_dir)
    active_count = _extract_question_count(live_rules_inputs.get('minibench_page_text', '')) or 60
    cfg = build_live_harness_config(
        cycle_id=cycle_id,
        question_count=active_count,
        settlement_date='first_full_cycle_close_after_live_submission',
        model={'provider': 'openrouter', 'name': 'to-be-set-before-live-submit'},
        prompt='Forecast MiniBench questions using cutoff-stamped evidence blocks; output probability and reasoning comment; no human-in-loop modification after question retrieval.',
        retrieval={'search_provider': 'hermes_web_search', 'max_sources': 5, 'cutoff_policy': 'retrieved_before_submission'},
    )
    seal = seal_harness_config(cfg)
    self_mastery = build_self_mastery_prereg(cycle_id, [0.18, 0.24], [40, 65])
    rules = build_live_rules_artifact(**live_rules_inputs)
    _write_json(out / 'live_config_seal.json', seal)
    _write_json(out / 'self_mastery_prereg.json', self_mastery)
    _write_json(out / 'live_rules_receipt.json', rules)
    manifest = {
        'artifact': 'minibench_live_manifest',
        'status': 'sealed_before_first_live_forecast',
        'created_at_utc': _now(),
        'artifacts': {},
        'first_live_forecast_allowed_after': 'live_config_seal hash is recorded here and current tournament ID is discovered',
    }
    for name, filename in [
        ('live_config_seal', 'live_config_seal.json'),
        ('self_mastery_prereg', 'self_mastery_prereg.json'),
        ('live_rules_receipt', 'live_rules_receipt.json'),
    ]:
        path = out / filename
        manifest['artifacts'][name] = {'path': filename, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
    _write_json(out / 'manifest.json', manifest)
    return {'status': manifest['status'], 'manifest': manifest}
