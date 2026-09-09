from farm_state import build_farm_state, get_drought_node_trends
from drought_risk import assess_drought_risk

state = build_farm_state(
    device_id="RPI-RICE-0001",
    farm_id=1,
    field_id=1,
)

node_trends = get_drought_node_trends(state)

print("DROUGHT NODE TRENDS")
print(node_trends)

print("\nFARM STATE CROP")
print(state["crop"])

print("\nFARM STATE WEATHER")
print(state["weather"])

print("\nCURRENT CONDITIONS")
for position, node in state["sensor_nodes"].items():
    print(position, node["current_conditions"])
