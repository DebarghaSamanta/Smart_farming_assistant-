"""
Smart Farming Assistant - End-to-End Demo Runner

Run:
    python demo_runner.py

Scenarios:
    python demo_runner.py --scenario disease
    python demo_runner.py --scenario drought
    python demo_runner.py --scenario normal
    python demo_runner.py --scenario flood

By default the demo resets farm.db, rebuilds all required data,
then runs Farm State + Drought + Disease.

Use --keep if you do NOT want to reset farm.db.

Demo sensor/rainfall values are simulation data, not agricultural
ground truth or ML training data.
"""

from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from datetime import date, datetime, timedelta

import requests


DB_PATH = "farm.db"

FARMER_NAME = "Demo Farmer"
FARMER_PHONE = "+91-9876543210"
FARMER_LANGUAGE = "Bengali"

LATITUDE = 22.5726
LONGITUDE = 88.3639
STATE = "West Bengal"

SOWING_DATE = "2026-06-15"
SEASON = "AMAN"
CROP = "Rice"

DEVICE_ID = "RPI-RICE-0001"

NODES = {
    "NW": "RPI-RICE-0001-NW",
    "NE": "RPI-RICE-0001-NE",
    "SW": "RPI-RICE-0001-SW",
    "SE": "RPI-RICE-0001-SE",
}

SCENARIOS = {
    "normal": {
        "description": "Normal field conditions",
        "current": {
            "NW": (27.0, 82.0, 25.5, 55.0, 2.5, 26.0, 0),
            "NE": (28.0, 80.0, 26.0, 57.0, 2.8, 26.3, 0),
            "SW": (27.5, 84.0, 25.0, 54.0, 2.6, 26.1, 0),
            "SE": (28.2, 81.0, 25.8, 56.0, 2.7, 26.4, 0),
        },
        "rainfall": [6, 4, 8, 2, 5, 7, 3],
    },
    "disease": {
        "description": "Warm and humid disease-favorable conditions",
        "current": {
            "NW": (27.0, 93.0, 26.0, 51.0, 3.0, 26.5, 0),
            "NE": (29.0, 91.0, 27.0, 53.0, 3.2, 27.0, 0),
            "SW": (28.0, 94.0, 25.5, 49.0, 2.8, 26.8, 0),
            "SE": (29.5, 92.0, 26.5, 52.0, 3.1, 27.2, 0),
        },
        "rainfall": [5, 8, 12, 7, 10, 4, 6],
    },
    "drought": {
        "description": "Dry spell with declining soil moisture",
        "current": {
            "NW": (31.0, 55.0, 28.0, 34.0, 1.4, 30.0, 0),
            "NE": (32.0, 52.0, 28.5, 32.0, 1.5, 30.5, 0),
            "SW": (31.5, 56.0, 27.8, 35.0, 1.3, 30.1, 0),
            "SE": (32.5, 50.0, 28.2, 31.0, 1.4, 30.7, 0),
        },
        "rainfall": [0, 0, 0, 0, 0, 0, 0],
    },
    "flood": {
        "description": "High water and wet field conditions",
        "current": {
            "NW": (29.0, 94.0, 27.0, 72.0, 7.0, 28.0, 1),
            "NE": (30.0, 95.0, 27.5, 75.0, 7.5, 28.5, 1),
            "SW": (29.5, 93.0, 27.0, 70.0, 6.8, 28.2, 1),
            "SE": (30.2, 94.0, 27.4, 73.0, 7.2, 28.7, 1),
        },
        "rainfall": [18, 22, 15, 20, 12, 8, 16],
    },
    "pests": {
            "description": "False smut",
            "current": {
                "NW": (29.0, 94.0, 27.0, 72.0, 7.0, 28.0, 1),
                "NE": (30.0, 95.0, 27.5, 75.0, 7.5, 28.5, 1),
                "SW": (29.5, 93.0, 27.0, 70.0, 6.8, 28.2, 1),
                "SE": (30.2, 94.0, 27.4, 73.0, 7.2, 28.7, 1),
            },
            "rainfall": [18, 22, 15, 20, 12, 8, 16],
        },
}


def db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    return conn


def setup_database():
    from database import create_database
    from drought_risk import initialize_drought_tables

    create_database()
    initialize_drought_tables()


def reset_database():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    print("Database reset.")


def register_demo():
    from database import (
        register_farmer,
        register_farm,
        create_field,
        register_crop,
        register_device,
    )

    farmer_id = register_farmer(
        FARMER_NAME,
        FARMER_PHONE,
        FARMER_LANGUAGE,
    )

    farm_id = register_farm(
        farmer_id,
        LATITUDE,
        LONGITUDE,
        STATE,
        "UNKNOWN",
        None,
    )

    field_id = create_field(farm_id)

    register_crop(
        field_id,
        SOWING_DATE,
        SEASON,
        CROP,
    )

    register_device(
        DEVICE_ID,
        field_id,
        "ACTIVE",
    )

    return farmer_id, farm_id, field_id


def register_nodes():
    conn = db()
    cur = conn.cursor()

    offsets = {
        "NW": (-0.0005, -0.0005),
        "NE": (-0.0005, 0.0005),
        "SW": (0.0005, -0.0005),
        "SE": (0.0005, 0.0005),
    }

    for position, node_id in NODES.items():
        dlat, dlon = offsets[position]

        cur.execute(
            """
            INSERT INTO sensor_nodes
            (sensor_node_id, device_id, grid_position,
             latitude, longitude, node_status)
            VALUES (?, ?, ?, ?, ?, 'ACTIVE')
            """,
            (
                node_id,
                DEVICE_ID,
                position,
                LATITUDE + dlat,
                LONGITUDE + dlon,
            ),
        )

    conn.commit()
    conn.close()


def sensor_values(position, scenario, progress):
    current = SCENARIOS[scenario]["current"][position]

    air, humidity, soil_temp, soil_moisture, water, leaf, rain = current

    if scenario == "drought":
        soil_moisture += 14.0 * (1.0 - progress)
        water += 0.8 * (1.0 - progress)
        humidity += 8.0 * (1.0 - progress)
        air -= 1.5 * (1.0 - progress)

    elif scenario == "disease":
        humidity -= 3.0 * (1.0 - progress)
        soil_moisture -= 2.0 * (1.0 - progress)

    elif scenario == "normal":
        soil_moisture += 1.5 * (1.0 - progress)

    return (
        round(air, 2),
        round(humidity, 2),
        round(soil_temp, 2),
        round(soil_moisture, 2),
        rain,
        round(water, 2),
        round(leaf, 2),
    )


def seed_sensor_history(scenario):
    conn = db()
    cur = conn.cursor()

    start = datetime.now() - timedelta(hours=9)

    for position, node_id in NODES.items():
        for i in range(10):
            progress = i / 9.0
            values = sensor_values(position, scenario, progress)
            timestamp = start + timedelta(hours=i)

            cur.execute(
                """
                INSERT INTO sensor_readings
                (sensor_node_id, timestamp,
                 air_temperature, air_humidity,
                 soil_temperature, soil_moisture,
                 rain_detected, water_level, leaf_temperature)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    node_id,
                    timestamp.isoformat(timespec="seconds"),
                    *values,
                ),
            )

    conn.commit()
    conn.close()


def seed_rainfall(scenario):
    from drought_risk import log_daily_rainfall

    pattern = SCENARIOS[scenario]["rainfall"]
    today = date.today()

    for i in range(30):
        day = today - timedelta(days=29 - i)
        amount = float(pattern[i % len(pattern)])
        log_daily_rainfall(1, day.isoformat(), amount)


def seed_weather():
    url = "https://api.open-meteo.com/v1/forecast"

    params = {
        "latitude": LATITUDE,
        "longitude": LONGITUDE,
        "daily": (
            "temperature_2m_min,"
            "temperature_2m_max,"
            "relative_humidity_2m_mean,"
            "precipitation_sum,"
            "precipitation_probability_max,"
            "wind_speed_10m_max"
        ),
        "timezone": "auto",
        "forecast_days": 7,
    }

    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        daily = response.json()["daily"]

        rows = []
        for i, forecast_date in enumerate(daily["time"]):
            rows.append(
                (
                    1,
                    forecast_date,
                    daily["temperature_2m_min"][i],
                    daily["temperature_2m_max"][i],
                    daily["relative_humidity_2m_mean"][i],
                    daily["precipitation_sum"][i],
                    daily["precipitation_probability_max"][i],
                    daily["wind_speed_10m_max"][i],
                    "Open-Meteo forecast",
                )
            )

        conn = db()
        conn.executemany(
            """
            INSERT INTO weather_forecasts
            (farm_id, forecast_date,
             temperature_min, temperature_max, humidity,
             rainfall, rainfall_probability, wind_speed,
             weather_description)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        conn.commit()
        conn.close()

        print("Live 7-day weather stored.")

    except Exception as exc:
        print("Weather API unavailable; using demo fallback.")
        print("Reason:", exc)

        fallback = [
            (30.0, 31.5, 88.0, 2.0, 60.0, 10.0),
            (29.0, 32.0, 86.0, 3.0, 65.0, 11.0),
            (28.5, 31.0, 90.0, 5.0, 75.0, 9.0),
            (28.0, 30.5, 91.0, 7.0, 80.0, 8.0),
            (27.5, 30.0, 92.0, 4.0, 65.0, 7.0),
            (27.0, 31.0, 88.0, 2.0, 50.0, 8.0),
            (27.0, 30.5, 87.0, 3.0, 55.0, 8.0),
        ]

        conn = db()
        for i, values in enumerate(fallback):
            conn.execute(
                """
                INSERT INTO weather_forecasts
                (farm_id, forecast_date,
                 temperature_min, temperature_max, humidity,
                 rainfall, rainfall_probability, wind_speed,
                 weather_description)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    1,
                    (date.today() + timedelta(days=i)).isoformat(),
                    *values,
                    "Demo fallback forecast",
                ),
            )

        conn.commit()
        conn.close()


def run_drought(farm_state, farm_id):
    from drought_risk import assess_drought_risk

    weather = farm_state.get("weather") or []
    spatial = farm_state["spatial_state"]

    forecast_sum = sum(
        float(row.get("rainfall") or 0)
        for row in weather[:7]
    )

    node_trends = {
        position: node["trends"]["soil_moisture"]
        for position, node in farm_state["sensor_nodes"].items()
    }

    return assess_drought_risk(
        farm_id=farm_id,
        latitude=LATITUDE,
        longitude=LONGITUDE,
        crop=CROP,
        state=STATE,
        sowing_date=SOWING_DATE,
        season=SEASON,
        node_trends=node_trends,
        air_temp_c=spatial["air_temperature"]["average"],
        humidity_pct=spatial["air_humidity"]["average"],
        forecast_7day_rainfall_mm=forecast_sum,
        current_date=date.today().isoformat(),
    )


def print_farm_state(state):
    crop = state["crop"]
    spatial = state["spatial_state"]

    print("\n" + "=" * 65)
    print("FARM STATE")
    print("=" * 65)

    print("Device       :", state["device_id"])
    print("State        :", state["context"]["state"])
    print("Crop         :", crop.get("crop"))
    print("Season       :", crop.get("season"))
    print("Growth stage :", crop.get("growth_stage"))
    print("Days after sowing:", crop.get("days_after_sowing"))

    print("\nSpatial observations:")
    print("  Air temp   :", round(spatial["air_temperature"]["average"], 2), "C")
    print("  Humidity   :", round(spatial["air_humidity"]["average"], 2), "%")
    print("  Soil moist :", round(spatial["soil_moisture"]["average"], 2), "%")
    print("  Water      :", round(spatial["water_level"]["average"], 2))
    print("  Leaf temp  :", round(spatial["leaf_temperature"]["average"], 2), "C")

    print("\nFour sensor nodes:")
    for position, node in state["sensor_nodes"].items():
        c = node["current_conditions"]
        print(
            f"  {position}: "
            f"air={c['air_temperature']:.1f} C, "
            f"RH={c['air_humidity']:.1f}%, "
            f"soil={c['soil_moisture']:.1f}%, "
            f"soil trend={node['trends']['soil_moisture']}"
        )


def print_drought(result):
    print("\n" + "=" * 65)
    print("DROUGHT ASSESSMENT")
    print("=" * 65)

    if not result.get("available", True):
        print("Unavailable:", result.get("reason"))
        return

    for key in (
        "risk_level",
        "condition_state",
        "trajectory",
        "score",
        "drought_probability",
        "evidence_coverage",
    ):
        if key in result:
            print(f"{key.replace('_', ' ').title():18}: {result[key]}")


def print_disease(result):
    print("\n" + "=" * 65)
    print("DISEASE RISK ASSESSMENT")
    print("=" * 65)

    if not result.get("available", False):
        print("Unavailable:", result.get("reason"))
        return

    print("Confidence       :", result["confidence"])
    print("Growth stage     :", result["growth_stage"])

    print("\nTOP 2 DISEASE RISKS:")
    for i, disease in enumerate(result["top_two"], 1):
        print(
            f"  {i}. {disease['disease_name']} "
            f"| Score: {disease['score']} "
            f"| Risk: {disease['risk_level']}"
        )


def main():
    parser = argparse.ArgumentParser(
        description="Run the Smart Farming Assistant end-to-end demo."
    )

    parser.add_argument(
        "--scenario",
        choices=list(SCENARIOS.keys()),
        default="disease",
    )

    parser.add_argument(
        "--keep",
        action="store_true",
        help="Keep the current database instead of resetting it.",
    )

    parser.add_argument(
        "--image",
        help="Leaf image for the trained camera disease model.",
    )

    parser.add_argument(
        "--model",
        help="Optional camera model path. If omitted, latest models/vN model is used.",
    )

    args = parser.parse_args()

    print("\n" + "=" * 65)
    print("SMART FARMING ASSISTANT")
    print("END-TO-END DEMONSTRATION")
    print("=" * 65)
    print("Scenario:", args.scenario.upper())
    print(SCENARIOS[args.scenario]["description"])

    try:
        if not args.keep:
            reset_database()

        print("\n[1] Initializing database...")
        setup_database()

        print("[2] Registering farmer/farm/field/crop/device...")
        _, farm_id, field_id = register_demo()

        print("[3] Registering four spatial nodes...")
        register_nodes()

        print("[4] Filling sensor history...")
        seed_sensor_history(args.scenario)

        print("[5] Filling 30 days rainfall history...")
        seed_rainfall(args.scenario)

        print("[6] Loading weather...")
        seed_weather()

        print("[7] Building Farm State...")
        from farm_state import build_farm_state

        farm_state = build_farm_state(
            DEVICE_ID,
            farm_id=farm_id,
            field_id=field_id,
            state=STATE,
            current_date=date.today().isoformat(),
        )

        print_farm_state(farm_state)

        print("\n[8] Running Drought Engine...")
        drought_result = None

        try:
            drought_result = run_drought(farm_state, farm_id)
            print_drought(drought_result)
        except Exception as exc:
            print("Drought engine error:", type(exc).__name__, exc)

        print("\n[9] Running Disease Engine...")
        try:
            from disease_predictor import predict_disease_risk

            disease_result = predict_disease_risk(
                farm_state=farm_state,
                farm_id=farm_id,
                drought_result=drought_result,
            )

            print_disease(disease_result)

        except Exception as exc:
            print("Disease engine error:", type(exc).__name__, exc)

        # --------------------------------------------------------
        # CAMERA DISEASE MODEL
        # --------------------------------------------------------
        if args.image:
            print("\n[10] Running Camera Disease Model...")
            try:
                from camera_disease import predict_camera_disease

                camera_result = predict_camera_disease(
                    image_path=args.image,
                    model_path=args.model,
                )

                print("\n" + "=" * 65)
                print("CAMERA DISEASE EVIDENCE")
                print("=" * 65)
                print("Image            :", camera_result["image"])
                print("Predicted class  :", camera_result["disease"])
                print("Source           :", camera_result["source"])

            except Exception as exc:
                print(
                    "Camera model error:",
                    type(exc).__name__,
                    exc,
                )
        else:
            print("\n[10] Camera Disease Model: skipped (no --image supplied).")

        print("\n" + "=" * 65)
        print("DEMO COMPLETE")
        print("=" * 65)
        print("Data: DEMO/SIMULATION sensor + rainfall values")
        print("Weather: live Open-Meteo when available")
        print("Flow: Sensors -> Farm State -> Drought/Disease -> Camera Evidence -> Assessment")
        print("SMS is NOT sent automatically during this demo.")
        print()

        return 0

    except KeyboardInterrupt:
        print("\nDemo stopped.")
        return 130

    except Exception as exc:
        print("\nDEMO FAILED")
        print(type(exc).__name__, ":", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
