from database import get_connection


def store_weather_forecast(
    farm_id,
    forecast_date,
    temperature_min=None,
    temperature_max=None,
    humidity=None,
    rainfall=None,
    rainfall_probability=None,
    wind_speed=None,
    weather_description=None
):
    connection = get_connection()

    try:
        cursor = connection.execute(
            """
            INSERT INTO weather_forecasts (
                farm_id,
                forecast_date,
                temperature_min,
                temperature_max,
                humidity,
                rainfall,
                rainfall_probability,
                wind_speed,
                weather_description
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                farm_id,
                forecast_date,
                temperature_min,
                temperature_max,
                humidity,
                rainfall,
                rainfall_probability,
                wind_speed,
                weather_description
            )
        )

        connection.commit()

        return cursor.lastrowid

    finally:
        connection.close()


def get_weather_forecast(farm_id):
    connection = get_connection()

    try:
        cursor = connection.execute(
            """
            SELECT *
            FROM weather_forecasts
            WHERE farm_id = ?
            ORDER BY forecast_date ASC
            """,
            (farm_id,)
        )

        return [dict(row) for row in cursor.fetchall()]

    finally:
        connection.close()