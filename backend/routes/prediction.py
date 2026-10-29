from flask import Blueprint, jsonify, request

from backend.services.prediction import generate_prediction


# ============================================================
# PREDICTION BLUEPRINT
# ============================================================

prediction_bp = Blueprint(
    "prediction",
    __name__,
    url_prefix="/api"
)


# ============================================================
# RUN PREDICTION
# POST /api/predict
# ============================================================

@prediction_bp.route(
    "/predict",
    methods=["POST"]
)
def predict():

    data = request.get_json(
        silent=True
    )

    if not data:

        return jsonify({
            "success": False,
            "error": "Request body must contain JSON data."
        }), 400

    try:

        result = generate_prediction(
            data=data
        )

        if not isinstance(result, dict):

            return jsonify({
                "success": False,
                "error": "Prediction service returned an invalid response."
            }), 500

        if not result.get(
            "success",
            False
        ):

            return jsonify(
                result
            ), 400

        return jsonify(
            result
        ), 200

    except Exception as e:

        return jsonify({

            "success": False,

            "error": (
                "Prediction failed: "
                f"{str(e)}"
            )

        }), 500


# ============================================================
# PREDICTION HISTORY
# GET /api/predictions
# ============================================================

@prediction_bp.route(
    "/predictions",
    methods=["GET"]
)
def prediction_history():

    try:

        from backend.models.models import PredictionLog

        limit = request.args.get(
            "limit",
            default=20,
            type=int
        )

        facility_id = request.args.get(
            "facility_id",
            default=None,
            type=int
        )

        if limit < 1:
            limit = 1

        if limit > 100:
            limit = 100

        query = PredictionLog.query

        if facility_id is not None:

            query = query.filter_by(
                facility_id=facility_id
            )

        predictions = (
            query
            .order_by(
                PredictionLog.prediction_timestamp.desc()
            )
            .limit(limit)
            .all()
        )

        output = []

        for prediction in predictions:

            timestamp = None

            if prediction.prediction_timestamp:

                timestamp = (
                    prediction
                    .prediction_timestamp
                    .isoformat()
                )

            output.append({

                "id": prediction.id,

                "facility_id": (
                    prediction.facility_id
                ),

                "device_id": (
                    prediction.device_id
                ),

                "timestamp": timestamp,

                "health_status": (
                    prediction.health_status
                ),

                "health_score": (
                    prediction.health_score
                ),

                "failure_probability": (
                    prediction.failure_probability
                ),

                "rul": (
                    prediction.rul
                ),

                "inference_time_ms": (
                    prediction.inference_time_ms
                )

            })

        return jsonify({

            "success": True,

            "count": len(output),

            "predictions": output

        }), 200

    except Exception as e:

        return jsonify({

            "success": False,

            "error": (
                "Could not retrieve prediction history: "
                f"{str(e)}"
            )

        }), 500


# ============================================================
# SINGLE PREDICTION
# GET /api/predictions/<prediction_id>
# ============================================================

@prediction_bp.route(
    "/predictions/<int:prediction_id>",
    methods=["GET"]
)
def get_prediction(
    prediction_id
):

    try:

        from backend.models.models import PredictionLog

        prediction = (
            PredictionLog.query.get(
                prediction_id
            )
        )

        if prediction is None:

            return jsonify({

                "success": False,

                "error": "Prediction not found."

            }), 404

        timestamp = None

        if prediction.prediction_timestamp:

            timestamp = (
                prediction
                .prediction_timestamp
                .isoformat()
            )

        return jsonify({

            "success": True,

            "prediction": {

                "id": prediction.id,

                "facility_id": (
                    prediction.facility_id
                ),

                "device_id": (
                    prediction.device_id
                ),

                "timestamp": timestamp,

                "feature_vector": (
                    prediction.feature_vector
                ),

                "health_status": (
                    prediction.health_status
                ),

                "health_score": (
                    prediction.health_score
                ),

                "failure_probability": (
                    prediction.failure_probability
                ),

                "rul": (
                    prediction.rul
                ),

                "inference_time_ms": (
                    prediction.inference_time_ms
                )

            }

        }), 200

    except Exception as e:

        return jsonify({

            "success": False,

            "error": (
                "Could not retrieve prediction: "
                f"{str(e)}"
            )

        }), 500


# ============================================================
# XAI EXPLANATION
# GET /api/predictions/<prediction_id>/explanation
# ============================================================

@prediction_bp.route(
    "/predictions/<int:prediction_id>/explanation",
    methods=["GET"]
)
def get_prediction_explanation(
    prediction_id
):

    try:

        from backend.models.models import (
            PredictionLog,
            XAIExplanation
        )

        # ----------------------------------------------------
        # Verify prediction exists
        # ----------------------------------------------------

        prediction = (
            PredictionLog.query.get(
                prediction_id
            )
        )

        if prediction is None:

            return jsonify({

                "success": False,

                "error": "Prediction not found."

            }), 404

        # ----------------------------------------------------
        # Find XAI explanation
        # ----------------------------------------------------

        explanation = (
            XAIExplanation.query.filter_by(
                prediction_id=prediction_id
            ).first()
        )

        if explanation is None:

            return jsonify({

                "success": False,

                "error": (
                    "XAI explanation not available "
                    "for this prediction."
                )

            }), 404

        # ----------------------------------------------------
        # Parse stored JSON
        # ----------------------------------------------------

        import json

        try:

            explanation_data = json.loads(
                explanation.explanation_json
            )

        except Exception:

            explanation_data = (
                explanation.explanation_json
            )

        # ----------------------------------------------------
        # Response
        # ----------------------------------------------------

        return jsonify({

            "success": True,

            "prediction_id": prediction_id,

            "explanation": explanation_data

        }), 200

    except Exception as e:

        return jsonify({

            "success": False,

            "error": (
                "Could not retrieve XAI explanation: "
                f"{str(e)}"
            )

        }), 500