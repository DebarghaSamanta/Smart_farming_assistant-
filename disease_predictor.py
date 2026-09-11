# ============================================================
# DISEASE PREDICTOR
# ============================================================
#
# Responsibility:
#   REAL FARM STATE
#       ↓
#   extract relevant data
#       ↓
#   normalize disease inputs
#       ↓
#   disease_rules.py
#       ↓
#   calculate all diseases
#       ↓
#   rank
#       ↓
#   return TOP 2
#
# This file does NOT contain disease thresholds or rules.
# It does NOT modify drought logic.
# ============================================================

from drought_risk import get_recent_rainfall_records
from disease_rules import score_all_diseases


# ------------------------------------------------------------
# RAINFALL EXTRACTION
# ------------------------------------------------------------

def get_recent_rainfall(farm_id, current_date=None):
    """
    Get actual recent rainfall from the existing rainfall log.

    We intentionally reuse drought_risk.py's rainfall repository
    function instead of creating another rainfall data pipeline.
    """

    records = get_recent_rainfall_records(
        farm_id=farm_id,
        days=30,
        as_of_date=current_date
    )

    rainfall_values = [
        record["rainfall_mm"]
        for record in records
        if record.get("rainfall_mm") is not None
    ]

    return {
        "records": records,
        "values": rainfall_values,
        "7day": rainfall_values[-7:],
        "30day": rainfall_values,
        "7day_sum_mm": round(
            sum(rainfall_values[-7:]), 1
        ),
        "30day_sum_mm": round(
            sum(rainfall_values), 1
        ),
        "available": len(rainfall_values) > 0,
        "observed_days": len(rainfall_values),
    }


# ------------------------------------------------------------
# FARM STATE → DISEASE INPUTS
# ------------------------------------------------------------

def extract_disease_inputs(
    farm_state,
    farm_id,
    current_date=None
):
    """
    Convert the real Farm State into the smaller input structure
    required by the disease rules.
    """

    crop = farm_state.get("crop", {})
    spatial = farm_state.get("spatial_state", {})
    weather_forecast = farm_state.get("weather", [])

    # --------------------------------------------------------
    # CURRENT FIELD CONDITIONS
    # --------------------------------------------------------
    temperature_data = spatial.get("air_temperature", {})
    humidity_data = spatial.get("air_humidity", {})

    temperature = temperature_data.get("average")
    humidity = humidity_data.get("average")

    # --------------------------------------------------------
    # CROP STAGE
    # --------------------------------------------------------
    growth_stage = crop.get("growth_stage")

    # --------------------------------------------------------
    # RECENT ACTUAL RAINFALL
    # --------------------------------------------------------
    rainfall = get_recent_rainfall(
        farm_id=farm_id,
        current_date=current_date
    )

    # --------------------------------------------------------
    # FORECAST RAINFALL
    # --------------------------------------------------------
    forecast_rainfall = [
        row.get("rainfall")
        for row in weather_forecast
        if row.get("rainfall") is not None
    ]

    # The first weather record represents the current day's
    # weather record. It is forecast rainfall, NOT sensor-measured
    # rainfall.
    current_day_forecast_rainfall = None

    if weather_forecast:
        current_day_forecast_rainfall = (
            weather_forecast[0].get("rainfall")
        )

    # --------------------------------------------------------
    # NORMALIZED WEATHER INPUT
    # --------------------------------------------------------
    weather = {
        "temperature": temperature,
        "humidity": humidity,
        "rainfall": current_day_forecast_rainfall,
    }

    # --------------------------------------------------------
    # DATA AVAILABILITY
    # --------------------------------------------------------
    availability = {
        "temperature": temperature is not None,
        "humidity": humidity is not None,
        "growth_stage": growth_stage is not None,
        "current_day_rainfall": (
            current_day_forecast_rainfall is not None
        ),
        "recent_rainfall": rainfall["available"],
        "forecast_rainfall": len(forecast_rainfall) > 0,
    }

    available_count = sum(availability.values())
    total_count = len(availability)

    confidence = (
        available_count / total_count
        if total_count > 0
        else 0.0
    )

    return {
        "weather": weather,
        "growth_stage": growth_stage,

        "recent_rainfall": rainfall["values"],
        "recent_rainfall_7day": rainfall["7day"],
        "recent_rainfall_30day": rainfall["30day"],

        "recent_7day_rainfall_mm":
            rainfall["7day_sum_mm"],

        "recent_30day_rainfall_mm":
            rainfall["30day_sum_mm"],

        "forecast_rainfall": forecast_rainfall,

        "data_availability": availability,

        "confidence": round(confidence, 3),

        "rainfall_data_quality": {
            "available": rainfall["available"],
            "observed_days": rainfall["observed_days"],
        },
    }


# ------------------------------------------------------------
# RANK DISEASES
# ------------------------------------------------------------

def rank_diseases(results):
    """
    Convert all disease results into a ranked list.
    """

    ranked = []

    for result in results:
        ranked.append(result)

    ranked.sort(
        key=lambda item: item.get("score", 0),
        reverse=True
    )

    return ranked


# ------------------------------------------------------------
# MAIN PREDICTOR
# ------------------------------------------------------------

def predict_disease_risk(
    farm_state,
    farm_id,
    drought_result=None,
    current_date=None
):
    """
    Main disease prediction entry point.

    Farm State is the observation source.
    disease_rules.py is the interpretation engine.
    """

    # --------------------------------------------------------
    # FARM STATE AVAILABILITY
    # --------------------------------------------------------

    if not farm_state:
        return {
            "available": False,
            "reason": "Farm State unavailable."
        }

    crop = farm_state.get("crop", {})

    if not crop.get("available", False):
        return {
            "available": False,
            "reason": "Crop context unavailable."
        }

    # --------------------------------------------------------
    # EXTRACT + NORMALIZE
    # --------------------------------------------------------

    inputs = extract_disease_inputs(
        farm_state=farm_state,
        farm_id=farm_id,
        current_date=current_date
    )

    # --------------------------------------------------------
    # RUN ALL DISEASE RULES
    # --------------------------------------------------------

    all_results = score_all_diseases(
        weather=inputs["weather"],
        growth_stage=inputs["growth_stage"],
        recent_rainfall=inputs["recent_rainfall"],
        forecast_rainfall=inputs["forecast_rainfall"],
        drought_result=drought_result,
    )

    # --------------------------------------------------------
    # RANK
    # --------------------------------------------------------

    ranked = rank_diseases(all_results)

    # --------------------------------------------------------
    # TOP TWO
    # --------------------------------------------------------

    top_two = ranked[:2]

    # --------------------------------------------------------
    # FINAL RESULT
    # --------------------------------------------------------

    return {
        "available": True,

        "crop": crop.get("crop"),
        "growth_stage": inputs["growth_stage"],

        "top_two": top_two,

        # Keep every disease internally available for
        # dashboard/debugging, while TOP 2 is the output.
        "all_diseases": ranked,

        "confidence": inputs["confidence"],

        "data_availability":
            inputs["data_availability"],

        "rainfall": {
            "recent_7day_mm":
                inputs["recent_7day_rainfall_mm"],

            "recent_30day_mm":
                inputs["recent_30day_rainfall_mm"],

            "forecast_7day_mm":
                round(
                    sum(inputs["forecast_rainfall"]),
                    1
                )
                if inputs["forecast_rainfall"]
                else None,

            "observed_days":
                inputs["rainfall_data_quality"]["observed_days"],
        },

        "normalized_inputs": {
            "weather": inputs["weather"],
            "growth_stage": inputs["growth_stage"],
        },
    }


# ------------------------------------------------------------
# SIMPLE DEMO
# ------------------------------------------------------------

if __name__ == "__main__":

    from farm_state import build_farm_state

    FARM_ID = 1
    FIELD_ID = 1
    DEVICE_ID = "RPI-RICE-0001"

    farm_state = build_farm_state(
        DEVICE_ID,
        farm_id=FARM_ID,
        field_id=FIELD_ID
    )

    result = predict_disease_risk(
        farm_state=farm_state,
        farm_id=FARM_ID
    )

    print("\n==============================")
    print("DISEASE PREDICTION")
    print("==============================")

    if not result["available"]:
        print("Unavailable:", result["reason"])

    else:
        print(
            "Crop:",
            result["crop"]
        )

        print(
            "Growth stage:",
            result["growth_stage"]
        )

        print(
            "Confidence:",
            result["confidence"]
        )

        print(
            "Recent 7-day rainfall:",
            result["rainfall"]["recent_7day_mm"],
            "mm"
        )

        print(
            "Recent 30-day rainfall:",
            result["rainfall"]["recent_30day_mm"],
            "mm"
        )

        print("\nTOP 2 DISEASES")

        for index, disease in enumerate(
            result["top_two"],
            start=1
        ):
            print(
                f"{index}. "
                f"{disease['disease']} - "
                f"{disease['score']} - "
                f"{disease['risk_level']}"
            )