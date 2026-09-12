# ============================================================
# demo_judges.py
# ============================================================
#
# Backend for the "Demo Control" panel judges will click through:
#
#       Week: 1 / 2 / 3
#       Module: Drought / Disease / Pest / NPK
#       Level: LOW / HIGH
#
# This file is the only thing that turns those three picks into
# real rows in farm.db. It does NOT reimplement any scoring logic.
# Every risk number shown to the judge comes from your existing
# drought_risk.py / disease_rules.py / pest_scoring.py, unchanged.
#
# NPK is a camera-only module (leaf photo -> N/P/K deficiency).
# It has no sensor/rainfall inputs, so there is nothing to
# simulate for it here -- it stays a manual "upload a photo" step,
# same as the disease/pest camera confirmation. That is what
# "keeps the camera separate" means in the flow diagram.
#
# WHY A SIMULATED CLOCK
# --------------------------------------------------------------
# Your rice calendar (crop_calendar.py) only accepts a sowing
# date whose MONTH falls inside a configured season window (e.g.
# AMAN in West Bengal = June/July). If "Week 1" were built as
# "real today minus 8 days", the demo would only work on days
# where that lands in June/July -- i.e. it would break depending
# on which day judges happen to run it.
#
# So this file never touches the real wall-clock date for
# anything that affects growth stage or rainfall windows. It
# fixes one sowing date (DEMO_SOWING_DATE, in June) and treats
# "the current date" as DEMO_SOWING_DATE + N days, where N is
# whatever WEEK_DAYS_AFTER_SOWING[week] says. Every sensor
# reading, rainfall-log day and weather-forecast day is written
# relative to that SIMULATED date, not the real one. The demo
# behaves identically today, next month, or during the actual
# judging round.
#
# HOW "LOW" / "HIGH" IS PRODUCED, PER MODULE
# --------------------------------------------------------------
# Drought:
#   The 6 evidence checks in drought_risk.py are plain booleans
#   (rainfall below normal? dry spell? soil moisture declining?
#   VPD high? forecast rain insufficient?). There is nothing to
#   "search" for -- every input is set in the same direction at
#   once (all-dry for HIGH, all-wet for LOW). See DROUGHT_PRESETS.
#
# Disease / Pest:
#   These ARE smooth scoring functions (temperature/humidity/
#   rainfall suitability curves). Instead of hand-guessing
#   numbers, this file runs an actual grid search: it tries a
#   grid of (temperature, humidity, rainfall) combinations through
#   your real score_disease_risk() / score_one_pest() functions
#   and keeps whichever combination pushes the highest-scoring
#   disease/pest furthest toward HIGH or LOW. Whatever the search
#   finds is exactly what gets written into the database.
#
# CAVEAT (told to Leo in chat, repeated here in code):
#   Growth-stage susceptibility is a FIXED weight in your rules
#   (e.g. TUNGRO is 100% susceptible at ESTABLISHMENT). Even with
#   the worst possible weather, that fixed weight puts a floor
#   under the score. So "LOW" means "the lowest this stage can
#   reach", not a guaranteed sub-25 score. The search always
#   reports the score it actually found, so nobody is surprised.
# ============================================================

from __future__ import annotations

import argparse
import json
from datetime import date, datetime, timedelta

from database import (
    create_database,
    get_connection,
    register_farmer,
    register_farm,
    create_field,
    register_crop,
    register_device,
)
from sensor_repository import register_sensor_node
from weather_repository import store_weather_forecast

from drought_risk import (
    initialize_drought_tables,
    log_daily_rainfall,
    assess_drought_risk,
)
from farm_state import (
    build_farm_state,
    build_crop_context,
    get_drought_node_trends,
)
from disease_predictor import predict_disease_risk
from pest_predictor import predict_pest_risk
from disease_rules import DISEASE_RULES, score_disease_risk
from pests_rules import PEST_RULES
from pest_scoring import score_one_pest
from alert_controller import (
    build_drought_message,
    should_send_alert,
    send_judge_alert,
)


# ============================================================
# FIXED DEMO IDENTITY
# One demo farmer/farm/field/crop/device. Reused on every call
# instead of creating a new one each time, so a judge can click
# through Week/Module/Level repeatedly without piling up junk
# rows in farm.db.
# ============================================================

DEMO_PHONE = "+918777786405"       
DEMO_NAME = "Judge Demo Farm"
DEMO_LANGUAGE = "English"
DEMO_LATITUDE = 22.5726
DEMO_LONGITUDE = 88.3639
DEMO_STATE = "West Bengal"
DEMO_SEASON = "AMAN"
DEMO_CROP = "Rice"
DEMO_DEVICE_ID = "DEMO-JUDGE-0001"

# Always within AMAN's configured months [6, 7] for West Bengal,
# regardless of which real-world date the demo is run on.
DEMO_SOWING_DATE = date(2026, 6, 1)

NODE_OFFSETS = {
    "NW": (-0.0005, -0.0005),
    "NE": (-0.0005, 0.0005),
    "SW": (0.0005, -0.0005),
    "SE": (0.0005, 0.0005),
}

# "Week 1/2/3" maps to days-after-sowing values that land solidly
# inside three different growth stages (thresholds come from
# crop_calendar.calculate_growth_stage; AMAN duration = 150 days),
# so judges can see the crop's stage -- and which disease/pest
# tops the list -- actually change between weeks.
WEEK_DAYS_AFTER_SOWING = {
    1: 8,    # progress 0.05  -> ESTABLISHMENT
    2: 55,   # progress 0.37  -> TILLERING
    3: 95,   # progress 0.63  -> REPRODUCTIVE
}

# Synthetic monsoon-season rainfall baseline for the demo farm.
# Written straight into the DB so the drought engine never has to
# reach out to the Open-Meteo archive API over the network during
# a live demo (no wifi, no flaky judge-day surprises).
DEMO_RAINFALL_BASELINE_MM = {
    "baseline_3day_mm": 15.0,
    "baseline_7day_mm": 40.0,
    "baseline_14day_mm": 70.0,
    "baseline_30day_mm": 150.0,
}

# Hand-picked, all-evidence-agrees presets for the drought module.
DROUGHT_PRESETS = {
    "HIGH": {
        "temperature": 34.0,
        "humidity": 36.0,
        "soil_moisture_start": 42.0,
        "soil_moisture_end": 24.0,   # declining trend
        "daily_rainfall_mm": 0.0,    # dry spell + big deficit
    },
    "LOW": {
        "temperature": 27.0,
        "humidity": 78.0,
        "soil_moisture_start": 34.0,
        "soil_moisture_end": 42.0,   # improving/stable trend
        "daily_rainfall_mm": 9.0,    # comfortably above baseline
    },
}

# Grid the search tries for disease/pest scenarios. Coarse enough
# to run in well under a second, fine enough to find real HIGH/LOW.
SEARCH_TEMPERATURE_RANGE = range(15, 41, 1)      # deg C
SEARCH_HUMIDITY_RANGE = range(30, 101, 5)        # %
SEARCH_RAINFALL_RANGE = [0, 2, 5, 8, 10, 15, 20, 25, 30, 40, 50, 60, 80, 100]  # mm/day


# ============================================================
# DEMO FARM: CREATE ONCE, REUSE AFTER THAT
# ============================================================

def get_or_create_demo_farm():
    """
    Returns (farmer_id, farm_id, field_id, crop_id) for the fixed
    demo farm, creating it (farmer + farm + field + crop + device
    + 4 sensor nodes) the first time this is ever called.
    """

    create_database()
    initialize_drought_tables()

    connection = get_connection()
    farmer_row = connection.execute(
        "SELECT farmer_id FROM farmers WHERE phone_number = ?",
        (DEMO_PHONE,),
    ).fetchone()

    if farmer_row is not None:
        farmer_id = farmer_row["farmer_id"]

        farm_row = connection.execute(
            "SELECT farm_id FROM farms WHERE farmer_id = ?",
            (farmer_id,),
        ).fetchone()
        farm_id = farm_row["farm_id"]

        field_row = connection.execute(
            "SELECT field_id FROM fields WHERE farm_id = ?",
            (farm_id,),
        ).fetchone()
        field_id = field_row["field_id"]

        crop_row = connection.execute(
            """
            SELECT crop_id FROM crops
            WHERE field_id = ?
            ORDER BY crop_id DESC LIMIT 1
            """,
            (field_id,),
        ).fetchone()
        crop_id = crop_row["crop_id"]

        connection.close()
        return farmer_id, farm_id, field_id, crop_id

    connection.close()

    # First run ever: build the demo farm from scratch.
    farmer_id = register_farmer(DEMO_NAME, DEMO_PHONE, DEMO_LANGUAGE)
    farm_id = register_farm(
        farmer_id, DEMO_LATITUDE, DEMO_LONGITUDE, DEMO_STATE,
        "UNKNOWN", None,
    )
    field_id = create_field(farm_id)

    crop_id = register_crop(
        field_id, DEMO_SOWING_DATE.isoformat(), DEMO_SEASON, DEMO_CROP,
    )

    register_device(DEMO_DEVICE_ID, field_id, "ACTIVE")

    for position, (dlat, dlon) in NODE_OFFSETS.items():
        register_sensor_node(
            sensor_node_id=f"{DEMO_DEVICE_ID}-{position}",
            device_id=DEMO_DEVICE_ID,
            grid_position=position,
            latitude=DEMO_LATITUDE + dlat,
            longitude=DEMO_LONGITUDE + dlon,
        )

    return farmer_id, farm_id, field_id, crop_id


def _ensure_rainfall_baseline(farm_id, as_of_date):
    """
    Insert the synthetic baseline once. get_rainfall_baseline() in
    drought_risk.py checks the DB first and only calls the live
    weather API if no row exists -- so this is what makes the demo
    fully offline-safe.
    """

    connection = get_connection()
    existing = connection.execute(
        "SELECT 1 FROM rainfall_baseline WHERE farm_id = ? AND season = ?",
        (farm_id, DEMO_SEASON),
    ).fetchone()

    if existing is None:
        connection.execute(
            """
            INSERT INTO rainfall_baseline
                (farm_id, season, baseline_3day_mm, baseline_7day_mm,
                 baseline_14day_mm, baseline_30day_mm, computed_on)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                farm_id,
                DEMO_SEASON,
                DEMO_RAINFALL_BASELINE_MM["baseline_3day_mm"],
                DEMO_RAINFALL_BASELINE_MM["baseline_7day_mm"],
                DEMO_RAINFALL_BASELINE_MM["baseline_14day_mm"],
                DEMO_RAINFALL_BASELINE_MM["baseline_30day_mm"],
                as_of_date.isoformat(),
            ),
        )
        connection.commit()

    connection.close()


def set_week(field_id, crop_id, week):
    """
    Keeps the crop's sowing_date fixed at DEMO_SOWING_DATE and
    returns the SIMULATED "current date" for this week (sowing +
    N days), plus the crop context (growth_stage, days_after_
    sowing, ...) as of that simulated date. Uses your existing
    get_crop_context() so growth-stage thresholds are never
    duplicated here.
    """

    if week not in WEEK_DAYS_AFTER_SOWING:
        raise ValueError("week must be 1, 2 or 3.")

    connection = get_connection()
    connection.execute(
        "UPDATE crops SET sowing_date = ? WHERE crop_id = ?",
        (DEMO_SOWING_DATE.isoformat(), crop_id),
    )
    connection.commit()
    connection.close()

    simulated_date = DEMO_SOWING_DATE + timedelta(
        days=WEEK_DAYS_AFTER_SOWING[week]
    )

    context = build_crop_context(
        field_id=field_id,
        state=DEMO_STATE,
        current_date=simulated_date.isoformat(),
    )

    if not context.get("available"):
        raise ValueError(
            f"Could not build crop context for week {week}: "
            f"{context.get('reason')}"
        )

    return DEMO_SOWING_DATE.isoformat(), simulated_date, context


# ============================================================
# SEEDING SENSOR READINGS / RAINFALL / FORECAST
# All of these are anchored to the SIMULATED date, never to the
# real wall-clock date.
# ============================================================

def _seed_sensor_history(
    simulated_date,
    temperature,
    humidity,
    soil_moisture_start,
    soil_moisture_end,
    rain_detected=0,
    hours_back=9,
    reading_count=10,
):
    """
    Writes `reading_count` hourly readings per node, oldest to
    newest, ending at noon on `simulated_date`. Soil moisture
    ramps from start -> end so build_node_trends() (farm_state.py)
    picks up a clear INCREASING/DECREASING/STABLE trend. Air
    temperature/humidity only need to be right on the LATEST
    reading -- that's the one spatial_state averages -- so the
    small per-node jitter below is just for realism.
    """

    connection = get_connection()
    end = datetime(
        simulated_date.year, simulated_date.month, simulated_date.day, 12, 0, 0
    )
    start = end - timedelta(hours=hours_back)

    node_jitter = {
        "NW": (-0.2, 1.0), "NE": (0.3, -1.0),
        "SW": (-0.3, 1.0), "SE": (0.2, -1.0),
    }

    for position, (temp_jitter, hum_jitter) in node_jitter.items():
        node_id = f"{DEMO_DEVICE_ID}-{position}"

        for i in range(reading_count):
            progress = i / (reading_count - 1)
            soil_moisture = round(
                soil_moisture_start
                + (soil_moisture_end - soil_moisture_start) * progress,
                2,
            )
            timestamp = (start + timedelta(hours=i)).isoformat(
                timespec="seconds"
            )
            node_temperature = round(temperature + temp_jitter, 2)
            node_humidity = round(humidity + hum_jitter, 2)

            connection.execute(
                """
                INSERT INTO sensor_readings
                    (sensor_node_id, timestamp, air_temperature,
                     air_humidity, soil_temperature, soil_moisture,
                     rain_detected, water_level, leaf_temperature)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    node_id,
                    timestamp,
                    node_temperature,
                    node_humidity,
                    round(node_temperature - 2, 2),
                    soil_moisture,
                    rain_detected,
                    round(max(soil_moisture / 10, 0.5), 2),
                    round(node_temperature - 1, 2),
                ),
            )

    connection.commit()
    connection.close()


def _seed_rainfall_log(farm_id, daily_mm, simulated_date, days=30):
    for i in range(days):
        day = simulated_date - timedelta(days=days - 1 - i)
        log_daily_rainfall(farm_id, day.isoformat(), float(daily_mm))


def _clear_weather_forecast(farm_id):
    """
    weather_repository.get_weather_forecast(farm_id) returns EVERY
    forecast row ever stored for this farm, with no date filter.
    Since the demo farm is reused across every week/module/level
    combination, an old run's forecast rows would otherwise still
    be sitting in the table and leak into farm_state["weather"]
    (disease_predictor.py reads forecast[0] off that list, so a
    stale leftover row silently overrides the one we just seeded).
    Wiping the table before every reseed keeps each run isolated.
    """

    connection = get_connection()
    connection.execute(
        "DELETE FROM weather_forecasts WHERE farm_id = ?", (farm_id,)
    )
    connection.commit()
    connection.close()


def _seed_weather_forecast(
    farm_id, daily_mm, temperature, humidity, simulated_date, days=7
):
    _clear_weather_forecast(farm_id)

    for i in range(days):
        day = simulated_date + timedelta(days=i)
        store_weather_forecast(
            farm_id,
            day.isoformat(),
            temperature_min=round(temperature - 3, 1),
            temperature_max=round(temperature + 3, 1),
            humidity=humidity,
            rainfall=float(daily_mm),
            rainfall_probability=90.0 if daily_mm > 5 else 10.0,
            wind_speed=8.0,
            weather_description="Judge demo synthetic forecast",
        )


# ============================================================
# THE ACTUAL SEARCH (disease / pest only)
# ============================================================

def _max_disease_score(temperature, humidity, rainfall, growth_stage):
    best = 0.0
    for disease_key in DISEASE_RULES:
        result = score_disease_risk(
            disease_key=disease_key,
            weather={
                "temperature": temperature,
                "humidity": humidity,
                "rainfall": rainfall,
            },
            growth_stage=growth_stage,
            recent_rainfall=[rainfall] * 7,
            forecast_rainfall=[rainfall] * 7,
            drought_result=None,
        )
        best = max(best, result["score"])
    return best


def _max_pest_score(temperature, humidity, rainfall_7day_sum, growth_stage, dat):
    # NOTE: pest_predictor.py resolves "rainfall" as a 7-DAY TOTAL
    # (extract_pest_inputs -> rainfall["7day_sum_mm"]), not a daily
    # amount. disease_predictor.py resolves it as a single day's
    # forecast instead. Same word, different meaning -- this search
    # has to match pest's meaning, or the seeded data won't produce
    # the score the search found.
    best = 0.0
    for pest_key in PEST_RULES:
        result = score_one_pest(
            pest_key=pest_key,
            temperature=temperature,
            humidity=humidity,
            rainfall=rainfall_7day_sum,
            growth_stage=growth_stage,
            dat=dat,
        )
        best = max(best, result["score"])
    return best


def _search_environment(score_fn, target_level):
    """
    Grid search over (temperature, humidity, rainfall). score_fn
    takes those 3 values and returns "how risky is the worst
    disease/pest under this weather". Keeps whichever combination
    pushes that number highest (HIGH) or lowest (LOW).
    """

    best_score = None
    best_combo = None

    for temperature in SEARCH_TEMPERATURE_RANGE:
        for humidity in SEARCH_HUMIDITY_RANGE:
            for rainfall in SEARCH_RAINFALL_RANGE:
                score = score_fn(temperature, humidity, rainfall)

                if best_score is None:
                    is_better = True
                elif target_level == "HIGH":
                    is_better = score > best_score
                else:
                    is_better = score < best_score

                if is_better:
                    best_score = score
                    best_combo = (temperature, humidity, rainfall)

    temperature, humidity, rainfall = best_combo
    return {
        "temperature": temperature,
        "humidity": humidity,
        "rainfall": rainfall,
        "predicted_score": round(best_score, 2),
        "candidates_tried": (
            len(SEARCH_TEMPERATURE_RANGE)
            * len(SEARCH_HUMIDITY_RANGE)
            * len(SEARCH_RAINFALL_RANGE)
        ),
    }


# ============================================================
# RUNNING THE REAL ENGINES ON WHATEVER WAS SEEDED
# ============================================================

def _run_drought(farm_state, farm_id, sowing_date, simulated_date):
    weather = farm_state.get("weather") or []
    forecast_sum = sum(float(row.get("rainfall") or 0) for row in weather[:7])
    node_trends = get_drought_node_trends(farm_state)
    spatial = farm_state["spatial_state"]

    return assess_drought_risk(
        farm_id=farm_id,
        latitude=DEMO_LATITUDE,
        longitude=DEMO_LONGITUDE,
        crop=DEMO_CROP,
        state=DEMO_STATE,
        sowing_date=sowing_date,
        season=DEMO_SEASON,
        node_trends=node_trends,
        air_temp_c=spatial["air_temperature"]["average"],
        humidity_pct=spatial["air_humidity"]["average"],
        forecast_7day_rainfall_mm=forecast_sum,
        current_date=simulated_date.isoformat(),
    )


def _summarize_farm_state(farm_state):
    spatial = farm_state["spatial_state"]
    return {
        "device_id": farm_state["device_id"],
        "air_temperature_c": round(spatial["air_temperature"]["average"], 2),
        "air_humidity_pct": round(spatial["air_humidity"]["average"], 2),
        "soil_moisture_pct": round(spatial["soil_moisture"]["average"], 2),
        "node_soil_moisture_trends": {
            position: node["trends"]["soil_moisture"]
            for position, node in farm_state["sensor_nodes"].items()
        },
    }


def _build_alert(module, drought_result, disease_result, pest_result):
    """
    Decides the SMS-worthy message for whichever module the judge
    picked. This only decides whether an alert WOULD go out -- it
    never calls send_sms() itself, so a live judge demo never
    fires a real text message by accident.
    """

    if module == "DROUGHT" and drought_result and drought_result.get("available"):
        return {
            "should_send_sms": should_send_alert(drought_result),
            "message": build_drought_message(drought_result),
        }

    if module == "DISEASE" and disease_result and disease_result.get("available"):
        top = disease_result["top_two"][0]
        alert_needed = top["risk_level"] in ("HIGH", "VERY HIGH")
        message = (
            f"Smart Farming Alert: {top['disease_name']} risk is "
            f"{top['risk_level']} (score {top['score']}) at the "
            f"{disease_result['growth_stage']} stage. Inspect the crop; "
            "a leaf photo can confirm this with the camera model."
            if alert_needed else
            f"{top['disease_name']} risk is currently {top['risk_level']}. "
            "No action needed."
        )
        return {"should_send_sms": alert_needed, "message": message}

    if module == "PEST" and pest_result and pest_result.get("available"):
        top = pest_result["top_two"][0]
        alert_needed = top["risk_level"] in ("HIGH", "VERY HIGH")
        message = (
            f"Smart Farming Alert: {top['pest_name']} risk is "
            f"{top['risk_level']} (score {top['score']}) at the "
            f"{pest_result['growth_stage']} stage. Inspect the crop; "
            "a photo can confirm this with the camera model."
            if alert_needed else
            f"{top['pest_name']} risk is currently {top['risk_level']}. "
            "No action needed."
        )
        return {"should_send_sms": alert_needed, "message": message}

    return {"should_send_sms": False, "message": "No assessment available."}


# ============================================================
# MAIN ENTRY POINT
# ============================================================

def run_judge_scenario(week, module, level):
    """
    week:   1, 2 or 3
    module: "DROUGHT" | "DISEASE" | "PEST"   (NPK is camera-only)
    level:  "LOW" | "HIGH"

    Seeds the demo farm's data for that combination, then runs the
    real drought/disease/pest engines against it and returns a
    plain dict app.py can hand back as JSON.
    """

    module = str(module).strip().upper()
    level = str(level).strip().upper()

    if module not in ("DROUGHT", "DISEASE", "PEST"):
        raise ValueError(
            "module must be DROUGHT, DISEASE or PEST. "
            "NPK is camera-only and has no simulated scenario."
        )

    if level not in ("LOW", "HIGH"):
        raise ValueError("level must be LOW or HIGH.")

    farmer_id, farm_id, field_id, crop_id = get_or_create_demo_farm()
    sowing_date, simulated_date, crop_context = set_week(
        field_id, crop_id, int(week)
    )
    growth_stage = crop_context["growth_stage"]
    days_after_sowing = crop_context["days_after_sowing"]

    _ensure_rainfall_baseline(farm_id, simulated_date)

    search_info = None

    if module == "DROUGHT":
        preset = DROUGHT_PRESETS[level]
        _seed_sensor_history(
            simulated_date,
            temperature=preset["temperature"],
            humidity=preset["humidity"],
            soil_moisture_start=preset["soil_moisture_start"],
            soil_moisture_end=preset["soil_moisture_end"],
        )
        _seed_rainfall_log(farm_id, preset["daily_rainfall_mm"], simulated_date)
        _seed_weather_forecast(
            farm_id, preset["daily_rainfall_mm"],
            preset["temperature"], preset["humidity"], simulated_date,
        )
        search_info = {
            "method": "direct_preset",
            "note": (
                "Drought evidence checks are plain booleans, so every "
                "input (rainfall, soil trend, VPD) is set directly in "
                "the same direction instead of being searched for."
            ),
        }

    elif module == "DISEASE":
        found = _search_environment(
            lambda t, h, r: _max_disease_score(t, h, r, growth_stage),
            level,
        )
        _seed_sensor_history(
            simulated_date,
            temperature=found["temperature"],
            humidity=found["humidity"],
            soil_moisture_start=40.0,
            soil_moisture_end=40.0,
        )
        _seed_rainfall_log(farm_id, found["rainfall"], simulated_date)
        _seed_weather_forecast(
            farm_id, found["rainfall"], found["temperature"], found["humidity"],
            simulated_date,
        )
        search_info = {"method": "grid_search", **found}

    else:  # PEST
        found = _search_environment(
            lambda t, h, r: _max_pest_score(
                t, h, r, growth_stage, days_after_sowing
            ),
            level,
        )
        # found["rainfall"] is a 7-DAY TOTAL (see _max_pest_score).
        # Spread it evenly across the daily rainfall log/forecast so
        # that when pest_predictor.py sums the last 7 logged days,
        # it gets back exactly the total the search optimized for.
        daily_rainfall = found["rainfall"] / 7.0
        _seed_sensor_history(
            simulated_date,
            temperature=found["temperature"],
            humidity=found["humidity"],
            soil_moisture_start=40.0,
            soil_moisture_end=40.0,
        )
        _seed_rainfall_log(farm_id, daily_rainfall, simulated_date)
        _seed_weather_forecast(
            farm_id, daily_rainfall, found["temperature"], found["humidity"],
            simulated_date,
        )
        search_info = {
            "method": "grid_search",
            "temperature": found["temperature"],
            "humidity": found["humidity"],
            "rainfall_7day_total_mm": found["rainfall"],
            "predicted_score": found["predicted_score"],
            "candidates_tried": found["candidates_tried"],
        }

    # --------------------------------------------------------
    # Build Farm State and run every engine, exactly the way
    # run_demo.py / app.py already do it -- just pointed at the
    # simulated date instead of the real one.
    # --------------------------------------------------------

    farm_state = build_farm_state(
        DEMO_DEVICE_ID,
        farm_id=farm_id,
        field_id=field_id,
        state=DEMO_STATE,
        current_date=simulated_date.isoformat(),
    )

    try:
        drought_result = _run_drought(
            farm_state, farm_id, sowing_date, simulated_date
        )
    except Exception as exc:
        drought_result = {
            "available": False,
            "reason": f"{type(exc).__name__}: {exc}",
        }

    try:
        disease_result = predict_disease_risk(
            farm_state=farm_state,
            farm_id=farm_id,
            drought_result=drought_result,
            current_date=simulated_date.isoformat(),
        )
    except Exception as exc:
        disease_result = {
            "available": False,
            "reason": f"{type(exc).__name__}: {exc}",
        }

    try:
        pest_result = predict_pest_risk(
            farm_state=farm_state,
            farm_id=farm_id,
            current_date=simulated_date.isoformat(),
        )
    except Exception as exc:
        pest_result = {
            "available": False,
            "reason": f"{type(exc).__name__}: {exc}",
        }

        # --------------------------------------------------------
    # BUILD ALERT
    # --------------------------------------------------------

    alert = _build_alert(
        module,
        drought_result,
        disease_result,
        pest_result
    )

    # --------------------------------------------------------
    # SEND SMS FOR JUDGE DEMO
    # --------------------------------------------------------

    sms_sent = False

    if alert.get("should_send_sms"):
        sms_sent = send_judge_alert(
            alert,
            DEMO_PHONE
        )

    alert["sms_sent"] = sms_sent

    return {
        "requested": {
            "week": int(week),
            "module": module,
            "level": level
        },

        "crop": {
            "growth_stage": growth_stage,
            "days_after_sowing": days_after_sowing,
            "sowing_date": sowing_date,
            "simulated_current_date": simulated_date.isoformat(),
            "season": DEMO_SEASON,
        },

        "search": search_info,

        "farm_state_summary":
            _summarize_farm_state(farm_state),

        "drought": drought_result,

        "disease": disease_result,

        "pest": pest_result,

        "alert": alert,

        "camera_note": (
            "Camera confirmation (disease/pest photo, NPK leaf photo) is "
            "a separate manual step and is not triggered by this demo."
        ),
    }


# ============================================================
# CLI, FOR TESTING WITHOUT app.py / A FRONTEND
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="Run one Week/Module/Level combination for the judge demo."
    )
    parser.add_argument("--week", type=int, choices=[1, 2, 3], required=True)
    parser.add_argument(
        "--module", choices=["drought", "disease", "pest"], required=True,
    )
    parser.add_argument("--level", choices=["low", "high"], required=True)

    args = parser.parse_args()

    result = run_judge_scenario(
        week=args.week, module=args.module, level=args.level,
    )

    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()