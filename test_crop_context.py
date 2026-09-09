from drought_risk import fuse_drought_evidence


def test_low_sensitivity_reduces_vulnerability():
    evidence = {
        "rainfall_below_normal": True,
        "seven_day_deficit": True,
        "dry_spell": True,
        "soil_moisture_declining": True,
        "leaf_temperature_stress": False,
        "atmospheric_drying": False,
        "rain_forecast_insufficient": True,
    }

    high = fuse_drought_evidence(
        evidence,
        drought_sensitivity=1.0,
    )

    low = fuse_drought_evidence(
        evidence,
        drought_sensitivity=0.2,
    )

    assert high[0] > low[0]
    assert high[1] in {"MEDIUM", "HIGH"}
    assert low[0] < high[0]


def test_no_evidence():
    evidence = {
        "rainfall_below_normal": False,
        "seven_day_deficit": False,
        "dry_spell": False,
        "soil_moisture_declining": False,
        "leaf_temperature_stress": False,
        "atmospheric_drying": False,
        "rain_forecast_insufficient": False,
    }

    score, risk, active = fuse_drought_evidence(
        evidence,
        drought_sensitivity=1.0,
    )

    assert score == 0
    assert risk == "NONE"
    assert active == []


if __name__ == "__main__":
    test_low_sensitivity_reduces_vulnerability()
    test_no_evidence()
    print("All drought_engine tests passed.")
