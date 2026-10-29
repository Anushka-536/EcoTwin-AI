"""
EcoTwin-AI Explainable AI (XAI) Service

SRS-aligned requirements:
- SHAP or equivalent feature importance
- Feature contribution percentages
- Percentages sum to 100%
- Confidence score
- Human-readable explanation
- Historical prediction explanation support

This implementation uses a lightweight model-agnostic
perturbation method around the deployed INT8 TFLite model.
"""

import json
import os
from datetime import datetime

import numpy as np


# ============================================================
# PROJECT PATHS
# ============================================================

BASE_DIR = os.path.dirname(
    os.path.dirname(
        os.path.abspath(__file__)
    )
)

PROJECT_ROOT = os.path.dirname(
    BASE_DIR
)

PROCESSED_DATA_PATH = os.path.join(
    PROJECT_ROOT,
    "data",
    "processed",
    "solards_cleaned.csv"
)


# ============================================================
# ECO TWIN SOLAR FEATURES
# ============================================================

FEATURE_NAMES = [
    "ambient_temperature",
    "module_temperature",
    "voltage",
    "current",
    "power",
    "irradiance"
]


DISPLAY_NAMES = {
    "ambient_temperature": "Ambient Temperature",
    "module_temperature": "Module Temperature",
    "voltage": "Voltage",
    "current": "Current",
    "power": "Power",
    "irradiance": "Irradiance"
}


# ============================================================
# BASELINE VALUES
# ============================================================

_baseline_values = None


def load_baseline_values():
    """
    Load median feature values from the cleaned solar dataset.

    These values are used as the reference point for
    perturbation-based feature contribution analysis.
    """

    global _baseline_values

    if _baseline_values is not None:
        return _baseline_values

    if not os.path.exists(
        PROCESSED_DATA_PATH
    ):
        raise FileNotFoundError(
            "Processed solar dataset not found: "
            f"{PROCESSED_DATA_PATH}"
        )

    import pandas as pd

    dataframe = pd.read_csv(
        PROCESSED_DATA_PATH
    )

    missing = [
        feature
        for feature in FEATURE_NAMES
        if feature not in dataframe.columns
    ]

    if missing:
        raise ValueError(
            "Processed dataset is missing XAI features: "
            + ", ".join(missing)
        )

    medians = {}

    for feature in FEATURE_NAMES:

        medians[feature] = float(
            dataframe[feature]
            .median()
        )

    _baseline_values = medians

    return _baseline_values


# ============================================================
# MODEL INFERENCE
# ============================================================

def _predict_probabilities(
    feature_values
):
    """
    Run the existing INT8 TFLite prediction model.

    Returns:
        numpy array containing class probabilities.
    """

    # Import lazily to avoid circular imports.
    from backend.services.prediction import (
        load_scaler,
        load_interpreter,
        quantize_input,
        dequantize_output,
        interpret_prediction
    )

    scaler = load_scaler()

    interpreter = load_interpreter()

    input_details = interpreter.get_input_details()
    output_details = interpreter.get_output_details()

    input_detail = input_details[0]
    output_detail = output_details[0]

    values = np.asarray(
        [feature_values],
        dtype=np.float32
    )

    scaled = scaler.transform(
        values
    )

    model_input = quantize_input(
        scaled,
        input_detail
    )

    interpreter.set_tensor(
        input_detail["index"],
        model_input
    )

    interpreter.invoke()

    raw_output = interpreter.get_tensor(
        output_detail["index"]
    )

    output = dequantize_output(
        raw_output,
        output_detail
    )

    probabilities = np.asarray(
        output,
        dtype=np.float32
    ).flatten()

    if probabilities.size == 0:
        raise ValueError(
            "XAI model returned no output."
        )

    # --------------------------------------------------------
    # Convert logits to probabilities if required
    # --------------------------------------------------------

    if (
        np.any(probabilities < 0)
        or np.sum(probabilities) <= 0
    ):

        exp_values = np.exp(
            probabilities
            - np.max(probabilities)
        )

        probabilities = (
            exp_values
            /
            np.sum(exp_values)
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

    # Keep interpretation logic available
    # for consistency with the prediction service.
    interpret_prediction(
        probabilities
    )

    return probabilities


# ============================================================
# FEATURE CONTRIBUTION
# ============================================================

def calculate_feature_contributions(
    feature_data
):
    """
    Calculate model-agnostic feature contributions.

    Each feature is replaced individually with its
    dataset median. The change in the predicted class
    probability represents that feature's influence.

    This is an equivalent feature-importance approach
    rather than SHAP itself.
    """

    baseline = load_baseline_values()

    current_values = [
        float(
            feature_data[feature]
        )
        for feature in FEATURE_NAMES
    ]

    original_probabilities = (
        _predict_probabilities(
            current_values
        )
    )

    predicted_class = int(
        np.argmax(
            original_probabilities
        )
    )

    original_probability = float(
        original_probabilities[
            predicted_class
        ]
    )

    contributions = {}

    for index, feature in enumerate(
        FEATURE_NAMES
    ):

        perturbed = list(
            current_values
        )

        perturbed[index] = baseline[
            feature
        ]

        perturbed_probabilities = (
            _predict_probabilities(
                perturbed
            )
        )

        perturbed_probability = float(
            perturbed_probabilities[
                predicted_class
            ]
        )

        contribution = (
            original_probability
            -
            perturbed_probability
        )

        contributions[feature] = {
            "raw_contribution": float(
                contribution
            ),
            "absolute_contribution": float(
                abs(contribution)
            ),
            "value": float(
                current_values[index]
            ),
            "baseline_value": float(
                baseline[feature]
            )
        }

    return (
        contributions,
        original_probabilities,
        predicted_class
    )


# ============================================================
# NORMALIZE CONTRIBUTIONS
# ============================================================

def normalize_contributions(
    contributions
):
    """
    Convert absolute feature contributions into
    percentages that sum to exactly 100%.
    """

    total = sum(
        item[
            "absolute_contribution"
        ]
        for item in contributions.values()
    )

    if total <= 0:

        equal_share = (
            100.0
            /
            len(FEATURE_NAMES)
        )

        return {
            feature: equal_share
            for feature in FEATURE_NAMES
        }

    percentages = {}

    for feature in FEATURE_NAMES:

        raw_percentage = (
            contributions[
                feature
            ][
                "absolute_contribution"
            ]
            /
            total
        ) * 100.0

        percentages[
            feature
        ] = raw_percentage

    # --------------------------------------------------------
    # Force exact 100% after rounding
    # --------------------------------------------------------

    rounded = {
        feature: round(
            value,
            2
        )
        for feature, value
        in percentages.items()
    }

    difference = round(
        100.0
        -
        sum(
            rounded.values()
        ),
        2
    )

    largest_feature = max(
        rounded,
        key=rounded.get
    )

    rounded[
        largest_feature
    ] = round(
        rounded[
            largest_feature
        ]
        +
        difference,
        2
    )

    return rounded


# ============================================================
# HUMAN-READABLE EXPLANATION
# ============================================================

def generate_human_explanation(
    health_status,
    failure_probability,
    ranked_features
):
    """
    Generate a concise explanation suitable for
    non-expert dashboard users.
    """

    if not ranked_features:
        return (
            "No feature contribution information "
            "is available."
        )

    top_features = ranked_features[
        :3
    ]

    descriptions = []

    for item in top_features:

        feature_name = item[
            "display_name"
        ]

        percentage = item[
            "contribution_percentage"
        ]

        direction = item[
            "direction"
        ]

        if direction == "increases":

            descriptions.append(
                f"{feature_name} "
                f"has a strong influence "
                f"toward the predicted "
                f"{health_status} state "
                f"({percentage:.2f}%)."
            )

        elif direction == "decreases":

            descriptions.append(
                f"{feature_name} "
                f"reduces the likelihood "
                f"of the predicted state "
                f"({percentage:.2f}%)."
            )

        else:

            descriptions.append(
                f"{feature_name} contributes "
                f"{percentage:.2f}% to the "
                f"prediction."
            )

    summary = " ".join(
        descriptions
    )

    return (
        f"The model predicts "
        f"{health_status} with a "
        f"failure probability of "
        f"{failure_probability:.2f}%. "
        f"{summary}"
    )

REFERENCE_RANGES = {
    "ambient_temperature": (25.0, 10.0),
    "module_temperature": (45.0, 20.0),
    "voltage": (20.0, 5.0),
    "current": (0.85, 0.5),
    "power": (17.0, 10.0),
    "irradiance": (800.0, 400.0),
}


def deviation_percentages(feature_data):
    """Fallback: importance = deviation from normal operating range."""

    scores = {}

    for feature in FEATURE_NAMES:
        normal, tolerance = REFERENCE_RANGES[feature]
        scores[feature] = min(
            1.0,
            abs(float(feature_data[feature]) - normal) / tolerance
        )

    total = sum(scores.values())

    if total <= 0:
        return {
            f: round(100.0 / len(FEATURE_NAMES), 2)
            for f in FEATURE_NAMES
        }

    rounded = {
        f: round(v / total * 100.0, 2)
        for f, v in scores.items()
    }

    diff = round(100.0 - sum(rounded.values()), 2)
    largest = max(rounded, key=rounded.get)
    rounded[largest] = round(rounded[largest] + diff, 2)

    return rounded

# ============================================================
# COMPLETE XAI EXPLANATION
# ============================================================

def generate_explanation(
    feature_data,
    health_status,
    failure_probability,
    confidence
):
    """
    Generate the complete XAI result.
    """

    (
        contributions,
        probabilities,
        predicted_class
    ) = calculate_feature_contributions(
        feature_data
    )

    method_name = (
        "Model-agnostic perturbation feature importance"
    )

    fallback_used = all(
        item["absolute_contribution"] <= 0
        for item in contributions.values()
    )

    if fallback_used:
        percentages = deviation_percentages(feature_data)
        method_name = (
            "Deviation from normal operating range "
            "(model output saturated)"
        )
    else:
        percentages = normalize_contributions(contributions)

    ranked = []

    for feature in FEATURE_NAMES:

        raw = contributions[
            feature
        ][
            "raw_contribution"
        ]

        if raw > 0:
            direction = "increases"

        elif raw < 0:
            direction = "decreases"

        else:
            direction = "neutral"
            if fallback_used and percentages[feature] > 0:
                direction = "increases"

        ranked.append({

            "feature": feature,

            "display_name":
                DISPLAY_NAMES[
                    feature
                ],

            "value":
                contributions[
                    feature
                ]["value"],

            "baseline_value":
                contributions[
                    feature
                ]["baseline_value"],

            "contribution":
                round(
                    raw,
                    6
                ),

            "contribution_percentage":
                percentages[
                    feature
                ],

            "direction":
                direction

        })

    ranked.sort(
        key=lambda item:
            item[
                "contribution_percentage"
            ],
        reverse=True
    )

    explanation_text = (
        generate_human_explanation(
            health_status,
            float(
                failure_probability
            ),
            ranked
        )
    )

    return {

        "method": method_name,

        "equivalent_to":
            "SHAP-style feature contribution",

        "predicted_class":
            health_status,

        "failure_probability":
            round(
                float(
                    failure_probability
                ),
                2
            ),

        "confidence":
            round(
                float(
                    confidence
                ),
                2
            ),

        "features":
            ranked,

        "contribution_sum":
            round(
                sum(
                    item[
                        "contribution_percentage"
                    ]
                    for item in ranked
                ),
                2
            ),

        "explanation":
            explanation_text,

        "generated_at":
            datetime.utcnow().isoformat()

    }


# ============================================================
# DATABASE SERIALIZATION HELPER
# ============================================================

def explanation_to_json(
    explanation
):
    """
    Convert an XAI explanation to a JSON string
    for database storage.
    """

    return json.dumps(
        explanation,
        ensure_ascii=False
    )