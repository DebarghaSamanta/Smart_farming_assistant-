from sensor_repository import (
    get_latest_field_readings,
    get_sensor_history
)

from database import get_crop
from crop_context import get_crop_context
from weather_repository import get_weather_forecast

DEFAULT_HISTORY_LIMIT = 20


# ============================================================
# TREND CALCULATION
# ============================================================

def calculate_trend(values, tolerance=0.05):
    """
    Determine the direction of a variable over recent readings.

    This is descriptive only.
    It does NOT determine whether the condition is good or bad.

    Returns:
        INCREASING
        DECREASING
        STABLE
        INSUFFICIENT_DATA
    """

    if values is None or len(values) < 2:
        return "INSUFFICIENT_DATA"

    values = [
        value for value in values
        if value is not None
    ]

    if len(values) < 2:
        return "INSUFFICIENT_DATA"

    first = values[0]
    last = values[-1]

    change = last - first

    scale = max(abs(first), 1)

    relative_change = abs(change) / scale

    if relative_change <= tolerance:
        return "STABLE"

    if change > 0:
        return "INCREASING"

    return "DECREASING"


# ============================================================
# NODE HISTORY
# ============================================================

def get_node_history(history, sensor_node_id):
    """
    Extract historical readings for one sensor node.

    Repository returns newest first, so reverse them
    to obtain:

        oldest → newest
    """

    node_history = [
        reading
        for reading in history
        if reading["sensor_node_id"] == sensor_node_id
    ]

    node_history.reverse()

    return node_history


# ============================================================
# NODE TRENDS
# ============================================================

def build_node_trends(node_history):

    variables = [
        "air_temperature",
        "air_humidity",
        "soil_temperature",
        "soil_moisture",
        "water_level",
        "leaf_temperature"
    ]

    trends = {}

    for variable in variables:

        values = [
            reading.get(variable)
            for reading in node_history
            if reading.get(variable) is not None
        ]

        trends[variable] = calculate_trend(values)

    return trends


# ============================================================
# NODE STATE
# ============================================================

def build_node_state(latest_reading, node_history):

    trends = build_node_trends(node_history)

    return {

        "sensor_node_id":
            latest_reading["sensor_node_id"],

        "grid_position":
            latest_reading["grid_position"],

        "latest_timestamp":
            latest_reading["timestamp"],

        # ----------------------------------------------------
        # Actual measurements
        # ----------------------------------------------------

        "current_conditions": {

            "air_temperature":
                latest_reading["air_temperature"],

            "air_humidity":
                latest_reading["air_humidity"],

            "soil_temperature":
                latest_reading["soil_temperature"],

            "soil_moisture":
                latest_reading["soil_moisture"],

            "rain_detected":
                bool(latest_reading["rain_detected"]),

            "water_level":
                latest_reading["water_level"],

            "leaf_temperature":
                latest_reading["leaf_temperature"]
        },

        # ----------------------------------------------------
        # Recent behaviour
        # ----------------------------------------------------

        "trends": trends,

        "history_count":
            len(node_history)
    }


# ============================================================
# SPATIAL STATE
# ============================================================

def build_spatial_state(node_states):

    """
    Describe how measurements differ between sensor nodes.

    This does NOT classify the spatial condition.
    """

    variables = [
        "air_temperature",
        "air_humidity",
        "soil_temperature",
        "soil_moisture",
        "water_level",
        "leaf_temperature"
    ]

    spatial_state = {}

    for variable in variables:

        values = []

        for node in node_states.values():

            value = node["current_conditions"].get(
                variable
            )

            if value is not None:
                values.append(value)

        if not values:

            spatial_state[variable] = {
                "available": False,
                "minimum": None,
                "maximum": None,
                "average": None,
                "range": None
            }

            continue

        spatial_state[variable] = {

            "available": True,

            "minimum":
                min(values),

            "maximum":
                max(values),

            "average":
                sum(values) / len(values),

            "range":
                max(values) - min(values)
        }

    return spatial_state


# ============================================================
# CROP CONTEXT
# ============================================================

def build_crop_context(field_id, state, current_date=None):
    if field_id is None:
        return {"available": False}

    crop = get_crop(field_id)

    if crop is None:
        return {"available": False}

    return get_crop_context(
        crop=crop["crop_name"],
        state=state,
        season=crop["season"],
        sowing_date=crop["sowing_date"],
        current_date=current_date,
    )


# ============================================================
# MAIN FARM STATE
# ============================================================

def build_farm_state(
    device_id,
    farm_id=None,
    field_id=None,
    state=None,
    history_limit=DEFAULT_HISTORY_LIMIT,
    current_date=None,
    weather=None
):
   

    # ========================================================
    # 1. Latest sensor readings
    # ========================================================

    latest_readings = get_latest_field_readings(
        device_id
    )

    if not latest_readings:

        raise ValueError(
            f"No sensor readings found for device "
            f"{device_id}"
        )

    # ========================================================
    # 2. Recent history
    # ========================================================

    history = get_sensor_history(
        device_id,
        limit=history_limit
    )

    # ========================================================
    # 3. Build state for each sensor node
    # ========================================================

    node_states = {}

    for latest_reading in latest_readings:

        sensor_node_id = (
            latest_reading["sensor_node_id"]
        )

        node_history = get_node_history(
            history,
            sensor_node_id
        )

        grid_position = (
            latest_reading["grid_position"]
        )

        node_states[grid_position] = (
            build_node_state(
                latest_reading,
                node_history
            )
        )

    # ========================================================
    # 4. Spatial state
    # ========================================================

    spatial_state = build_spatial_state(
        node_states
    )

    # ========================================================
    # 5. Crop context
    # ========================================================

    crop_context = build_crop_context(
        field_id=field_id,
        state=state,
        current_date=current_date
    )

    if weather is None and farm_id is not None:
        weather = get_weather_forecast(farm_id)

    # ========================================================
    # 6. Final Farm State
    # ========================================================

    farm_state = {

        "device_id":
            device_id,

        "farm_id":
            farm_id,

        "field_id":
            field_id,

        # ----------------------------------------------------
        # Field context
        # ----------------------------------------------------

        "context": {

            "state":
                state
        },

        # ----------------------------------------------------
        # Sensor information
        # ----------------------------------------------------

        "sensor_nodes":
            node_states,

        # ----------------------------------------------------
        # Spatial information
        # ----------------------------------------------------

        "spatial_state":
            spatial_state,

        # ----------------------------------------------------
        # Crop information
        # ----------------------------------------------------

        "crop":
            crop_context,

        # ----------------------------------------------------
        # Weather information
        # ----------------------------------------------------

        "weather":
            weather
    }

    return farm_state