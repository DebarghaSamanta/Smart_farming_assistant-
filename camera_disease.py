"""
Rice disease camera inference using MobileNetV3 ONNX.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from PIL import Image


MODEL_ROOT = Path("models")
DEFAULT_MODEL_NAME = "rice_disease_mobilenetv3_best.onnx"

DEFAULT_CLASSES = [
    "Bacterial Blight",
    "Bacterial Streak",
    "Bakanae",
    "Brown Spot",
    "False Smut",
    "Grassy Stunt Virus",
    "Healthy",
    "Hispa",
    "Leaf Blast",
    "Leaf Scald",
    "Leaf Smut",
    "Narrow Brown Spot",
    "Neck Blast",
    "Ragged Stunt Virus",
    "Sheath Blight",
    "Sheath Rot",
    "Stem Rot",
    "Tungro",
]


def find_model(model_root=MODEL_ROOT):
    """Find the current rice disease ONNX model."""

    model_path = Path(model_root) / DEFAULT_MODEL_NAME

    if model_path.exists():
        return model_path

    matches = list(
        Path(model_root).rglob(DEFAULT_MODEL_NAME)
    )

    if matches:
        return matches[0]

    raise FileNotFoundError(
        f"Rice disease model not found. "
        f"Expected: {model_path}"
    )


def load_classes(metadata_path=None):
    """
    Load the rice disease class list from metadata.json.

    Expected structure:

    {
        "models": {
            "rice_disease": {
                "classes": [...]
            }
        }
    }
    """

    if metadata_path is None:
        return DEFAULT_CLASSES.copy()

    metadata_path = Path(metadata_path)

    if not metadata_path.exists():
        return DEFAULT_CLASSES.copy()

    with open(
        metadata_path,
        "r",
        encoding="utf-8"
    ) as f:
        metadata = json.load(f)

    classes = (
        metadata
        .get("models", {})
        .get("rice_disease", {})
        .get("classes")
    )

    if classes:
        return list(classes)

    return DEFAULT_CLASSES.copy()


def prepare_image(image_path):
    """
    Prepare image exactly for MobileNetV3.

    Input:
        RGB
        224 x 224

    MobileNetV3 preprocessing:
        [0, 255] -> [-1, 1]
    """

    image_path = Path(image_path)

    if not image_path.is_file():
        raise FileNotFoundError(
            f"Image not found: {image_path}"
        )

    with Image.open(image_path) as image:

        image = image.convert("RGB")

        image = image.resize(
            (224, 224)
        )

        array = np.asarray(
            image,
            dtype=np.float32
        )

    
    return np.expand_dims(array, axis=0)


def predict_onnx(model_path, image):
    """Run ONNX inference on CPU and print all class scores."""

    import onnxruntime as ort

    session = ort.InferenceSession(
        str(model_path),
        providers=["CPUExecutionProvider"],
    )

    input_name = session.get_inputs()[0].name

    output = session.run(
        None,
        {
            input_name: image
        }
    )[0]

    # Your 18 classes

    print("\n--- MODEL OUTPUT ---")

    for i, score in enumerate(output[0]):
        print(f"{i:2d} {DEFAULT_CLASSES[i]:25s} {float(score):.6f}")

    predicted_index = int(
        np.argmax(output, axis=1)[0]
    )

    print("--------------------")
    print(
        "Winner:",
        DEFAULT_CLASSES[predicted_index],
        "index:",
        predicted_index
    )

    return predicted_index

def predict_from_image(
    image_path,
    model_path=None,
    metadata_path=None,
):
    """
    Predict rice disease from one leaf image.

    Returns ONLY the predicted class.

    Example:
        "Brown Spot"
    """

    if model_path is None:
        model_path = find_model()
    else:
        model_path = Path(model_path)

    if not model_path.exists():
        raise FileNotFoundError(
            f"Model not found: {model_path}"
        )

    if model_path.suffix.lower() != ".onnx":
        raise ValueError(
            "Camera inference requires "
            "an ONNX model (.onnx)."
        )

    classes = load_classes(
        metadata_path
    )

    image = prepare_image(
        image_path
    )

    predicted_index = predict_onnx(
        model_path,
        image
    )

    if predicted_index >= len(classes):
        raise RuntimeError(
            f"Model returned class index "
            f"{predicted_index}, but metadata "
            f"contains only {len(classes)} classes."
        )

    return classes[predicted_index]


def predict_camera_disease(
    image_path,
    model_path=None,
    metadata_path=None,
):
    """
    Return camera evidence for the main pipeline.

    The actual classifier remains single-label.
    """

    disease = predict_from_image(
        image_path=image_path,
        model_path=model_path,
        metadata_path=metadata_path,
    )

    return {
        "available": True,
        "disease": disease,
        "source": "CAMERA",
        "image": str(image_path),
    }


if __name__ == "__main__":

    import argparse

    parser = argparse.ArgumentParser(
        description="Rice disease camera inference"
    )

    parser.add_argument(
        "image",
        help="Path to rice leaf image"
    )

    parser.add_argument(
        "--model",
        help="Optional ONNX model path"
    )

    parser.add_argument(
        "--metadata",
        help="Optional metadata JSON path"
    )

    args = parser.parse_args()

    result = predict_camera_disease(
        image_path=args.image,
        model_path=args.model,
        metadata_path=args.metadata,
    )

    print(
        "Predicted disease:",
        result["disease"]
    )