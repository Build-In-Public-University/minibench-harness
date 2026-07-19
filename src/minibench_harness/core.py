from __future__ import annotations

import copy
import hashlib
import json
import math
from datetime import datetime, timezone
from typing import Any


def _sha(obj: Any) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _round4(x: float) -> float:
    return round(float(x), 4)


def seal_harness_config(config: dict[str, Any]) -> dict[str, Any]:
    config_copy = copy.deepcopy(config)
    return {
        'artifact': 'minibench_harness_config_seal',
        'status': 'sealed_waiting_for_external_notary_cycle',
        'sha256': _sha(config_copy),
        'sealed_at_utc': _now(),
        'config': config_copy,
        'stopping_law': {
            'optional_stopping_forbidden': True,
            'primary_evaluation': 'fixed_point_only',
            'interim_results': 'sensitivity_only_no_promotion',
        },
    }


def mint_forecast_artifact(
    question: dict[str, Any],
    config_seal: dict[str, Any],
    compressor: dict[str, Any],
    prediction: float,
    submitted_at: str,
) -> dict[str, Any]:
    if not 0 <= prediction <= 1:
        raise ValueError('prediction must be in [0, 1]')
    prompt = compressor.get('prompt', '')
    question_hash = _sha({'url': question.get('url'), 'text': question.get('text'), 'cutoff': question.get('cutoff')})
    blocks = [
        {
            'role': 'evidence_retrieved',
            'cutoff': question.get('cutoff'),
            'items': copy.deepcopy(question.get('retrieved_evidence', [])),
        }
    ]
    return {
        'artifact': 'minibench_forecast',
        'status': 'submitted_unsettled',
        'question_hash': question_hash,
        'question_url': question.get('url'),
        'blocks': blocks,
        'compressor': {
            'id': compressor.get('id'),
            'version': compressor.get('version'),
            'prompt_hash': hashlib.sha256(prompt.encode()).hexdigest(),
        },
        'input_blocks': [{'role': 'sealed_harness_config', 'sha256': config_seal['sha256']}],
        'prediction': float(prediction),
        'submitted_at': submitted_at,
        'null_ducks': {
            'base_rate': 0.5,
            'persistence': 0.5,
        },
        'settlement': None,
    }


def _brier(p: float, y: int) -> float:
    return _round4((p - y) ** 2)


def _binary_log_loss_proxy(p: float, y: int) -> float:
    p = min(max(float(p), 1e-6), 1 - 1e-6)
    return _round4(-(y * math.log(p) + (1 - y) * math.log(1 - p)))


def settle_forecast(forecast: dict[str, Any], outcome: dict[str, Any]) -> dict[str, Any]:
    y = int(outcome['outcome'])
    settled = copy.deepcopy(forecast)
    p = float(settled['prediction'])
    brier = _brier(p, y)
    log_loss = _binary_log_loss_proxy(p, y)
    vs_ducks = {}
    for name, duck_p in settled.get('null_ducks', {}).items():
        duck_brier = _brier(float(duck_p), y)
        duck_log_loss = _binary_log_loss_proxy(float(duck_p), y)
        vs_ducks[name] = {
            'brier': {'score': duck_brier, 'beat': brier < duck_brier},
            'binary_log_loss_proxy': {'score': duck_log_loss, 'beat': log_loss < duck_log_loss},
        }
    settled['status'] = 'settled'
    settled['settlement'] = {
        'resolved': True,
        'resolved_at': outcome.get('resolved_at'),
        'outcome': y,
        'notary_url': outcome.get('notary_url'),
        'brier': brier,
        'binary_log_loss_proxy': log_loss,
        'scoring_note': 'venue uses unified forecasting score based on log scores; store Brier plus binary log-loss proxy. Venue score is peer-relative; internal proxies are absolute and correlate with leaderboard movement but do not equate to it.',
        'vs_ducks': vs_ducks,
    }
    return settled


def build_settlement_calendar(streams: list[dict[str, Any]]) -> dict[str, Any]:
    forbidden_defaults = {
        'minibench_forecasting_resolutions': 'no calibration claim from interim drips',
        'atlas_future_windows': 'no arena v2 promotion before fixed point',
        'twitter_funnel_t30_settlement': 'no funnel claim before T+30/T+60 settlement',
        'raw_text_corpus_work': 'no promotion-grade census claim without raw text evidence blocks',
    }
    return {
        'artifact': 'settlement_calendar',
        'status': 'active',
        'streams': copy.deepcopy(streams),
        'forbidden_until_settlement': {
            stream['stream']: forbidden_defaults.get(stream['stream'], 'no primary claim before settlement')
            for stream in streams
        },
    }
