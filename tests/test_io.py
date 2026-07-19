from minibench_harness.io import write_demo_cycle


def test_write_demo_cycle_emits_config_forecast_settlement_and_calendar(tmp_path):
    result = write_demo_cycle(tmp_path)
    assert (tmp_path / 'config_seal.json').exists()
    assert (tmp_path / 'forecasts.jsonl').exists()
    assert (tmp_path / 'settlements.jsonl').exists()
    assert (tmp_path / 'settlement_calendar.json').exists()
    assert result['forecast_count'] == 2
    assert result['settled_count'] == 2
    assert result['mean_brier'] >= 0
    assert result['mean_binary_log_loss_proxy'] >= 0
    assert result['beat_ducks']['brier']['base_rate'] >= 0
    assert result['beat_ducks']['brier']['persistence'] >= 0
    assert result['beat_ducks']['binary_log_loss_proxy']['base_rate'] >= 0
