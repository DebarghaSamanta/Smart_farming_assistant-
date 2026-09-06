import requests
from datetime import date

from weather_repository import store_weather_forecast


OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"


def fetch_weather_forecast(latitude, longitude):

    params = {
        "latitude": latitude,
        "longitude": longitude,

        "daily": ",".join([
            "temperature_2m_min",
            "temperature_2m_max",
            "relative_humidity_2m_mean",
            "precipitation_sum",
            "precipitation_probability_max",
            "wind_speed_10m_max"
        ]),

        "forecast_days": 7,

        "timezone": "auto"
    }

    response = requests.get(
        OPEN_METEO_URL,
        params=params,
        timeout=10
    )

    response.raise_for_status()

    return response.json()


def parse_weather_response(data):

    daily = data.get("daily")

    if not daily:
        raise ValueError(
            "Weather API returned no daily forecast data"
        )

    dates = daily.get("time", [])

    temperatures_min = daily.get(
        "temperature_2m_min", []
    )

    temperatures_max = daily.get(
        "temperature_2m_max", []
    )

    humidity = daily.get(
        "relative_humidity_2m_mean", []
    )

    rainfall = daily.get(
        "precipitation_sum", []
    )

    rainfall_probability = daily.get(
        "precipitation_probability_max", []
    )

    wind_speed = daily.get(
        "wind_speed_10m_max", []
    )

    forecast = []

    for i in range(len(dates)):

        forecast.append({

            "forecast_date":
                dates[i],

            "temperature_min":
                temperatures_min[i],

            "temperature_max":
                temperatures_max[i],

            "humidity":
                humidity[i],

            "rainfall":
                rainfall[i],

            "rainfall_probability":
                rainfall_probability[i],

            "wind_speed":
                wind_speed[i]
        })

    return forecast


def fetch_and_store_weather(
    farm_id,
    latitude,
    longitude
):

    data = fetch_weather_forecast(
        latitude,
        longitude
    )

    forecast = parse_weather_response(data)

    stored_ids = []

    for day in forecast:

        reading_id = store_weather_forecast(

            farm_id=farm_id,

            forecast_date=
                day["forecast_date"],

            temperature_min=
                day["temperature_min"],

            temperature_max=
                day["temperature_max"],

            humidity=
                day["humidity"],

            rainfall=
                day["rainfall"],

            rainfall_probability=
                day["rainfall_probability"],

            wind_speed=
                day["wind_speed"]
        )

        stored_ids.append(reading_id)

    return stored_ids