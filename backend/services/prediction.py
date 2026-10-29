import json
import os
import time
from datetime import datetime

import numpy as np

from backend.models.models import (
    db,
    PredictionLog,
    XAIExplanation
)

from backend.services.xai import (
    generate_explanation,
    explanation_to_json
)


# ============================================================
# PATHS
# ============================================================

BASE_DIR = os.path.dirname(
    os.path.dirname(
        os.path.abspath(__file__)
    )
)

MODEL_DIR = os.path.join(
    BASE_DIR,
    "models"
)

TFLITE_MODEL_PATH = os.path.join(
    MODEL_DIR,
    "ecotwin_health_model_int8.tflite"
)

SCALER_PATH = os.path.join(
    MODEL_DIR,
    "ecotwin_scaler.pkl"
)

METADATA_PATH = os.path.join(
    MODEL_DIR,
    "model_metadata.json"
)


# ============================================================
# SRS CONFIGURATION
# ============================================================

SRS_INFERENCE_LIMIT_MS = 2000.0


# ============================================================
# MODEL OBJECTS
# ============================================================

_interpreter = None
_input_details = None
_output_details = None
_scaler = None
_metadata = None


# ============================================================
# LOAD SCALER
# ============================================================

def load_scaler():

    global _scaler

    if _scaler is not None:
        return _scaler

    if not os.path.exists(SCALER_PATH):

        raise FileNotFoundError(
            "Scaler file not found: "
            f"{SCALER_PATH}"
        )

    import joblib

    _scaler = joblib.load(
        SCALER_PATH
    )

    return _scaler


# ============================================================
# LOAD MODEL METADATA
# ============================================================

def load_metadata():

    global _metadata

    if _metadata is not None:
        return _metadata

    if not os.path.exists(METADATA_PATH):

        _metadata = {}

        return _metadata

    with open(
        METADATA_PATH,
        "r",
        encoding="utf-8"
    ) as file:

        _metadata = json.load(
            file
        )

    return _metadata


# ============================================================
# LOAD TFLITE MODEL
# ============================================================

def load_interpreter():

    global _interpreter
    global _input_details
    global _output_details

    if _interpreter is not None:
        return _interpreter

    if not os.path.exists(
        TFLITE_MODEL_PATH
    ):

        raise FileNotFoundError(
            "INT8 TensorFlow Lite model "
            "not found: "
            f"{TFLITE_MODEL_PATH}"
        )

    try:

        import tensorflow as tf

        interpreter = (
            tf.lite.Interpreter(
                model_path=TFLITE_MODEL_PATH
            )
        )

    except ImportError:

        try:

            from tflite_runtime.interpreter import (
                Interpreter
            )

            interpreter = Interpreter(
                model_path=TFLITE_MODEL_PATH
            )

        except ImportError:

            raise RuntimeError(
                "Neither TensorFlow nor "
                "tflite-runtime is installed."
            )

    interpreter.allocate_tensors()

    _interpreter = interpreter

    _input_details = (
        interpreter.get_input_details()
    )

    _output_details = (
        interpreter.get_output_details()
    )

    return _interpreter


# ============================================================
# PRELOAD MODEL
# ============================================================

def initialize_prediction_engine():

    """
    Preload the scaler, metadata and TFLite
    interpreter.

    This prevents the first API request from
    paying the model-loading cost.
    """

    load_metadata()
    load_scaler()
    load_interpreter()

    return True


# ============================================================
# FEATURE EXTRACTION
# ============================================================

def build_feature_vector(data):

    required_features = [

        "ambient_temperature",

        "module_temperature",

        "voltage",

        "current",

        "power",

        "irradiance"

    ]

    missing = []

    for feature in required_features:

        if data.get(feature) is None:

            missing.append(
                feature
            )

    if missing:

        raise ValueError(
            "Missing required prediction "
            "features: "
            +
            ", ".join(missing)
        )

    feature_vector = [

        float(
            data[
                "ambient_temperature"
            ]
        ),

        float(
            data[
                "module_temperature"
            ]
        ),

        float(
            data[
                "voltage"
            ]
        ),

        float(
            data[
                "current"
            ]
        ),

        float(
            data[
                "power"
            ]
        ),

        float(
            data[
                "irradiance"
            ]
        )

    ]

    return (
        required_features,
        feature_vector
    )


# ============================================================
# QUANTIZATION HELPER
# ============================================================

def quantize_input(
    values,
    input_detail
):

    dtype = input_detail[
        "dtype"
    ]

    if dtype != np.int8:

        return np.asarray(
            values,
            dtype=dtype
        )

    scale, zero_point = (
        input_detail[
            "quantization"
        ]
    )

    if scale == 0:

        raise ValueError(
            "Invalid INT8 input "
            "quantization scale."
        )

    quantized = (

        np.round(

            np.asarray(
                values,
                dtype=np.float32
            )
            /
            scale

        )
        +
        zero_point

    )

    quantized = np.clip(
        quantized,
        -128,
        127
    )

    return quantized.astype(
        np.int8
    )


# ============================================================
# DEQUANTIZATION HELPER
# ============================================================

def dequantize_output(
    values,
    output_detail
):

    values = np.asarray(
        values
    )

    dtype = output_detail[
        "dtype"
    ]

    if dtype != np.int8:

        return values.astype(
            np.float32
        )

    scale, zero_point = (
        output_detail[
            "quantization"
        ]
    )

    if scale == 0:

        return values.astype(
            np.float32
        )

    return (

        values.astype(
            np.float32
        )
        -
        zero_point

    ) * scale


# ============================================================
# HEALTH STATUS FROM HEALTH SCORE
# ============================================================

def get_health_status_from_score(
    health_score
):

    """
    SRS-consistent health classification.

    80-100  -> Healthy
    50-79.99 -> Warning
    0-49.99 -> Critical
    """

    health_score = float(
        health_score
    )

    if health_score >= 80.0:

        return "Healthy"

    elif health_score >= 50.0:

        return "Warning"

    else:

        return "Critical"


# ============================================================
# CLASS INTERPRETATION
# ============================================================

def interpret_prediction(
    output
):

    probabilities = np.asarray(
        output,
        dtype=np.float32
    ).flatten()

    if probabilities.size == 0:

        raise ValueError(
            "Model returned no output."
        )

    # --------------------------------------------------------
    # Convert logits to probabilities if necessary
    # --------------------------------------------------------

    if (

        np.any(
            probabilities < 0
        )

        or

        np.sum(
            probabilities
        ) <= 0

    ):

        exp_values = np.exp(

            probabilities
            -
            np.max(
                probabilities
            )

        )

        probabilities = (

            exp_values
            /
            np.sum(
                exp_values
            )

        )

    else:

        total = np.sum(
            probabilities
        )

        if (

            total > 0

            and

            not np.isclose(
                total,
                1.0,
                atol=0.05
            )

        ):

            probabilities = (

                probabilities
                /
                total

            )

    # --------------------------------------------------------
    # Model classes
    # --------------------------------------------------------

    class_names = [

        "Healthy",

        "Warning",

        "Critical"

    ]

    if probabilities.size >= 3:

        class_index = int(

            np.argmax(
                probabilities
            )

        )

        class_index = min(
            class_index,
            2
        )

        model_health_status = (
            class_names[
                class_index
            ]
        )

        # Critical class probability
        # is treated as failure probability.

        failure_probability = float(

            probabilities[2]
            *
            100.0

        )

        confidence = float(

            np.max(
                probabilities
            )
            *
            100.0

        )

        class_probability = float(
            probabilities[
                class_index
            ]
        )

    else:

        # ----------------------------------------------------
        # Binary-model fallback
        # ----------------------------------------------------

        probability = float(

            probabilities[-1]

        )

        failure_probability = (

            probability
            *
            100.0

        )

        confidence = (

            max(
                probability,
                1.0 - probability
            )
            *
            100.0

        )

        class_probability = (
            confidence
            /
            100.0
        )

    # --------------------------------------------------------
    # Calculate health score
    # --------------------------------------------------------

    health_score = (

        100.0
        -
        failure_probability

    )

    health_score = max(

        0.0,

        min(
            100.0,
            health_score
        )

    )

    # --------------------------------------------------------
    # IMPORTANT:
    # Derive displayed health status from health score.
    #
    # This prevents:
    #
    # health_score = 100
    # health_status = Warning
    #
    # --------------------------------------------------------

    health_status = (
        get_health_status_from_score(
            health_score
        )
    )

    return {

        "health_status":
            health_status,

        "model_health_status":
            model_health_status
            if probabilities.size >= 3
            else health_status,

        "health_score":
            round(
                health_score,
                2
            ),

        "failure_probability":
            round(
                failure_probability,
                2
            ),

        "confidence":
            round(
                confidence,
                2
            ),

        "class_probability":
            round(
                class_probability
                *
                100.0,
                2
            )

    }


# ============================================================
# RUL ESTIMATION
# ============================================================

def estimate_rul(
    failure_probability,
    health_status
):

    """
    Health-based prototype RUL indicator.

    This is NOT a physical lifetime prediction.
    """

    if health_status == "Healthy":

        base_rul = 180.0

    elif health_status == "Warning":

        base_rul = 90.0

    else:

        base_rul = 30.0

    risk_factor = (

        1.0
        -
        (
            failure_probability
            /
            100.0
        )

    )

    rul = (

        base_rul
        *
        max(
            0.05,
            risk_factor
        )

    )

    return round(

        max(
            1.0,
            rul
        ),

        1

    )


# ============================================================
# MAIN PREDICTION FUNCTION
# ============================================================

def generate_prediction(
    data
):

    # ========================================================
    # REQUEST START
    # ========================================================

    request_start_time = (
        time.perf_counter()
    )

    # --------------------------------------------------------
    # Facility
    # --------------------------------------------------------

    facility_id = data.get(
        "facility_id"
    )

    if facility_id is not None:

        try:

            facility_id = int(
                facility_id
            )

        except (
            TypeError,
            ValueError
        ):

            raise ValueError(
                "facility_id must be an integer."
            )

    # --------------------------------------------------------
    # Device ID
    # --------------------------------------------------------

    device_id = data.get(
        "device_id"
    )

    if not device_id:

        device_id = (

            data.get(
                "device"
            )

            or

            "SIMULATED-DEVICE-001"

        )

    # --------------------------------------------------------
    # Feature vector
    # --------------------------------------------------------

    feature_names, raw_features = (
        build_feature_vector(
            data
        )
    )

    # ========================================================
    # MODEL PREPARATION
    # ========================================================

    scaler = load_scaler()

    interpreter = load_interpreter()

    # --------------------------------------------------------
    # Scale features
    # --------------------------------------------------------

    scaled_features = (
        scaler.transform(

            np.asarray(
                [raw_features],
                dtype=np.float32
            )

        )
    )

    # --------------------------------------------------------
    # Model input/output details
    # --------------------------------------------------------

    input_detail = (
        _input_details[0]
    )

    output_detail = (
        _output_details[0]
    )

    # --------------------------------------------------------
    # Verify model feature count
    # --------------------------------------------------------

    input_shape = (
        input_detail[
            "shape"
        ]
    )

    expected_features = (
        input_shape[-1]
    )

    if (

        expected_features
        !=
        len(feature_names)

    ):

        raise ValueError(

            "Model expects "
            f"{expected_features} features, "
            "but the prediction pipeline "
            f"provides {len(feature_names)}."

        )

    # ========================================================
    # QUANTIZE INPUT
    # ========================================================

    model_input = (
        quantize_input(

            scaled_features,

            input_detail

        )
    )

    # ========================================================
    # ACTUAL TFLITE INFERENCE TIMER
    # ========================================================

    inference_start = (
        time.perf_counter()
    )

    interpreter.set_tensor(

        input_detail[
            "index"
        ],

        model_input

    )

    interpreter.invoke()

    raw_output = (
        interpreter.get_tensor(

            output_detail[
                "index"
            ]

        )
    )

    inference_end = (
        time.perf_counter()
    )

    # --------------------------------------------------------
    # SRS inference latency
    #
    # Only actual model execution is measured here.
    # XAI/database operations are NOT included.
    # --------------------------------------------------------

    inference_time_ms = (

        inference_end
        -
        inference_start

    ) * 1000.0

    # ========================================================
    # DEQUANTIZE OUTPUT
    # ========================================================

    output = (
        dequantize_output(

            raw_output,

            output_detail

        )
    )

    # ========================================================
    # INTERPRET MODEL OUTPUT
    # ========================================================

    prediction = (
        interpret_prediction(
            output
        )
    )

    # ========================================================
    # RUL
    # ========================================================

    rul = estimate_rul(

        prediction[
            "failure_probability"
        ],

        prediction[
            "health_status"
        ]

    )

    # ========================================================
    # AUDIT FEATURE VECTOR
    # ========================================================

    feature_data = {

        name: value

        for name, value

        in zip(
            feature_names,
            raw_features
        )

    }

    feature_data[
        "device_id"
    ] = device_id

    # ========================================================
    # TIMESTAMP
    # ========================================================

    prediction_timestamp = (
        datetime.utcnow()
    )

    # ========================================================
    # SAVE PREDICTION
    # ========================================================

    prediction_log = (
        PredictionLog(

            facility_id=(
                facility_id
            ),

            device_id=str(
                device_id
            ),

            prediction_timestamp=(
                prediction_timestamp
            ),

            feature_vector=json.dumps(
                feature_data
            ),

            health_status=(
                prediction[
                    "health_status"
                ]
            ),

            health_score=(
                prediction[
                    "health_score"
                ]
            ),

            failure_probability=(
                prediction[
                    "failure_probability"
                ]
            ),

            rul=rul,

            inference_time_ms=round(
                inference_time_ms,
                3
            )

        )
    )

    db.session.add(
        prediction_log
    )

    # --------------------------------------------------------
    # Obtain ID before XAI
    # --------------------------------------------------------

    db.session.flush()

    # ========================================================
    # XAI
    # ========================================================

    xai_result = None

    try:

        xai_result = (
            generate_explanation(

                feature_data=(
                    feature_data
                ),

                health_status=(
                    prediction[
                        "health_status"
                    ]
                ),

                failure_probability=(
                    prediction[
                        "failure_probability"
                    ]
                ),

                confidence=(
                    prediction[
                        "confidence"
                    ]
                )

            )
        )

        # ----------------------------------------------------
        # Store XAI explanation
        # ----------------------------------------------------

        xai_record = (
            XAIExplanation(

                prediction_id=(
                    prediction_log.id
                ),

                explanation_json=(
                    explanation_to_json(
                        xai_result
                    )
                )

            )
        )

        db.session.add(
            xai_record
        )

    except Exception as xai_error:

        # ----------------------------------------------------
        # XAI failure must not break prediction.
        # ----------------------------------------------------

        xai_result = {

            "success": False,

            "error": str(
                xai_error
            )

        }

    # ========================================================
    # COMMIT
    # ========================================================

    db.session.commit()

    # ========================================================
    # TOTAL REQUEST TIME
    # ========================================================

    total_request_time_ms = (

        time.perf_counter()
        -
        request_start_time

    ) * 1000.0

    # ========================================================
    # SRS RESPONSE
    # ========================================================

    response = {

        "success": True,

        "prediction_id": (
            prediction_log.id
        ),

        "facility_id":
            facility_id,

        "device_id":
            str(device_id),

        "timestamp": (
            prediction_timestamp
            .isoformat()
        ),

        "feature_vector":
            feature_data,

        "health_status": (
            prediction[
                "health_status"
            ]
        ),

        "health_score": (
            prediction[
                "health_score"
            ]
        ),

        "failure_probability": (
            prediction[
                "failure_probability"
            ]
        ),

        "rul": {

            "value": rul,

            "unit": "days",

            "type":
                "health-based prototype "
                "indicator"

        },

        "confidence": (
            prediction[
                "confidence"
            ]
        ),

        # ----------------------------------------------------
        # Actual model inference latency
        # ----------------------------------------------------

        "inference_time_ms":
            round(
                inference_time_ms,
                3
            ),

        "within_srs_limit":
            (
                inference_time_ms
                <=
                SRS_INFERENCE_LIMIT_MS
            ),

        # ----------------------------------------------------
        # Additional diagnostic information
        # ----------------------------------------------------

        "total_request_time_ms":
            round(
                total_request_time_ms,
                3
            )

    }

    # ========================================================
    # XAI STATUS
    # ========================================================

    if xai_result is not None:

        if xai_result.get(
            "success",
            True
        ):

            response[
                "xai_available"
            ] = True

            response[
                "xai_method"
            ] = xai_result.get(
                "method"
            )

            response[
                "xai_contribution_sum"
            ] = xai_result.get(
                "contribution_sum"
            )

        else:

            response[
                "xai_available"
            ] = False

            response[
                "xai_error"
            ] = xai_result.get(
                "error"
            )

    else:

        response[
            "xai_available"
        ] = False

    return response


# ============================================================
# OPTIONAL STARTUP INITIALIZATION
# ============================================================

try:

    initialize_prediction_engine()

except Exception as startup_error:

    # Do not crash the application if the
    # prediction model cannot be initialized.
    #
    # The error will be raised normally when
    # /api/predict is called.

    print(
        "Prediction engine startup initialization "
        "warning:"
    )

    print(
        str(startup_error)
    )