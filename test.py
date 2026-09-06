from farm_state import build_farm_state


# ============================================================
# Configuration
# ============================================================

DEVICE_ID = "RPI-RICE-0001"
FARM_ID = 1
FIELD_ID = 1

# This must match the state stored/used for this farm.
STATE = "West Bengal"

HISTORY_LIMIT = 20


# ============================================================
# Build Farm State
# ============================================================

try:

    farm_state = build_farm_state(
        device_id=DEVICE_ID,
        farm_id=FARM_ID,
        field_id=FIELD_ID,
        state=STATE,
        history_limit=HISTORY_LIMIT
    )

except Exception as e:

    print("\nERROR while building Farm State:")
    print(e)
    raise


# ============================================================
# Basic Information
# ============================================================

print("\n")
print("=" * 70)
print("                         FARM STATE")
print("=" * 70)

print("\nDevice ID :", farm_state["device_id"])
print("Farm ID   :", farm_state["farm_id"])
print("Field ID  :", farm_state["field_id"])


# ============================================================
# Farm Context
# ============================================================

print("\n")
print("-" * 70)
print("FARM CONTEXT")
print("-" * 70)

context = farm_state["context"]

print("State :", context["state"])


# ============================================================
# Crop Context
# ============================================================

print("\n")
print("-" * 70)
print("CROP CONTEXT")
print("-" * 70)

crop = farm_state["crop"]

if crop and crop.get("available"):

    print("Crop        :", crop["crop_name"])
    print("Season      :", crop["season"])
    print("Sowing date :", crop["sowing_date"])
    print("State       :", crop["state"])

    if "growth" in crop:

        growth = crop["growth"]

        print("\nGrowth information:")

        for key, value in growth.items():

            print(f"  {key}: {value}")

else:

    print("Crop information not available.")


# ============================================================
# Sensor Nodes
# ============================================================

print("\n")
print("=" * 70)
print("                       SENSOR NODES")
print("=" * 70)

nodes = farm_state["sensor_nodes"]

print("\nNumber of nodes:", len(nodes))


for position, node in nodes.items():

    print("\n")
    print("-" * 70)
    print(f"NODE: {position}")
    print("-" * 70)

    print("Sensor node ID :", node["sensor_node_id"])
    print("Latest reading :", node["latest_timestamp"])
    print("History count  :", node["history_count"])

    # --------------------------------------------------------
    # Current measurements
    # --------------------------------------------------------

    print("\nCURRENT CONDITIONS")

    current = node["current_conditions"]

    print(
        f"  Air temperature : {current['air_temperature']} °C"
    )

    print(
        f"  Air humidity    : {current['air_humidity']} %"
    )

    print(
        f"  Soil temperature: {current['soil_temperature']} °C"
    )

    print(
        f"  Soil moisture   : {current['soil_moisture']} %"
    )

    print(
        f"  Leaf temperature: {current['leaf_temperature']} °C"
    )

    print(
        f"  Water level     : {current['water_level']}"
    )

    print(
        f"  Rain detected   : {current['rain_detected']}"
    )

    # --------------------------------------------------------
    # Trends
    # --------------------------------------------------------

    print("\nRECENT TRENDS")

    trends = node["trends"]

    for variable, trend in trends.items():

        print(
            f"  {variable:20} : {trend}"
        )


# ============================================================
# Spatial State
# ============================================================

print("\n")
print("=" * 70)
print("                       SPATIAL STATE")
print("=" * 70)

spatial = farm_state["spatial_state"]


for variable, data in spatial.items():

    print("\n")
    print(f"{variable.upper()}")

    if not data["available"]:

        print("  No data available.")
        continue

    print(
        f"  Minimum : {data['minimum']:.2f}"
    )

    print(
        f"  Maximum : {data['maximum']:.2f}"
    )

    print(
        f"  Average : {data['average']:.2f}"
    )

    print(
        f"  Range   : {data['range']:.2f}"
    )


# ============================================================
# Weather
# ============================================================

print("\n")
print("=" * 70)
print("                    WEATHER FORECAST")
print("=" * 70)

weather = farm_state["weather"]

if weather:

    print(
        f"\nForecast records available: {len(weather)}"
    )

    for day in weather:

        print("\n")
        print("-" * 70)

        print(
            "Date:",
            day["forecast_date"]
        )

        print(
            "Temperature:",
            day["temperature_min"],
            "to",
            day["temperature_max"],
            "°C"
        )

        print(
            "Humidity:",
            day["humidity"],
            "%"
        )

        print(
            "Rainfall:",
            day["rainfall"],
            "mm"
        )

        print(
            "Rain probability:",
            day["rainfall_probability"],
            "%"
        )

        print(
            "Wind speed:",
            day["wind_speed"]
        )

else:

    print("\nNo weather forecast available.")


# ============================================================
# End
# ============================================================

print("\n")
print("=" * 70)
print("                 FARM STATE COMPLETE")
print("=" * 70)

print(
    "\nNo risk classification has been performed."
)

print(
    "Farm State contains observations, trends, "
    "spatial information, crop context and weather."
)

print("\n")