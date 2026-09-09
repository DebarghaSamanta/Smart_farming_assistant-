from database import get_farmer,get_farm
from textbee import send_sms


ALERT_STATES = {
    "DEVELOPING",
    "HIGH RISK",
}


def build_drought_message(result):
    """
    Convert a drought-risk result into a farmer-friendly SMS.
    """

    state = result.get("condition_state", "UNKNOWN")
    crop = result.get("crop_context", {}).get("crop", "CROP")
    stage = result.get("growth_stage", "UNKNOWN")

    return (
        f"Smart Farming Alert: {crop} is at {state} "
        f"during the {stage} stage. "
        f"Please check field moisture and irrigation conditions."
    )


def should_send_alert(result):
    """
    Decide whether the drought engine result requires an SMS.
    """

    if not result.get("available"):
        return False

    return result.get("condition_state") in ALERT_STATES


def send_drought_alert(result, farm_id):
    """
    Send a drought alert to the farmer registered to the farm.
    """

    if not should_send_alert(result):
        print("No drought alert required.")
        return False

    farm = get_farm(farm_id)

    if not farm:
        print(f"ERROR: Farm {farm_id} not found.")
        return False

    farmer_id = farm["farmer_id"]
    farmer = get_farmer(farmer_id)

    if not farmer:
        print(f"ERROR: Farmer {farmer_id} not found.")
        return False

    phone = farmer["phone_number"]

    message = build_drought_message(result)

    print("\n=== DROUGHT ALERT ===")
    print("Farmer:", farmer["name"])
    print("Message:", message)

    return send_sms(phone, message)
