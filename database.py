import sqlite3


DATABASE_NAME = "farm.db"


# =========================================================
# DATABASE CONNECTION
# =========================================================

def get_connection():

    connection = sqlite3.connect(DATABASE_NAME)

    # Enable foreign key support
    connection.execute("PRAGMA foreign_keys = ON")
    connection.row_factory = sqlite3.Row
    return connection


# =========================================================
# DATABASE TABLES
# =========================================================

def create_database():

    connection = get_connection()
    cursor = connection.cursor()

    # -----------------------------------------------------
    # FARMERS
    # -----------------------------------------------------

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS farmers (

        farmer_id INTEGER PRIMARY KEY AUTOINCREMENT,

        name TEXT NOT NULL,

        phone_number TEXT NOT NULL UNIQUE,

        preferred_language TEXT NOT NULL,

        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)


    # -----------------------------------------------------
    # FARMS
    # -----------------------------------------------------

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS farms (

        farm_id INTEGER PRIMARY KEY AUTOINCREMENT,

        farmer_id INTEGER NOT NULL,

        latitude REAL NOT NULL,

        longitude REAL NOT NULL,

        state TEXT,

        soil_type TEXT DEFAULT 'UNKNOWN',

        soil_data_source TEXT,

        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,

        FOREIGN KEY (farmer_id)
        REFERENCES farmers(farmer_id)
    )
    """)


    # -----------------------------------------------------
    # FIELDS
    # -----------------------------------------------------

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS fields (

        field_id INTEGER PRIMARY KEY AUTOINCREMENT,

        farm_id INTEGER NOT NULL,

        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,

        FOREIGN KEY (farm_id)
        REFERENCES farms(farm_id)
    )
    """)


    # -----------------------------------------------------
    # CROPS
    # -----------------------------------------------------

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS crops (

        crop_id INTEGER PRIMARY KEY AUTOINCREMENT,

        field_id INTEGER NOT NULL,

        crop_name TEXT NOT NULL DEFAULT 'Rice',

        sowing_date TEXT NOT NULL,

        season TEXT,

        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,

        FOREIGN KEY (field_id)
        REFERENCES fields(field_id)
    )
    """)


    # -----------------------------------------------------
    # DEVICES
    # -----------------------------------------------------

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS devices (

        device_id TEXT PRIMARY KEY,

        field_id INTEGER NOT NULL UNIQUE,

        device_status TEXT NOT NULL DEFAULT 'ACTIVE',

        registered_at DATETIME DEFAULT CURRENT_TIMESTAMP,

        FOREIGN KEY (field_id)
        REFERENCES fields(field_id)
    )
    """)
    # -----------------------------------------------------
# SENSOR NODES
# -----------------------------------------------------

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS sensor_nodes (

        sensor_node_id TEXT PRIMARY KEY,

        device_id TEXT NOT NULL,

        grid_position TEXT NOT NULL,

        latitude REAL,

        longitude REAL,

        node_status TEXT DEFAULT 'ACTIVE',

        registered_at DATETIME DEFAULT CURRENT_TIMESTAMP,

        FOREIGN KEY (device_id)
        REFERENCES devices(device_id)
    )
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS sensor_readings (

        reading_id INTEGER PRIMARY KEY AUTOINCREMENT,

        sensor_node_id TEXT NOT NULL,

        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,

        air_temperature REAL,

        air_humidity REAL,

        soil_temperature REAL,

        soil_moisture REAL,

        rain_detected INTEGER DEFAULT 0,

        water_level REAL,

        leaf_temperature REAL,

        FOREIGN KEY (sensor_node_id)
        REFERENCES sensor_nodes(sensor_node_id)
    )
    """)
    connection.execute("""
    CREATE TABLE IF NOT EXISTS weather_forecasts (
        forecast_id INTEGER PRIMARY KEY AUTOINCREMENT,
        farm_id INTEGER NOT NULL,
        forecast_date TEXT NOT NULL,
        fetched_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        temperature_min REAL,
        temperature_max REAL,
        humidity REAL,
        rainfall REAL,
        rainfall_probability REAL,
        wind_speed REAL,
        weather_description TEXT,
        FOREIGN KEY (farm_id)
            REFERENCES farms(farm_id)
    )
    """)
    connection.commit()
    connection.close()

    print("Database created successfully.")


# =========================================================
# FARMER OPERATIONS
# =========================================================

def register_farmer(
        name,
        phone_number,
        preferred_language
):

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
    INSERT INTO farmers (

        name,
        phone_number,
        preferred_language

    )

    VALUES (?, ?, ?)
    """, (
        name,
        phone_number,
        preferred_language
    ))

    connection.commit()

    farmer_id = cursor.lastrowid

    connection.close()

    return farmer_id


# =========================================================
# FARM OPERATIONS
# =========================================================

def register_farm(
        farmer_id,
        latitude,
        longitude,
        state,
        soil_type="UNKNOWN",
        soil_data_source=None
):

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
    INSERT INTO farms (

        farmer_id,
        latitude,
        longitude,
        state,
        soil_type,
        soil_data_source

    )

    VALUES (?, ?, ?, ?, ?, ?)
    """, (
        farmer_id,
        latitude,
        longitude,
        state,
        soil_type,
        soil_data_source
    ))

    connection.commit()

    farm_id = cursor.lastrowid

    connection.close()

    return farm_id


# =========================================================
# FIELD OPERATIONS
# =========================================================

def create_field(farm_id):

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
    INSERT INTO fields (

        farm_id

    )

    VALUES (?)
    """, (
        farm_id,
    ))

    connection.commit()

    field_id = cursor.lastrowid

    connection.close()

    return field_id


# =========================================================
# CROP OPERATIONS
# =========================================================

def register_crop(
        field_id,
        sowing_date,
        season,
        crop_name="Rice"
):

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
    INSERT INTO crops (

        field_id,
        crop_name,
        sowing_date,
        season

    )

    VALUES (?, ?, ?, ?)
    """, (
        field_id,
        crop_name,
        sowing_date,
        season
    ))

    connection.commit()

    crop_id = cursor.lastrowid

    connection.close()

    return crop_id


# =========================================================
# DEVICE OPERATIONS
# =========================================================

def register_device(
        device_id,
        field_id,
        device_status="ACTIVE"
):

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
    INSERT INTO devices (

        device_id,
        field_id,
        device_status

    )

    VALUES (?, ?, ?)
    """, (
        device_id,
        field_id,
        device_status
    ))

    connection.commit()

    connection.close()


# =========================================================
# DATABASE RETRIEVAL
# =========================================================

def get_farmer(farmer_id):

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
    SELECT *

    FROM farmers

    WHERE farmer_id = ?
    """, (
        farmer_id,
    ))

    farmer = cursor.fetchone()

    connection.close()

    return farmer


def get_farm(farm_id):

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
    SELECT *

    FROM farms

    WHERE farm_id = ?
    """, (
        farm_id,
    ))

    farm = cursor.fetchone()

    connection.close()

    return farm


def get_crop(field_id):

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
    SELECT *

    FROM crops

    WHERE field_id = ?

    ORDER BY crop_id DESC

    LIMIT 1
    """, (
        field_id,
    ))

    crop = cursor.fetchone()

    connection.close()

    return crop

# =========================================================
# DELETE DATABASE
# DEVELOPMENT ONLY
# =========================================================

def reset_database():

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("DROP TABLE IF EXISTS devices")
    cursor.execute("DROP TABLE IF EXISTS crops")
    cursor.execute("DROP TABLE IF EXISTS fields")
    cursor.execute("DROP TABLE IF EXISTS farms")
    cursor.execute("DROP TABLE IF EXISTS farmers")

    connection.commit()
    connection.close()

    print("Database reset successfully.")


# =========================================================
# TEST DATABASE ONLY
# =========================================================

if __name__ == "__main__":

    create_database()

    print("Database is ready.")