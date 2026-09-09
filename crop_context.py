from datetime import date, datetime
from crop_calendar import get_crop_status


# PROTOTYPE: replace stage values with research-backed/calibrated values later.
BASE_RICE_STAGE_SENSITIVITY = {
    "ESTABLISHMENT": 0.60,
    "VEGETATIVE": 0.50,
    "TILLERING": 0.70,
    "REPRODUCTIVE": 0.90,
    "FLOWERING": 1.00,
    "GRAIN_FILLING": 0.85,
    "MATURITY": 0.40,
    "HARVEST_OVERDUE": 0.20,
}

# Keep at 1.00 until research provides defensible regional/seasonal factors.
LOCATION_SEASON_ADJUSTMENTS = {
    "WEST BENGAL": {"AUS": 1.00, "AMAN": 1.00, "BORO": 1.00},
    "ODISHA": {"BEALI": 1.00, "KHARIF_SARAD": 1.00, "RABI_SUMMER": 1.00},
    "TAMIL NADU": {
        "NAVARAI": 1.00, "SORNAVARI": 1.00, "KAR": 1.00,
        "KURUVAI": 1.00, "EARLY_SAMBA": 1.00, "SAMBA": 1.00,
        "THALADI": 1.00,
    },
    "PUNJAB": {"KHARIF_RICE": 1.00},
    "MAHARASHTRA": {"KHARIF_RICE": 1.00},
    "UTTAR PRADESH": {"KHARIF_RICE": 1.00},
}

CRITICAL_RICE_STAGES = {
    "ESTABLISHMENT",
    "VEGETATIVE",
    "TILLERING",
    "REPRODUCTIVE",
    "FLOWERING",
    "GRAIN_FILLING",
    "MATURITY",
    "HARVEST_OVERDUE"
}


def _normalize(value):
    return str(value).strip().upper() if value is not None else None


def _get_adjustment(state, season):
    return LOCATION_SEASON_ADJUSTMENTS.get(state, {}).get(season)


def get_crop_context(
    crop,
    state,
    season,
    sowing_date,
    current_date=None,
):
    crop = _normalize(crop)
    state = _normalize(state)
    season = _normalize(season)

    if crop != "RICE":
        return {
            "available": False,
            "reason": "Only rice is currently supported.",
            "crop": crop,
            "state": state,
            "season": season,
        }

    adjustment = _get_adjustment(state, season)
    if adjustment is None:
        return {
            "available": False,
            "reason": "Crop context is not configured for this state and season.",
            "crop": crop,
            "state": state,
            "season": season,
        }

    crop_status = get_crop_status(
        state=state,
        sowing_date=sowing_date,
        selected_season=season,
        current_date=current_date,
    )

    if not crop_status.get("available", True) or "growth_stage" not in crop_status:
        return {
            "available": False,
            "reason": "Unable to determine crop growth stage.",
            "crop": crop,
            "state": state,
            "season": season,
            "crop_calendar_status": crop_status,
        }

    growth_stage = crop_status["growth_stage"]
    base_sensitivity = BASE_RICE_STAGE_SENSITIVITY.get(growth_stage)

    if base_sensitivity is None:
        return {
            "available": False,
            "reason": f"No drought sensitivity configured for stage: {growth_stage}",
            "crop": crop,
            "state": state,
            "season": season,
            "crop_calendar_status": crop_status,
        }

    return {
        "available": True,
        "crop": crop,
        "state": state,
        "season": season,
        "days_after_sowing": crop_status.get("days_after_sowing"),
        "expected_duration_days": crop_status.get("expected_duration"),
        "growth_stage": growth_stage,
        "base_drought_sensitivity": base_sensitivity,
        "location_season_adjustment": adjustment,
        "drought_sensitivity": round(base_sensitivity * adjustment, 3),
        "critical_stage": growth_stage in CRITICAL_RICE_STAGES,
        "sensitivity_source": "DERIVED_PROTOTYPE",
        "context_version": "rice_v1",
        "crop_calendar_status": crop_status,
    }


def get_supported_crop_contexts():
    return {
        state: list(seasons.keys())
        for state, seasons in LOCATION_SEASON_ADJUSTMENTS.items()
    }


if __name__ == "__main__":
    print(get_crop_context(
        crop="rice",
        state="West Bengal",
        season="Aman",
        sowing_date="2026-07-01",
    ))
