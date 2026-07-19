from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .core import build_settlement_calendar, mint_forecast_artifact, seal_harness_config, settle_forecast


def _write_json(path: Path, obj: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + '\n')


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(''.join(json.dumps(row, sort_keys=True) + '\n' for row in rows))


def _summary(settled: list[dict[str, Any]]) -> dict[str, Any]:
    if not settled:
        return {'forecast_count': 0, 'settled_count': 0, 'mean_brier': None, 'mean_binary_log_loss_proxy': None, 'beat_ducks': {}}
    mean_brier = round(sum(row['settlement']['brier'] for row in settled) / len(settled), 4)
    mean_log_loss = round(sum(row['settlement']['binary_log_loss_proxy'] for row in settled) / len(settled), 4)
    duck_names = sorted(settled[0]['settlement']['vs_ducks'])
    beat_ducks = {
        metric: {
            name: sum(1 for row in settled if row['settlement']['vs_ducks'][name][metric]['beat'])
            for name in duck_names
        }
        for metric in ['brier', 'binary_log_loss_proxy']
    }
    return {
        'forecast_count': len(settled),
        'settled_count': len(settled),
        'mean_brier': mean_brier,
        'mean_binary_log_loss_proxy': mean_log_loss,
        'beat_ducks': beat_ducks,
    }


def write_demo_cycle(out_dir: str | Path) -> dict[str, Any]:
    out = Path(out_dir)
    config = {
        'cycle_id': 'minibench-demo-cycle',
        'question_source': 'MiniBench external notary placeholder',
        'fixed_point': {'question_count': 2, 'settlement_date': 'demo'},
        'compressor': {'id': 'marvin-b2a-forecast-v0', 'version': '0.1.0'},
    }
    seal = seal_harness_config(config)
    questions = [
        {
            'url': 'https://example.test/minibench/q1',
            'text': 'Will demo question 1 resolve true?',
            'cutoff': '2026-07-18T00:00:00Z',
            'retrieved_evidence': [{'url': 'https://evidence.test/q1', 'retrieved_at': '2026-07-18T00:00:00Z'}],
            'prediction': 0.70,
            'outcome': 1,
        },
        {
            'url': 'https://example.test/minibench/q2',
            'text': 'Will demo question 2 resolve true?',
            'cutoff': '2026-07-18T00:00:00Z',
            'retrieved_evidence': [{'url': 'https://evidence.test/q2', 'retrieved_at': '2026-07-18T00:00:00Z'}],
            'prediction': 0.40,
            'outcome': 0,
        },
    ]
    compressor = {'id': 'marvin-b2a-forecast-v0', 'version': '0.1.0', 'prompt': 'Forecast with cutoff-stamped evidence and no optional stopping.'}
    forecasts = [
        mint_forecast_artifact(q, seal, compressor, q['prediction'], submitted_at='2026-07-18T12:00:00Z')
        for q in questions
    ]
    settled = [
        settle_forecast(forecast, {'resolved_at': 'demo', 'outcome': q['outcome'], 'notary_url': q['url']})
        for forecast, q in zip(forecasts, questions)
    ]
    calendar = build_settlement_calendar([
        {'stream': 'minibench_forecasting_resolutions', 'next_settlement': 'next two-week cycle close', 'resolves': 'cycle brier vs ducks'},
        {'stream': 'atlas_future_windows', 'next_settlement': 'after 251 future windows and 74 positives', 'resolves': 'arena v2 fixed point'},
        {'stream': 'twitter_funnel_t30_settlement', 'next_settlement': 'T+30 from first sealed post', 'resolves': 'funnel stage rates'},
        {'stream': 'raw_text_corpus_work', 'next_settlement': 'rolling receipts', 'resolves': 'substrate coverage, not model promotion'},
    ])
    summary = _summary(settled)
    _write_json(out / 'config_seal.json', seal)
    _write_jsonl(out / 'forecasts.jsonl', forecasts)
    _write_jsonl(out / 'settlements.jsonl', settled)
    _write_json(out / 'settlement_calendar.json', calendar)
    _write_json(out / 'cycle_summary.json', summary)
    return summary
