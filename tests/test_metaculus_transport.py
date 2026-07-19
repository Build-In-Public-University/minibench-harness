import json

import pytest

from minibench_harness.metaculus_transport import (
    BOT_TESTING_AREA_ID,
    CURRENT_MINIBENCH_ID,
    MetaculusTransport,
    build_comment_payload,
    build_forecast_payload,
    build_posts_query_params,
    hash_transport_response,
    normalize_post_question,
)


SAMPLE_POST = {
    'id': 123,
    'title': 'Will the demo resolve yes?',
    'url': 'https://www.metaculus.com/questions/123/demo/',
    'question': {
        'id': 456,
        'title': 'Will the demo resolve yes?',
        'status': 'open',
        'type': 'binary',
        'scheduled_close_time': '2026-08-01T00:00:00Z',
        'resolution_criteria': 'Resolve yes if demo happens.',
        'description': 'Background text',
    },
}

SAMPLE_MULTIPLE_CHOICE_POST = {
    'id': 43326,
    'title': 'Which party will hold the most seats in the US House after 2026?',
    'url': 'https://www.metaculus.com/questions/43326/us-house-plurality-after-2026-midterms/',
    'question': {
        'id': 43331,
        'title': 'Which party will hold the most seats in the US House after 2026?',
        'status': 'open',
        'type': 'multiple_choice',
        'scheduled_close_time': '2026-11-02T00:00:00Z',
        'resolution_criteria': 'Resolve to the party with the most seats.',
        'description': 'Background text',
        'options': ['Democrats', 'Republicans', 'Other'],
    },
}


def test_build_posts_query_params_matches_metaculus_template_tournament_filter():
    params = build_posts_query_params('bot-testing-area', offset=50, count=25)
    assert params == {
        'limit': 25,
        'offset': 50,
        'order_by': '-hotness',
        'forecast_type': 'binary,multiple_choice,numeric,discrete',
        'tournaments': ['bot-testing-area'],
        'statuses': 'open',
        'include_description': 'true',
    }


def test_payload_shapes_match_no_framework_reference_binary_and_comment():
    forecast = build_forecast_payload(question_id=456, probability=0.62, question_type='binary')
    assert forecast == [
        {
            'question': 456,
            'source': 'api',
            'probability_yes': 0.62,
            'probability_yes_per_category': None,
            'continuous_cdf': None,
        }
    ]
    comment = build_comment_payload(post_id=123, comment_text='Dry run rationale')
    assert comment == {
        'text': 'Dry run rationale',
        'parent': None,
        'included_forecast': True,
        'is_private': True,
        'on_post': 123,
    }


def test_payload_shape_matches_no_framework_reference_multiple_choice():
    forecast = build_forecast_payload(
        question_id=43331,
        probability={'Democrats': 0.48, 'Republicans': 0.49, 'Other': 0.03},
        question_type='multiple_choice',
        options=['Democrats', 'Republicans', 'Other'],
    )
    assert forecast == [
        {
            'question': 43331,
            'source': 'api',
            'probability_yes': None,
            'probability_yes_per_category': {
                'Democrats': 0.48,
                'Republicans': 0.49,
                'Other': 0.03,
            },
            'continuous_cdf': None,
        }
    ]


@pytest.mark.parametrize('bad_probability', [-0.01, 0, 1, 1.01])
def test_binary_forecast_payload_rejects_values_outside_metaculus_safe_open_interval(bad_probability):
    with pytest.raises(ValueError, match='probability must be strictly between 0 and 1'):
        build_forecast_payload(question_id=456, probability=bad_probability, question_type='binary')


@pytest.mark.parametrize(
    'bad_forecast',
    [
        {'Democrats': 0.5, 'Republicans': 0.5},
        {'Democrats': 0.5, 'Republicans': 0.49, 'Other': 0.03},
        {'Democrats': 1.0, 'Republicans': 0.0, 'Other': 0.0},
        {'Democrats': 0.5, 'Republicans': -0.1, 'Other': 0.6},
    ],
)
def test_multiple_choice_forecast_payload_rejects_missing_non_normalized_or_boundary_values(bad_forecast):
    with pytest.raises(ValueError):
        build_forecast_payload(
            question_id=43331,
            probability=bad_forecast,
            question_type='multiple_choice',
            options=['Democrats', 'Republicans', 'Other'],
        )


def test_normalize_post_question_extracts_question_without_raw_token_or_full_payload():
    normalized = normalize_post_question(SAMPLE_POST)
    assert normalized == {
        'post_id': 123,
        'question_id': 456,
        'title': 'Will the demo resolve yes?',
        'type': 'binary',
        'status': 'open',
        'scheduled_close_time': '2026-08-01T00:00:00Z',
        'url': 'https://www.metaculus.com/questions/123/demo/',
        'resolution_criteria': 'Resolve yes if demo happens.',
        'description': 'Background text',
        'options': None,
    }


def test_normalize_post_question_preserves_multiple_choice_options():
    normalized = normalize_post_question(SAMPLE_MULTIPLE_CHOICE_POST)
    assert normalized['type'] == 'multiple_choice'
    assert normalized['options'] == ['Democrats', 'Republicans', 'Other']


def test_transport_dry_run_records_payloads_without_network_submission():
    calls = []

    def fake_request(method, path, *, params=None, json_payload=None):
        calls.append({'method': method, 'path': path, 'params': params, 'json_payload': json_payload})
        if method == 'GET':
            return {'results': [SAMPLE_POST]}
        raise AssertionError('dry run should not POST')

    transport = MetaculusTransport(token='private-token', request_fn=fake_request)
    questions = transport.list_open_questions(BOT_TESTING_AREA_ID)
    dry_run = transport.prepare_submission(
        post_id=questions[0]['post_id'],
        question_id=questions[0]['question_id'],
        probability=0.62,
        rationale='Dry run rationale',
        dry_run=True,
    )

    assert len(calls) == 1
    assert calls[0]['method'] == 'GET'
    assert calls[0]['path'] == '/posts/'
    assert dry_run['status'] == 'dry_run_not_submitted'
    assert dry_run['submission_endpoints_called'] is False
    assert dry_run['forecast_endpoint'] == '/questions/forecast/'
    assert dry_run['comment_endpoint'] == '/comments/create/'
    assert dry_run['payload_sha256'] == hash_transport_response(dry_run['payload'])
    assert 'private-token' not in json.dumps(dry_run, sort_keys=True)


def test_transport_dry_run_records_multiple_choice_payload_without_network_submission():
    calls = []

    def fake_request(method, path, *, params=None, json_payload=None):
        calls.append({'method': method, 'path': path, 'params': params, 'json_payload': json_payload})
        if method == 'GET':
            return {'results': [SAMPLE_MULTIPLE_CHOICE_POST]}
        raise AssertionError('dry run should not POST')

    transport = MetaculusTransport(token='private-token', request_fn=fake_request)
    question = transport.list_open_questions(BOT_TESTING_AREA_ID)[0]
    dry_run = transport.prepare_submission(
        post_id=question['post_id'],
        question_id=question['question_id'],
        probability={'Democrats': 0.48, 'Republicans': 0.49, 'Other': 0.03},
        rationale='Dry run rationale',
        dry_run=True,
        question_type='multiple_choice',
        options=question['options'],
    )

    assert len(calls) == 1
    assert dry_run['status'] == 'dry_run_not_submitted'
    assert dry_run['payload']['forecast'][0]['probability_yes'] is None
    assert dry_run['payload']['forecast'][0]['probability_yes_per_category']['Other'] == 0.03
    assert dry_run['submission_endpoints_called'] is False
    assert 'private-token' not in json.dumps(dry_run, sort_keys=True)


def test_transport_submit_requires_explicit_allow_submit_even_when_dry_run_false():
    transport = MetaculusTransport(token='private-token', request_fn=lambda *a, **k: {})
    with pytest.raises(PermissionError, match='explicit allow_submit=True'):
        transport.prepare_submission(
            post_id=123,
            question_id=456,
            probability=0.62,
            rationale='Would submit if allowed',
            dry_run=False,
        )


def test_transport_constants_capture_template_targets():
    assert BOT_TESTING_AREA_ID == 'bot-testing-area'
    assert CURRENT_MINIBENCH_ID == 'minibench'
