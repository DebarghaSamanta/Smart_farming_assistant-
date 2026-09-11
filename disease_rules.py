from __future__ import annotations

import math
from typing import Dict, List, Optional, Any


# ============================================================
# 1. DISEASE DEFINITIONS
# ============================================================

DISEASE_RULES = {

    "TUNGRO": {
        "name": "Rice Tungro",
        "temperature": {
            "low": 25,
            "high": 32,
            "tolerance": 5
        },
        "humidity": {
            "threshold": 70,
            "span": 20
        },
        "rainfall": {
            "low": 5,
            "high": 25,
            "tolerance": 15
        },
        "stage_weights": {
            "ESTABLISHMENT": 1.0,
            "SEEDLING": 1.0,
            "VEGETATIVE": 0.9,
            "TILLERING": 0.9,
            "REPRODUCTIVE": 0.4,
            "FLOWERING": 0.3,
            "GRAIN_FILLING": 0.2,
            "MATURITY": 0.1
        }
    },

    "LEAF_SMUT": {
        "name": "Leaf Smut",
        "temperature": {
            "low": 20,
            "high": 28,
            "tolerance": 5
        },
        "humidity": {
            "threshold": 85,
            "span": 15
        },
        "rainfall": {
            "low": 5,
            "high": 20,
            "tolerance": 15
        },
        "stage_weights": {
            "ESTABLISHMENT": 0.2,
            "SEEDLING": 0.3,
            "VEGETATIVE": 0.5,
            "TILLERING": 0.6,
            "REPRODUCTIVE": 0.8,
            "FLOWERING": 0.9,
            "GRAIN_FILLING": 1.0,
            "MATURITY": 0.7
        }
    },

    "BAKANAE": {
        "name": "Bakanae",
        "temperature": {
            "low": 25,
            "high": 35,
            "tolerance": 5
        },
        "humidity": {
            "threshold": 65,
            "span": 20
        },
        "rainfall": {
            "low": 5,
            "high": 30,
            "tolerance": 20
        },
        "stage_weights": {
            "ESTABLISHMENT": 1.0,
            "SEEDLING": 1.0,
            "VEGETATIVE": 0.7,
            "TILLERING": 0.5,
            "REPRODUCTIVE": 0.2,
            "FLOWERING": 0.1,
            "GRAIN_FILLING": 0.1,
            "MATURITY": 0.1
        }
    },

    "BROWN_SPOT": {
        "name": "Brown Spot",
        "temperature": {
            "low": 25,
            "high": 30,
            "tolerance": 5
        },
        "humidity": {
            "threshold": 80,
            "span": 20
        },
        "rainfall": {
            "low": 5,
            "high": 20,
            "tolerance": 15
        },
        "stage_weights": {
            "ESTABLISHMENT": 0.7,
            "SEEDLING": 0.8,
            "VEGETATIVE": 0.8,
            "TILLERING": 0.8,
            "REPRODUCTIVE": 0.9,
            "FLOWERING": 1.0,
            "GRAIN_FILLING": 1.0,
            "MATURITY": 0.8
        }
    },

    "BACTERIAL_BLIGHT": {
        "name": "Bacterial Blight",
        "temperature": {
            "low": 25,
            "high": 34,
            "tolerance": 5
        },
        "humidity": {
            "threshold": 70,
            "span": 20
        },
        "rainfall": {
            "low": 10,
            "high": 40,
            "tolerance": 20
        },
        "stage_weights": {
            "ESTABLISHMENT": 0.2,
            "SEEDLING": 0.3,
            "VEGETATIVE": 0.6,
            "TILLERING": 0.9,
            "REPRODUCTIVE": 1.0,
            "FLOWERING": 0.8,
            "GRAIN_FILLING": 0.5,
            "MATURITY": 0.2
        }
    },

    "FALSE_SMUT": {
        "name": "False Smut",
        "temperature": {
            "low": 25,
            "high": 32,
            "tolerance": 5
        },
        "humidity": {
            "threshold": 85,
            "span": 15
        },
        "rainfall": {
            "low": 5,
            "high": 20,
            "tolerance": 15
        },
        "stage_weights": {
            "ESTABLISHMENT": 0.1,
            "SEEDLING": 0.1,
            "VEGETATIVE": 0.2,
            "TILLERING": 0.4,
            "REPRODUCTIVE": 0.9,
            "FLOWERING": 1.0,
            "GRAIN_FILLING": 0.9,
            "MATURITY": 0.4
        }
    }
}


# ============================================================
# 2. FALLBACK WEIGHTS
# ============================================================
#
# These are ONLY development fallback weights.
#
# They are NOT claimed to be Shannon entropy weights.
#
# Once the real reference dataset is available, these will be
# replaced by calculate_entropy_weights().
# ============================================================

REAL_WEIGHTS = {

    "TUNGRO": {
        "temperature": 0.167423,
        "humidity": 0.197441,
        "rainfall": 0.340827,
        "stage": 0.294309,
    },

    "LEAF_SMUT": {
        "temperature": 0.137527,
        "humidity": 0.257104,
        "rainfall": 0.340827,
        "stage": 0.264542,
    },

    "BAKANAE": {
        "temperature": 0.197321,
        "humidity": 0.167679,
        "rainfall": 0.340827,
        "stage": 0.294173,
    },

    "BROWN_SPOT": {
        "temperature": 0.167423,
        "humidity": 0.257104,
        "rainfall": 0.340827,
        "stage": 0.234646,
    },

    "BACTERIAL_BLIGHT": {
        "temperature": 0.167423,
        "humidity": 0.197441,
        "rainfall": 0.400263,
        "stage": 0.234646,
    },

    "FALSE_SMUT": {
        "temperature": 0.167423,
        "humidity": 0.287281,
        "rainfall": 0.340827,
        "stage": 0.204469,
    }
}


# ============================================================
# 3. SUITABILITY FUNCTIONS
# ============================================================

def trapezoid_suitability(
    value: float,
    low: float,
    high: float,
    tolerance: float
) -> float:
    """
    Returns suitability between 0 and 1.

    1.0 = ideal range
    0.0 = completely unsuitable
    """

    if value is None:
        return 0.0

    value = float(value)

    if low <= value <= high:
        return 1.0

    if value < low:
        distance = low - value
    else:
        distance = value - high

    if tolerance <= 0:
        return 0.0

    return max(0.0, 1.0 - (distance / tolerance))


def threshold_suitability(
    value: float,
    threshold: float,
    span: float
) -> float:
    """
    Suitability for conditions where risk increases above
    a threshold.

    Example:
        RH >= threshold -> 1.0
        RH below threshold -> gradually decreases
    """

    if value is None:
        return 0.0

    value = float(value)

    if value >= threshold:
        return 1.0

    if span <= 0:
        return 0.0

    return max(0.0, 1.0 - ((threshold - value) / span))


def stage_suitability(
    growth_stage: str,
    stage_weights: Dict[str, float]
) -> float:
    """
    Returns disease susceptibility for the current crop stage.
    """

    if not growth_stage:
        return 0.0

    stage = str(growth_stage).upper().replace(" ", "_")

    return float(stage_weights.get(stage, 0.0))


# ============================================================
# 4. RAINFALL EVIDENCE
# ============================================================

def prepare_rainfall_evidence(
    current_rainfall: Optional[float],
    recent_rainfall: Optional[List[float]] = None,
    forecast_rainfall: Optional[List[float]] = None
) -> Dict[str, Any]:
    """
    Prepare rainfall evidence without treating missing rainfall as 0.

    Missing rainfall means unavailable data, NOT zero rainfall.
    """

    recent_values = [
        float(x)
        for x in (recent_rainfall or [])
        if x is not None
    ]

    forecast_values = [
        float(x)
        for x in (forecast_rainfall or [])
        if x is not None
    ]

    current_available = current_rainfall is not None

    recent_available = len(recent_values) > 0
    forecast_available = len(forecast_values) > 0

    recent_average = (
        sum(recent_values) / len(recent_values)
        if recent_available
        else None
    )

    forecast_average = (
        sum(forecast_values) / len(forecast_values)
        if forecast_available
        else None
    )

    # Combine ONLY available rainfall sources.
    combined_values = []

    if current_available:
        combined_values.append(float(current_rainfall))

    if recent_average is not None:
        combined_values.append(recent_average)

    if forecast_average is not None:
        combined_values.append(forecast_average)

    combined_average = (
        sum(combined_values) / len(combined_values)
        if combined_values
        else None
    )

    return {
        "current_rainfall": (
            float(current_rainfall)
            if current_available
            else None
        ),
        "recent_average": recent_average,
        "forecast_average": forecast_average,
        "combined_average": combined_average,

        "current_available": current_available,
        "recent_available": recent_available,
        "forecast_available": forecast_available,

        "available": bool(combined_values)
    }
def rainfall_suitability(
    disease_key: str,
    rainfall_evidence: Dict[str, Any]
) -> Optional[float]:
    """
    Calculate rainfall suitability using only available rainfall evidence.

    Returns None when no rainfall information is available.
    """

    rule = DISEASE_RULES[disease_key]["rainfall"]

    combined = rainfall_evidence.get("combined_average")

    # No rainfall information available.
    if combined is None:
        return None

    return trapezoid_suitability(
        combined,
        rule["low"],
        rule["high"],
        rule["tolerance"]
    )

# ============================================================
# 5. SHANNON ENTROPY WEIGHTS
# ============================================================

def calculate_entropy_weights(
    records: List[Dict[str, Any]],
    features: Optional[List[str]] = None
) -> Dict[str, float]:
    
    if not records:
        raise ValueError(
            "No reference records supplied for entropy calculation."
        )

    if features is None:
        features = [
            "temperature",
            "humidity",
            "rainfall",
            "stage"
        ]

    # --------------------------------------------------------
    # Extract valid numerical values
    # --------------------------------------------------------

    matrix = []

    for record in records:

        row = []

        for feature in features:

            value = record.get(feature)

            if value is None:
                value = 0.0

            row.append(float(value))

        matrix.append(row)

    n = len(matrix)

    if n == 0:
        raise ValueError("Reference dataset contains no usable rows.")

    # --------------------------------------------------------
    # Normalize each feature
    # --------------------------------------------------------

    normalized = []

    for j in range(len(features)):

        column = [
            matrix[i][j]
            for i in range(n)
        ]

        minimum = min(column)
        maximum = max(column)

        if maximum == minimum:
            normalized_column = [1.0] * n

        else:
            normalized_column = [
                (x - minimum) / (maximum - minimum)
                for x in column
            ]

        normalized.append(normalized_column)

    # --------------------------------------------------------
    # Shannon entropy
    # --------------------------------------------------------

    k = 1.0 / math.log(n) if n > 1 else 0.0

    entropy = []

    for column in normalized:

        total = sum(column)

        if total == 0:
            entropy.append(1.0)
            continue

        e = 0.0

        for value in column:

            if value <= 0:
                continue

            probability = value / total

            e -= probability * math.log(probability)

        e *= k

        entropy.append(e)

    # --------------------------------------------------------
    # Degree of diversification
    # --------------------------------------------------------

    diversification = [
        1.0 - e
        for e in entropy
    ]

    total_diversification = sum(diversification)

    if total_diversification == 0:

        equal_weight = 1.0 / len(features)

        return {
            feature: equal_weight
            for feature in features
        }

    weights = {
        feature: diversification[i] / total_diversification
        for i, feature in enumerate(features)
    }

    return weights


# ============================================================
# 6. RISK CLASSIFICATION
# ============================================================

def classify_risk(score: float) -> str:
    """
    Risk boundaries:

        0-24   LOW
        25-49  MEDIUM
        50-74  HIGH
        75-100 VERY HIGH
    """

    score = max(0.0, min(100.0, float(score)))

    if score < 25:
        return "LOW"

    if score < 50:
        return "MEDIUM"

    if score < 75:
        return "HIGH"

    return "VERY HIGH"


# ============================================================
# 7. DISEASE-SPECIFIC WEIGHT SELECTION
# ============================================================

def get_disease_weights(
    disease_key: str,
    entropy_weights: Optional[Dict[str, float]] = None
) -> Dict[str, float]:
    """
    Returns weights for one disease.

    Entropy weights are disease-specific.

    If no entropy weights are supplied, development fallback
    weights are used.
    """

    if entropy_weights is not None:

        required = [
            "temperature",
            "humidity",
            "rainfall",
            "stage"
        ]

        if all(key in entropy_weights for key in required):

            weights = {
                key: float(entropy_weights[key])
                for key in required
            }

            total = sum(weights.values())

            if total > 0:

                return {
                    key: value / total
                    for key, value in weights.items()
                }

    return REAL_WEIGHTS[disease_key].copy()


# ============================================================
# 8. SCORE ONE DISEASE
# ============================================================

def score_disease_risk(
    disease_key: str,
    weather: Dict[str, Any],
    growth_stage: str,
    recent_rainfall: Optional[List[float]] = None,
    forecast_rainfall: Optional[List[float]] = None,
    drought_result: Optional[Dict[str, Any]] = None,
    entropy_weights: Optional[Dict[str, float]] = None
) -> Dict[str, Any]:
    """
    Calculate risk score for one disease.

    Required weather fields:
        temperature
        humidity
        rainfall

    Optional:
        recent_rainfall
        forecast_rainfall
        drought_result

    State is intentionally NOT used in this calculation.
    """

    if disease_key not in DISEASE_RULES:
        raise ValueError(
            f"Unknown disease: {disease_key}"
        )

    rule = DISEASE_RULES[disease_key]

    # --------------------------------------------------------
    # Read weather
    # --------------------------------------------------------

    temperature = weather.get("temperature")
    humidity = weather.get("humidity")
    
    current_rainfall = weather.get("rainfall")

    if temperature is None:
        raise ValueError("Weather temperature is required.")

    if humidity is None:
        raise ValueError("Weather humidity is required.")

    # --------------------------------------------------------
    # Calculate rainfall evidence
    # --------------------------------------------------------

    rainfall_evidence = prepare_rainfall_evidence(
        current_rainfall=current_rainfall,
        recent_rainfall=recent_rainfall,
        forecast_rainfall=forecast_rainfall
    )

    # --------------------------------------------------------
    # Environmental suitability
    # --------------------------------------------------------

    temperature_score = trapezoid_suitability(
        temperature,
        rule["temperature"]["low"],
        rule["temperature"]["high"],
        rule["temperature"]["tolerance"]
    )

    humidity_score = threshold_suitability(
        humidity,
        rule["humidity"]["threshold"],
        rule["humidity"]["span"]
    )

    rainfall_score = rainfall_suitability(
        disease_key,
        rainfall_evidence
    )

    stage_score = stage_suitability(
        growth_stage,
        rule["stage_weights"]
    )

    # --------------------------------------------------------
    # Disease-specific weights
    # --------------------------------------------------------

    weights = get_disease_weights(
        disease_key,
        entropy_weights
    )

    # --------------------------------------------------------
    # Base score
    # --------------------------------------------------------

    factor_scores = {
    "temperature": temperature_score,
    "humidity": humidity_score,
    "rainfall": rainfall_score,
    "stage": stage_score,
    }

    available_factors = {
        key: value
        for key, value in factor_scores.items()
        if value is not None
    }

    available_weights = {
        key: weights[key]
        for key in available_factors
    }

    total_available_weight = sum(
        available_weights.values()
    )

    if total_available_weight <= 0:
        score = 0.0
    else:
        base_score = sum(
            available_factors[key]
            * (available_weights[key] / total_available_weight)
            for key in available_factors
        )

    score = base_score * 100.0

    # --------------------------------------------------------
    # Brown Spot + drought interaction
    # --------------------------------------------------------

    drought_modifier = 0.0

    if (
        disease_key == "BROWN_SPOT"
        and drought_result
    ):

        drought_level = str(
            drought_result.get("risk_level", "")
        ).upper()

        drought_modifier_map = {
            "LOW": 0.00,
            "MEDIUM": 0.03,
            "HIGH": 0.07
        }

        drought_modifier = drought_modifier_map.get(
            drought_level,
            0.0
        )

        score *= (1.0 + drought_modifier)

    # Keep score inside 0-100.
    score = max(0.0, min(100.0, score))

    # --------------------------------------------------------
    # Final classification
    # --------------------------------------------------------

    risk_level = classify_risk(score)

    return {
        "disease": disease_key,
        "disease_name": rule["name"],
        "score": round(score, 2),
        "risk_level": risk_level,

        "breakdown": {
        "temperature": round(temperature_score, 3),
        "humidity": round(humidity_score, 3),
        "rainfall": (
            round(rainfall_score, 3)
            if rainfall_score is not None
            else None
        ),
        "growth_stage": round(stage_score, 3)
        },

        "weights": {
            key: round(value, 4)
            for key, value in weights.items()
        },

        "rainfall_evidence": {
            key: (
                round(value, 2)
                if value is not None
                else None
            )
            for key, value in rainfall_evidence.items()
        },

        "drought_modifier": round(
            drought_modifier,
            4
        )
    }


# ============================================================
# 9. SCORE ALL SIX DISEASES
# ============================================================

def score_all_diseases(
    weather: Dict[str, Any],
    growth_stage: str,
    recent_rainfall: Optional[List[float]] = None,
    forecast_rainfall: Optional[List[float]] = None,
    drought_result: Optional[Dict[str, Any]] = None,
    entropy_weights_by_disease: Optional[
        Dict[str, Dict[str, float]]
    ] = None
) -> List[Dict[str, Any]]:
    """
    Calculate risk for all six diseases.

    Returns results sorted from highest to lowest risk.
    """

    results = []

    for disease_key in DISEASE_RULES:

        disease_weights = None

        if entropy_weights_by_disease:

            disease_weights = (
                entropy_weights_by_disease
                .get(disease_key)
            )

        result = score_disease_risk(
            disease_key=disease_key,
            weather=weather,
            growth_stage=growth_stage,
            recent_rainfall=recent_rainfall,
            forecast_rainfall=forecast_rainfall,
            drought_result=drought_result,
            entropy_weights=disease_weights
        )

        results.append(result)

    # Highest risk first.
    results.sort(
        key=lambda item: item["score"],
        reverse=True
    )

    return results


# ============================================================
# 10. RETURN ONLY TOP TWO
# ============================================================

def get_top_two_diseases(
    weather: Dict[str, Any],
    growth_stage: str,
    recent_rainfall: Optional[List[float]] = None,
    forecast_rainfall: Optional[List[float]] = None,
    drought_result: Optional[Dict[str, Any]] = None,
    entropy_weights_by_disease: Optional[
        Dict[str, Dict[str, float]]
    ] = None
) -> List[Dict[str, Any]]:
    """
    Calculate all six diseases internally and return only
    the two highest-risk diseases.
    """

    all_results = score_all_diseases(
        weather=weather,
        growth_stage=growth_stage,
        recent_rainfall=recent_rainfall,
        forecast_rainfall=forecast_rainfall,
        drought_result=drought_result,
        entropy_weights_by_disease=entropy_weights_by_disease
    )

    return all_results[:2]


# ============================================================
# 11. SIMPLE DEVELOPMENT TEST
# ============================================================

if __name__ == "__main__":

    weather = {
        "temperature": 30,
        "humidity": 90,
        "rainfall": 10
    }

    recent_rainfall = [
        2,
        4,
        1,
        3,
        2
    ]

    forecast_rainfall = [
        12,
        10,
        8,
        5,
        3,
        1,
        0
    ]

    drought_result = {
        "risk_level": "HIGH"
    }

    top_two = get_top_two_diseases(
        weather=weather,
        growth_stage="REPRODUCTIVE",
        recent_rainfall=recent_rainfall,
        forecast_rainfall=forecast_rainfall,
        drought_result=drought_result
    )

    print("\nTOP 2 RICE DISEASE RISKS")
    print("=" * 50)

    for result in top_two:

        print(
            f"{result['disease_name']}: "
            f"{result['score']} "
            f"({result['risk_level']})"
        )

        print(
            "Breakdown:",
            result["breakdown"]
        )

        print(
            "Weights:",
            result["weights"]
        )

        print()