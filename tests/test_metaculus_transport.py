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


SAMPLE_NUMERIC_POST = {
    'id': 43323,
    'title': "What will be Donald Trump's net approval on December 31, 2026?",
    'url': 'https://www.metaculus.com/questions/43323/trumps-approval-on-dec-31-2026/',
    'question': {
        'id': 43325,
        'title': "What will be Donald Trump's net approval on December 31, 2026?",
        'status': 'open',
        'type': 'numeric',
        'scheduled_close_time': '2026-12-31T00:00:00Z',
        'unit': '%',
        'open_lower_bound': True,
        'open_upper_bound': True,
        'scaling': {'continuous_range': [-35, -17.5, 0], 'range_min': -35, 'range_max': 0},
    },
}

SAMPLE_DATE_POST = {
    'id': 43324,
    'title': 'When will martial law be lifted in at least 3/4 of Ukraine?',
    'url': 'https://www.metaculus.com/questions/43324/date-of-end-of-martial-law-in-ukraine/',
    'question': {
        'id': 43326,
        'title': 'When will martial law be lifted in at least 3/4 of Ukraine?',
        'status': 'open',
        'type': 'date',
        'scheduled_close_time': '2027-05-27T21:00:00Z',
        'open_lower_bound': False,
        'open_upper_bound': True,
        'scaling': {
            'continuous_range': [
                '2022-05-29T00:00:00Z',
                '2024-11-27T12:00:00Z',
                '2027-05-28T00:00:00Z',
            ],
        },
    },
}

SAMPLE_DISCRETE_POST = {
    'id': 43321,
    'title': 'How many of these 15 top US executive branch officials will be out before 2027?',
    'url': 'https://www.metaculus.com/questions/43321/of-top-us-officials-out-in-2026/',
    'question': {
        'id': 43322,
        'title': 'How many of these 15 top US executive branch officials will be out before 2027?',
        'status': 'open',
        'type': 'discrete',
        'scheduled_close_time': '2027-01-01T00:00:00Z',
        'unit': 'Officials',
        'open_lower_bound': False,
        'open_upper_bound': False,
        'scaling': {'continuous_range': [-0.5, 0.5, 1.5, 2.5], 'nominal_min': 0, 'nominal_max': 3},
    },
}


def test_build_posts_query_params_matches_metaculus_template_tournament_filter():
    params = build_posts_query_params('bot-testing-area', offset=50, count=25)
    assert params == {
        'limit': 25,
        'offset': 50,
        'order_by': '-hotness',
        'forecast_type': 'binary,multiple_choice,numeric,discrete,date',
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


@pytest.mark.parametrize('question_type', ['numeric', 'date', 'discrete'])
def test_payload_shape_matches_no_framework_reference_continuous_cdf_types(question_type):
    cdf = [0.05, 0.5, 0.95]
    forecast = build_forecast_payload(
        question_id=43325,
        probability=cdf,
        question_type=question_type,
        continuous_range=[-35, -17.5, 0],
    )
    assert forecast == [
        {
            'question': 43325,
            'source': 'api',
            'probability_yes': None,
            'probability_yes_per_category': None,
            'continuous_cdf': cdf,
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


@pytest.mark.parametrize(
    'bad_cdf',
    [
        [0.05, 0.9],
        [0.05, 0.5, 0.49],
        [0.0, 0.5, 0.95],
        [0.05, 0.5, 1.0],
        'not-a-list',
    ],
)
def test_continuous_cdf_payload_rejects_wrong_length_non_monotone_boundary_or_non_list(bad_cdf):
    with pytest.raises(ValueError):
        build_forecast_payload(
            question_id=43325,
            probability=bad_cdf,
            question_type='numeric',
            continuous_range=[-35, -17.5, 0],
        )


@pytest.mark.parametrize(
    'question_type, cdf, open_lower_bound, open_upper_bound',
    [
        ('numeric', [0.001, 0.5, 0.95], True, True),
        ('date', [0.0, 0.5, 0.95], False, True),
        ('discrete', [0.0, 0.5, 1.0], False, False),
    ],
)
def test_continuous_cdf_payload_respects_open_and_closed_bounds(
    question_type, cdf, open_lower_bound, open_upper_bound
):
    forecast = build_forecast_payload(
        question_id=43325,
        probability=cdf,
        question_type=question_type,
        continuous_range=[-35, -17.5, 0],
        open_lower_bound=open_lower_bound,
        open_upper_bound=open_upper_bound,
    )
    assert forecast[0]['continuous_cdf'] == cdf


@pytest.mark.parametrize(
    'cdf, open_lower_bound, open_upper_bound',
    [
        ([0.05, 0.5, 0.95], False, True),
        ([0.0, 0.5, 0.95], True, True),
        ([0.0, 0.5, 0.95], False, False),
        ([0.0, 0.5, 1.0], False, True),
        ([0.0009, 0.5, 0.95], True, True),
        ([0.001, 0.00104, 0.95], True, True),
    ],
)
def test_continuous_cdf_payload_rejects_bound_values_that_conflict_with_question_bounds(
    cdf, open_lower_bound, open_upper_bound
):
    with pytest.raises(ValueError):
        build_forecast_payload(
            question_id=43325,
            probability=cdf,
            question_type='numeric',
            continuous_range=[-35, -17.5, 0],
            open_lower_bound=open_lower_bound,
            open_upper_bound=open_upper_bound,
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
        'unit': None,
        'scaling': None,
        'continuous_range': None,
        'open_lower_bound': None,
        'open_upper_bound': None,
    }


def test_normalize_post_question_preserves_multiple_choice_options():
    normalized = normalize_post_question(SAMPLE_MULTIPLE_CHOICE_POST)
    assert normalized['type'] == 'multiple_choice'
    assert normalized['options'] == ['Democrats', 'Republicans', 'Other']


@pytest.mark.parametrize(
    'post, expected_type, expected_range',
    [
        (SAMPLE_NUMERIC_POST, 'numeric', [-35, -17.5, 0]),
        (SAMPLE_DATE_POST, 'date', ['2022-05-29T00:00:00Z', '2024-11-27T12:00:00Z', '2027-05-28T00:00:00Z']),
        (SAMPLE_DISCRETE_POST, 'discrete', [-0.5, 0.5, 1.5, 2.5]),
    ],
)
def test_normalize_post_question_preserves_continuous_scaling(post, expected_type, expected_range):
    normalized = normalize_post_question(post)
    assert normalized['type'] == expected_type
    assert normalized['continuous_range'] == expected_range
    assert normalized['scaling'] == post['question']['scaling']
    assert normalized['open_lower_bound'] is post['question']['open_lower_bound']
    assert normalized['open_upper_bound'] is post['question']['open_upper_bound']


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


def test_transport_dry_run_records_continuous_cdf_payload_without_network_submission():
    calls = []

    def fake_request(method, path, *, params=None, json_payload=None):
        calls.append({'method': method, 'path': path, 'params': params, 'json_payload': json_payload})
        if method == 'GET':
            return {'results': [SAMPLE_NUMERIC_POST]}
        raise AssertionError('dry run should not POST')

    transport = MetaculusTransport(token='private-token', request_fn=fake_request)
    question = transport.list_open_questions(BOT_TESTING_AREA_ID)[0]
    dry_run = transport.prepare_submission(
        post_id=question['post_id'],
        question_id=question['question_id'],
        probability=[0.05, 0.5, 0.95],
        rationale='Dry run rationale',
        dry_run=True,
        question_type=question['type'],
        continuous_range=question['continuous_range'],
    )

    assert len(calls) == 1
    assert dry_run['status'] == 'dry_run_not_submitted'
    assert dry_run['payload']['forecast'][0]['continuous_cdf'] == [0.05, 0.5, 0.95]
    assert dry_run['payload']['forecast'][0]['probability_yes'] is None
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
