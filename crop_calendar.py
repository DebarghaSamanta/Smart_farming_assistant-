# =========================================================
# CROP CALENDAR
# =========================================================

from datetime import date

from validation import validate_sowing_date


# =========================================================
# RICE CROP CALENDARS
# =========================================================

RICE_CALENDARS = {

    "West Bengal": [

        {
            "season": "AUS",
            "months": [4, 5],
            "duration_days": 120
        },

        {
            "season": "AMAN",
            "months": [6, 7],
            "duration_days": 150
        },

        {
            "season": "BORO",
            "months": [12, 1],
            "duration_days": 150
        }
    ],


    "Odisha": [

        {
            "season": "BEALI",
            "months": [5, 6],
            "duration_days": 120
        },

        {
            "season": "KHARIF_SARAD",
            "months": [6, 7],
            "duration_days": 150
        },

        {
            "season": "RABI_SUMMER",
            "months": [12, 1],
            "duration_days": 130
        }
    ],


    "Tamil Nadu": [

        {
            "season": "NAVARAI",
            "months": [12, 1],
            "duration_days": 120
        },

        {
            "season": "SORNAVARI",
            "months": [4, 5],
            "duration_days": 120
        },

        {
            "season": "KAR",
            "months": [5, 6],
            "duration_days": 120
        },

        {
            "season": "KURUVAI",
            "months": [6, 7],
            "duration_days": 120
        },

        {
            "season": "EARLY_SAMBA",
            "months": [7, 8],
            "duration_days": 135
        },

        {
            "season": "SAMBA",
            "months": [8],
            "duration_days": 150
        },

        {
            "season": "THALADI",
            "months": [9, 10],
            "duration_days": 135
        }
    ],


    "Punjab": [

        {
            "season": "KHARIF_RICE",
            "months": [6, 7],
            "duration_days": 110
        }
    ],


    "Maharashtra": [

        {
            "season": "KHARIF_RICE",
            "months": [6, 7],
            "duration_days": 130
        }
    ]
}


# =========================================================
# NORMALIZE STATE
# =========================================================

def normalize_state(state):

    if not isinstance(state, str):
        raise ValueError(
            "State must be text."
        )

    state = state.strip()

    # Handles capitalization differences
    for available_state in RICE_CALENDARS:

        if available_state.lower() == state.lower():

            return available_state

    raise ValueError(
        f"No rice calendar available for {state}"
    )


# =========================================================
# IDENTIFY POSSIBLE RICE SEASONS
# =========================================================

def identify_rice_season(
        state,
        sowing_date
):

    state = normalize_state(state)

    sowing = validate_sowing_date(
        sowing_date
    )

    sowing_month = sowing.month

    matches = []

    for season_data in RICE_CALENDARS[state]:

        if sowing_month in season_data["months"]:

            matches.append(season_data)

    if not matches:

        raise ValueError(
            f"Sowing date does not match a "
            f"configured rice season in {state}."
        )

    return matches


# =========================================================
# VALIDATE / IDENTIFY SEASON
# =========================================================

def validate_and_identify_season(
        state,
        sowing_date
):

    matches = identify_rice_season(
        state,
        sowing_date
    )

    # Only one possible season
    if len(matches) == 1:

        return {
            "status": "SUCCESS",
            "season_data": matches[0]
        }

    # More than one possible season
    return {
        "status": "SEASON_SELECTION_REQUIRED",
        "possible_seasons": [
            item["season"]
            for item in matches
        ]
    }


# =========================================================
# CALCULATE DAYS AFTER SOWING
# =========================================================

def calculate_days_after_sowing(
        sowing_date,
        current_date=None
):

    sowing = validate_sowing_date(
        sowing_date
    )

    if current_date is None:

        current_date = date.today()

    elif isinstance(current_date, str):

        try:

            current_date = date.fromisoformat(
                current_date
            )

        except ValueError:

            raise ValueError(
                "Current date must use YYYY-MM-DD format."
            )

    if not isinstance(current_date, date):

        raise ValueError(
            "Current date must be a valid date."
        )

    days = (
        current_date - sowing
    ).days

    if days < 0:

        raise ValueError(
            "Current date cannot be before sowing date."
        )

    return days


# =========================================================
# CALCULATE GROWTH STAGE
# =========================================================

def calculate_growth_stage(
        days_after_sowing,
        duration_days
):

    if not isinstance(
        days_after_sowing,
        (int, float)
    ):
        raise ValueError(
            "Days after sowing must be numeric."
        )

    if not isinstance(
        duration_days,
        (int, float)
    ):
        raise ValueError(
            "Crop duration must be numeric."
        )

    if days_after_sowing < 0:

        raise ValueError(
            "Days after sowing cannot be negative."
        )

    if duration_days <= 0:

        raise ValueError(
            "Crop duration must be greater than zero."
        )

    progress = (
        days_after_sowing / duration_days
    )


    if progress <= 0.10:

        return "ESTABLISHMENT"

    elif progress <= 0.30:

        return "VEGETATIVE"

    elif progress <= 0.50:

        return "TILLERING"

    elif progress <= 0.70:

        return "REPRODUCTIVE"

    elif progress <= 0.82:

        return "FLOWERING"

    elif progress <= 0.95:

        return "GRAIN_FILLING"

    elif progress <= 1.10:

        return "MATURITY"

    else:

        return "HARVEST_OVERDUE"


# =========================================================
# SELECT SEASON
# =========================================================

def select_season(
        season_matches,
        selected_season
):

    if not isinstance(selected_season, str):

        raise ValueError(
            "Selected season must be text."
        )

    selected_season = (
        selected_season.strip().upper()
    )

    for season_data in season_matches:

        if (
            season_data["season"].upper()
            == selected_season
        ):

            return season_data

    raise ValueError(
        "Selected season is not valid "
        "for this sowing date."
    )


# =========================================================
# COMPLETE CROP STATUS
# =========================================================

def get_crop_status(
        state,
        sowing_date,
        selected_season=None,
        current_date=None
):

    # Normalize state
    state = normalize_state(state)


    # -----------------------------------------------------
    # FIND POSSIBLE SEASONS
    # -----------------------------------------------------

    season_matches = identify_rice_season(
        state,
        sowing_date
    )


    # -----------------------------------------------------
    # HANDLE MULTIPLE SEASONS
    # -----------------------------------------------------

    if len(season_matches) > 1:

        if selected_season is None:

            return {
                "status":
                    "SEASON_SELECTION_REQUIRED",

                "state":
                    state,

                "possible_seasons": [
                    season["season"]
                    for season in season_matches
                ]
            }

        season_data = select_season(
            season_matches,
            selected_season
        )


    # -----------------------------------------------------
    # ONLY ONE SEASON
    # -----------------------------------------------------

    else:

        season_data = season_matches[0]


    # -----------------------------------------------------
    # CALCULATE DAYS AFTER SOWING
    # -----------------------------------------------------

    days_after_sowing = (
        calculate_days_after_sowing(
            sowing_date,
            current_date
        )
    )


    # -----------------------------------------------------
    # CALCULATE GROWTH STAGE
    # -----------------------------------------------------

    growth_stage = (
        calculate_growth_stage(
            days_after_sowing,
            season_data["duration_days"]
        )
    )


    # -----------------------------------------------------
    # RETURN COMPLETE RESULT
    # -----------------------------------------------------

    return {

        "status": "SUCCESS",

        "state": state,

        "season": (
            season_data["season"]
        ),

        "days_after_sowing":
            days_after_sowing,

        "expected_duration":
            season_data["duration_days"],

        "growth_stage":
            growth_stage
    }


# =========================================================
# TEST
# =========================================================

if __name__ == "__main__":

    try:

        result = get_crop_status(

            state="West Bengal",

            sowing_date="2026-07-01"
        )


        print("\nCROP STATUS\n")

        for key, value in result.items():

            print(
                f"{key}: {value}"
            )


    except Exception as error:

        print(
            "Error:",
            error
        )