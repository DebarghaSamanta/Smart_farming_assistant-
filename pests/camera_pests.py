
"""
Rice pest camera inference.

This inference code mirrors the actual training/export pipeline:

    Image
      ↓
    RGB
      ↓
    Resize 224 x 224
      ↓
    [0,255] -> [0,1]
      ↓
    ImageNet normalization
      ↓
    NHWC [1,224,224,3]
      ↓
    MobileNetV3-Small ONNX
      ↓
    Softmax
      ↓
    8-class pest prediction
"""

from __future__ import annotations

from pathlib import Path
import argparse

import numpy as np
from PIL import Image
import onnxruntime as ort


# ============================================================
# PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

MODEL_PATH = (
    BASE_DIR /
    "rice_pest_final.onnx"
)


# ============================================================
# MODEL CONFIGURATION
# ============================================================

IMAGE_SIZE = 224
NUM_CLASSES = 8

CLASS_NAMES = [
    "brown plant hopper",
    "paddy stem maggot",
    "rice borer",
    "rice gall midge",
    "rice leaf roller",
    "rice leafhopper",
    "rice water weevil",
    "small brown plant hopper",
]


# ============================================================
# IMAGE NORMALIZATION
#
# EXACTLY MATCHES THE TRAINING NOTEBOOK
# ============================================================

IMAGENET_MEAN = np.array(
    [0.485, 0.456, 0.406],
    dtype=np.float32,
)

IMAGENET_STD = np.array(
    [0.229, 0.224, 0.225],
    dtype=np.float32,
)


# ============================================================
# LOAD MODEL
# ============================================================

if not MODEL_PATH.exists():
    raise FileNotFoundError(
        f"Rice pest ONNX model not found:\n"
        f"{MODEL_PATH}"
    )


session = ort.InferenceSession(
    str(MODEL_PATH),
    providers=[
        "CPUExecutionProvider"
    ],
)


# ============================================================
# READ MODEL INTERFACE
# ============================================================

input_info = session.get_inputs()[0]
output_info = session.get_outputs()[0]

INPUT_NAME = input_info.name
OUTPUT_NAME = output_info.name


print("\n========== RICE PEST MODEL ==========")
print("Model :", MODEL_PATH)
print("Input :", INPUT_NAME)
print("Shape :", input_info.shape)
print("Type  :", input_info.type)
print("Output:", OUTPUT_NAME)
print("OShape:", output_info.shape)
print("======================================\n")


# ============================================================
# VERIFY MODEL
# ============================================================

if input_info.type != "tensor(float)":
    raise TypeError(
        "Expected float32 ONNX input, "
        f"found {input_info.type}"
    )


actual_shape = input_info.shape

if len(actual_shape) != 4:
    raise ValueError(
        f"Expected 4D input, found {actual_shape}"
    )

if actual_shape[1] != IMAGE_SIZE:
    raise ValueError(
        f"Expected height {IMAGE_SIZE}, "
        f"found {actual_shape[1]}"
    )

if actual_shape[2] != IMAGE_SIZE:
    raise ValueError(
        f"Expected width {IMAGE_SIZE}, "
        f"found {actual_shape[2]}"
    )

if actual_shape[3] != 3:
    raise ValueError(
        f"Expected 3 RGB channels, "
        f"found {actual_shape[3]}"
    )


if len(CLASS_NAMES) != NUM_CLASSES:
    raise ValueError(
        f"Expected {NUM_CLASSES} classes, "
        f"found {len(CLASS_NAMES)}"
    )


# ============================================================
# IMAGE PREPROCESSING
#
# EXACT EQUIVALENT OF:
#
# transforms.Compose([
#     transforms.Resize((224,224)),
#     transforms.ToTensor(),
#     transforms.Normalize(
#         mean=[0.485,0.456,0.406],
#         std=[0.229,0.224,0.225]
#     )
# ])
#
# The ONNX wrapper already performs the same operations.
# Therefore this function returns RAW 0..255 RGB pixels.
# ============================================================

def prepare_image(image_path):
    """
    Prepare image for the exported ONNX model.

    Returns:

        shape  = [1, 224, 224, 3]
        dtype  = float32
        range  = 0..255
        layout = NHWC
        color  = RGB
    """

    image_path = Path(image_path)

    if not image_path.is_file():
        raise FileNotFoundError(
            f"Image not found:\n{image_path}"
        )


    # --------------------------------------------------------
    # PIL RGB
    # --------------------------------------------------------

    with Image.open(image_path) as image:

        image = image.convert("RGB")

        # Same resize requested by training.
        image = image.resize(
            (IMAGE_SIZE, IMAGE_SIZE),
            Image.Resampling.BILINEAR,
        )

        image_array = np.asarray(
            image,
            dtype=np.float32,
        )


    # --------------------------------------------------------
    # Add batch dimension
    #
    # [224,224,3]
    #       ↓
    # [1,224,224,3]
    # --------------------------------------------------------

    image_array = np.expand_dims(
        image_array,
        axis=0,
    )


    return image_array


# ============================================================
# PREDICTION
# ============================================================

def predict_pest(image_path):
    """
    Predict rice pest from one image.

    Returns:

    {
        "prediction": str,
        "confidence": float,
        "probabilities": dict,
        "top3": list
    }
    """

    image = prepare_image(
        image_path
    )


    # --------------------------------------------------------
    # ONNX INFERENCE
    #
    # The exported ONNX model itself performs:
    #
    # /255
    # ImageNet normalization
    # NHWC -> NCHW
    # MobileNetV3
    # Softmax
    # --------------------------------------------------------

    raw_output = session.run(
        [OUTPUT_NAME],
        {
            INPUT_NAME: image
        },
    )[0]


    probabilities = np.asarray(
        raw_output,
        dtype=np.float32,
    )


    # --------------------------------------------------------
    # Remove batch dimension
    #
    # [1,8] -> [8]
    # --------------------------------------------------------

    if probabilities.ndim != 2:
        raise ValueError(
            "Unexpected ONNX output dimensions: "
            f"{probabilities.shape}"
        )

    if probabilities.shape[0] != 1:
        raise ValueError(
            "Expected batch size 1, "
            f"found {probabilities.shape}"
        )

    if probabilities.shape[1] != NUM_CLASSES:
        raise ValueError(
            "Expected "
            f"{NUM_CLASSES} class probabilities, "
            f"found {probabilities.shape}"
        )


    probabilities = probabilities[0]


    # --------------------------------------------------------
    # VALIDATE PROBABILITIES
    # --------------------------------------------------------

    if not np.all(
        np.isfinite(probabilities)
    ):
        raise ValueError(
            "Model returned NaN or infinite values."
        )


    if np.any(probabilities < 0):
        raise ValueError(
            "Model returned negative probabilities."
        )


    if np.any(probabilities > 1):
        raise ValueError(
            "Model returned values greater than 1."
        )


    probability_sum = float(
        probabilities.sum()
    )


    if not np.isclose(
        probability_sum,
        1.0,
        atol=1e-3,
    ):
        raise ValueError(
            "Model output does not look like "
            f"Softmax probabilities. Sum={probability_sum}"
        )


    # --------------------------------------------------------
    # PREDICTED CLASS
    # --------------------------------------------------------

    predicted_index = int(
        np.argmax(probabilities)
    )

    predicted_class = CLASS_NAMES[
        predicted_index
    ]

    confidence = float(
        probabilities[predicted_index]
    )


    # --------------------------------------------------------
    # TOP 3
    # --------------------------------------------------------

    ranked_indices = np.argsort(
        probabilities
    )[::-1]

    top3 = []

    for index in ranked_indices[:3]:

        index = int(index)

        top3.append(
            {
                "class": CLASS_NAMES[index],
                "confidence": float(
                    probabilities[index]
                ),
            }
        )


    # --------------------------------------------------------
    # RESULT
    # --------------------------------------------------------

    return {
        "prediction": predicted_class,
        "confidence": confidence,
        "probabilities": {
            CLASS_NAMES[i]: float(
                probabilities[i]
            )
            for i in range(NUM_CLASSES)
        },
        "top3": top3,
    }


# ============================================================
# COMMAND LINE
# ============================================================

def main():

    parser = argparse.ArgumentParser(
        description=(
            "Rice pest prediction using "
            "MobileNetV3-Small ONNX"
        )
    )

    parser.add_argument(
        "image_path",
        help="Path to rice pest image",
    )

    args = parser.parse_args()


    result = predict_pest(
        args.image_path
    )


    print(
        "\n"
        + "=" * 65
    )

    print(
        "RICE PEST PREDICTION"
    )

    print(
        "=" * 65
    )

    print(
        f"\nImage      : {args.image_path}"
    )

    print(
        f"Prediction : {result['prediction']}"
    )

    print(
        f"Confidence : "
        f"{result['confidence'] * 100:.2f}%"
    )


    print(
        "\nTop 3 predictions:"
    )

    for item in result["top3"]:

        print(
            f"  {item['class']:30s} "
            f"{item['confidence'] * 100:7.2f}%"
        )


    print(
        "\nAll probabilities:"
    )

    for class_name, probability in (
        result["probabilities"].items()
    ):

        print(
            f"  {class_name:30s} "
            f"{probability * 100:7.2f}%"
        )


    print(
        "\n"
        + "=" * 65
    )


if __name__ == "__main__":
    main()

