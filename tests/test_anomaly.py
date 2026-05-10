from healops.anomaly import calculate_z_score, detect_spike


def test_normal_value_is_not_anomaly():
    result = calculate_z_score(51, [48, 49, 50, 51, 52, 50, 49])
    assert result.is_anomaly is False
    assert result.level == "none"


def test_spike_is_anomaly():
    result = detect_spike(95, [40, 42, 41, 39, 43, 40, 42])
    assert result.is_anomaly is True
    assert result.level in ["medium", "high", "critical"]


def test_not_enough_baseline_data():
    result = calculate_z_score(90, [40, 41])
    assert result.is_anomaly is False
    assert result.reason == "not_enough_baseline_data"