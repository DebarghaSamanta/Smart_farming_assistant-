import os
import time
from datetime import date, timedelta
from twilio.rest import Client

from drought_risk import assess_drought_risk


# ---------------- CONFIG ----------------

FARM_ID = 1
FARMER_NAME = "Demo Farmer"
MOBILE_NUMBER = "+91XXXXXXXXXX"   # replace with registered number

TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN")
TWILIO_FROM_NUMBER = os.environ.get("TWILIO_FROM_NUMBER")

CHECK_INTERVAL_SECONDS = 60


# ------------- DEMO SENSOR DATA -------------

def get_demo_sensor_data():
    """
    Replace this function later with your real sensor-node readings.

    The values below intentionally represent a drought-like situation
    so the complete Raspberry Pi -> drought engine -> SMS pipeline
    can be demonstrated without waiting for a real drought.
    """

    return {
        "latitude": 22.5726,
        "longitude": 88.3639,

        "crop": "rice",
        "state": "West Bengal",
        "season": "AMAN",
        "sowing_date": "2026-07-10",

        "node_trends": [
            {
                "sensor_node_id": "NW",
                "soil_moisture": 22,
                "soil_moisture_trend": "DECREASING"
            },
            {
                "sensor_node_id": "NE",
                "soil_moisture": 24,
                "soil_moisture_trend": "DECREASING"
            },
            {
                "sensor_node_id": "SW",
                "soil_moisture": 23,
                "soil_moisture_trend": "DECREASING"
            },
            {
                "sensor_node_id": "SE",
                "soil_moisture": 25,
                "soil_moisture_trend": "DECREASING"
            }
        ],

        "air_temp_c": 32.0,
        "humidity_pct": 42.0,

        # Demo value. Replace with forecast API data later.
        "forecast_7day_rainfall_mm": 2.0,
    }


# ------------- SMS -------------

def send_sms(message):
    if not all([
        TWILIO_ACCOUNT_SID,
        TWILIO_AUTH_TOKEN,
        TWILIO_FROM_NUMBER
    ]):
        print("\n[SMS NOT SENT]")
        print("Twilio environment variables are missing.")
        print("Message that would have been sent:")
        print(message)
        return False

    client = Client(
        TWILIO_ACCOUNT_SID,
        TWILIO_AUTH_TOKEN
    )

    client.messages.create(
        body=message,
        from_=TWILIO_FROM_NUMBER,
        to=MOBILE_NUMBER
    )

    print("\nSMS SENT")
    return True


def build_alert_message(result):
    risk = result.get("risk_level", "UNKNOWN")
    stage = result.get("crop_context", {}).get(
        "growth_stage",
        "UNKNOWN"
    )
    trajectory = result.get("trajectory", "UNKNOWN")

    if risk in ("HIGH", "MEDIUM"):
        return (
            f"Farm Alert - {FARMER_NAME}\n"
            f"Rice field is showing drought-like conditions.\n"
            f"Risk: {risk}\n"
            f"Crop stage: {stage}\n"
            f"Trend: {trajectory}\n"
            f"Please check field water availability."
        )

    if risk == "LOW":
        return (
            f"Farm Update - {FARMER_NAME}\n"
            f"Early signs of water stress detected.\n"
            f"Risk: LOW\n"
            f"Crop stage: {stage}\n"
            f"Continue monitoring the field."
        )

    return None


# ------------- ALERT CONTROL -------------

last_alert_state = None


def process_farm():
    global last_alert_state

    sensor_data = get_demo_sensor_data()

    today = date.today().isoformat()

    result = assess_drought_risk(
        farm_id=FARM_ID,
        latitude=sensor_data["latitude"],
        longitude=sensor_data["longitude"],
        crop=sensor_data["crop"],
        state=sensor_data["state"],
        sowing_date=sensor_data["sowing_date"],
        season=sensor_data["season"],
        node_trends=sensor_data["node_trends"],
        air_temp_c=sensor_data["air_temp_c"],
        humidity_pct=sensor_data["humidity_pct"],
        forecast_7day_rainfall_mm=sensor_data["forecast_7day_rainfall_mm"],
        current_date=today,
    )

    risk = result.get("risk_level")
    state = result.get("condition_state")

    print("\n-----------------------------")
    print("DROUGHT DEMONSTRATION")
    print("-----------------------------")
    print("Risk:", risk)
    print("Condition:", state)
    print("Trajectory:", result.get("trajectory"))
    print("Probability:", result.get("drought_probability"))
    print("Evidence:", result.get("active_evidence"))
    print("Coverage:", result.get("evidence_coverage"))

    current_alert_state = (risk, state)

    # Send only when the alert state changes.
    if risk in ("LOW", "MEDIUM", "HIGH"):
        if current_alert_state != last_alert_state:
            message = build_alert_message(result)

            if message:
                send_sms(message)

            last_alert_state = current_alert_state
        else:
            print("No new SMS - alert state unchanged.")
    else:
        last_alert_state = None
        print("No alert required.")


# ------------- MAIN LOOP -------------

if __name__ == "__main__":
    print("Raspberry Pi Smart Farming SMS Demonstration")
    print("Press Ctrl+C to stop.\n")

    while True:
        try:
            process_farm()
            time.sleep(CHECK_INTERVAL_SECONDS)

        except KeyboardInterrupt:
            print("\nDemo stopped.")
            break

        except Exception as e:
            print("\nERROR:", e)
            time.sleep(CHECK_INTERVAL_SECONDS)
