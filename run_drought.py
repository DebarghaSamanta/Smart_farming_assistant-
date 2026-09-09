from database import get_farm, get_crop
from farm_state import build_farm_state
from drought_risk import assess_drought_risk


FARM_ID = 1
DEVICE_ID = "RPI-RICE-0001"
FIELD_ID = 1


# ---------------------------------------------------------
# 1. Get farm and crop information from database
# ---------------------------------------------------------

farm = get_farm(FARM_ID)
crop = get_crop(FIELD_ID)

if not farm:
    raise ValueError("Farm not found")

if not crop:
    raise ValueError("Crop not found")


# ---------------------------------------------------------
# 2. Build complete Farm State
# ---------------------------------------------------------

farm_state = build_farm_state(
    device_id=DEVICE_ID,
    farm_id=FARM_ID,
    field_id=FIELD_ID,
)


# ---------------------------------------------------------
# 3. Extract drought-engine inputs
# ---------------------------------------------------------

node_trends = {
    position: node["trends"]["soil_moisture"]
    for position, node in farm_state["sensor_nodes"].items()
    if node["trends"].get("soil_moisture") is not None
}


# Use spatial average for current atmospheric conditions
conditions = [
    node["current_conditions"]
    for node in farm_state["sensor_nodes"].values()
]

air_temp_c = sum(
    c["air_temperature"] for c in conditions
) / len(conditions)

humidity_pct = sum(
    c["air_humidity"] for c in conditions
) / len(conditions)


# ---------------------------------------------------------
# 4. Extract 7-day forecast rainfall
# ---------------------------------------------------------

weather = farm_state["weather"]

forecast_7day_rainfall_mm = sum(
    row["rainfall"]
    for row in weather
)


# ---------------------------------------------------------
# 5. Run drought engine
# ---------------------------------------------------------

result = assess_drought_risk(
    farm_id=FARM_ID,
    latitude=farm["latitude"],
    longitude=farm["longitude"],
    crop=crop["crop_name"],
    state=farm["state"],
    sowing_date=crop["sowing_date"],
    season=crop["season"],
    node_trends=node_trends,
    air_temp_c=air_temp_c,
    humidity_pct=humidity_pct,
    forecast_7day_rainfall_mm=forecast_7day_rainfall_mm,
)


# ---------------------------------------------------------
# 6. Display result
# ---------------------------------------------------------

print("\n==============================")
print("DROUGHT ASSESSMENT")
print("==============================")

print("Risk Level       :", result["risk_level"])
print("Condition State  :", result["condition_state"])
print("Drought Score    :", result["drought_probability"])
print("Trajectory       :", result["trajectory"])
print("Growth Stage     :", result["growth_stage"])
print("Critical Stage   :", result["critical_stage"])

print("\nActive Evidence:")
for item in result["active_evidence"]:
    print(" -", item)

print("\nEvidence:")
for key, value in result["evidence"].items():
    print(f" - {key}: {value}")

print("\nData Quality:")
print(result["data_quality"])

print("\n==============================")
