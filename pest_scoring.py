# ============================================================
# RICE PEST SCORING
# Same scoring principle as disease_rules.py.
# ============================================================

from pests_rules import PEST_RULES, classify_risk


WEIGHTS = {
    "temperature": 0.25,
    "humidity": 0.20,
    "rainfall": 0.20,
    "growth_stage": 0.20,
    "dat": 0.15,
}


def trapezoid_suitability(value, low, high, tolerance):
    if value is None:
        return None

    value = float(value)

    if low <= value <= high:
        return 1.0

    if tolerance <= 0:
        return 0.0

    if value < low:
        distance = low - value
    else:
        distance = value - high

    return max(0.0, 1.0 - distance / tolerance)


def threshold_suitability(value, threshold, span):
    if value is None:
        return None

    value = float(value)

    if value >= threshold:
        return 1.0

    if span <= 0:
        return 0.0

    return max(0.0, 1.0 - (threshold - value) / span)


def stage_suitability(growth_stage, stage_weights):
    if not growth_stage:
        return None

    stage = str(growth_stage).upper().replace(" ", "_")
    return float(stage_weights.get(stage, 0.0))


def dat_suitability(dat, dat_rule):
    if dat is None:
        return None

    return trapezoid_suitability(
        float(dat),
        dat_rule["low"],
        dat_rule["high"],
        max(
            dat_rule["low"] * 0.5,
            (dat_rule["high"] - dat_rule["low"]) * 0.25,
        ),
    )


def rainfall_suitability(rainfall, rainfall_rule):
    if rainfall is None:
        return None

    return trapezoid_suitability(
        rainfall,
        rainfall_rule["low"],
        rainfall_rule["high"],
        rainfall_rule["tolerance"],
    )


def score_one_pest(
    pest_key,
    temperature,
    humidity,
    rainfall,
    growth_stage,
    dat=None,
):
    rule = PEST_RULES[pest_key]

    factors = {
        "temperature": trapezoid_suitability(
            temperature,
            rule["temperature"]["low"],
            rule["temperature"]["high"],
            rule["temperature"]["tolerance"],
        ),
        "humidity": threshold_suitability(
            humidity,
            rule["humidity"]["threshold"],
            rule["humidity"]["span"],
        ),
        "rainfall": rainfall_suitability(
            rainfall,
            rule["rainfall"],
        ),
        "growth_stage": stage_suitability(
            growth_stage,
            rule["stage_weights"],
        ),
        "dat": dat_suitability(dat, rule["dat"]),
    }

    available = {
        k: v for k, v in factors.items()
        if v is not None
    }

    available_weights = {
        k: WEIGHTS[k] for k in available
    }

    total_weight = sum(available_weights.values())

    if total_weight == 0:
        score = 0.0
    else:
        score = 100.0 * sum(
            available[k] *
            (available_weights[k] / total_weight)
            for k in available
        )

    return {
        "pest": pest_key,
        "pest_name": rule["name"],
        "score": round(score, 2),
        "risk_level": classify_risk(score),
        "breakdown": {
            key: round(value, 3) if value is not None else None
            for key, value in factors.items()
        },
        "data_type": "BIOLOGICAL_DEVELOPMENT_PRIOR",
    }


def score_all_pests(
    temperature,
    humidity,
    rainfall,
    growth_stage,
    dat=None,
):
    results = []

    for pest_key in PEST_RULES:
        results.append(
            score_one_pest(
                pest_key=pest_key,
                temperature=temperature,
                humidity=humidity,
                rainfall=rainfall,
                growth_stage=growth_stage,
                dat=dat,
            )
        )

    results.sort(
        key=lambda item: item["score"],
        reverse=True,
    )

    return results


if __name__ == "__main__":
    results = score_all_pests(
        temperature=30,
        humidity=85,
        rainfall=15,
        growth_stage="TILLERING",
        dat=45,
    )

    print("\nTOP RICE PEST RISKS")
    print("=" * 50)

    for item in results[:2]:
        print(
            f"{item['pest_name']}: "
            f"{item['score']} "
            f"({item['risk_level']})"
        )
        print("Breakdown:", item["breakdown"])
