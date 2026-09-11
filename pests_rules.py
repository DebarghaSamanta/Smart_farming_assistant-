# ============================================================
# RICE PEST RULES
# Simple, biologically-informed development rules.
# ============================================================

RISK_BANDS = {
    "LOW": (0, 24),
    "MEDIUM": (25, 49),
    "HIGH": (50, 74),
    "VERY HIGH": (75, 100),
}

# These are development priors where a directly executable local
# research threshold is not available. They are NOT field-calibrated
# probabilities or guaranteed infestation thresholds.
#
# The engine uses the same principle as disease_rules.py:
# temperature + humidity + rainfall + crop stage + DAT.

PEST_RULES = {

    "BPH": {
        "name": "Brown Planthopper",
        "scientific_name": "Nilaparvata lugens",
        "temperature": {"low": 25, "high": 32, "tolerance": 5},
        "humidity": {"threshold": 70, "span": 20},
        "rainfall": {"low": 5, "high": 40, "tolerance": 25, "window": 7},
        "dat": {"low": 25, "high": 100},
        "stage_weights": {
            "SEEDLING": 0.5, "VEGETATIVE": 0.7, "TILLERING": 1.0,
            "REPRODUCTIVE": 0.9, "FLOWERING": 0.8,
            "GRAIN_FILLING": 0.4, "MATURITY": 0.2,
        },
    },

    "YSB": {
        "name": "Yellow Stem Borer",
        "scientific_name": "Scirpophaga incertulas",
        "temperature": {"low": 22, "high": 32, "tolerance": 5},
        "humidity": {"threshold": 60, "span": 25},
        "rainfall": {"low": 0, "high": 40, "tolerance": 30, "window": 7},
        "dat": {"low": 20, "high": 110},
        "stage_weights": {
            "SEEDLING": 0.4, "VEGETATIVE": 0.8, "TILLERING": 1.0,
            "REPRODUCTIVE": 1.0, "FLOWERING": 0.9,
            "GRAIN_FILLING": 0.5, "MATURITY": 0.2,
        },
    },

    "RICE_LEAF_FOLDER": {
        "name": "Rice Leaf Folder",
        "scientific_name": "Cnaphalocrocis medinalis",
        "temperature": {"low": 25, "high": 32, "tolerance": 5},
        "humidity": {"threshold": 70, "span": 20},
        "rainfall": {"low": 5, "high": 50, "tolerance": 30, "window": 7},
        "dat": {"low": 20, "high": 100},
        "stage_weights": {
            "SEEDLING": 0.3, "VEGETATIVE": 0.8, "TILLERING": 1.0,
            "REPRODUCTIVE": 0.9, "FLOWERING": 0.7,
            "GRAIN_FILLING": 0.4, "MATURITY": 0.2,
        },
    },

    "GALL_MIDGE": {
        "name": "Gall Midge",
        "scientific_name": "Orseolia oryzae",
        "temperature": {"low": 25, "high": 30, "tolerance": 5},
        "humidity": {"threshold": 75, "span": 20},
        "rainfall": {"low": 15, "high": 100, "tolerance": 50, "window": 14},
        "dat": {"low": 15, "high": 70},
        "stage_weights": {
            "SEEDLING": 0.6, "VEGETATIVE": 0.9, "TILLERING": 1.0,
            "REPRODUCTIVE": 0.4, "FLOWERING": 0.2,
            "GRAIN_FILLING": 0.1, "MATURITY": 0.0,
        },
    },

    "RICE_BUG": {
        "name": "Rice Bug (Gundhi Bug)",
        "scientific_name": "Leptocorisa acuta",
        "temperature": {"low": 25, "high": 32, "tolerance": 5},
        "humidity": {"threshold": 60, "span": 25},
        "rainfall": {"low": 0, "high": 25, "tolerance": 25, "window": 7},
        "dat": {"low": 55, "high": 125},
        "stage_weights": {
            "VEGETATIVE": 0.2, "TILLERING": 0.3, "REPRODUCTIVE": 0.8,
            "FLOWERING": 1.0, "GRAIN_FILLING": 1.0, "MATURITY": 0.7,
        },
    },

    "GLH": {
        "name": "Green Leaf Hopper",
        "scientific_name": "Nephotettix spp.",
        "temperature": {"low": 25, "high": 32, "tolerance": 5},
        "humidity": {"threshold": 70, "span": 20},
        "rainfall": {"low": 5, "high": 40, "tolerance": 30, "window": 7},
        "dat": {"low": 15, "high": 100},
        "stage_weights": {
            "SEEDLING": 0.7, "VEGETATIVE": 0.9, "TILLERING": 1.0,
            "REPRODUCTIVE": 0.8, "FLOWERING": 0.5,
            "GRAIN_FILLING": 0.3, "MATURITY": 0.1,
        },
    },

    "WBPH": {
        "name": "Whitebacked Planthopper",
        "scientific_name": "Sogatella furcifera",
        "temperature": {"low": 25, "high": 32, "tolerance": 5},
        "humidity": {"threshold": 70, "span": 20},
        "rainfall": {"low": 5, "high": 40, "tolerance": 25, "window": 7},
        "dat": {"low": 25, "high": 100},
        "stage_weights": {
            "SEEDLING": 0.4, "VEGETATIVE": 0.8, "TILLERING": 1.0,
            "REPRODUCTIVE": 0.8, "FLOWERING": 0.6,
            "GRAIN_FILLING": 0.3, "MATURITY": 0.1,
        },
    },

    "RICE_THRIPS": {
        "name": "Rice Thrips",
        "scientific_name": "Stenchaetothrips biformis",
        "temperature": {"low": 25, "high": 32, "tolerance": 5},
        "humidity": {"threshold": 55, "span": 25},
        "rainfall": {"low": 0, "high": 20, "tolerance": 25, "window": 7},
        "dat": {"low": 5, "high": 50},
        "stage_weights": {
            "SEEDLING": 1.0, "VEGETATIVE": 0.9, "TILLERING": 0.7,
            "REPRODUCTIVE": 0.3, "FLOWERING": 0.2,
            "GRAIN_FILLING": 0.1, "MATURITY": 0.0,
        },
    },
}


def classify_risk(score):
    score = max(0.0, min(100.0, float(score)))
    if score < 25:
        return "LOW"
    if score < 50:
        return "MEDIUM"
    if score < 75:
        return "HIGH"
    return "VERY HIGH"


def pest_rule(pest_key):
    return PEST_RULES[pest_key]


def score_all_pests(*args, **kwargs):
    # Kept as a compatibility shim only.
    from pest_scoring import score_all_pests as _score_all_pests
    return _score_all_pests(*args, **kwargs)


if __name__ == "__main__":
    print("Registered rice pests:", len(PEST_RULES))
    for key, rule in PEST_RULES.items():
        print("-", key, ":", rule["name"])
