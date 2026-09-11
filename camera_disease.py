"""
Rice disease camera inference using the final
MobileNetV3-Small + 576-D embedding + KNN ONNX pipeline.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from PIL import Image


MODEL_ROOT = Path("models")


DEFAULT_MODEL_NAME = "rice_disease_final5_mobilenetv3_knn.onnx"


# FINAL 5 DISEASE CLASSES
# IMPORTANT: order must match the ONNX model
DEFAULT_CLASSES = [
    "Bacterial Blight",
    "Bakanae",
    "Brown Spot",
    "False Smut",
    "Tungro",
]


def find_model(model_root=MODEL_ROOT):
    """Find the final rice disease ONNX model."""

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
    Prepare image exactly as expected by the exported ONNX pipeline.

    Input to ONNX:
        RGB
        224 x 224
        float32
        pixel range [0, 255]

    IMPORTANT:
    The ONNX model itself performs:
        /255
        ImageNet normalization
        MobileNetV3 feature extraction
        L2 normalization
        KNN classification

    Therefore DO NOT normalize the image here.
    """

    image_path = Path(image_path)

    if not image_path.is_file():
        raise FileNotFoundError(
            f"Image not found: {image_path}"
        )

    with Image.open(image_path) as image:

        image = image.convert("RGB")

        image = image.resize(
            (224, 224),
            Image.Resampling.BILINEAR,
        )

        array = np.asarray(
            image,
            dtype=np.float32
        )

    # ONNX expects:
    # [1, 224, 224, 3]
    return np.expand_dims(
        array,
        axis=0
    )


def predict_onnx(model_path, image, classes):

    import onnxruntime as ort

    session = ort.InferenceSession(
        str(model_path),
        providers=["CPUExecutionProvider"]
    )

    input_name = session.get_inputs()[0].name

    outputs = session.run(
        None,
        {
            input_name: image
        }
    )

    predicted_index = int(
        np.asarray(outputs[0]).reshape(-1)[0]
    )

    similarity = float(
        np.asarray(outputs[1]).reshape(-1)[0]
    )

    embedding = np.asarray(
        outputs[2],
        dtype=np.float32
    )

    disease = classes[predicted_index]

    print("\n--- RICE DISEASE MODEL OUTPUT ---")
    print("Predicted class :", disease)
    print("Class index     :", predicted_index)
    print(f"KNN similarity  : {similarity:.6f}")
    print("Embedding shape :", embedding.shape)
    print("----------------------------------")

    return {
        "class_index": predicted_index,
        "disease": disease,
        "similarity": similarity,
        "embedding": embedding,
    }


def predict_camera_disease(
    image_path,
    model_path=None,
    metadata_path=None,
):
    """
    Return camera evidence for the main pipeline.

    The classifier remains single-label,
    but the ONNX model also provides KNN similarity.
    """

    if model_path is None:
        model_path = find_model()
    else:
        model_path = Path(model_path)

    classes = load_classes(
        metadata_path
    )

    image = prepare_image(
        image_path
    )

    result = predict_onnx(
        model_path=model_path,
        image=image,
        classes=classes,
    )

    return {
        "available": True,
        "disease": result["disease"],
        "class_index": result["class_index"],
        "similarity": result["similarity"],
        "source": "CAMERA",
        "image": str(image_path),
    }


if __name__ == "__main__":

    import argparse

    parser = argparse.ArgumentParser(
        description=(
            "Rice disease camera inference using "
            "MobileNetV3 + KNN ONNX"
        )
    )

    parser.add_argument(
        "image",
        help="Path to rice leaf image"
    )

    parser.add_argument(
        "--model",
        help=(
            "Optional ONNX model path"
        )
    )

    parser.add_argument(
        "--metadata",
        help=(
            "Optional metadata JSON path"
        )
    )

    args = parser.parse_args()

    result = predict_camera_disease(
        image_path=args.image,
        model_path=args.model,
        metadata_path=args.metadata,
    )

    print(
        "\nPredicted disease:",
        result["disease"]
    )

    if result["similarity"] is not None:

        print(
            "KNN similarity:",
            f"{result['similarity']:.6f}"
        )