from __future__ import annotations

from typing import Any, Dict, List, Optional
from drought_risk import get_recent_rainfall_records

# New Phase-1 pest_rules.py
from pests_rules import PETS, PHASE1_WEIGHTS, classify_risk


# ============================================================
# HELPERS
# ============================================================

def _number(value):
    """Convert a value to float or return None."""
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _range_score(value, low, high):
    """
    0-1 suitability for a bounded range.

    Inside the threshold range = 1.
    Outside the range = linearly decreases toward 0.

    Because the new CSV does not provide a universal tolerance for
    every pest, the distance outside the range uses the range width
    itself as the falloff distance. This is an engineering Phase-1
    mapping, not a claim from the source literature.
    """
    value = _number(value)
    low = _number(low)
    high = _number(high)

    if value is None or low is None or high is None:
        return None

    if low > high:
        low, high = high, low

    if low <= value <= high:
        return 1.0

    width = max(high - low, 1.0)

    if value < low:
        return max(0.0, 1.0 - ((low - value) / width))

    return max(0.0, 1.0 - ((value - high) / width))


def _threshold_score(value, threshold, direction="above"):
    """
    0-1 suitability for one-sided threshold rules.

    This is used only when a rule clearly expresses a directional
    threshold in the source metadata.
    """
    value = _number(value)
    threshold = _number(threshold)

    if value is None or threshold is None:
        return None

    if direction == "above":
        if value >= threshold:
            return 1.0
        span = max(abs(threshold) * 0.25, 1.0)
        return max(0.0, 1.0 - ((threshold - value) / span))

    if direction == "below":
        if value <= threshold:
            return 1.0
        span = max(abs(threshold) * 0.25, 1.0)
        return max(0.0, 1.0 - ((value - threshold) / span))

    raise ValueError("direction must be 'above' or 'below'")


def _text_matches(value: Optional[str], candidates) -> bool:
    if value is None:
        return False

    text = str(value).strip().lower()
    if not text:
        return False

    return any(str(candidate).strip().lower() in text for candidate in candidates)


def _stage_score(growth_stage, rule):
    """
    Score stage compatibility.

    New CSV rules may contain a free-text growth_stage_or_timing field.
    We deliberately do not invent stage probabilities: a clear textual
    match gives 1, a clear non-match gives 0, and an absent timing rule
    gives None.
    """
    timing = rule.get("growth_stage_or_timing")

    if not timing or growth_stage is None:
        return None

    return 1.0 if _text_matches(growth_stage, [timing]) else 0.0


def _dat_score(dat, rule):
    return _range_score(
        dat,
        rule.get("DAT_min"),
        rule.get("DAT_max"),
    )


# ============================================================
# RAINFALL
# ============================================================

def get_recent_rainfall(farm_id, current_date=None):
    """
    Reuse drought_risk.py's existing rainfall history.

    Returns up to 30 observed daily rainfall values, oldest -> newest.
    """
    records = get_recent_rainfall_records(
        farm_id=farm_id,
        days=30,
        as_of_date=current_date,
    )

    values = [
        _number(record.get("rainfall_mm"))
        for record in records
        if record.get("rainfall_mm") is not None
    ]

    return {
        "records": records,
        "values": values,
        "7day": values[-7:],
        "14day": values[-14:],
        "30day": values[-30:],
        "7day_sum_mm": round(sum(values[-7:]), 1),
        "14day_sum_mm": round(sum(values[-14:]), 1),
        "30day_sum_mm": round(sum(values[-30:]), 1),
        "available": len(values) > 0,
        "observed_days": len(values),
    }


def rainfall_for_rule(rainfall_data, rule):
    """
    Select the rainfall window requested by the source rule.

    If the source does not specify a window, use 7 days as the
    Phase-1 default because it is already available in Farm State.
    """
    window = _number(rule.get("rain_window_days"))

    if window is None:
        window = 7

    window = int(window)

    if window <= 7:
        return rainfall_data["7day_sum_mm"], 7

    if window <= 14:
        return rainfall_data["14day_sum_mm"], 14

    return rainfall_data["30day_sum_mm"], 30


# ============================================================
# FARM STATE → PEST INPUTS
# ============================================================

def extract_pest_inputs(
    farm_state: Dict[str, Any],
    farm_id: int,
    current_date=None,
):
    """
    Convert the common Farm State into the smaller structure required
    by the pest engine.
    """
    crop = farm_state.get("crop", {})
    spatial = farm_state.get("spatial_state", {})
    weather_forecast = farm_state.get("weather", [])

    temperature = (
        spatial.get("air_temperature", {})
        .get("average")
    )

    humidity = (
        spatial.get("air_humidity", {})
        .get("average")
    )

    growth_stage = crop.get("growth_stage")
    dat = crop.get("days_after_sowing")
    season = crop.get("season")

    # State is retained as context, but is not automatically converted
    # into a risk modifier because the Phase-1 rules do not define one.
    state = crop.get("state")

    rainfall = get_recent_rainfall(
        farm_id=farm_id,
        current_date=current_date,
    )

    forecast_rainfall = [
        _number(row.get("rainfall"))
        for row in weather_forecast
        if row.get("rainfall") is not None
    ]

    # Farm State does not currently contain sunshine observations.
    sunshine = None

    availability = {
        "temperature": temperature is not None,
        "humidity": humidity is not None,
        "recent_rainfall": rainfall["available"],
        "growth_stage": growth_stage is not None,
        "dat": dat is not None,
        "season": season is not None,
        "sunshine": sunshine is not None,
        "forecast_rainfall": len(forecast_rainfall) > 0,
    }

    return {
        "temperature": temperature,
        "humidity": humidity,
        "sunshine": sunshine,
        "growth_stage": growth_stage,
        "dat": dat,
        "season": season,
        "state": state,
        "recent_rainfall": rainfall,
        "forecast_rainfall": forecast_rainfall,
        "data_availability": availability,
    }


# ============================================================
# PEST SCORING
# ============================================================

def _get_rule_range(rule, prefix):
    """
    Read new CSV-derived fields such as:
        temp_min_c / temp_max_c
        rh_min_pct / rh_max_pct
        rain_min_mm / rain_max_mm
        sunshine_min_hr / sunshine_max_hr
    """
    return (
        rule.get(f"{prefix}_min"),
        rule.get(f"{prefix}_max"),
    )


def score_pest(
    pest_key: str,
    inputs: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Score one pest from the new Phase-1 pest_rules.py.

    Only factors that both:
      1. exist in the source rule, and
      2. are available in Farm State
    contribute to the score.

    Missing factors are reported rather than silently treated as zero.
    """
    if pest_key not in PETS:
        raise ValueError(f"Unknown pest: {pest_key}")

    rule = PETS[pest_key]

    factors = {}
    weights = {}
    missing = []

    # --------------------------------------------------------
    # Temperature
    # --------------------------------------------------------
    t_low, t_high = _get_rule_range(rule, "temp")
    if t_low is not None or t_high is not None:
        score = _range_score(inputs["temperature"], t_low, t_high)
        if score is None:
            missing.append("temperature")
        else:
            factors["temperature"] = score
            weights["temperature"] = PHASE1_WEIGHTS["temperature"]

    # --------------------------------------------------------
    # Humidity
    # --------------------------------------------------------
    h_low, h_high = _get_rule_range(rule, "rh")
    if h_low is not None or h_high is not None:
        score = _range_score(inputs["humidity"], h_low, h_high)
        if score is None:
            missing.append("humidity")
        else:
            factors["humidity"] = score
            weights["humidity"] = PHASE1_WEIGHTS["humidity"]

    # --------------------------------------------------------
    # Rainfall
    # --------------------------------------------------------
    r_low, r_high = _get_rule_range(rule, "rain")
    if r_low is not None or r_high is not None:
        rainfall_value, rainfall_window = rainfall_for_rule(
            inputs["recent_rainfall"],
            rule,
        )

        score = _range_score(rainfall_value, r_low, r_high)

        if score is None:
            missing.append("rainfall")
        else:
            factors["rainfall"] = score
            weights["rainfall"] = PHASE1_WEIGHTS["rainfall"]

    # --------------------------------------------------------
    # Growth stage / timing
    # --------------------------------------------------------
    if rule.get("growth_stage_or_timing"):
        score = _stage_score(
            inputs["growth_stage"],
            rule,
        )

        if score is None:
            missing.append("growth_stage")
        else:
            factors["growth_stage"] = score
            weights["growth_stage"] = PHASE1_WEIGHTS["growth_stage"]

    # --------------------------------------------------------
    # DAT
    # --------------------------------------------------------
    if rule.get("DAT_min") is not None or rule.get("DAT_max") is not None:
        score = _dat_score(
            inputs["dat"],
            rule,
        )

        if score is None:
            missing.append("DAT")
        else:
            factors["DAT"] = score
            weights["DAT"] = PHASE1_WEIGHTS["days_after_sowing"]

    # --------------------------------------------------------
    # Sunshine
    # --------------------------------------------------------
    if (
        rule.get("sunshine_min_hr") is not None
        or rule.get("sunshine_max_hr") is not None
    ):
        if inputs["sunshine"] is None:
            missing.append("sunshine")
        else:
            s_low, s_high = _get_rule_range(rule, "sunshine")
            factors["sunshine"] = _range_score(
                inputs["sunshine"],
                s_low,
                s_high,
            )
            # Sunshine is not part of PHASE1_WEIGHTS because current
            # Farm State cannot measure it.
            # If added later, it must receive an explicit weight.

    if not factors:
        return {
            "pest": pest_key,
            "pest_name": rule.get("pest_name", pest_key),
            "score": 0.0,
            "risk_level": "LOW",
            "breakdown": {},
            "weights": {},
            "coverage": 0.0,
            "missing_factors": missing,
            "evidence_limited": True,
        }

    total_weight = sum(weights.values())

    weighted_sum = sum(
        factors[name] * weights[name]
        for name in factors
        if name in weights
    )

    score = (
        (weighted_sum / total_weight) * 100.0
        if total_weight > 0
        else 0.0
    )

    # Coverage is how much of the Phase-1 weight was actually usable.
    full_weight = sum(
        PHASE1_WEIGHTS[key]
        for key in ("temperature", "humidity", "rainfall",
                    "growth_stage", "days_after_sowing")
    )

    coverage = (
        total_weight / full_weight
        if full_weight > 0
        else 0.0
    )

    score = max(0.0, min(100.0, score))

    return {
        "pest": pest_key,
        "pest_name": rule.get("pest_name", pest_key),
        "score": round(score, 2),
        "risk_level": classify_risk(score),
        "breakdown": {
            key: round(value, 3)
            for key, value in factors.items()
        },
        "weights": {
            key: round(value, 4)
            for key, value in weights.items()
        },
        "coverage": round(coverage, 3),
        "missing_factors": sorted(set(missing)),
        "evidence_limited": len(missing) > 0,
    }


def score_all_pests(inputs: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Calculate every pest defined in the new pest_rules.py."""
    results = []

    for pest_key in PETS:
        results.append(
            score_pest(
                pest_key=pest_key,
                inputs=inputs,
            )
        )

    results.sort(
        key=lambda item: item["score"],
        reverse=True,
    )

    return results


# ============================================================
# RANK
# ============================================================

def rank_pests(results):
    """Return pests highest-risk first."""
    return sorted(
        results,
        key=lambda item: item.get("score", 0),
        reverse=True,
    )


# ============================================================
# MAIN PREDICTOR
# ============================================================

def predict_pest_risk(
    farm_state: Dict[str, Any],
    farm_id: int,
    current_date=None,
) -> Dict[str, Any]:
    """
    Main pest prediction entry point.

    Farm State is the observation source.
    pest_rules.py is the interpretation source.
    """
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

    if str(crop.get("crop", "")).upper() != "RICE":
        return {
            "available": False,
            "reason": "Phase-1 pest engine is configured for rice.",
        }

    inputs = extract_pest_inputs(
        farm_state=farm_state,
        farm_id=farm_id,
        current_date=current_date,
    )

    all_results = score_all_pests(inputs)
    ranked = rank_pests(all_results)

    top_two = ranked[:2]

    rainfall = inputs["recent_rainfall"]

    return {
        "available": True,
        "crop": crop.get("crop"),
        "state": crop.get("state"),
        "season": inputs["season"],
        "growth_stage": inputs["growth_stage"],
        "days_after_sowing": inputs["dat"],

        "top_two": top_two,
        "all_pests": ranked,

        "confidence": round(
            sum(inputs["data_availability"].values())
            / len(inputs["data_availability"]),
            3,
        ),

        "data_availability": inputs["data_availability"],

        "rainfall": {
            "recent_7day_mm": rainfall["7day_sum_mm"],
            "recent_14day_mm": rainfall["14day_sum_mm"],
            "recent_30day_mm": rainfall["30day_sum_mm"],
            "observed_days": rainfall["observed_days"],
            "forecast_7day_mm": (
                round(sum(inputs["forecast_rainfall"]), 1)
                if inputs["forecast_rainfall"]
                else None
            ),
        },

        "normalized_inputs": {
            "temperature": inputs["temperature"],
            "humidity": inputs["humidity"],
            "growth_stage": inputs["growth_stage"],
            "days_after_sowing": inputs["dat"],
            "season": inputs["season"],
        },
    }


# ============================================================
# SIMPLE DEMO
# ============================================================

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
        print("State:", result["state"])
        print("Season:", result["season"])
        print("Growth stage:", result["growth_stage"])
        print("DAT:", result["days_after_sowing"])
        print("Confidence:", result["confidence"])

        print("\nRAINFALL")
        print(
            "Recent 7-day:",
            result["rainfall"]["recent_7day_mm"],
            "mm",
        )
        print(
            "Recent 14-day:",
            result["rainfall"]["recent_14day_mm"],
            "mm",
        )
        print(
            "Recent 30-day:",
            result["rainfall"]["recent_30day_mm"],
            "mm",
        )
        print(
            "Forecast 7-day:",
            result["rainfall"]["forecast_7day_mm"],
            "mm",
        )

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

        print("\nALL PESTS")

        for pest in result["all_pests"]:
            print(
                f"{pest['pest_name']}: "
                f"{pest['score']} "
                f"({pest['risk_level']}) "
                f"| coverage={pest['coverage']}"
            )

        print("\nDATA AVAILABILITY")
        for key, value in result["data_availability"].items():
            print(f"{key}: {value}")
