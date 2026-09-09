# =========================================================
# MAIN APPLICATION
# =========================================================

from validation import (
    validate_name,
    validate_phone,
    validate_language,
    validate_sowing_date,
    validate_device_id
)

from location import (
    get_farm_location
)

from crop_calendar import (
    get_crop_status
)

from database import (
    create_database,
    register_farmer,
    register_farm,
    create_field,
    register_crop,
    register_device
)
from sensor_repository import register_sensor_node

# =========================================================
# REGISTER COMPLETE FARM SYSTEM
# =========================================================

def register_complete_farm(
        name,
        phone_number,
        language,
        latitude,
        longitude,
        sowing_date,
        device_id,
        selected_season=None
):

    print("\n" + "=" * 60)
    print("STARTING FARM REGISTRATION")
    print("=" * 60)


    # =====================================================
    # STEP 1: VALIDATE FARMER INFORMATION
    # =====================================================

    print("\nSTEP 1: VALIDATING FARMER INFORMATION")

    validated_name = validate_name(
        name
    )

    validated_phone = validate_phone(
        phone_number
    )

    validated_language = validate_language(
        language
    )

    print("Farmer information validated.")


    # =====================================================
    # STEP 2: VALIDATE DEVICE
    # =====================================================

    print("\nSTEP 2: VALIDATING DEVICE")

    validated_device_id = validate_device_id(
        device_id
    )

    print("Device validated.")


    # =====================================================
    # STEP 3: DETERMINE FARM LOCATION
    # =====================================================

    print("\nSTEP 3: DETECTING FARM LOCATION")

    location = get_farm_location(
        latitude,
        longitude
    )

    state = location["state"]

    print("Detected State:", state)


    # =====================================================
    # CHECK SUPPORTED STATE
    # =====================================================

    if not location["supported"]:

        raise ValueError(
            f"Farm location is {state}. "
            "Rice crop calendar is currently "
            "not configured for this state."
        )

    print("Supported state confirmed.")


    # =====================================================
    # STEP 4: VALIDATE SOWING DATE
    # =====================================================

    print("\nSTEP 4: VALIDATING SOWING DATE")

    validated_sowing_date = validate_sowing_date(
        sowing_date
    )

    # Convert date object to SQLite-friendly format
    validated_sowing_date = (
        validated_sowing_date.isoformat()
    )

    print(
        "Sowing date:",
        validated_sowing_date
    )


    # =====================================================
    # STEP 5: DETERMINE CROP STATUS
    # =====================================================

    print("\nSTEP 5: ANALYSING RICE CROP")

    crop_status = get_crop_status(
        state=state,
        sowing_date=validated_sowing_date,
        selected_season=selected_season
    )


    # =====================================================
    # HANDLE AMBIGUOUS SEASON
    # =====================================================

    if (
        crop_status["status"]
        == "SEASON_SELECTION_REQUIRED"
    ):

        print("\nMultiple rice seasons match")
        print(
            "Possible seasons:",
            crop_status["possible_seasons"]
        )

        return {
            "status": "SEASON_SELECTION_REQUIRED",

            "state": state,

            "possible_seasons":
                crop_status["possible_seasons"]
        }


    print(
        "Rice Season:",
        crop_status["season"]
    )

    print(
        "Days After Sowing:",
        crop_status["days_after_sowing"]
    )

    print(
        "Estimated Growth Stage:",
        crop_status["growth_stage"]
    )


    # =====================================================
    # STEP 6: STORE FARMER
    # =====================================================

    print("\nSTEP 6: REGISTERING FARMER")

    farmer_id = register_farmer(
        name=validated_name,
        phone_number=validated_phone,
        preferred_language=validated_language
    )

    print(
        "Farmer registered:",
        farmer_id
    )


    # =====================================================
    # STEP 7: STORE FARM
    # =====================================================

    print("\nSTEP 7: REGISTERING FARM")

    farm_id = register_farm(
        farmer_id=farmer_id,

        latitude=location["latitude"],

        longitude=location["longitude"],

        state=state
    )

    print(
        "Farm registered:",
        farm_id
    )


    # =====================================================
    # STEP 8: CREATE FIELD
    # =====================================================

    print("\nSTEP 8: CREATING FIELD")

    field_id = create_field(
        farm_id
    )

    print(
        "Field created:",
        field_id
    )


    # =====================================================
    # STEP 9: REGISTER CROP
    # =====================================================

    print("\nSTEP 9: REGISTERING RICE CROP")

    crop_id = register_crop(
        field_id=field_id,

        sowing_date=validated_sowing_date,

        season=crop_status["season"],

        crop_name="Rice"
    )

    print(
        "Crop registered:",
        crop_id
    )


    # =====================================================
    # STEP 10: REGISTER DEVICE
    # =====================================================

    print("\nSTEP 10: REGISTERING DEVICE")

    register_device(
        device_id=validated_device_id,

        field_id=field_id
    )
    register_sensor_node(
    sensor_node_id=f"{validated_device_id}-NW",
    device_id=validated_device_id,
    grid_position="NW"
    )

    register_sensor_node(
        sensor_node_id=f"{validated_device_id}-NE",
        device_id=validated_device_id,
        grid_position="NE"
    )

    register_sensor_node(
        sensor_node_id=f"{validated_device_id}-SW",
        device_id=validated_device_id,
        grid_position="SW"
    )

    register_sensor_node(
        sensor_node_id=f"{validated_device_id}-SE",
        device_id=validated_device_id,
        grid_position="SE"
    )
    print(
            "Device registered:",
            validated_device_id
        )


    # =====================================================
    # FINAL RESULT
    # =====================================================

    result = {

        "status": "SUCCESS",

        "farmer_id": farmer_id,

        "farm_id": farm_id,

        "field_id": field_id,

        "crop_id": crop_id,

        "device_id": validated_device_id,

        "state": state,

        "season": crop_status["season"],

        "days_after_sowing":
            crop_status["days_after_sowing"],

        "growth_stage":
            crop_status["growth_stage"]
    }


    print("\n" + "=" * 60)
    print("FARM REGISTRATION COMPLETED")
    print("=" * 60)

    return result


# =========================================================
# DEVELOPMENT TEST
# =========================================================

if __name__ == "__main__":

    # -----------------------------------------------------
    # CREATE DATABASE
    # -----------------------------------------------------

    create_database()


    # -----------------------------------------------------
    # TEST FARM REGISTRATION
    # -----------------------------------------------------

    try:

        result = register_complete_farm(

            # Farmer
            name="Demo Farmer",

            phone_number="9876543210",

            language="Bengali",


            # Farm GPS
            # Kolkata test coordinates
            latitude=22.5726,

            longitude=88.3639,


            # Crop
            sowing_date="2026-06-15",


            # Device
            device_id="RPI-RICE-0001",


            # Leave None initially.
            # Required only if multiple seasons match.
            selected_season=None
        )


        print("\nFINAL RESULT")

        for key, value in result.items():

            print(
                f"{key}: {value}"
            )


    except Exception as error:

        print("\nREGISTRATION FAILED")

        print(
            "Error:",
            error
        )