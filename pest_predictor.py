# ============================================================
# RICE PEST PREDICTOR
#
# FARM STATE
#     ↓
# extract environment + crop context
#     ↓
# pest_scoring.py
#     ↓
# score all 8 pests
#     ↓
# rank
#     ↓
# TOP 2
#
# Camera confirmation remains separate.
# ============================================================

from drought_risk import get_recent_rainfall_records
from pest_scoring import score_all_pests


def get_recent_rainfall(farm_id, current_date=None):
    records = get_recent_rainfall_records(
        farm_id=farm_id,
        days=30,
        as_of_date=current_date,
    )

    values = [
        record["rainfall_mm"]
        for record in records
        if record.get("rainfall_mm") is not None
    ]

    return {
        "records": records,
        "values": values,
        "7day": values[-7:],
        "14day": values[-14:],
        "30day": values,
        "7day_sum_mm": round(sum(values[-7:]), 1),
        "14day_sum_mm": round(sum(values[-14:]), 1),
        "30day_sum_mm": round(sum(values), 1),
        "available": bool(values),
        "observed_days": len(values),
    }


def _get_dat(crop):
    for key in (
        "days_after_sowing",
        "dat",
        "days_after_transplanting",
        "days_after_planting",
    ):
        value = crop.get(key)
        if value is not None:
            return value
    return None


def extract_pest_inputs(farm_state, farm_id, current_date=None):
    crop = farm_state.get("crop", {})
    spatial = farm_state.get("spatial_state", {})
    forecast = farm_state.get("weather", [])

    temperature_data = spatial.get("air_temperature", {})
    humidity_data = spatial.get("air_humidity", {})

    temperature = temperature_data.get("average")
    humidity = humidity_data.get("average")

    growth_stage = crop.get("growth_stage")
    season = crop.get("season")
    dat = _get_dat(crop)

    rainfall = get_recent_rainfall(
        farm_id=farm_id,
        current_date=current_date,
    )

    # Current forecast rainfall.
    current_forecast_rainfall = None
    forecast_rainfall = []

    if forecast:
        current_forecast_rainfall = forecast[0].get("rainfall")
        forecast_rainfall = [
            row.get("rainfall")
            for row in forecast
            if row.get("rainfall") is not None
        ]

    # Use the most recent actual rainfall window when available.
    # If it is unavailable, fall back to forecast/current rainfall.
    rainfall_value = None

    if rainfall["7day"]:
        rainfall_value = rainfall["7day_sum_mm"]
    elif current_forecast_rainfall is not None:
        rainfall_value = current_forecast_rainfall

    return {
        "temperature": temperature,
        "humidity": humidity,
        "rainfall": rainfall_value,
        "actual_rainfall_7day_mm": rainfall["7day_sum_mm"],
        "actual_rainfall_14day_mm": rainfall["14day_sum_mm"],
        "actual_rainfall_30day_mm": rainfall["30day_sum_mm"],
        "forecast_rainfall": forecast_rainfall,
        "growth_stage": growth_stage,
        "season": season,
        "dat": dat,
        "rainfall_observed_days": rainfall["observed_days"],
        "data_availability": {
            "temperature": temperature is not None,
            "humidity": humidity is not None,
            "rainfall": rainfall_value is not None,
            "growth_stage": growth_stage is not None,
            "dat": dat is not None,
        },
    }


def predict_pest_risk(
    farm_state,
    farm_id,
    current_date=None,
):
    if not farm_state:
        return {
            "available": False,
            "reason": "Farm State unavailable.",
        }

    crop = farm_state.get("crop", {})

    if not crop.get("available", False):
        return {
            "available": False,
            "reason": "Crop context unavailable.",
        }

    inputs = extract_pest_inputs(
        farm_state=farm_state,
        farm_id=farm_id,
        current_date=current_date,
    )

    results = score_all_pests(
        temperature=inputs["temperature"],
        humidity=inputs["humidity"],
        rainfall=inputs["rainfall"],
        growth_stage=inputs["growth_stage"],
        dat=inputs["dat"],
    )

    # Early warning = pests whose environmental suitability
    # is already high enough to deserve attention. This is a
    # risk signal, not confirmation of infestation.
    early_warning = [
        item for item in results
        if item["score"] >= 50
    ]

    return {
        "available": True,
        "crop": crop.get("crop"),
        "season": inputs["season"],
        "growth_stage": inputs["growth_stage"],
        "dat": inputs["dat"],

        "top_two": results[:2],
        "all_pests": results,

        "early_warning": early_warning[:2],

        "rainfall": {
            "recent_7day_mm": inputs["actual_rainfall_7day_mm"],
            "recent_14day_mm": inputs["actual_rainfall_14day_mm"],
            "recent_30day_mm": inputs["actual_rainfall_30day_mm"],
            "forecast_mm": (
                round(sum(inputs["forecast_rainfall"]), 1)
                if inputs["forecast_rainfall"]
                else None
            ),
            "observed_days": inputs["rainfall_observed_days"],
        },

        "data_availability": inputs["data_availability"],

        "normalized_inputs": {
            "temperature": inputs["temperature"],
            "humidity": inputs["humidity"],
            "rainfall_used_for_scoring": inputs["rainfall"],
            "growth_stage": inputs["growth_stage"],
            "dat": inputs["dat"],
        },

        "note": (
            "Pest scores are biologically-informed risk priors. "
            "They indicate favorable conditions and do not confirm "
            "visible infestation. Camera confirmation remains separate."
        ),
    }


if __name__ == "__main__":
    from farm_state import build_farm_state

    FARM_ID = 1
    FIELD_ID = 1
    DEVICE_ID = "RPI-RICE-0001"

    farm_state = build_farm_state(
        DEVICE_ID,
        farm_id=FARM_ID,
        field_id=FIELD_ID,
    )

    result = predict_pest_risk(
        farm_state=farm_state,
        farm_id=FARM_ID,
    )

    print("\n==============================")
    print("PEST PREDICTION")
    print("==============================")

    if not result["available"]:
        print("Unavailable:", result["reason"])
    else:
        print("Crop:", result["crop"])
        print("Season:", result["season"])
        print("Growth stage:", result["growth_stage"])
        print("DAT:", result["dat"])

        print("\nTOP 2 PESTS")

        for index, pest in enumerate(
            result["top_two"],
            start=1,
        ):
            print(
                f"{index}. "
                f"{pest['pest_name']} - "
                f"{pest['score']} - "
                f"{pest['risk_level']}"
            )

        print("\nEARLY WARNING")

        for pest in result["early_warning"]:
            print(
                f"{pest['pest_name']} - "
                f"{pest['score']} - "
                f"{pest['risk_level']}"
            )
