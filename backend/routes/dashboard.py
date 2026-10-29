from flask import Blueprint, jsonify, request
from datetime import datetime
import json

from backend.models.models import (
    Facility,
    Sensor,
    SensorReading,
    PredictionLog,
    Alert,
    DigitalTwinModel,
    SimulationRun
)


# ============================================================
# DASHBOARD BLUEPRINT
# ============================================================

dashboard_bp = Blueprint(
    "dashboard",
    __name__,
    url_prefix="/api/dashboard"
)


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def serialize_datetime(value):
    if value is None:
        return None

    return value.isoformat()


def parse_json(value):
    if not value:
        return None

    try:
        return json.loads(value)
    except Exception:
        return value


# ============================================================
# DASHBOARD SUMMARY
# ============================================================

@dashboard_bp.route(
    "/summary",
    methods=["GET"]
)
def dashboard_summary():

    facility_id = request.args.get(
        "facility_id",
        default=None,
        type=int
    )

    # --------------------------------------------------------
    # FACILITY
    # --------------------------------------------------------

    facility = None

    if facility_id is not None:

        facility = (
            Facility.query
            .filter_by(id=facility_id)
            .first()
        )

        if facility is None:

            return jsonify({
                "success": False,
                "error": "Facility not found."
            }), 404

    else:

        facility = (
            Facility.query
            .order_by(Facility.id.asc())
            .first()
        )

    # --------------------------------------------------------
    # LATEST PREDICTION
    # --------------------------------------------------------

    prediction_query = PredictionLog.query

    if facility is not None:

        prediction_query = (
            prediction_query
            .filter_by(
                facility_id=facility.id
            )
        )

    latest_prediction = (
        prediction_query
        .order_by(
            PredictionLog.prediction_timestamp.desc()
        )
        .first()
    )

    # --------------------------------------------------------
    # ACTIVE ALERTS
    # --------------------------------------------------------

    alert_query = Alert.query

    active_alerts = (
        alert_query
        .filter(
            Alert.status == "Active"
        )
        .order_by(
            Alert.created_at.desc()
        )
        .limit(10)
        .all()
    )

    # --------------------------------------------------------
    # DIGITAL TWIN MODEL
    # --------------------------------------------------------

    twin_query = DigitalTwinModel.query

    if facility is not None:

        twin_query = (
            twin_query
            .filter_by(
                facility_id=facility.id
            )
        )

    twin_model = (
        twin_query
        .order_by(
            DigitalTwinModel.last_updated.desc()
        )
        .first()
    )

    # --------------------------------------------------------
    # RECENT SIMULATIONS
    # --------------------------------------------------------

    simulation_query = SimulationRun.query

    if facility is not None:

        simulation_query = (
            simulation_query
            .filter_by(
                facility_id=facility.id
            )
        )

    simulations = (
        simulation_query
        .order_by(
            SimulationRun.created_at.desc()
        )
        .limit(10)
        .all()
    )

    # --------------------------------------------------------
    # SENSOR COUNT
    # --------------------------------------------------------

    sensor_count = 0

    if facility is not None:

        sensor_count = (
            Sensor.query
            .filter_by(
                facility_id=facility.id
            )
            .count()
        )

    # --------------------------------------------------------
    # FACILITY DATA
    # --------------------------------------------------------

    facility_data = None

    if facility is not None:

        facility_data = {

            "id": facility.id,

            "name": facility.name,

            "facility_type": (
                facility.facility_type
            ),

            "installed_capacity_kw": (
                facility.installed_capacity_kw
            ),

            "location": facility.location,

            "commission_date": (
                serialize_datetime(
                    facility.commission_date
                )
            ),

            "sensor_count": sensor_count

        }

    # --------------------------------------------------------
    # PREDICTION DATA
    # --------------------------------------------------------

    prediction_data = None

    if latest_prediction is not None:

        prediction_data = {

            "id": latest_prediction.id,

            "device_id": (
                latest_prediction.device_id
            ),

            "timestamp": (
                serialize_datetime(
                    latest_prediction
                    .prediction_timestamp
                )
            ),

            "health_status": (
                latest_prediction.health_status
            ),

            "health_score": (
                latest_prediction.health_score
            ),

            "failure_probability": (
                latest_prediction
                .failure_probability
            ),

            "rul": latest_prediction.rul,

            "inference_time_ms": (
                latest_prediction
                .inference_time_ms
            )

        }

    # --------------------------------------------------------
    # ALERT DATA
    # --------------------------------------------------------

    alert_data = []

    for alert in active_alerts:

        alert_data.append({

            "id": alert.id,

            "alert_type": (
                alert.alert_type
            ),

            "message": alert.message,

            "severity": alert.severity,

            "status": alert.status,

            "created_at": (
                serialize_datetime(
                    alert.created_at
                )
            )

        })

    # --------------------------------------------------------
    # DIGITAL TWIN DATA
    # --------------------------------------------------------

    twin_data = None

    if twin_model is not None:

        twin_data = {

            "id": twin_model.id,

            "facility_id": (
                twin_model.facility_id
            ),

            "name": (
                twin_model.model_name
            ),

            "version": (
                twin_model.model_version
            ),

            "status": twin_model.status,

            "last_updated": (
                serialize_datetime(
                    twin_model.last_updated
                )
            )

        }

    # --------------------------------------------------------
    # SIMULATION DATA
    # --------------------------------------------------------

    simulation_data = []

    for simulation in simulations:

        simulation_data.append({

            "id": simulation.id,

            "simulation_name": (
                simulation.simulation_name
            ),

            "model_id": (
                simulation.model_id
            ),

            "status": simulation.status,

            "created_at": (
                serialize_datetime(
                    simulation.created_at
                )
            ),

            "input_data": (
                parse_json(
                    simulation.input_data
                )
            ),

            "output_data": (
                parse_json(
                    simulation.output_data
                )
            )

        })

    # --------------------------------------------------------
    # DASHBOARD RESPONSE
    # --------------------------------------------------------

    return jsonify({

        "success": True,

        "dashboard": {

            "facility": facility_data,

            "latest_prediction": (
                prediction_data
            ),

            "active_alerts": alert_data,

            "digital_twin": twin_data,

            "recent_simulations": (
                simulation_data
            ),

            "generated_at": (
                datetime.utcnow()
                .isoformat()
            )

        }

    }), 200


# ============================================================
# DASHBOARD HEALTH
# ============================================================

@dashboard_bp.route(
    "/health",
    methods=["GET"]
)
def dashboard_health():

    facility_id = request.args.get(
        "facility_id",
        default=None,
        type=int
    )

    query = PredictionLog.query

    if facility_id is not None:

        query = query.filter_by(
            facility_id=facility_id
        )

    latest_prediction = (
        query
        .order_by(
            PredictionLog.prediction_timestamp.desc()
        )
        .first()
    )

    if latest_prediction is None:

        return jsonify({

            "success": True,

            "health": {

                "status": "Unknown",

                "health_score": None,

                "failure_probability": None,

                "rul": None,

                "timestamp": None

            }

        }), 200

    return jsonify({

        "success": True,

        "health": {

            "status": (
                latest_prediction.health_status
            ),

            "health_score": (
                latest_prediction.health_score
            ),

            "failure_probability": (
                latest_prediction
                .failure_probability
            ),

            "rul": latest_prediction.rul,

            "timestamp": (
                serialize_datetime(
                    latest_prediction
                    .prediction_timestamp
                )
            )

        }

    }), 200


# ============================================================
# DASHBOARD PREDICTIONS
# ============================================================

@dashboard_bp.route(
    "/predictions",
    methods=["GET"]
)
def dashboard_predictions():

    limit = request.args.get(
        "limit",
        default=10,
        type=int
    )

    if limit < 1:
        limit = 1

    if limit > 100:
        limit = 100

    facility_id = request.args.get(
        "facility_id",
        default=None,
        type=int
    )

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

        output.append({

            "id": prediction.id,

            "facility_id": (
                prediction.facility_id
            ),

            "device_id": (
                prediction.device_id
            ),

            "timestamp": (
                serialize_datetime(
                    prediction
                    .prediction_timestamp
                )
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

            "rul": prediction.rul,

            "inference_time_ms": (
                prediction.inference_time_ms
            )

        })

    return jsonify({

        "success": True,

        "count": len(output),

        "predictions": output

    }), 200


# ============================================================
# DASHBOARD ALERTS
# ============================================================

@dashboard_bp.route(
    "/alerts",
    methods=["GET"]
)
def dashboard_alerts():

    limit = request.args.get(
        "limit",
        default=10,
        type=int
    )

    if limit < 1:
        limit = 1

    if limit > 100:
        limit = 100

    alerts = (
        Alert.query
        .order_by(
            Alert.created_at.desc()
        )
        .limit(limit)
        .all()
    )

    output = []

    for alert in alerts:

        output.append({

            "id": alert.id,

            "alert_type": (
                alert.alert_type
            ),

            "message": alert.message,

            "severity": alert.severity,

            "status": alert.status,

            "created_at": (
                serialize_datetime(
                    alert.created_at
                )
            )

        })

    return jsonify({

        "success": True,

        "count": len(output),

        "alerts": output

    }), 200