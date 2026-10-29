"""
EcoTwin-AI
Phase 3 - TinyML Prediction Engine

This module:

1. Loads the cleaned solar telemetry dataset.
2. Creates a synthetic health/failure target because
   the external SolarPanel dataset has no failure label.
3. Trains a lightweight neural-network classifier.
4. Produces Healthy / Warning / Critical classes.
5. Saves the trained model.
6. Converts the model to TensorFlow Lite.
7. Produces an INT8 quantized TensorFlow Lite model.
8. Saves training metadata.

SRS telemetry features:

    ambient_temperature
    module_temperature
    voltage
    current
    power
    irradiance
"""

from pathlib import Path
import json
import time

import numpy as np
import pandas as pd
import tensorflow as tf

from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import (
    classification_report,
    accuracy_score
)

import joblib


# ============================================================
# PATHS
# ============================================================

PROJECT_ROOT = Path(
    __file__
).resolve().parent.parent

PROCESSED_DATA_DIR = (
    PROJECT_ROOT /
    "data" /
    "processed"
)

MODEL_DIR = (
    PROJECT_ROOT /
    "backend" /
    "models"
)

MODEL_DIR.mkdir(
    parents=True,
    exist_ok=True
)


DATASET_FILE = (
    PROCESSED_DATA_DIR /
    "solards_cleaned.csv"
)

KERAS_MODEL_FILE = (
    MODEL_DIR /
    "ecotwin_health_model.keras"
)

TFLITE_MODEL_FILE = (
    MODEL_DIR /
    "ecotwin_health_model.tflite"
)

TFLITE_INT8_MODEL_FILE = (
    MODEL_DIR /
    "ecotwin_health_model_int8.tflite"
)

SCALER_FILE = (
    MODEL_DIR /
    "ecotwin_scaler.pkl"
)

METADATA_FILE = (
    MODEL_DIR /
    "model_metadata.json"
)


# ============================================================
# SRS FEATURE VECTOR
# ============================================================

FEATURE_COLUMNS = [

    "ambient_temperature",

    "module_temperature",

    "voltage",

    "current",

    "power",

    "irradiance"

]


# ============================================================
# CLASS DEFINITIONS
# ============================================================

CLASS_NAMES = [

    "Healthy",

    "Warning",

    "Critical"

]


# ============================================================
# LOAD DATA
# ============================================================

def load_data():

    if not DATASET_FILE.exists():

        raise FileNotFoundError(

            f"Dataset not found:\n"
            f"{DATASET_FILE}\n\n"
            "Run Phase 2 preprocessing first."

        )

    dataframe = pd.read_csv(
        DATASET_FILE
    )

    missing = [

        column

        for column in FEATURE_COLUMNS

        if column not in dataframe.columns

    ]

    if missing:

        raise ValueError(

            "Missing required features: "
            + ", ".join(missing)

        )

    dataframe = dataframe[
        FEATURE_COLUMNS
    ].copy()

    dataframe = dataframe.replace(

        [
            np.inf,
            -np.inf
        ],

        np.nan

    )

    dataframe.dropna(
        inplace=True
    )

    return dataframe


# ============================================================
# SYNTHETIC HEALTH LABEL
# ============================================================

def create_health_labels(
    dataframe
):
    """
    Create an engineering-based synthetic target.

    IMPORTANT:
    The original SolarPanel dataset does not provide a
    failure/health label.

    Therefore this target is explicitly marked as
    synthetic and is used for prototype development
    and TinyML demonstration.

    Lower score  -> Healthy
    Medium score -> Warning
    Higher score -> Critical
    """

    data = dataframe.copy()

    # --------------------------------------------------------
    # Normalized stress indicators
    # --------------------------------------------------------

    ambient_stress = np.clip(

        (
            data[
                "ambient_temperature"
            ] - 300.0
        ) / 250.0,

        0.0,
        1.0

    )

    module_stress = np.clip(

        (
            data[
                "module_temperature"
            ] - 350.0
        ) / 250.0,

        0.0,
        1.0

    )

    temperature_gap = (

        data[
            "module_temperature"
        ]

        -

        data[
            "ambient_temperature"
        ]

    )

    temperature_stress = np.clip(

        temperature_gap / 250.0,

        0.0,
        1.0

    )

    irradiance_stress = np.clip(

        np.abs(
            data[
                "irradiance"
            ] - 800.0
        ) / 800.0,

        0.0,
        1.0

    )

    # --------------------------------------------------------
    # Electrical consistency
    # --------------------------------------------------------

    expected_power = (

        data[
            "voltage"
        ]

        *

        data[
            "current"
        ]

    )

    power_error = (

        np.abs(

            data[
                "power"
            ]

            -

            expected_power

        )

        /

        (
            np.abs(
                expected_power
            )

            + 1e-6
        )

    )

    power_stress = np.clip(

        power_error,

        0.0,
        1.0

    )

    # --------------------------------------------------------
    # Combined degradation/stress score
    # --------------------------------------------------------

    stress_score = (

        0.25 *
        ambient_stress

        +

        0.30 *
        module_stress

        +

        0.20 *
        temperature_stress

        +

        0.10 *
        irradiance_stress

        +

        0.15 *
        power_stress

    )

    # --------------------------------------------------------
    # Add small deterministic variation
    # --------------------------------------------------------

    # This avoids creating an excessively simple
    # threshold-only classification boundary.

    variation = (

        np.sin(
            data[
                "voltage"
            ].to_numpy()
        )

        * 0.015

    )

    stress_score = np.clip(

        stress_score.to_numpy()
        + variation,

        0.0,
        1.0

    )

    # --------------------------------------------------------
    # Convert score to health class
    # --------------------------------------------------------

    labels = np.select(

        [

            stress_score < 0.35,

            stress_score < 0.65

        ],

        [

            0,  # Healthy

            1   # Warning

        ],

        default=2  # Critical

    )

    return labels.astype(
        np.int32
    )


# ============================================================
# CREATE MODEL
# ============================================================

def create_model(
    input_size
):

    model = tf.keras.Sequential([

        tf.keras.layers.Input(
            shape=(input_size,)
        ),

        tf.keras.layers.Dense(
            16,
            activation="relu"
        ),

        tf.keras.layers.Dense(
            8,
            activation="relu"
        ),

        tf.keras.layers.Dense(
            3,
            activation="softmax"
        )

    ])

    model.compile(

        optimizer=tf.keras.optimizers.Adam(
            learning_rate=0.001
        ),

        loss=(
            "sparse_categorical_crossentropy"
        ),

        metrics=[
            "accuracy"
        ]

    )

    return model


# ============================================================
# INT8 REPRESENTATIVE DATASET
# ============================================================

def representative_dataset(
    X
):

    sample_count = min(
        200,
        len(X)
    )

    for index in range(
        sample_count
    ):

        yield [

            X[
                index:index + 1
            ].astype(
                np.float32
            )

        ]


# ============================================================
# CONVERT TO TFLITE
# ============================================================

def convert_to_tflite(
    model,
    X_train
):

    # --------------------------------------------------------
    # Standard TFLite model
    # --------------------------------------------------------

    converter = (
        tf.lite.TFLiteConverter
        .from_keras_model(model)
    )

    tflite_model = (
        converter.convert()
    )

    with open(

        TFLITE_MODEL_FILE,

        "wb"

    ) as file:

        file.write(
            tflite_model
        )


    # --------------------------------------------------------
    # INT8 quantized model
    # --------------------------------------------------------

    converter = (
        tf.lite.TFLiteConverter
        .from_keras_model(model)
    )

    converter.optimizations = [

        tf.lite.Optimize.DEFAULT

    ]

    converter.representative_dataset = (

        lambda:
        representative_dataset(
            X_train
        )

    )

    converter.target_spec.supported_ops = [

        tf.lite.OpsSet.TFLITE_BUILTINS_INT8

    ]

    converter.inference_input_type = (
        tf.int8
    )

    converter.inference_output_type = (
        tf.int8
    )

    int8_model = (
        converter.convert()
    )

    with open(

        TFLITE_INT8_MODEL_FILE,

        "wb"

    ) as file:

        file.write(
            int8_model
        )


# ============================================================
# MAIN TRAINING PIPELINE
# ============================================================

def train():

    print("=" * 60)

    print(
        "EcoTwin-AI TinyML Model Training"
    )

    print("=" * 60)


    # --------------------------------------------------------
    # Load
    # --------------------------------------------------------

    dataframe = load_data()

    print(
        f"\nTraining records: "
        f"{len(dataframe)}"
    )


    # --------------------------------------------------------
    # Features
    # --------------------------------------------------------

    X = dataframe[
        FEATURE_COLUMNS
    ].to_numpy(
        dtype=np.float32
    )


    # --------------------------------------------------------
    # Synthetic labels
    # --------------------------------------------------------

    y = create_health_labels(
        dataframe
    )


    print(
        "\nClass distribution:"
    )

    for class_id, class_name in enumerate(
        CLASS_NAMES
    ):

        count = int(
            np.sum(
                y == class_id
            )
        )

        percentage = (
            count /
            len(y)
            *
            100
        )

        print(

            f"  {class_name}: "
            f"{count} "
            f"({percentage:.2f}%)"

        )


    # --------------------------------------------------------
    # Train/test split
    # --------------------------------------------------------

    X_train, X_test, y_train, y_test = (

        train_test_split(

            X,
            y,

            test_size=0.20,

            random_state=42,

            stratify=y

        )

    )


    # --------------------------------------------------------
    # Scaling
    # --------------------------------------------------------

    scaler = StandardScaler()

    X_train_scaled = scaler.fit_transform(
        X_train
    ).astype(
        np.float32
    )

    X_test_scaled = scaler.transform(
        X_test
    ).astype(
        np.float32
    )


    joblib.dump(

        scaler,

        SCALER_FILE

    )


    # --------------------------------------------------------
    # Create model
    # --------------------------------------------------------

    model = create_model(
        len(FEATURE_COLUMNS)
    )


    # --------------------------------------------------------
    # Training
    # --------------------------------------------------------

    print(
        "\nTraining TinyML model..."
    )

    model.fit(

        X_train_scaled,

        y_train,

        validation_split=0.20,

        epochs=25,

        batch_size=32,

        verbose=1

    )


    # --------------------------------------------------------
    # Evaluation
    # --------------------------------------------------------

    probabilities = model.predict(

        X_test_scaled,

        verbose=0

    )

    predictions = np.argmax(

        probabilities,

        axis=1

    )


    accuracy = accuracy_score(

        y_test,

        predictions

    )


    print(
        "\nModel accuracy: "
        f"{accuracy * 100:.2f}%"
    )


    print(
        "\nClassification report:"
    )

    print(

        classification_report(

            y_test,

            predictions,

            target_names=CLASS_NAMES,

            zero_division=0

        )

    )


    # --------------------------------------------------------
    # Save Keras model
    # --------------------------------------------------------

    model.save(
        KERAS_MODEL_FILE
    )


    # --------------------------------------------------------
    # Convert to TFLite
    # --------------------------------------------------------

    print(
        "\nConverting to TensorFlow Lite..."
    )

    convert_to_tflite(

        model,

        X_train_scaled

    )


    # --------------------------------------------------------
    # Inference performance
    # --------------------------------------------------------

    sample = X_test_scaled[
        :1
    ]


    start_time = time.perf_counter()

    model.predict(

        sample,

        verbose=0

    )

    inference_time = (

        time.perf_counter()
        -
        start_time

    )


    # --------------------------------------------------------
    # Metadata
    # --------------------------------------------------------

    metadata = {

        "project": "EcoTwin-AI",

        "model_type": (
            "Lightweight neural-network "
            "health classifier"
        ),

        "target_type": (
            "Synthetic engineering health "
            "label"
        ),

        "features": FEATURE_COLUMNS,

        "classes": CLASS_NAMES,

        "training_records": int(
            len(X_train)
        ),

        "testing_records": int(
            len(X_test)
        ),

        "accuracy": float(
            accuracy
        ),

        "inference_time_seconds": float(
            inference_time
        ),

        "keras_model": str(
            KERAS_MODEL_FILE
        ),

        "tflite_model": str(
            TFLITE_MODEL_FILE
        ),

        "int8_model": str(
            TFLITE_INT8_MODEL_FILE
        ),

        "scaler": str(
            SCALER_FILE
        )

    }


    with open(

        METADATA_FILE,

        "w",

        encoding="utf-8"

    ) as file:

        json.dump(

            metadata,

            file,

            indent=4

        )


    # --------------------------------------------------------
    # Final output
    # --------------------------------------------------------

    print("\n" + "=" * 60)

    print(
        "TinyML training completed."
    )

    print("=" * 60)

    print(
        f"\nKeras model:"
        f"\n{KERAS_MODEL_FILE}"
    )

    print(
        f"\nTensorFlow Lite:"
        f"\n{TFLITE_MODEL_FILE}"
    )

    print(
        f"\nINT8 TensorFlow Lite:"
        f"\n{TFLITE_INT8_MODEL_FILE}"
    )

    print(
        f"\nScaler:"
        f"\n{SCALER_FILE}"
    )

    print(
        f"\nMetadata:"
        f"\n{METADATA_FILE}"
    )

    print(
        "\nInference time:"
        f" {inference_time:.6f} seconds"
    )


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":

    train()