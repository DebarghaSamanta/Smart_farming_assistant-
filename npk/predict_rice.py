# ============================================================
# RICE NPK INFERENCE MODULE
# ============================================================
#
# Project-ready inference for the trained rice N/P/K classifier.
#
# Pipeline:
#   image -> 61 handcrafted features -> saved feature order
#         -> Random Forest -> N/P/K deficiency prediction
#
# The trained artifacts are expected to live beside this file:
#   rice_npk_rf.pkl
#   rice_npk_feature_columns.pkl
#
# The 61-feature extractor below is kept compatible with the
# preprocessing used by the trained model.
# ============================================================

from pathlib import Path
import argparse
import cv2
import joblib
import numpy as np
import pandas as pd


# ============================================================
# LOAD TRAINED MODEL + FEATURE ORDER
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

MODEL_PATH = BASE_DIR / "rice_npk_rf.pkl"
FEATURES_PATH = BASE_DIR / "rice_npk_feature_columns.pkl"

if not MODEL_PATH.exists():
    raise FileNotFoundError(f"Rice NPK model not found: {MODEL_PATH}")

if not FEATURES_PATH.exists():
    raise FileNotFoundError(
        f"Rice NPK feature-column file not found: {FEATURES_PATH}"
    )

model = joblib.load(MODEL_PATH)
feature_cols = joblib.load(FEATURES_PATH)

# Fail early if the saved artifacts are incompatible with this extractor.
if len(feature_cols) != 61:
    raise ValueError(
        f"Expected 61 saved feature columns, found {len(feature_cols)}"
    )

if getattr(model, "n_features_in_", 61) != len(feature_cols):
    raise ValueError(
        "Model/feature mismatch: "
        f"model expects {getattr(model, 'n_features_in_', 'unknown')} "
        f"features, but feature file contains {len(feature_cols)}"
    )

if not hasattr(model, "predict_proba"):
    raise TypeError("The loaded rice NPK model does not support predict_proba().")


# ============================================================
# 61-FEATURE EXTRACTOR
# ============================================================

def extract_61_features(image_path):

    img = cv2.imread(image_path)

    if img is None:
        raise FileNotFoundError(
            f"Could not read image: {image_path}"
        )

    # --------------------------------------------------------
    # Resize
    # --------------------------------------------------------

    img = cv2.resize(img, (256, 256))

    # --------------------------------------------------------
    # BGR -> RGB
    # --------------------------------------------------------

    rgb = cv2.cvtColor(
        img,
        cv2.COLOR_BGR2RGB
    )

    R = rgb[:, :, 0].astype(np.float32)
    G = rgb[:, :, 1].astype(np.float32)
    B = rgb[:, :, 2].astype(np.float32)

    # --------------------------------------------------------
    # Excess Green
    # --------------------------------------------------------

    ExG = 2 * G - R - B

    # --------------------------------------------------------
    # Leaf mask
    # --------------------------------------------------------

    mask = (
        (G > R * 0.90) &
        (G > B * 0.90) &
        (ExG > 10)
    ).astype(np.uint8)

    kernel = np.ones((5, 5), np.uint8)

    mask = cv2.morphologyEx(
        mask,
        cv2.MORPH_OPEN,
        kernel
    )

    mask = cv2.morphologyEx(
        mask,
        cv2.MORPH_CLOSE,
        kernel
    )

    # --------------------------------------------------------
    # Largest connected component
    # --------------------------------------------------------

    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(
        mask,
        8
    )

    if num_labels > 1:

        largest = 1 + np.argmax(
            stats[1:, cv2.CC_STAT_AREA]
        )

        leaf_mask = (
            labels == largest
        ).astype(np.uint8)

    else:

        leaf_mask = mask

    # --------------------------------------------------------
    # Fallback
    # --------------------------------------------------------

    if leaf_mask.sum() < 500:

        leaf_mask = np.ones(
            (256, 256),
            dtype=np.uint8
        )

    m = leaf_mask.astype(bool)

    # ========================================================
    # HSV
    # ========================================================

    hsv = cv2.cvtColor(
        rgb.astype(np.uint8),
        cv2.COLOR_RGB2HSV
    ).astype(np.float32)

    H = hsv[:, :, 0]
    S = hsv[:, :, 1]
    V = hsv[:, :, 2]

    # ========================================================
    # LAB
    # ========================================================

    lab = cv2.cvtColor(
        rgb.astype(np.uint8),
        cv2.COLOR_RGB2LAB
    ).astype(np.float32)

    L = lab[:, :, 0]
    A = lab[:, :, 1]
    LabB = lab[:, :, 2]

    # ========================================================
    # FEATURE DICTIONARY
    # ========================================================

    f = {}

    # --------------------------------------------------------
    # RGB / HSV / LAB statistics
    # --------------------------------------------------------

    for name, arr in [
        ("R", R),
        ("G", G),
        ("B", B),
        ("H", H),
        ("HSV_S", S),
        ("V", V),
        ("Lab_L", L),
        ("Lab_A", A),
        ("Lab_B", LabB)
    ]:

        values = arr[m]

        f[f"{name}_mean"] = values.mean()
        f[f"{name}_std"] = values.std()
        f[f"{name}_median"] = np.median(values)

    # ========================================================
    # NORMALIZED RGB
    # ========================================================

    rgb_sum = R + G + B + 1e-6

    f["r_mean"] = (R / rgb_sum)[m].mean()
    f["g_mean"] = (G / rgb_sum)[m].mean()
    f["b_mean"] = (B / rgb_sum)[m].mean()

    # ========================================================
    # EXG
    # ========================================================

    f["ExG_mean"] = ExG[m].mean()
    f["ExG_std"] = ExG[m].std()

    # ========================================================
    # COLOR MASKS
    # ========================================================

    yellow = (
        (R > 80) &
        (G > 80) &
        (R > B * 1.15) &
        (G > B * 1.15)
    )

    brown = (
        (R > G * 1.05) &
        (G > B * 1.15) &
        (R > 60)
    )

    purple = (
        (R > B * 1.05) &
        (B > G * 1.05) &
        (R > 50)
    )

    # Green mask recovered from the feature CSV
    green = (
        (G > R * 1.05) &
        (G > B * 1.05) &
        (ExG > 5)
    )

    f["green_ratio"] = green[m].mean()
    f["yellow_ratio"] = yellow[m].mean()
    f["brown_ratio"] = brown[m].mean()
    f["purple_ratio"] = purple[m].mean()

    # ========================================================
    # IMAGE DIMENSIONS
    # ========================================================

    h, w = leaf_mask.shape

    # ========================================================
    # TOP / MIDDLE / BOTTOM
    # ========================================================

    vertical_zones = {
        "top": (
            slice(0, h // 3),
            slice(None)
        ),
        "middle": (
            slice(h // 3, 2 * h // 3),
            slice(None)
        ),
        "bottom": (
            slice(2 * h // 3, h),
            slice(None)
        )
    }

    for name, sl in vertical_zones.items():

        zone = np.zeros_like(
            m,
            dtype=bool
        )

        zone[sl] = True
        zone &= m

        if zone.sum() == 0:

            f[f"{name}_yellow"] = 0
            f[f"{name}_brown"] = 0
            f[f"{name}_green"] = 0

        else:

            f[f"{name}_yellow"] = yellow[zone].mean()
            f[f"{name}_brown"] = brown[zone].mean()
            f[f"{name}_green"] = green[zone].mean()

    # ========================================================
    # LEFT / CENTER / RIGHT
    # ========================================================

    horizontal_zones = {
        "left": (
            slice(None),
            slice(0, w // 3)
        ),
        "center": (
            slice(None),
            slice(w // 3, 2 * w // 3)
        ),
        "right": (
            slice(None),
            slice(2 * w // 3, w)
        )
    }

    for name, sl in horizontal_zones.items():

        zone = np.zeros_like(
            m,
            dtype=bool
        )

        zone[sl] = True
        zone &= m

        if zone.sum() == 0:

            f[f"{name}_yellow"] = 0
            f[f"{name}_brown"] = 0
            f[f"{name}_green"] = 0

        else:

            f[f"{name}_yellow"] = yellow[zone].mean()
            f[f"{name}_brown"] = brown[zone].mean()
            f[f"{name}_green"] = green[zone].mean()

    # ========================================================
    # MARGIN / INTERIOR
    # ========================================================

    eroded = cv2.erode(
        leaf_mask,
        np.ones((11, 11), np.uint8),
        iterations=1
    )

    margin = (
        (leaf_mask == 1) &
        (eroded == 0)
    )

    interior = (
        eroded == 1
    )

    f["margin_yellow"] = (
        yellow[margin].mean()
        if margin.sum()
        else 0
    )

    f["margin_brown"] = (
        brown[margin].mean()
        if margin.sum()
        else 0
    )

    f["margin_green"] = (
        green[margin].mean()
        if margin.sum()
        else 0
    )

    f["interior_yellow"] = (
        yellow[interior].mean()
        if interior.sum()
        else 0
    )

    f["interior_brown"] = (
        brown[interior].mean()
        if interior.sum()
        else 0
    )

    f["margin_vs_interior_yellow"] = (
        f["margin_yellow"] -
        f["interior_yellow"]
    )

    f["margin_vs_interior_brown"] = (
        f["margin_brown"] -
        f["interior_brown"]
    )

    return f


# ============================================================
# PREDICTION FUNCTION
# ============================================================

def predict_rice(image_path):
    """
    Predict the rice nutrient-deficiency class for one image.

    Parameters
    ----------
    image_path : str or pathlib.Path
        Path to the rice-leaf image.

    Returns
    -------
    dict
        {
            "prediction": "Nitrogen(N)" | "Phosphorus(P)" | "Potassium(K)",
            "probabilities": {
                class_name: probability,
                ...
            }
        }
    """
    image_path = Path(image_path)

    if not image_path.exists():
        raise FileNotFoundError(f"Image not found: {image_path}")

    features = extract_61_features(str(image_path))

    if len(features) != 61:
        raise ValueError(
            f"Feature extractor produced {len(features)} features; "
            "expected exactly 61."
        )

    # Put features in exactly the order used during model training.
    missing = [col for col in feature_cols if col not in features]
    extra = [col for col in features if col not in feature_cols]

    if missing:
        raise ValueError(f"Missing required features: {missing}")

    if extra:
        raise ValueError(f"Unexpected extracted features: {extra}")

    X_new = pd.DataFrame(
        [[features[col] for col in feature_cols]],
        columns=feature_cols
    )

    prediction = model.predict(X_new)[0]
    probabilities = model.predict_proba(X_new)[0]

    results = {
        str(cls): float(probability)
        for cls, probability in zip(model.classes_, probabilities)
    }

    return {
        "prediction": str(prediction),
        "probabilities": results
    }


# ============================================================
# OPTIONAL COMMAND-LINE TESTER
# ============================================================
#
# This keeps the convenient:
#
#     python predict_rice.py path/to/image.jpg
#
# for testing, while the actual project can simply import
# predict_rice().
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="Predict N/P/K nutrient deficiency from a rice-leaf image."
    )
    parser.add_argument(
        "image_path",
        help="Path to the rice-leaf image"
    )
    args = parser.parse_args()

    result = predict_rice(args.image_path)

    print("\n" + "=" * 65)
    print("RICE N/P/K NUTRIENT DEFICIENCY PREDICTION")
    print("=" * 65)

    print(f"\nImage: {args.image_path}")
    print(f"Prediction: {result['prediction']}")

    print("\nModel probabilities:")
    for cls, probability in result["probabilities"].items():
        print(f"  {cls:<20} {probability * 100:.2f}%")

    print("=" * 65)


if __name__ == "__main__":
    main()
