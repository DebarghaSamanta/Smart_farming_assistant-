import os
import requests
from dotenv import load_dotenv


TEXTBEE_URL = "https://api.textbee.dev/api/v1/gateway/send-sms"


def send_sms(phone, message):
    """
    Send an SMS through TextBee.

    This function is ONLY responsible for SMS delivery.
    It does not decide whether an alert should be generated.
    """

    load_dotenv(override=True)

    api_key = os.getenv("TEXTBEE_API_KEY")
    device_id = os.getenv("TEXTBEE_DEVICE_ID")

    if not api_key:
        print("ERROR: TEXTBEE_API_KEY is not configured.")
        return False

    if not device_id:
        print("ERROR: TEXTBEE_DEVICE_ID is not configured.")
        return False

    # Normalize Indian phone numbers.
    phone = str(phone).strip()

    if phone.startswith("0"):
        phone = phone[1:]

    if not phone.startswith("+"):
        phone = "+91" + phone

    headers = {
        "Content-Type": "application/json",
        "x-api-key": api_key,
    }

    payload = {
        "deviceId": device_id,
        "recipients": [phone],
        "message": message,
    }

    try:
        response = requests.post(
            TEXTBEE_URL,
            headers=headers,
            json=payload,
            timeout=30,
        )

        print("TextBee HTTP status:", response.status_code)

        if response.ok:
            print("SMS successfully queued through TextBee.")
            return True

        print("TextBee SMS failed:", response.text)
        return False

    except requests.RequestException as error:
        print("TextBee connection error:", error)
        return False
