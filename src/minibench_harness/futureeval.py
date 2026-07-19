from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _score_before(label: str, text: str) -> float | None:
    m = re.search(rf'([+-]?\d+(?:\.\d+)?)\s+{re.escape(label)}', text)
    return round(float(m.group(1)), 2) if m else None


def build_futureeval_receipt(text: str) -> dict[str, Any]:
    pro = _score_before('Metaculus Pro Forecasters', text)
    community = _score_before('Metaculus Community', text)
    best_model_score = _score_before('Gemini 3.1 Pro High', text)
    gap = round(pro - best_model_score, 2) if pro is not None and best_model_score is not None else None
    gap_fraction = round(gap / best_model_score, 4) if gap is not None and best_model_score else None
    lower = text.lower()
    return {
        'artifact': 'futureeval_public_scoreboard_receipt',
        'retrieved_at_utc': _now(),
        'source': 'https://www.metaculus.com/futureeval/',
        'leaderboard': {
            'metaculus_pro_forecasters': pro,
            'metaculus_community': community,
            'best_model': {'name': 'Gemini 3.1 Pro High', 'score': best_model_score},
            'summer_2026_live_prize_pool_usd': 58000 if '$58,000' in text and 'LIVE' in text else None,
            'pros_won_every_season_so_far': 'won every season so far' in lower,
        },
        'derived': {
            'pro_minus_best_model_gap': gap,
            'gap_as_fraction_of_best_model_score': gap_fraction,
            'interpretation': 'public coordinate system shows process gap, not saturated model-capability ceiling',
        },
        'scoring': {
            'venue_score_basis': 'unified_forecasting_score_based_on_log_scores'
            if 'unified forecasting score based on log scores' in lower else 'not_confirmed',
            'internal_records': ['brier', 'binary_log_loss_proxy'],
            'warning': 'optimize and settle in the venue currency; Brier remains diagnostic but not sufficient',
        },
        'published_failure_mode_checks': {
            'status_quo_bias': {
                'detected_on_page': 'status quo' in lower,
                'baseline_mapping': 'persistence_duck',
                'harness_check': 'report beat/loss against persistence duck every cycle',
            },
            'self_retrieval_failure': {
                'detected_on_page': 'failed to find their current rank' in lower,
                'harness_check': 'verify_self_referential_claims_against_fetched_evidence_before_submission',
            },
            'historical_seasonality_over_anchor': {
                'detected_on_page': 'historical seasonal' in lower or 'seasonal decline' in lower,
                'harness_check': 'force_current_evidence_vs_historical_pattern_contrast_block',
            },
        },
        'claim_language': {
            'cycle_one': 'calibration_data_not_track_record',
            'unit_of_claim': 'season_over_season_hash_committed_process_trajectory',
            'leaderboard_claim': 'placement_is_secondary_to_derivative_process_improvement',
        },
    }
