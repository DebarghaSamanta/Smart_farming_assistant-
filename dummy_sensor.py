import random
import time
from datetime import datetime

from sensor_repository import store_sensor_reading


DEVICE_ID = "RPI-RICE-0001"

SENSOR_NODES = {
    "RPI-RICE-0001-NW": "NW",
    "RPI-RICE-0001-NE": "NE",
    "RPI-RICE-0001-SW": "SW",
    "RPI-RICE-0001-SE": "SE"
}

# ---------------------------------------------------------
# Scenario definitions
# ---------------------------------------------------------

SCENARIOS = {
    "NORMAL": {
        "air_temperature": (28, 32),
        "air_humidity": (60, 75),
        "soil_temperature": (26, 30),
        "soil_moisture": (35, 50),
        "water_level": (1, 3),
        "leaf_temperature": (29, 33),
        "rain_probability": 0.05
    },

    "DRY": {
        "air_temperature": (30, 36),
        "air_humidity": (35, 55),
        "soil_temperature": (29, 34),
        "soil_moisture": (15, 28),
        "water_level": (0, 1),
        "leaf_temperature": (34, 39),
        "rain_probability": 0.01
    },

    "HEAT": {
        "air_temperature": (36, 42),
        "air_humidity": (30, 50),
        "soil_temperature": (32, 37),
        "soil_moisture": (25, 40),
        "water_level": (0, 2),
        "leaf_temperature": (39, 45),
        "rain_probability": 0.01
    },

    "FLOOD": {
        "air_temperature": (27, 32),
        "air_humidity": (75, 95),
        "soil_temperature": (25, 29),
        "soil_moisture": (65, 90),
        "water_level": (5, 12),
        "leaf_temperature": (27, 32),
        "rain_probability": 0.8
    },

    "DISEASE_FAVORABLE": {
        "air_temperature": (25, 30),
        "air_humidity": (80, 95),
        "soil_temperature": (24, 28),
        "soil_moisture": (45, 65),
        "water_level": (2, 4),
        "leaf_temperature": (25, 29),
        "rain_probability": 0.4
    }
}


# ---------------------------------------------------------
# Generate one reading
# ---------------------------------------------------------

def generate_reading(grid_position, scenario="NORMAL"):

    if scenario not in SCENARIOS:
        raise ValueError(
            f"Unknown scenario: {scenario}. "
            f"Available: {list(SCENARIOS.keys())}"
        )

    conditions = SCENARIOS[scenario]

    # Slight spatial variation between field locations
    spatial_offset = {
        "NW": 0.0,
        "NE": 0.5,
        "SW": -0.5,
        "SE": 1.0
    }.get(grid_position, 0)

    air_temperature = random.uniform(
        *conditions["air_temperature"]
    ) + spatial_offset

    air_humidity = random.uniform(
        *conditions["air_humidity"]
    )

    soil_temperature = random.uniform(
        *conditions["soil_temperature"]
    )

    soil_moisture = random.uniform(
        *conditions["soil_moisture"]
    )

    water_level = random.uniform(
        *conditions["water_level"]
    )

    leaf_temperature = random.uniform(
        *conditions["leaf_temperature"]
    )

    rain_detected = (
        1
        if random.random() < conditions["rain_probability"]
        else 0
    )

    return {
        "air_temperature": round(air_temperature, 2),
        "air_humidity": round(air_humidity, 2),
        "soil_temperature": round(soil_temperature, 2),
        "soil_moisture": round(soil_moisture, 2),
        "rain_detected": rain_detected,
        "water_level": round(water_level, 2),
        "leaf_temperature": round(leaf_temperature, 2)
    }


# ---------------------------------------------------------
# Store one complete field snapshot
# ---------------------------------------------------------

def generate_field_snapshot(scenario="NORMAL"):

    print(f"\nGenerating scenario: {scenario}")

    for sensor_node_id, grid_position in SENSOR_NODES.items():

        reading = generate_reading(
            grid_position,
            scenario
        )

        reading_id = store_sensor_reading(
            sensor_node_id=sensor_node_id,
            air_temperature=reading["air_temperature"],
            air_humidity=reading["air_humidity"],
            soil_temperature=reading["soil_temperature"],
            soil_moisture=reading["soil_moisture"],
            rain_detected=reading["rain_detected"],
            water_level=reading["water_level"],
            leaf_temperature=reading["leaf_temperature"]
        )

        print(
            f"{grid_position} | "
            f"Air: {reading['air_temperature']}°C | "
            f"Humidity: {reading['air_humidity']}% | "
            f"Soil moisture: {reading['soil_moisture']}% | "
            f"Leaf: {reading['leaf_temperature']}°C | "
            f"Water: {reading['water_level']} | "
            f"Rain: {reading['rain_detected']} | "
            f"Reading ID: {reading_id}"
        )


# ---------------------------------------------------------
# Continuous simulation
# ---------------------------------------------------------

def run_simulation(
    scenario="NORMAL",
    interval_seconds=5,
    cycles=None
):

    print("\n===================================")
    print(" SMART FARM SENSOR SIMULATOR")
    print("===================================")
    print(f"Device: {DEVICE_ID}")
    print(f"Scenario: {scenario}")
    print(f"Interval: {interval_seconds} seconds")

    cycle = 0

    try:

        while cycles is None or cycle < cycles:

            cycle += 1

            print(
                f"\n--- Field Snapshot {cycle} "
                f"({datetime.now().strftime('%Y-%m-%d %H:%M:%S')}) ---"
            )

            generate_field_snapshot(scenario)

            if cycles is not None and cycle >= cycles:
                break

            time.sleep(interval_seconds)

    except KeyboardInterrupt:

        print("\nSimulation stopped.")


# ---------------------------------------------------------
# Program entry
# ---------------------------------------------------------

if __name__ == "__main__":

    # Change this to:
    # NORMAL
    # DRY
    # HEAT
    # FLOOD
    # DISEASE_FAVORABLE

    run_simulation(
        scenario="DISEASE_FAVORABLE",
        interval_seconds=5,
        cycles=10
    )