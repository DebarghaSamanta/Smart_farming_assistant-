from database import get_connection


def register_sensor_node(
    sensor_node_id,
    device_id,
    grid_position,
    latitude=None,
    longitude=None
):
    connection = get_connection()

    try:
        connection.execute(
            """
            INSERT INTO sensor_nodes (
                sensor_node_id,
                device_id,
                grid_position,
                latitude,
                longitude
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                sensor_node_id,
                device_id,
                grid_position,
                latitude,
                longitude
            )
        )

        connection.commit()

    finally:
        connection.close()


def store_sensor_reading(
    sensor_node_id,
    air_temperature=None,
    air_humidity=None,
    soil_temperature=None,
    soil_moisture=None,
    rain_detected=0,
    water_level=None,
    leaf_temperature=None
):
    connection = get_connection()

    try:
        cursor = connection.execute(
            """
            INSERT INTO sensor_readings (
                sensor_node_id,
                air_temperature,
                air_humidity,
                soil_temperature,
                soil_moisture,
                rain_detected,
                water_level,
                leaf_temperature
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                sensor_node_id,
                air_temperature,
                air_humidity,
                soil_temperature,
                soil_moisture,
                rain_detected,
                water_level,
                leaf_temperature
            )
        )

        connection.commit()

        return cursor.lastrowid

    finally:
        connection.close()


def get_latest_sensor_reading(sensor_node_id):
    connection = get_connection()

    try:
        cursor = connection.execute(
            """
            SELECT *
            FROM sensor_readings
            WHERE sensor_node_id = ?
            ORDER BY timestamp DESC
            LIMIT 1
            """,
            (sensor_node_id,)
        )

        row = cursor.fetchone()

        return dict(row) if row else None

    finally:
        connection.close()


def get_latest_field_readings(device_id):
    connection = get_connection()

    try:
        cursor = connection.execute(
            """
            SELECT
                sr.*,
                sn.grid_position
            FROM sensor_readings sr
            JOIN sensor_nodes sn
                ON sr.sensor_node_id = sn.sensor_node_id
            WHERE sn.device_id = ?
              AND sr.timestamp = (
                  SELECT MAX(sr2.timestamp)
                  FROM sensor_readings sr2
                  WHERE sr2.sensor_node_id = sr.sensor_node_id
              )
            ORDER BY sn.grid_position
            """,
            (device_id,)
        )

        return [dict(row) for row in cursor.fetchall()]

    finally:
        connection.close()


def get_sensor_history(device_id, limit=100):
    """
    Get recent readings for every sensor node belonging
    to one device.

    The limit is applied PER SENSOR NODE.
    """

    connection = get_connection()

    try:
        cursor = connection.execute(
            """
            SELECT sensor_node_id
            FROM sensor_nodes
            WHERE device_id = ?
            """,
            (device_id,)
        )

        sensor_nodes = [
            row["sensor_node_id"]
            for row in cursor.fetchall()
        ]

        history = []

        for sensor_node_id in sensor_nodes:

            cursor = connection.execute(
                """
                SELECT
                    sr.*,
                    sn.grid_position
                FROM sensor_readings sr
                JOIN sensor_nodes sn
                    ON sr.sensor_node_id = sn.sensor_node_id
                WHERE sr.sensor_node_id = ?
                ORDER BY sr.timestamp DESC
                LIMIT ?
                """,
                (sensor_node_id, limit)
            )

            history.extend(
                dict(row)
                for row in cursor.fetchall()
            )

        # Keep newest readings first overall.
        history.sort(
            key=lambda reading: reading["timestamp"],
            reverse=True
        )

        return history

    finally:
        connection.close()