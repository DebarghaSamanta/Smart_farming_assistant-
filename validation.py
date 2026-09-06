import re
from datetime import date, datetime


# =========================================================
# SUPPORTED LANGUAGES
# =========================================================

SUPPORTED_LANGUAGES = {
    "bengali": "Bengali",
    "marathi": "Marathi",
    "punjabi": "Punjabi",
    "tamil": "Tamil",
    "odia": "Odia",
    "hindi": "Hindi",
    "english": "English"
}


# =========================================================
# NAME VALIDATION
# =========================================================

def validate_name(name):

    if not isinstance(name, str):
        raise ValueError("Name must be text.")

    name = " ".join(name.strip().split())

    if len(name) < 2:
        raise ValueError(
            "Name must contain at least 2 characters."
        )

    if len(name) > 100:
        raise ValueError(
            "Name is too long."
        )

    # Every meaningful character should be
    # alphabetic or a space/apostrophe/dot.
    for char in name:

        if not (
            char.isalpha()
            or char in " .'"
        ):
            raise ValueError(
                "Name contains invalid characters."
            )

    return name


# =========================================================
# INDIAN PHONE VALIDATION
# =========================================================

def validate_phone(phone_number):

    phone = str(phone_number).strip()

    # Remove common formatting characters
    phone = phone.replace(" ", "")
    phone = phone.replace("-", "")

    # Handle +91XXXXXXXXXX
    if phone.startswith("+91"):
        phone = phone[3:]

    # Handle 91XXXXXXXXXX
    elif phone.startswith("91") and len(phone) == 12:
        phone = phone[2:]

    # Indian mobile number:
    # Starts with 6, 7, 8 or 9
    # Followed by 9 digits
    if not re.fullmatch(
        r"[6-9]\d{9}",
        phone
    ):
        raise ValueError(
            "Invalid Indian mobile number."
        )

    return phone


# =========================================================
# LANGUAGE VALIDATION
# =========================================================

def validate_language(language):

    if not isinstance(language, str):
        raise ValueError(
            "Language must be text."
        )

    normalized = language.strip().lower()

    if normalized not in SUPPORTED_LANGUAGES:

        supported = ", ".join(
            SUPPORTED_LANGUAGES.values()
        )

        raise ValueError(
            f"Unsupported language. "
            f"Supported languages: {supported}"
        )

    return SUPPORTED_LANGUAGES[normalized]


# =========================================================
# GPS COORDINATE VALIDATION
# =========================================================

def validate_coordinates(latitude, longitude):

    try:

        latitude = float(latitude)
        longitude = float(longitude)

    except (TypeError, ValueError):

        raise ValueError(
            "Latitude and longitude must be numeric."
        )

    if not -90 <= latitude <= 90:

        raise ValueError(
            "Latitude must be between -90 and 90."
        )

    if not -180 <= longitude <= 180:

        raise ValueError(
            "Longitude must be between -180 and 180."
        )

    return latitude, longitude


# =========================================================
# INDIA LOCATION SANITY CHECK
# =========================================================

def validate_india_coordinates(
        latitude,
        longitude
):

    latitude, longitude = validate_coordinates(
        latitude,
        longitude
    )

    # Approximate geographic bounds of India.
    # This is only a first-level sanity check,
    # not a precise state boundary check.

    if not (
        6 <= latitude <= 37
        and
        68 <= longitude <= 98
    ):

        raise ValueError(
            "Location appears to be outside India."
        )

    return latitude, longitude


# =========================================================
# SOWING DATE VALIDATION
# =========================================================

def validate_sowing_date(sowing_date):

    if isinstance(sowing_date, date):

        sowing = sowing_date

    elif isinstance(sowing_date, str):

        try:

            sowing = date.fromisoformat(
                sowing_date.strip()
            )

        except ValueError:

            raise ValueError(
                "Sowing date must be in "
                "YYYY-MM-DD format."
            )

    else:

        raise ValueError(
            "Invalid sowing date."
        )

    today = date.today()

    if sowing > today:

        raise ValueError(
            "Sowing date cannot be in the future."
        )

    # Prevent clearly unreasonable historical data.
    if sowing.year < 2000:

        raise ValueError(
            "Sowing date is too old."
        )

    return sowing


# =========================================================
# DEVICE ID VALIDATION
# =========================================================

def validate_device_id(device_id):

    if not isinstance(device_id, str):

        raise ValueError(
            "Device ID must be text."
        )

    device_id = device_id.strip()

    if len(device_id) < 3:

        raise ValueError(
            "Device ID is too short."
        )

    if len(device_id) > 100:

        raise ValueError(
            "Device ID is too long."
        )

    # Example:
    # RPI-RICE-0001
    # DEVICE_123
    # ESP32-001

    if not re.fullmatch(
        r"[A-Za-z0-9_-]+",
        device_id
    ):

        raise ValueError(
            "Device ID contains invalid characters."
        )

    return device_id


# =========================================================
# DAYS AFTER SOWING
# =========================================================

def calculate_days_after_sowing(
        sowing_date
):

    sowing = validate_sowing_date(
        sowing_date
    )

    days = (
        date.today() - sowing
    ).days

    return days