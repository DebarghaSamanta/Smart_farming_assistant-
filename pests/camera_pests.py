# ============================================================
# RICE PEST INFERENCE MODULE - ONNX
# ============================================================
#
# Project-ready inference for the trained MobileNetV3-Small
# rice pest classifier.
#
# Pipeline:
#
#   image
#      ↓
#   resize to 224 x 224
#      ↓
#   BGR -> RGB
#      ↓
#   scale pixels to [0, 1]
#      ↓
#   ImageNet normalization
#      ↓
#   float32 NHWC tensor [1, 224, 224, 3]
#      ↓
#   MobileNetV3-Small ONNX
#      ↓
#   Softmax output [1, 8]
#      ↓
#   pest + confidence + top-3
#
# The ONNX model contract:
#   Input name  : input
#   Input shape : [1, 224, 224, 3]
#   Input type  : float32
#   Output name : output
#   Output shape: [1, 8]
#   Output      : Softmax probabilities
#
# Import from the main project:
#
#   from predict_pests import predict_pest
#   result = predict_pest("image.jpg")
#
# Command-line test:
#
#   python predict_pests.py image.jpg
# ============================================================

from pathlib import Path
import argparse

import cv2
import numpy as np
import onnxruntime as ort


# ============================================================
# MODEL CONFIGURATION
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

MODEL_PATH = BASE_DIR / "mobilenetv3_model_pests.onnx"

INPUT_NAME = "input"
OUTPUT_NAME = "output"

INPUT_HEIGHT = 224
INPUT_WIDTH = 224
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


# ImageNet normalization values.
# These are applied AFTER scaling the image from [0,255] to [0,1].
IMAGENET_MEAN = np.array(
    [0.485, 0.456, 0.406],
    dtype=np.float32
)

IMAGENET_STD = np.array(
    [0.229, 0.224, 0.225],
    dtype=np.float32
)


# ============================================================
# LOAD ONNX MODEL
# ============================================================

if not MODEL_PATH.exists():
    raise FileNotFoundError(
        f"Rice pest ONNX model not found: {MODEL_PATH}"
    )

session = ort.InferenceSession(
    str(MODEL_PATH),
    providers=["CPUExecutionProvider"]
)


# ============================================================
# VERIFY ONNX MODEL CONTRACT
# ============================================================

input_info = session.get_inputs()[0]
output_info = session.get_outputs()[0]
INPUT_NAME = input_info.name
OUTPUT_NAME = output_info.name
if input_info.name != INPUT_NAME:
    raise ValueError(
        f"Expected ONNX input name '{INPUT_NAME}', "
        f"but found '{input_info.name}'"
    )

if input_info.type != "tensor(float)":
    raise TypeError(
        f"Expected ONNX input type tensor(float), "
        f"but found '{input_info.type}'"
    )

expected_height = 224
expected_width = 224
expected_channels = 3

actual_shape = input_info.shape

if len(actual_shape) != 4:
    raise ValueError(
        f"Expected a 4D ONNX input, but found {actual_shape}"
    )

if actual_shape[1] != expected_height:
    raise ValueError(
        f"Expected input height {expected_height}, "
        f"but found {actual_shape[1]}"
    )

if actual_shape[2] != expected_width:
    raise ValueError(
        f"Expected input width {expected_width}, "
        f"but found {actual_shape[2]}"
    )

if actual_shape[3] != expected_channels:
    raise ValueError(
        f"Expected {expected_channels} channels, "
        f"but found {actual_shape[3]}"
    )

if output_info.name != session.get_outputs()[0].name:
    raise ValueError(
        f"Expected ONNX output name '{OUTPUT_NAME}', "
        f"but found '{output_info.name}'"
    )

actual_output_shape = output_info.shape

if len(actual_output_shape) != 2:
    raise ValueError(
        f"Expected a 2D ONNX output, found {actual_output_shape}"
    )

# Batch dimension may be dynamic.
if actual_output_shape[1] != NUM_CLASSES:
    raise ValueError(
        f"Expected {NUM_CLASSES} class outputs, "
        f"but found {actual_output_shape}"
    )

if len(CLASS_NAMES) != NUM_CLASSES:
    raise ValueError(
        f"Expected {NUM_CLASSES} class names, "
        f"but found {len(CLASS_NAMES)}"
    )


# ============================================================
# IMAGE PREPROCESSING
# ============================================================

def prepare_image(image_path):
    """
    Prepare one image exactly according to the ONNX model contract.

    Steps:
        1. Read image
        2. Resize to 224 x 224
        3. BGR -> RGB
        4. Convert to float32
        5. Scale [0,255] -> [0,1]
        6. ImageNet normalization
        7. Add batch dimension

    Returns
    -------
    np.ndarray
        Shape: [1, 224, 224, 3]
        dtype: float32
    """

    image_path = Path(image_path)

    if not image_path.exists():
        raise FileNotFoundError(
            f"Image not found: {image_path}"
        )

    image = cv2.imread(str(image_path))

    if image is None:
        raise ValueError(
            f"Could not read image: {image_path}"
        )

    # OpenCV loads BGR. The model expects RGB.
    image = cv2.cvtColor(
        image,
        cv2.COLOR_BGR2RGB
    )

    # Resize exactly to model input dimensions.
    image = cv2.resize(
        image,
        (INPUT_WIDTH, INPUT_HEIGHT),
        interpolation=cv2.INTER_LINEAR
    )

    # Convert [0,255] uint8 -> [0,1] float32.
    image = image.astype(np.float32) / 255.0

    # ImageNet normalization:
    #
    # normalized = (image - mean) / std
    #
    # Broadcasting applies the values independently to
    # the R, G and B channels.
    image = (
        image - IMAGENET_MEAN
    ) / IMAGENET_STD

    # Add batch dimension:
    #
    # (224, 224, 3)
    #       ↓
    # (1, 224, 224, 3)
    image = np.expand_dims(
        image,
        axis=0
    ).astype(np.float32)

    return image


# ============================================================
# PREDICTION
# ============================================================

def predict_pest(image_path):
    """
    Predict the rice pest in an image.

    Parameters
    ----------
    image_path : str or pathlib.Path
        Path to the rice-pest image.

    Returns
    -------
    dict
        {
            "prediction": str,
            "confidence": float,
            "probabilities": {
                class_name: float,
                ...
            },
            "top3": [
                {
                    "class": str,
                    "confidence": float
                },
                ...
            ]
        }
    """

    image = prepare_image(image_path)

    # Run ONNX inference.
    raw_output = session.run(
    [OUTPUT_NAME],
    {INPUT_NAME: image}
    )[0]

    # Model output is already Softmax probabilities.
    probabilities = np.asarray(
        raw_output,
        dtype=np.float32
    )[0]

    if probabilities.shape != (NUM_CLASSES,):
        raise ValueError(
            f"Expected prediction vector shape "
            f"({NUM_CLASSES},), found {probabilities.shape}"
        )

    if not np.all(np.isfinite(probabilities)):
        raise ValueError(
            "ONNX model returned NaN or infinite probabilities."
        )

    # Since the ONNX output is explicitly Softmax, do NOT apply
    # another softmax here.
    if np.any(probabilities < 0) or np.any(probabilities > 1):
        raise ValueError(
            "ONNX output contains values outside [0,1]. "
            "The model is expected to return Softmax probabilities."
        )

    if not np.isclose(
        float(probabilities.sum()),
        1.0,
        atol=1e-3
    ):
        raise ValueError(
            "ONNX output does not sum to approximately 1. "
            "Expected Softmax probabilities."
        )

    # Highest-probability class.
    predicted_index = int(
        np.argmax(probabilities)
    )

    predicted_class = CLASS_NAMES[
        predicted_index
    ]

    confidence = float(
        probabilities[predicted_index]
    )

    # Top 3 classes.
    ranked_indices = np.argsort(
        probabilities
    )[::-1][:3]

    top3 = [
        {
            "class": CLASS_NAMES[int(index)],
            "confidence": float(
                probabilities[int(index)]
            )
        }
        for index in ranked_indices
    ]

    return {
        "prediction": predicted_class,
        "confidence": confidence,
        "probabilities": {
            CLASS_NAMES[index]: float(
                probabilities[index]
            )
            for index in range(NUM_CLASSES)
        },
        "top3": top3,
    }


# ============================================================
# COMMAND-LINE TESTER
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description=(
            "Predict rice pest from an image "
            "using the MobileNetV3-Small ONNX model."
        )
    )

    parser.add_argument(
        "image_path",
        help="Path to the rice-pest image"
    )

    args = parser.parse_args()

    result = predict_pest(
        args.image_path
    )

    print("\n" + "=" * 65)
    print("RICE PEST PREDICTION")
    print("=" * 65)

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

    print("\nTop 3 predictions:")

    for item in result["top3"]:
        print(
            f"  {item['class']:30s} "
            f"{item['confidence'] * 100:.2f}%"
        )

    print("=" * 65)


if __name__ == "__main__":
    main()
