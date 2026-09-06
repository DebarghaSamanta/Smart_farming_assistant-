from weather import fetch_and_store_weather


FARM_ID = 1

LATITUDE = 22.57
LONGITUDE = 88.36


stored_ids = fetch_and_store_weather(
    farm_id=FARM_ID,
    latitude=LATITUDE,
    longitude=LONGITUDE
)


print("\nWeather synchronization complete.")

print(
    "Stored forecast records:",
    len(stored_ids)
)