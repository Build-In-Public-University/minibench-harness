from __future__ import annotations

import hashlib
import json
import urllib.parse
import urllib.request
from typing import Any, Callable

API_BASE_URL = 'https://www.metaculus.com/api'
BOT_TESTING_AREA_ID = 'bot-testing-area'
CURRENT_MINIBENCH_ID = 'minibench'
FORECAST_ENDPOINT = '/questions/forecast/'
COMMENT_ENDPOINT = '/comments/create/'
POSTS_ENDPOINT = '/posts/'

RequestFn = Callable[..., Any]


def _sha_json(obj: Any) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def hash_transport_response(obj: Any) -> str:
    return _sha_json(obj)


def build_posts_query_params(tournament_id: int | str, *, offset: int = 0, count: int = 50) -> dict[str, Any]:
    return {
        'limit': count,
        'offset': offset,
        'order_by': '-hotness',
        'forecast_type': 'binary,multiple_choice,numeric,discrete,date',
        'tournaments': [tournament_id],
        'statuses': 'open',
        'include_description': 'true',
    }


def _validate_probability(value: float) -> float:
    probability = float(value)
    if not 0 < probability < 1:
        raise ValueError('probability must be strictly between 0 and 1')
    return probability


def _validate_multiple_choice(probability: Any, options: list[str] | None) -> dict[str, float]:
    if not options:
        raise ValueError('multiple_choice options are required')
    if not isinstance(probability, dict):
        raise ValueError('multiple_choice probability must be a dict keyed by option')
    if set(probability) != set(options):
        raise ValueError('multiple_choice probability keys must match options exactly')
    normalized = {option: float(probability[option]) for option in options}
    if any(value <= 0 or value >= 1 for value in normalized.values()):
        raise ValueError('multiple_choice probabilities must be strictly between 0 and 1')
    if abs(sum(normalized.values()) - 1.0) > 1e-9:
        raise ValueError('multiple_choice probabilities must sum to 1')
    return normalized


def _validate_continuous_cdf(
    probability: Any,
    continuous_range: list[Any] | None,
    *,
    open_lower_bound: bool | None = None,
    open_upper_bound: bool | None = None,
) -> list[float]:
    if not isinstance(probability, list):
        raise ValueError('continuous_cdf probability must be a list')
    if not continuous_range:
        raise ValueError('continuous_range is required for continuous_cdf payloads')
    if len(probability) != len(continuous_range):
        raise ValueError('continuous_cdf length must match continuous_range length')
    cdf = [float(value) for value in probability]
    if any(value < 0 or value > 1 for value in cdf):
        raise ValueError('continuous_cdf values must be between 0 and 1')
    if any(left > right for left, right in zip(cdf, cdf[1:])):
        raise ValueError('continuous_cdf values must be monotone nondecreasing')
    if any((right - left) < 5e-05 for left, right in zip(cdf, cdf[1:])):
        raise ValueError('continuous_cdf values must increase by at least 5e-05 at every step')
    if open_lower_bound is False and cdf[0] != 0.0:
        raise ValueError('continuous_cdf[0] must be 0.0 for closed lower bound')
    if open_lower_bound is True and cdf[0] < 0.001:
        raise ValueError('continuous_cdf[0] must be at least 0.001 for open lower bound')
    if open_lower_bound is None and cdf[0] <= 0.0:
        raise ValueError('continuous_cdf[0] must be greater than 0.0 unless lower bound is known closed')
    if open_upper_bound is False and cdf[-1] != 1.0:
        raise ValueError('continuous_cdf[-1] must be 1.0 for closed upper bound')
    if open_upper_bound is not False and cdf[-1] >= 1.0:
        raise ValueError('continuous_cdf[-1] must be less than 1.0 unless upper bound is known closed')
    return cdf


def build_forecast_payload(
    question_id: int,
    probability: float | dict[str, float] | list[float],
    question_type: str = 'binary',
    *,
    options: list[str] | None = None,
    continuous_range: list[Any] | None = None,
    open_lower_bound: bool | None = None,
    open_upper_bound: bool | None = None,
) -> list[dict[str, Any]]:
    if question_type == 'binary':
        probability_yes = _validate_probability(float(probability))
        return [
            {
                'question': int(question_id),
                'source': 'api',
                'probability_yes': probability_yes,
                'probability_yes_per_category': None,
                'continuous_cdf': None,
            }
        ]
    if question_type == 'multiple_choice':
        return [
            {
                'question': int(question_id),
                'source': 'api',
                'probability_yes': None,
                'probability_yes_per_category': _validate_multiple_choice(probability, options),
                'continuous_cdf': None,
            }
        ]
    if question_type in {'numeric', 'date', 'discrete'}:
        return [
            {
                'question': int(question_id),
                'source': 'api',
                'probability_yes': None,
                'probability_yes_per_category': None,
                'continuous_cdf': _validate_continuous_cdf(
                    probability,
                    continuous_range,
                    open_lower_bound=open_lower_bound,
                    open_upper_bound=open_upper_bound,
                ),
            }
        ]
    raise NotImplementedError(f'{question_type} payloads are not supported in the harness adapter so far')


def build_comment_payload(post_id: int, comment_text: str) -> dict[str, Any]:
    return {
        'text': comment_text,
        'parent': None,
        'included_forecast': True,
        'is_private': True,
        'on_post': int(post_id),
    }


def normalize_post_question(post: dict[str, Any]) -> dict[str, Any] | None:
    question = post.get('question')
    if not isinstance(question, dict):
        return None
    scaling = question.get('scaling') if isinstance(question.get('scaling'), dict) else None
    return {
        'post_id': post.get('id'),
        'question_id': question.get('id'),
        'title': question.get('title') or post.get('title'),
        'type': question.get('type') or question.get('forecast_type'),
        'status': question.get('status'),
        'scheduled_close_time': question.get('scheduled_close_time'),
        'url': post.get('url') or post.get('page_url'),
        'resolution_criteria': question.get('resolution_criteria'),
        'description': question.get('description') or question.get('background_info'),
        'options': question.get('options'),
        'unit': question.get('unit'),
        'scaling': scaling,
        'continuous_range': scaling.get('continuous_range') if scaling else None,
        'open_lower_bound': question.get('open_lower_bound'),
        'open_upper_bound': question.get('open_upper_bound'),
    }


class MetaculusTransport:
    def __init__(
        self,
        token: str,
        *,
        api_base_url: str = API_BASE_URL,
        request_fn: RequestFn | None = None,
        allow_submit: bool = False,
    ) -> None:
        if not token or not token.strip():
            raise ValueError('token is required for authenticated Metaculus transport')
        self._token = token.strip()
        self.api_base_url = api_base_url.rstrip('/')
        self._request_fn = request_fn or self._urllib_request
        self.allow_submit = allow_submit

    def _urllib_request(self, method: str, path: str, *, params: dict[str, Any] | None = None, json_payload: Any = None) -> Any:
        url = self.api_base_url + path
        if params:
            query = urllib.parse.urlencode(params, doseq=True)
            url = f'{url}?{query}'
        body = None
        headers = {
            'Authorization': f'Token {self._token}',
            'Accept': 'application/json',
            'User-Agent': 'minibench-harness/0.1 (+https://github.com/Build-In-Public-University/minibench-harness)',
        }
        if json_payload is not None:
            body = json.dumps(json_payload).encode()
            headers['Content-Type'] = 'application/json'
        request = urllib.request.Request(url, data=body, headers=headers, method=method)
        with urllib.request.urlopen(request, timeout=30) as response:
            data = response.read().decode()
        return json.loads(data) if data else {}

    def list_open_questions(self, tournament_id: int | str, *, offset: int = 0, count: int = 50) -> list[dict[str, Any]]:
        data = self._request_fn('GET', POSTS_ENDPOINT, params=build_posts_query_params(tournament_id, offset=offset, count=count))
        questions = [normalize_post_question(post) for post in data.get('results', [])]
        return [q for q in questions if q and q.get('status') == 'open']

    def prepare_submission(
        self,
        *,
        post_id: int,
        question_id: int,
        probability: float | dict[str, float] | list[float],
        rationale: str,
        dry_run: bool = True,
        question_type: str = 'binary',
        options: list[str] | None = None,
        continuous_range: list[Any] | None = None,
        open_lower_bound: bool | None = None,
        open_upper_bound: bool | None = None,
    ) -> dict[str, Any]:
        payload = {
            'forecast': build_forecast_payload(
                question_id,
                probability,
                question_type,
                options=options,
                continuous_range=continuous_range,
                open_lower_bound=open_lower_bound,
                open_upper_bound=open_upper_bound,
            ),
            'comment': build_comment_payload(post_id, rationale),
        }
        receipt = {
            'artifact': 'metaculus_submission_transport_receipt',
            'forecast_endpoint': FORECAST_ENDPOINT,
            'comment_endpoint': COMMENT_ENDPOINT,
            'payload': payload,
            'payload_sha256': hash_transport_response(payload),
            'submission_endpoints_called': False,
        }
        if dry_run:
            return {**receipt, 'status': 'dry_run_not_submitted'}
        if not self.allow_submit:
            raise PermissionError('Metaculus submission requires explicit allow_submit=True')
        forecast_response = self._request_fn('POST', FORECAST_ENDPOINT, json_payload=payload['forecast'])
        comment_response = self._request_fn('POST', COMMENT_ENDPOINT, json_payload=payload['comment'])
        return {
            **receipt,
            'status': 'submitted',
            'submission_endpoints_called': True,
            'forecast_response_sha256': hash_transport_response(forecast_response),
            'comment_response_sha256': hash_transport_response(comment_response),
        }
