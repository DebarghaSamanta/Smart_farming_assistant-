import sys
import types


sensor_repository = types.ModuleType("sensor_repository")
sensor_repository.get_latest_field_readings = lambda device_id: []
sensor_repository.get_sensor_history = lambda device_id, limit=20: []
sys.modules["sensor_repository"] = sensor_repository

database = types.ModuleType("database")
database.get_crop = lambda field_id: None
sys.modules["database"] = database

weather_repository = types.ModuleType("weather_repository")
weather_repository.get_weather_forecast = lambda farm_id: None
sys.modules["weather_repository"] = weather_repository

crop_calendar = types.ModuleType("crop_calendar")
crop_calendar.get_crop_status = lambda **kwargs: {
    "available": True,
    "days_after_sowing": 106,
    "expected_duration": 150,
    "growth_stage": "FLOWERING",
}
sys.modules["crop_calendar"] = crop_calendar

import farm_state


def test_crop_context_is_wired():
    original_get_crop = farm_state.get_crop
    original_get_crop_context = farm_state.get_crop_context

    farm_state.get_crop = lambda field_id: {
        "crop_id": 1,
        "crop_name": "RICE",
        "sowing_date": "2026-07-01",
        "season": "AMAN",
    }

    farm_state.get_crop_context = lambda **kwargs: {
        "available": True,
        "crop": kwargs["crop"],
        "state": kwargs["state"],
        "season": kwargs["season"],
        "growth_stage": "FLOWERING",
        "drought_sensitivity": 1.0,
        "critical_stage": True,
    }

    result = farm_state.build_crop_context(
        field_id=1,
        state="West Bengal",
        current_date="2026-10-15",
    )

    assert result["available"] is True
    assert result["crop"] == "RICE"
    assert result["state"] == "West Bengal"
    assert result["season"] == "AMAN"
    assert result["growth_stage"] == "FLOWERING"
    assert result["drought_sensitivity"] == 1.0
    assert result["critical_stage"] is True

    farm_state.get_crop = original_get_crop
    farm_state.get_crop_context = original_get_crop_context


def test_missing_field():
    assert farm_state.build_crop_context(None, "West Bengal") == {
        "available": False
    }


if __name__ == "__main__":
    test_crop_context_is_wired()
    test_missing_field()
    print("All farm_state crop-context tests passed.")
