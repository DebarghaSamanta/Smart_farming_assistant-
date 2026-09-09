import requests
from datetime import date, datetime, timedelta

from database import get_connection
from crop_context import get_crop_context


DRY_DAY_RAINFALL_THRESHOLD_MM = 1.0
DRY_SPELL_MIN_DAYS = 5
VPD_HIGH_THRESHOLD_KPA = 2.0
SOIL_DECLINE_MAJORITY_FRACTION = 0.5
TRAJECTORY_CHANGE_THRESHOLD = 0.05

# Lightweight AHP weights; provisional until historical outcomes are available.
EVIDENCE_WEIGHTS = {
    "soil_moisture_declining": 0.34087586,
    "seven_day_deficit": 0.19309838,
    "dry_spell": 0.19309838,
    "rainfall_below_normal": 0.10627857,
    "atmospheric_drying": 0.10627857,
    "rain_forecast_insufficient": 0.06037024,
}

AHP_CRITERIA = list(EVIDENCE_WEIGHTS)
AHP_PAIRWISE_MATRIX = [
    [1,   2,   2,   3,   3,   5],
    [1/2, 1,   1,   2,   2,   3],
    [1/2, 1,   1,   2,   2,   3],
    [1/3, 1/2, 1/2, 1,   1,   2],
    [1/3, 1/2, 1/2, 1,   1,   2],
    [1/5, 1/3, 1/3, 1/2, 1/2, 1],
]

MAX_POSSIBLE_SCORE = sum(EVIDENCE_WEIGHTS.values())


RISK_THRESHOLDS = {
    "LOW": 0.20,
    "MEDIUM": 0.45,
    "HIGH": 0.70,
}


def initialize_drought_tables():
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS rainfall_baseline (
            farm_id INTEGER NOT NULL,
            season TEXT NOT NULL,
            baseline_3day_mm REAL NOT NULL,
            baseline_7day_mm REAL NOT NULL,
            baseline_14day_mm REAL NOT NULL,
            baseline_30day_mm REAL NOT NULL,
            computed_on TEXT NOT NULL,
            PRIMARY KEY (farm_id, season),
            FOREIGN KEY (farm_id) REFERENCES farms(farm_id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS rainfall_log (
            farm_id INTEGER NOT NULL,
            log_date TEXT NOT NULL,
            rainfall_mm REAL NOT NULL,
            PRIMARY KEY (farm_id, log_date),
            FOREIGN KEY (farm_id) REFERENCES farms(farm_id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS drought_assessment_history (
            farm_id INTEGER NOT NULL,
            assessment_date TEXT NOT NULL,
            score REAL NOT NULL,
            risk_level TEXT NOT NULL,
            condition_state TEXT NOT NULL,
            PRIMARY KEY (farm_id, assessment_date),
            FOREIGN KEY (farm_id) REFERENCES farms(farm_id)
        )
    """)

    connection.commit()
    connection.close()


def fetch_historical_rainfall_baseline(
    latitude,
    longitude,
    sowing_date,
    years_back=10
):
    sowing = datetime.strptime(sowing_date, "%Y-%m-%d").date()
    all_daily_totals = []

    for year_offset in range(1, years_back + 1):
        try:
            window_start = sowing.replace(
                year=sowing.year - year_offset
            )
        except ValueError:
            window_start = sowing.replace(
                year=sowing.year - year_offset,
                day=28
            )

        window_end = window_start + timedelta(days=30)

        params = {
            "latitude": latitude,
            "longitude": longitude,
            "start_date": window_start.isoformat(),
            "end_date": window_end.isoformat(),
            "daily": "precipitation_sum",
            "timezone": "auto",
        }

        try:
            response = requests.get(
                "https://archive-api.open-meteo.com/v1/archive",
                params=params,
                timeout=10,
            )
        except requests.RequestException:
            continue

        if response.status_code != 200:
            continue

        daily_rain = response.json().get(
            "daily", {}
        ).get("precipitation_sum", [])

        if daily_rain:
            all_daily_totals.append(daily_rain)

    if not all_daily_totals:
        raise ConnectionError(
            "Could not fetch historical rainfall data for baseline."
        )

    num_days = min(
        len(year_data) for year_data in all_daily_totals
    )

    averaged_daily = [
        sum(
            year_data[day] or 0
            for year_data in all_daily_totals
        ) / len(all_daily_totals)
        for day in range(num_days)
    ]

    def rolling_sum(days):
        return round(sum(averaged_daily[:days]), 1)

    return {
        "baseline_3day_mm": rolling_sum(3),
        "baseline_7day_mm": rolling_sum(7),
        "baseline_14day_mm": rolling_sum(14),
        "baseline_30day_mm": rolling_sum(30),
    }


def get_rainfall_baseline(
    farm_id,
    latitude,
    longitude,
    sowing_date,
    season
):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT
            baseline_3day_mm,
            baseline_7day_mm,
            baseline_14day_mm,
            baseline_30day_mm
        FROM rainfall_baseline
        WHERE farm_id = ? AND season = ?
    """, (farm_id, season))

    row = cursor.fetchone()

    if row:
        connection.close()
        return {
            "baseline_3day_mm": row["baseline_3day_mm"],
            "baseline_7day_mm": row["baseline_7day_mm"],
            "baseline_14day_mm": row["baseline_14day_mm"],
            "baseline_30day_mm": row["baseline_30day_mm"],
        }

    baseline = fetch_historical_rainfall_baseline(
        latitude,
        longitude,
        sowing_date,
    )

    cursor.execute("""
        INSERT INTO rainfall_baseline
        (
            farm_id,
            season,
            baseline_3day_mm,
            baseline_7day_mm,
            baseline_14day_mm,
            baseline_30day_mm,
            computed_on
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        farm_id,
        season,
        baseline["baseline_3day_mm"],
        baseline["baseline_7day_mm"],
        baseline["baseline_14day_mm"],
        baseline["baseline_30day_mm"],
        date.today().isoformat(),
    ))

    connection.commit()
    connection.close()

    return baseline


def log_daily_rainfall(farm_id, log_date, rainfall_mm):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        INSERT OR REPLACE INTO rainfall_log
        (farm_id, log_date, rainfall_mm)
        VALUES (?, ?, ?)
    """, (farm_id, log_date, rainfall_mm))

    connection.commit()
    connection.close()


def get_recent_rainfall_log(farm_id, days):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT rainfall_mm
        FROM rainfall_log
        WHERE farm_id = ?
        ORDER BY log_date DESC
        LIMIT ?
    """, (farm_id, days))

    rows = cursor.fetchall()
    connection.close()

    return [
        row["rainfall_mm"]
        for row in reversed(rows)
    ]


def get_recent_rainfall_records(farm_id, days, as_of_date=None):
    as_of = as_of_date or date.today().isoformat()
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute("""
        SELECT log_date, rainfall_mm
        FROM rainfall_log
        WHERE farm_id = ? AND log_date <= ?
        ORDER BY log_date DESC
        LIMIT ?
    """, (farm_id, as_of, days))
    rows = cursor.fetchall()
    connection.close()
    return [
        {"date": row["log_date"], "rainfall_mm": row["rainfall_mm"]}
        for row in reversed(rows)
    ]


def _window_status(records, required_days, as_of_date=None):
    if not records:
        return "UNAVAILABLE", 0
    as_of = datetime.strptime(as_of_date or date.today().isoformat(), "%Y-%m-%d").date()
    dates = [datetime.strptime(r["date"], "%Y-%m-%d").date() for r in records]
    if dates[-1] != as_of:
        return "PARTIAL", len(records)
    for a, b in zip(dates, dates[1:]):
        if (b - a).days != 1:
            return "UNAVAILABLE", len(records)
    if len(records) < required_days:
        return "PARTIAL", len(records)
    return "COMPLETE", len(records)


def check_rainfall_below_normal(
    recent_30day_sum, baseline_30day_mm, observed_days=None, window_days=30
):
    if baseline_30day_mm is None or baseline_30day_mm <= 0:
        return None
    expected = baseline_30day_mm
    if observed_days is not None and observed_days < window_days:
        expected = baseline_30day_mm * observed_days / window_days
    if expected <= 0:
        return None
    return ((expected - recent_30day_sum) / expected * 100) >= 25


def check_seven_day_deficit(
    recent_7day_sum, baseline_7day_mm, observed_days=None
):
    if baseline_7day_mm is None or baseline_7day_mm <= 0:
        return None
    expected = baseline_7day_mm
    if observed_days is not None and observed_days < 7:
        expected = baseline_7day_mm * observed_days / 7
    if expected <= 0:
        return None
    return ((expected - recent_7day_sum) / expected * 100) >= 25


def count_consecutive_dry_days(daily_rainfall_log):
    count = 0

    for value in reversed(daily_rainfall_log):
        if value is None:
            break

        if value < DRY_DAY_RAINFALL_THRESHOLD_MM:
            count += 1
        else:
            break

    return count


def check_dry_spell(daily_rainfall_log):
    return (
        count_consecutive_dry_days(daily_rainfall_log)
        >= DRY_SPELL_MIN_DAYS
    )


def check_soil_moisture_declining(node_trends):
    total_nodes = len(node_trends)

    if total_nodes == 0:
        return None, 0, 0

    declining_count = sum(
        1
        for trend in node_trends.values()
        if trend == "DECREASING"
    )

    return (
        declining_count / total_nodes
        >= SOIL_DECLINE_MAJORITY_FRACTION,
        declining_count,
        total_nodes,
    )


def calculate_vpd_kpa(air_temp_c, humidity_pct):
    if air_temp_c is None or humidity_pct is None:
        return None
    if humidity_pct < 0 or humidity_pct > 100:
        return None
    saturation_vp = 0.6108 * __import__("math").exp(
        (17.27 * air_temp_c) / (air_temp_c + 237.3)
    )
    return saturation_vp * (1 - humidity_pct / 100.0)


def check_atmospheric_drying(air_temp_c, humidity_pct):
    vpd_kpa = calculate_vpd_kpa(air_temp_c, humidity_pct)
    if vpd_kpa is None:
        return None, None
    return vpd_kpa >= VPD_HIGH_THRESHOLD_KPA, vpd_kpa


def check_rain_forecast_insufficient(
    forecast_7day_sum,
    baseline_7day_mm
):
    if forecast_7day_sum is None or baseline_7day_mm is None or baseline_7day_mm <= 0:
        return None

    return forecast_7day_sum < (
        baseline_7day_mm * 0.4
    )


def fuse_drought_evidence(evidence, drought_sensitivity=1.0):
    available_weight = sum(
        EVIDENCE_WEIGHTS[key]
        for key, value in evidence.items()
        if key in EVIDENCE_WEIGHTS and value is not None
    )
    positive_weight = sum(
        EVIDENCE_WEIGHTS[key]
        for key, value in evidence.items()
        if key in EVIDENCE_WEIGHTS and value is True
    )

    if available_weight == 0:
        return 0.0, "NONE", [], 0.0

    # CHANGED (option 2): renormalize against what was actually
    # available, not the full weight table. A farm with only 2 of
    # 6 signals reporting is now judged on those 2 signals' own
    # severity, not diluted against 4 checks that never ran.
    # `coverage` still reports how much of the full picture that is,
    # so low-coverage assessments are noisier but no longer silently
    # suppressed toward NONE/LOW regardless of what little evidence says.
    raw_fraction = positive_weight / available_weight
    sensitivity = max(0.0, min(1.0, drought_sensitivity))
    adjusted_score = raw_fraction * (0.5 + 0.5 * sensitivity)
    coverage = available_weight / MAX_POSSIBLE_SCORE

    if adjusted_score >= RISK_THRESHOLDS["HIGH"]:
        risk_level = "HIGH"
    elif adjusted_score >= RISK_THRESHOLDS["MEDIUM"]:
        risk_level = "MEDIUM"
    elif adjusted_score >= RISK_THRESHOLDS["LOW"]:
        risk_level = "LOW"
    else:
        risk_level = "NONE"

    active_evidence = [
        key for key, value in evidence.items()
        if value is True
    ]
    return adjusted_score, risk_level, active_evidence, coverage


def get_previous_assessment(farm_id, as_of_date=None, days_ago=1):
    connection = get_connection()
    cursor = connection.cursor()
    base = datetime.strptime(as_of_date or date.today().isoformat(), "%Y-%m-%d").date()
    target_date = (base - timedelta(days=days_ago)).isoformat()
    cursor.execute("""
        SELECT score, risk_level, condition_state
        FROM drought_assessment_history
        WHERE farm_id = ? AND assessment_date <= ?
        ORDER BY assessment_date DESC
        LIMIT 1
    """, (farm_id, target_date))
    row = cursor.fetchone()
    connection.close()
    if row is None:
        return None
    return {"score": row["score"], "risk_level": row["risk_level"], "condition_state": row["condition_state"]}


def compute_trajectory(current_score, previous_score):
    if previous_score is None:
        return "STABLE"

    delta = current_score - previous_score

    if delta >= TRAJECTORY_CHANGE_THRESHOLD:
        return "WORSENING"

    if delta <= -TRAJECTORY_CHANGE_THRESHOLD:
        return "IMPROVING"

    return "STABLE"


def classify_condition_state(
    previous_state,
    risk_level,
    trajectory
):
    if previous_state is None:
        previous_state = "NORMAL"

    if (
        risk_level in ("NONE", "LOW")
        and trajectory in ("STABLE", "IMPROVING")
        and previous_state in ("NORMAL", "RECOVERING")
    ):
        return "NORMAL"

    if (
        trajectory == "IMPROVING"
        and previous_state
        in ("WATCH", "DEVELOPING", "HIGH RISK")
    ):
        return "RECOVERING"

    if (
        trajectory == "WORSENING"
        and previous_state
        in ("NORMAL", "RECOVERING")
        and risk_level in ("LOW", "MEDIUM")
    ):
        return "WATCH"

    if trajectory == "WORSENING":
        return "DEVELOPING"

    if (
        trajectory == "STABLE"
        and risk_level == "HIGH"
    ):
        return "HIGH RISK"

    return previous_state


def save_assessment(
    farm_id,
    score,
    risk_level,
    condition_state,
    assessment_date=None
):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        INSERT OR REPLACE INTO drought_assessment_history
        (
            farm_id,
            assessment_date,
            score,
            risk_level,
            condition_state
        )
        VALUES (?, ?, ?, ?, ?)
    """, (
        farm_id,
        assessment_date or date.today().isoformat(),
        score,
        risk_level,
        condition_state,
    ))

    connection.commit()
    connection.close()


def assess_drought_risk(
    farm_id, latitude, longitude, crop, state, sowing_date, season,
    node_trends, air_temp_c, humidity_pct, forecast_7day_rainfall_mm,
    current_date=None,
):
    initialize_drought_tables()
    as_of_date = current_date or date.today().isoformat()

    crop_context = get_crop_context(
        crop=crop, state=state, season=season, sowing_date=sowing_date,
        current_date=as_of_date,
    )
    if not crop_context["available"]:
        return {"available": False, "reason": "Crop context unavailable.", "crop_context": crop_context}

    baseline = get_rainfall_baseline(farm_id, latitude, longitude, sowing_date, season)
    records = get_recent_rainfall_records(farm_id, 30, as_of_date)
    status_7, observed_7 = _window_status(records[-7:], 7, as_of_date)
    status_30, observed_30 = _window_status(records, 30, as_of_date)

    recent_7day_sum = sum(r["rainfall_mm"] for r in records[-7:])
    recent_30day_sum = sum(r["rainfall_mm"] for r in records)
    vpd_high, vpd_kpa = check_atmospheric_drying(air_temp_c, humidity_pct)
    soil_evidence = check_soil_moisture_declining(node_trends)[0]

    evidence = {
        "rainfall_below_normal": (
            check_rainfall_below_normal(recent_30day_sum, baseline["baseline_30day_mm"], observed_30, 30)
            if status_30 != "UNAVAILABLE" else None
        ),
        "seven_day_deficit": (
            check_seven_day_deficit(recent_7day_sum, baseline["baseline_7day_mm"], observed_7)
            if status_7 != "UNAVAILABLE" else None
        ),
        # FIXED: now gated on status_30 like the other rainfall checks.
        # Previously this ran on `records` regardless of gaps, so a
        # logging gap got silently glued into one long dry streak
        # (proven: 3 dry + 2-day gap + 3 dry days = false 6-day streak).
        "dry_spell": (
            check_dry_spell([r["rainfall_mm"] for r in records])
            if records and status_30 != "UNAVAILABLE" else None
        ),
        "soil_moisture_declining": soil_evidence,
        "atmospheric_drying": vpd_high,
        "rain_forecast_insufficient": check_rain_forecast_insufficient(
            forecast_7day_rainfall_mm, baseline["baseline_7day_mm"]
        ),
    }

    score, risk_level, active_evidence, coverage = fuse_drought_evidence(
        evidence, crop_context["drought_sensitivity"]
    )
    previous = get_previous_assessment(farm_id, as_of_date=as_of_date)
    previous_score = previous["score"] if previous else None
    previous_state = previous["condition_state"] if previous else None
    trajectory = compute_trajectory(score, previous_score)
    condition_state = classify_condition_state(previous_state, risk_level, trajectory)
    save_assessment(farm_id, score, risk_level, condition_state, assessment_date=as_of_date)

    return {
        "available": True, "condition_state": condition_state, "risk_level": risk_level,
        "trajectory": trajectory, "drought_probability": round(score, 3),
        "probability_calibrated": False,
        "score_interpretation": "uncalibrated evidence-derived likelihood score",
        "drought_sensitivity": crop_context["drought_sensitivity"],
        "growth_stage": crop_context["growth_stage"], "critical_stage": crop_context["critical_stage"],
        "active_evidence": active_evidence, "evidence": evidence,
        "evidence_coverage": round(coverage, 3),
        "data_quality": {"rainfall_7day": status_7, "rainfall_30day": status_30, "vpd_kpa": vpd_kpa},
        "recent_7day_rainfall_mm": round(recent_7day_sum, 1),
        "recent_30day_rainfall_mm": round(recent_30day_sum, 1),
        "forecast_7day_rainfall_mm": forecast_7day_rainfall_mm,
        "baseline": baseline, "crop_context": crop_context,
    }