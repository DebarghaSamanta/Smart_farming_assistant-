# location.py

import requests

from validation import validate_india_coordinates


SUPPORTED_STATES = {
    "West Bengal",
    "Maharashtra",
    "Punjab",
    "Tamil Nadu",
    "Odisha"
}


def get_state_from_coordinates(latitude, longitude):

    latitude, longitude = validate_india_coordinates(
        latitude,
        longitude
    )

    url = "https://nominatim.openstreetmap.org/reverse"

    params = {
        "lat": latitude,
        "lon": longitude,
        "format": "jsonv2",
        "zoom": 5,
        "addressdetails": 1
    }

    headers = {
        "User-Agent": "SmartFarmingPrototype/1.0"
    }

    try:

        response = requests.get(
            url,
            params=params,
            headers=headers,
            timeout=10
        )

        response.raise_for_status()

    except requests.RequestException as error:

        raise ConnectionError(
            f"Could not determine location: {error}"
        )

    data = response.json()

    address = data.get("address", {})

    state = address.get("state")

    if not state:

        raise ValueError(
            "State could not be determined "
            "from these coordinates."
        )

    return state


def get_farm_location(latitude, longitude):

    state = get_state_from_coordinates(
        latitude,
        longitude
    )

    return {
        "latitude": latitude,
        "longitude": longitude,
        "state": state,
        "supported": state in SUPPORTED_STATES
    }