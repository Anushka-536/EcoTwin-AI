import json
from datetime import datetime

from flask import Blueprint, request, jsonify

from backend.models.models import db

from backend.models.models import (
    Facility,
    Sensor,
    SensorReading,
    Threshold,
    Alert,
    PredictionLog,
    DigitalTwinModel,
    DigitalTwinState,
    SimulationRun
)


# ============================================================
# DIGITAL TWIN BLUEPRINT
# ============================================================

digital_twin_bp = Blueprint(
    "digital_twin",
    __name__,
    url_prefix="/api/digital-twin"
)


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def safe_float(value):
    """
    Safely convert a value to float.
    """
    try:
        if value is None:
            return None

        return float(value)

    except (TypeError, ValueError):
        return None


def determine_status_color(health_status):
    """
    SRS REQ-DT-3:
    Green  = Healthy
    Yellow = Warning
    Red    = Critical
    """

    status = str(
        health_status or "Unknown"
    ).strip().lower()

    if status == "healthy":
        return "green"

    if status == "warning":
        return "yellow"

    if status == "critical":
        return "red"

    return "gray"


def determine_risk_level(
    health_status,
    failure_probability
):
    """
    Determine a human-readable risk level.
    """

    status = str(
        health_status or ""
    ).lower()

    probability = safe_float(
        failure_probability
    )

    if status == "critical":
        return "High"

    if probability is not None:

        if probability >= 70:
            return "High"

        if probability >= 30:
            return "Medium"

        return "Low"

    if status == "warning":
        return "Medium"

    if status == "healthy":
        return "Low"

    return "Unknown"


def determine_recommendation(
    health_status,
    failure_probability,
    health_score
):
    """
    Decision-support prototype used by the
    Digital Twin state.

    Categories are aligned with the SRS:
    - Immediate Maintenance
    - Inspection Schedule
    - Cleaning Recommendation
    - Continued Operation
    """

    status = str(
        health_status or ""
    ).lower()

    probability = safe_float(
        failure_probability
    )

    score = safe_float(
        health_score
    )

    if status == "critical":

        return "Immediate Maintenance"

    if probability is not None:

        if probability >= 70:
            return "Immediate Maintenance"

        if probability >= 30:
            return "Inspection Schedule"

    if status == "warning":

        return "Inspection Schedule"

    if score is not None:

        if score < 50:
            return "Inspection Schedule"

    return "Continued Operation"


def get_latest_telemetry(facility_id):
    """
    Retrieve the latest reading for each sensor
    belonging to the selected facility.
    """

    sensors = (
        Sensor.query
        .filter_by(facility_id=facility_id)
        .all()
    )

    telemetry = {}

    for sensor in sensors:

        reading = (
            SensorReading.query
            .filter_by(sensor_id=sensor.id)
            .order_by(
                SensorReading.timestamp.desc()
            )
            .first()
        )

        if reading is None:
            continue

        parameter = (
            sensor.sensor_type or ""
        ).strip().lower()

        telemetry[parameter] = {
            "value": reading.value,
            "timestamp": (
                reading.timestamp.isoformat()
                if reading.timestamp
                else None
            ),
            "unit": sensor.unit
        }

    return telemetry


def normalize_telemetry(telemetry):
    """
    Map different sensor names to the
    Digital Twin's canonical fields.
    """

    result = {
        "temperature": None,
        "ambient_temperature": None,
        "module_temperature": None,
        "voltage": None,
        "current": None,
        "light_intensity": None,
        "irradiance": None,
        "vibration": None,
        "power": None
    }

    for key, data in telemetry.items():

        key_lower = str(
            key
        ).strip().lower()

        value = (
            data.get("value")
            if isinstance(data, dict)
            else data
        )

        if key_lower in (
            "temperature",
            "temp"
        ):

            result["temperature"] = safe_float(value)

        elif key_lower in (
            "ambient_temperature",
            "ambient temperature"
        ):

            result["ambient_temperature"] = safe_float(
                value
            )

            if result["temperature"] is None:
                result["temperature"] = safe_float(
                    value
                )

        elif key_lower in (
            "module_temperature",
            "module temperature"
        ):

            result["module_temperature"] = safe_float(
                value
            )

        elif key_lower == "voltage":

            result["voltage"] = safe_float(
                value
            )

        elif key_lower == "current":

            result["current"] = safe_float(
                value
            )

        elif key_lower in (
            "irradiance",
            "solar irradiance",
            "light",
            "light_intensity",
            "light intensity"
        ):

            result["irradiance"] = safe_float(
                value
            )

            result["light_intensity"] = safe_float(
                value
            )

        elif key_lower == "vibration":

            result["vibration"] = safe_float(
                value
            )

        elif key_lower == "power":

            result["power"] = safe_float(
                value
            )

    return result


def get_latest_prediction(facility_id):
    """
    Retrieve the most recent ML prediction.
    """

    return (
        PredictionLog.query
        .filter_by(facility_id=facility_id)
        .order_by(
            PredictionLog.prediction_timestamp.desc()
        )
        .first()
    )


def get_active_alerts(facility_id):
    """
    Retrieve active alerts related to the
    facility's sensors or prediction system.
    """

    sensor_ids = [
        sensor.id
        for sensor in (
            Sensor.query
            .filter_by(facility_id=facility_id)
            .all()
        )
    ]

    query = Alert.query.filter(
        Alert.status == "Active"
    )

    alerts = query.order_by(
        Alert.created_at.desc()
    ).all()

    result = []

    for alert in alerts:

        if alert.sensor_id is not None:

            if alert.sensor_id not in sensor_ids:
                continue

        result.append({
            "id": alert.id,
            "alert_type": alert.alert_type,
            "message": alert.message,
            "severity": alert.severity,
            "status": alert.status,
            "created_at": (
                alert.created_at.isoformat()
                if alert.created_at
                else None
            )
        })

    return result


def detect_threshold_breaches(
    facility_id,
    normalized
):
    """
    Compare the current virtual asset state
    against configured thresholds.

    This implements REQ-DT-4.
    """

    thresholds = (
        Threshold.query
        .filter_by(facility_id=facility_id)
        .all()
    )

    breaches = []

    for threshold in thresholds:

        parameter = (
            threshold.parameter_name or ""
        ).strip().lower()

        value = None

        if parameter in normalized:
            value = normalized.get(parameter)

        elif parameter in (
            "light",
            "light intensity",
            "solar irradiance",
            "irradiance"
        ):

            value = normalized.get(
                "light_intensity"
            )

        elif parameter in (
            "temp",
            "temperature"
        ):

            value = normalized.get(
                "temperature"
            )

        if value is None:
            continue

        minimum = threshold.minimum_value
        maximum = threshold.maximum_value

        breached = False
        reason = None

        if minimum is not None and value < minimum:

            breached = True

            reason = (
                f"{parameter} below minimum "
                f"({value} < {minimum})"
            )

        if maximum is not None and value > maximum:

            breached = True

            reason = (
                f"{parameter} above maximum "
                f"({value} > {maximum})"
            )

        if breached:

            breaches.append({
                "threshold_id": threshold.id,
                "parameter": parameter,
                "value": value,
                "minimum": minimum,
                "maximum": maximum,
                "severity": threshold.severity,
                "reason": reason
            })

    return breaches


def find_or_create_digital_twin_model(
    facility_id
):
    """
    Ensure every facility has a Digital Twin model
    metadata record.
    """

    model = (
        DigitalTwinModel.query
        .filter_by(facility_id=facility_id)
        .order_by(
            DigitalTwinModel.id.desc()
        )
        .first()
    )

    if model:
        return model

    model = DigitalTwinModel(
        facility_id=facility_id,
        model_name="EcoTwin-AI Solar Digital Twin",
        model_version="1.0",
        model_path=None,
        status="Active",
        created_at=datetime.utcnow(),
        last_updated=datetime.utcnow()
    )

    db.session.add(model)
    db.session.flush()

    return model


def serialize_state(state):
    """
    Convert DigitalTwinState into API JSON.
    """

    active_alerts = []

    if state.active_alerts:

        try:
            active_alerts = json.loads(
                state.active_alerts
            )

        except Exception:
            active_alerts = []

    snapshot = {}

    if state.state_snapshot:

        try:
            snapshot = json.loads(
                state.state_snapshot
            )

        except Exception:
            snapshot = {}

    return {
        "id": state.id,
        "facility_id": state.facility_id,
        "model_id": state.model_id,
        "device_id": state.device_id,

        "virtual_asset": {
            "asset_id": state.facility_id,
            "asset_name": snapshot.get(
                "asset_name",
                "EcoTwin-AI Solar Energy Asset"
            ),
            "asset_type": snapshot.get(
                "asset_type",
                "Solar Energy Asset"
            )
        },

        "telemetry": {
            "temperature": state.temperature,
            "voltage": state.voltage,
            "current": state.current,
            "light_intensity": state.light_intensity,
            "vibration": state.vibration,
            "power": state.power
        },

        "health": {
            "status": state.health_status,
            "score": state.health_score,
            "failure_probability": (
                state.failure_probability
            ),
            "rul": state.rul
        },

        "risk": {
            "level": state.risk_level,
            "status_color": state.status_color
        },

        "maintenance_recommendation": (
            state.maintenance_recommendation
        ),

        "active_alerts": active_alerts,

        "synchronized_at": (
            state.synchronized_at.isoformat()
            if state.synchronized_at
            else None
        ),

        "snapshot": snapshot
    }


# ============================================================
# GET CURRENT DIGITAL TWIN
# ============================================================

@digital_twin_bp.route(
    "",
    methods=["GET"]
)
def get_digital_twin():

    try:

        facility_id = request.args.get(
            "facility_id",
            default=1,
            type=int
        )

        facility = db.session.get(
            Facility,
            facility_id
        )

        if facility is None:

            return jsonify({
                "success": False,
                "error": "Facility not found."
            }), 404

        state = (
            DigitalTwinState.query
            .filter_by(
                facility_id=facility_id
            )
            .order_by(
                DigitalTwinState.created_at.desc()
            )
            .first()
        )

        # If no persistent state exists yet,
        # synchronize once.
        if state is None:

            result = synchronize_twin_internal(
                facility_id
            )

            if not result["success"]:
                return jsonify(result), 500

            state = result["state"]

        return jsonify({
            "success": True,
            "digital_twin": serialize_state(
                state
            )
        })

    except Exception as e:

        db.session.rollback()

        return jsonify({
            "success": False,
            "error": "Could not retrieve Digital Twin.",
            "details": str(e)
        }), 500

def apply_rule_layer(
    telemetry,
    health_status,
    health_score,
    failure_probability,
    rul
):
    """
    Rule-based safety layer on top of the ML model.
    Returns (status, score, failure_probability, rul, reason).
    reason is None when no rule fired.
    """

    module_temp = safe_float(
        telemetry.get("module_temperature")
    )

    vibration = safe_float(
        telemetry.get("vibration")
    )

    level = 0
    reasons = []

    if module_temp is not None:

        if module_temp >= 80:
            level = 2
            reasons.append(
                f"Module temperature {module_temp:.1f} °C "
                f"is at or above 80 °C"
            )

        elif module_temp >= 65:
            level = max(level, 1)
            reasons.append(
                f"Module temperature {module_temp:.1f} °C "
                f"is at or above 65 °C"
            )

    if vibration is not None:

        if vibration >= 4.0:
            level = 2
            reasons.append(
                f"Vibration {vibration:.2f} mm/s "
                f"is at or above 4.0 mm/s"
            )

        elif vibration >= 2.5:
            level = max(level, 1)
            reasons.append(
                f"Vibration {vibration:.2f} mm/s "
                f"is at or above 2.5 mm/s"
            )

    # No rule fired: keep the model's output
    if level == 0:
        return (
            health_status,
            health_score,
            failure_probability,
            rul,
            None
        )

    score = safe_float(health_score)
    if score is None:
        score = 100.0

    probability = safe_float(failure_probability) or 0.0

    remaining = safe_float(rul)
    if remaining is None:
        remaining = 180.0

    if level == 2:
        return (
            "Critical",
            min(score, 30.0),
            max(probability, 85.0),
            min(remaining, 7.0),
            "; ".join(reasons)
        )

    return (
        "Warning",
        min(score, 60.0),
        max(probability, 45.0),
        min(remaining, 60.0),
        "; ".join(reasons)
    )
# ============================================================
# SYNCHRONIZE DIGITAL TWIN
# ============================================================

def synchronize_twin_internal(
    facility_id
):

    start_time = datetime.utcnow()

    facility = db.session.get(
        Facility,
        facility_id
    )

    if facility is None:

        return {
            "success": False,
            "error": "Facility not found."
        }

    model = find_or_create_digital_twin_model(
        facility_id
    )

    telemetry_raw = get_latest_telemetry(
        facility_id
    )

    telemetry = normalize_telemetry(
        telemetry_raw
    )

    prediction = get_latest_prediction(
        facility_id
    )

    # --------------------------------------------------------
    # HEALTH STATE
    # --------------------------------------------------------

    if prediction:

        health_status = (
            prediction.health_status
        )

        health_score = (
            prediction.health_score
        )

        failure_probability = (
            prediction.failure_probability
        )

        rul = prediction.rul

        device_id = prediction.device_id

    else:

        health_status = "Unknown"
        health_score = None
        failure_probability = None
        rul = None
        device_id = None

    # --------------------------------------------------------
    # RULE-BASED SAFETY LAYER (on top of the ML model)
    # --------------------------------------------------------

    (
        health_status,
        health_score,
        failure_probability,
        rul,
        rule_reason
    ) = apply_rule_layer(
        telemetry,
        health_status,
        health_score,
        failure_probability,
        rul
    )

   
    # --------------------------------------------------------
    # STATUS / RISK
    # --------------------------------------------------------

    status_color = determine_status_color(
        health_status
    )

    risk_level = determine_risk_level(
        health_status,
        failure_probability
    )

    recommendation = determine_recommendation(
        health_status,
        failure_probability,
        health_score
    )

    # --------------------------------------------------------
    # THRESHOLD BREACHES
    # --------------------------------------------------------

    threshold_breaches = (
        detect_threshold_breaches(
            facility_id,
            telemetry
        )
    )

    # --------------------------------------------------------
    # ACTIVE ALERTS
    # --------------------------------------------------------

    active_alerts = get_active_alerts(
        facility_id
    )
    if rule_reason:
        active_alerts.insert(0, {
            "id": None,
            "alert_type": "Rule-Based Safety Alert",
            "message": rule_reason,
            "severity": (
                "Critical" if health_status == "Critical"
                else "Warning"
            ),
            "status": "Active",
            "created_at": datetime.utcnow().isoformat()
        })
    # Add threshold breaches to the
    # virtual twin state.
    for breach in threshold_breaches:

        active_alerts.append({
            "id": None,
            "alert_type": "Threshold Breach",
            "message": breach["reason"],
            "severity": breach["severity"],
            "status": "Active",
            "created_at": None,
            "threshold_id": breach["threshold_id"]
        })

    # --------------------------------------------------------
    # SNAPSHOT
    # --------------------------------------------------------

    synchronized_at = datetime.utcnow()

    snapshot = {
        "asset_id": facility.id,

        "asset_name": facility.name,

        "asset_type": (
            facility.facility_type
            or "Solar Energy Asset"
        ),

        "facility": {
            "name": facility.name,
            "location": facility.location,
            "installed_capacity_kw": (
                facility.installed_capacity_kw
            )
        },

        "device_id": device_id,

        "telemetry": telemetry,

        "health": {
            "status": health_status,
            "score": health_score,
            "failure_probability": (
                failure_probability
            ),
            "rul": rul
        },

        "risk": {
            "level": risk_level,
            "status_color": status_color
        },

        "maintenance_recommendation": (
            recommendation
        ),

        "active_alerts": active_alerts,

        "threshold_breaches": (
            threshold_breaches
        ),

        "synchronized_at": (
            synchronized_at.isoformat()
        )
    }
    # --------------------------------------------------------
    # CREATE AN ALERT WHEN HEALTH STATUS CHANGES
    # --------------------------------------------------------

    previous_state = (
        DigitalTwinState.query
        .filter_by(facility_id=facility_id)
        .order_by(DigitalTwinState.created_at.desc())
        .first()
    )

    previous_status = (
        previous_state.health_status
        if previous_state else None
    )

    if health_status != previous_status:

        if health_status == "Critical":
            alert_severity = "Critical"
        elif health_status == "Warning":
            alert_severity = "Warning"
        else:
            alert_severity = "Info"

        alert_message = (
            f"Health status changed from "
            f"{previous_status or 'Unknown'} to "
            f"{health_status}. Health score: {health_score}."
        )

        if rule_reason:
            alert_message += f" Cause: {rule_reason}."

        db.session.add(Alert(
            alert_type="Health Status Change",
            message=alert_message,
            severity=alert_severity,
            status="Active",
            created_at=datetime.utcnow()
        ))
    # --------------------------------------------------------
    # PERSIST DIGITAL TWIN STATE
    # --------------------------------------------------------

    state = DigitalTwinState(

        facility_id=facility_id,

        model_id=model.id,

        device_id=device_id,

        temperature=(
            telemetry.get("temperature")
        ),

        voltage=(
            telemetry.get("voltage")
        ),

        current=(
            telemetry.get("current")
        ),

        light_intensity=(
            telemetry.get("light_intensity")
        ),

        vibration=(
            telemetry.get("vibration")
        ),

        power=(
            telemetry.get("power")
        ),

        health_status=health_status,

        health_score=health_score,

        failure_probability=(
            failure_probability
        ),

        rul=rul,

        status="Synchronized",

        status_color=status_color,

        risk_level=risk_level,

        maintenance_recommendation=(
            recommendation
        ),

        active_alerts=json.dumps(
            active_alerts
        ),

        state_snapshot=json.dumps(
            snapshot
        ),

        synchronized_at=synchronized_at,

        created_at=synchronized_at
    )

    db.session.add(state)

    model.last_updated = synchronized_at

    db.session.commit()

    elapsed_ms = (
        datetime.utcnow() - start_time
    ).total_seconds() * 1000

    return {
        "success": True,
        "state": state,
        "elapsed_ms": elapsed_ms
    }


@digital_twin_bp.route(
    "/synchronize",
    methods=["POST"]
)
def synchronize_digital_twin():

    try:

        data = request.get_json(
            silent=True
        ) or {}

        facility_id = int(
            data.get(
                "facility_id",
                1
            )
        )

        result = synchronize_twin_internal(
            facility_id
        )

        if not result["success"]:

            return jsonify(result), 404

        state = result["state"]

        return jsonify({

            "success": True,

            "synchronized": True,

            "facility_id": facility_id,

            "message": (
                "Digital Twin synchronized successfully."
            ),

            "update_time_ms": (
                round(
                    result["elapsed_ms"],
                    3
                )
            ),

            "within_srs_limit": (
                result["elapsed_ms"] <= 5000
            ),

            "digital_twin": (
                serialize_state(state)
            ),

            "timestamp": (
                datetime.utcnow().isoformat()
            )
        })

    except Exception as e:

        db.session.rollback()

        return jsonify({
            "success": False,
            "synchronized": False,
            "error": "Digital Twin synchronization failed.",
            "details": str(e)
        }), 500


# ============================================================
# DIGITAL TWIN HISTORY
# ============================================================

@digital_twin_bp.route(
    "/history",
    methods=["GET"]
)
def digital_twin_history():

    try:

        facility_id = request.args.get(
            "facility_id",
            default=1,
            type=int
        )

        limit = request.args.get(
            "limit",
            default=50,
            type=int
        )

        limit = min(
            max(limit, 1),
            500
        )

        states = (
            DigitalTwinState.query
            .filter_by(
                facility_id=facility_id
            )
            .order_by(
                DigitalTwinState.created_at.desc()
            )
            .limit(limit)
            .all()
        )

        return jsonify({

            "success": True,

            "facility_id": facility_id,

            "count": len(states),

            "states": [
                serialize_state(state)
                for state in reversed(states)
            ]
        })

    except Exception as e:

        return jsonify({
            "success": False,
            "error": "Could not retrieve Digital Twin history.",
            "details": str(e)
        }), 500


# ============================================================
# DIGITAL TWIN SIMULATION
# ============================================================

@digital_twin_bp.route(
    "/simulate",
    methods=["POST"]
)
def simulate_digital_twin():

    try:

        data = request.get_json(
            silent=True
        ) or {}

        facility_id = int(
            data.get(
                "facility_id",
                1
            )
        )

        scenario = str(
            data.get(
                "scenario",
                "normal"
            )
        ).strip().lower()

        # ----------------------------------------------------
        # Get current twin WITHOUT modifying it
        # ----------------------------------------------------

        current_state = (
            DigitalTwinState.query
            .filter_by(
                facility_id=facility_id
            )
            .order_by(
                DigitalTwinState.created_at.desc()
            )
            .first()
        )

        if current_state is None:

            sync_result = synchronize_twin_internal(
                facility_id
            )

            if not sync_result["success"]:
                return jsonify(sync_result), 404

            current_state = sync_result["state"]

        snapshot = {}

        if current_state.state_snapshot:

            snapshot = json.loads(
                current_state.state_snapshot
            )

        current_telemetry = (
            snapshot.get(
                "telemetry",
                {}
            )
        )

        simulated_telemetry = json.loads(
            json.dumps(
                current_telemetry
            )
        )

        # ----------------------------------------------------
        # WHAT-IF SCENARIOS
        # ----------------------------------------------------

        if scenario == "high_temperature":

            if simulated_telemetry.get(
                "module_temperature"
            ) is not None:

                simulated_telemetry[
                    "module_temperature"
                ] += 20

            if simulated_telemetry.get(
                "temperature"
            ) is not None:

                simulated_telemetry[
                    "temperature"
                ] += 20

        elif scenario == "low_irradiance":

            if simulated_telemetry.get(
                "irradiance"
            ) is not None:

                simulated_telemetry[
                    "irradiance"
                ] *= 0.40

            if simulated_telemetry.get(
                "light_intensity"
            ) is not None:

                simulated_telemetry[
                    "light_intensity"
                ] *= 0.40

        elif scenario == "high_load":

            if simulated_telemetry.get(
                "current"
            ) is not None:

                simulated_telemetry[
                    "current"
                ] *= 1.25

            if simulated_telemetry.get(
                "power"
            ) is not None:

                simulated_telemetry[
                    "power"
                ] *= 1.25

        elif scenario == "normal":

            pass

        else:

            return jsonify({
                "success": False,
                "error": (
                    "Unknown simulation scenario."
                ),
                "supported_scenarios": [
                    "normal",
                    "high_temperature",
                    "low_irradiance",
                    "high_load"
                ]
            }), 400

        # ----------------------------------------------------
        # Simple simulation impact model
        # ----------------------------------------------------

        simulated_power = safe_float(
            simulated_telemetry.get(
                "power"
            )
        )

        simulated_temperature = safe_float(
            simulated_telemetry.get(
                "module_temperature"
            )
        )

        if simulated_power is None:

            simulated_power = safe_float(
                simulated_telemetry.get(
                    "power"
                )
            )

        # Derive simulated health from
        # scenario impact.
        simulated_health = (
            current_state.health_score
            if current_state.health_score is not None
            else 100.0
        )

        simulated_failure_probability = (
            current_state.failure_probability
            if current_state.failure_probability is not None
            else 0.0
        )

        if scenario == "high_temperature":

            simulated_health = max(
                0.0,
                simulated_health - 15.0
            )

            simulated_failure_probability = min(
                100.0,
                simulated_failure_probability + 20.0
            )

        elif scenario == "low_irradiance":

            simulated_health = max(
                0.0,
                simulated_health - 5.0
            )

            simulated_failure_probability = min(
                100.0,
                simulated_failure_probability + 5.0
            )

        elif scenario == "high_load":

            simulated_health = max(
                0.0,
                simulated_health - 10.0
            )

            simulated_failure_probability = min(
                100.0,
                simulated_failure_probability + 10.0
            )

        if simulated_health >= 70:

            simulated_status = "Healthy"

        elif simulated_health >= 40:

            simulated_status = "Warning"

        else:

            simulated_status = "Critical"

        simulated_color = (
            determine_status_color(
                simulated_status
            )
        )

        simulated_risk = (
            determine_risk_level(
                simulated_status,
                simulated_failure_probability
            )
        )

        simulated_recommendation = (
            determine_recommendation(
                simulated_status,
                simulated_failure_probability,
                simulated_health
            )
        )

        simulated_rul = (
            current_state.rul
            if current_state.rul is not None
            else None
        )

        if simulated_rul is not None:

            if simulated_status == "Critical":

                simulated_rul = max(
                    1,
                    simulated_rul * 0.40
                )

            elif simulated_status == "Warning":

                simulated_rul = max(
                    1,
                    simulated_rul * 0.70
                )

        # ----------------------------------------------------
        # Get model
        # ----------------------------------------------------

        model = find_or_create_digital_twin_model(
            facility_id
        )

        # ----------------------------------------------------
        # Store simulation
        # IMPORTANT:
        # Does NOT modify DigitalTwinState.
        # ----------------------------------------------------

        simulation_input = {
            "scenario": scenario,
            "base_state_id": current_state.id,
            "telemetry": current_telemetry
        }

        simulation_output = {
            "scenario": scenario,
            "simulated_telemetry": simulated_telemetry,
            "health_status": simulated_status,
            "health_score": simulated_health,
            "failure_probability": (
                simulated_failure_probability
            ),
            "rul": simulated_rul,
            "risk_level": simulated_risk,
            "status_color": simulated_color,
            "maintenance_recommendation": (
                simulated_recommendation
            ),
            "is_simulation": True,
            "generated_at": (
                datetime.utcnow().isoformat()
            )
        }

        simulation = SimulationRun(

            facility_id=facility_id,

            model_id=model.id,

            simulation_name=(
                f"Digital Twin - {scenario}"
            ),

            input_data=json.dumps(
                simulation_input
            ),

            output_data=json.dumps(
                simulation_output
            ),

            status="Completed",

            created_at=datetime.utcnow()
        )

        db.session.add(simulation)

        db.session.commit()

        return jsonify({

            "success": True,

            "simulation": {

                "id": simulation.id,

                "name": simulation.simulation_name,

                "status": simulation.status,

                "scenario": scenario,

                "base_state_id": (
                    current_state.id
                ),

                "virtual_twin": {

                    "health_status": (
                        simulated_status
                    ),

                    "health_score": (
                        round(
                            simulated_health,
                            2
                        )
                    ),

                    "failure_probability": (
                        round(
                            simulated_failure_probability,
                            2
                        )
                    ),

                    "rul": simulated_rul,

                    "risk_level": (
                        simulated_risk
                    ),

                    "status_color": (
                        simulated_color
                    ),

                    "maintenance_recommendation": (
                        simulated_recommendation
                    ),

                    "telemetry": (
                        simulated_telemetry
                    )
                },

                "note": (
                    "Simulation only. "
                    "The live Digital Twin state "
                    "was not overwritten."
                )
            },

            "timestamp": (
                datetime.utcnow().isoformat()
            )
        })

    except Exception as e:

        db.session.rollback()

        return jsonify({
            "success": False,
            "error": "Digital Twin simulation failed.",
            "details": str(e)
        }), 500

# ============================================================
# RESET DASHBOARD DATA
# ============================================================

@digital_twin_bp.route(
    "/reset",
    methods=["POST"]
)
def reset_dashboard_data():

    try:

        from backend.models.models import XAIExplanation

        data = request.get_json(silent=True) or {}

        facility_id = int(data.get("facility_id", 1))

        sensor_ids = [
            s.id for s in
            Sensor.query.filter_by(facility_id=facility_id).all()
        ]

        # Readings
        if sensor_ids:
            SensorReading.query.filter(
                SensorReading.sensor_id.in_(sensor_ids)
            ).delete(synchronize_session=False)

        # Predictions and their explanations
        prediction_ids = [
            p.id for p in
            PredictionLog.query.filter_by(
                facility_id=facility_id
            ).all()
        ]

        if prediction_ids:
            XAIExplanation.query.filter(
                XAIExplanation.prediction_id.in_(prediction_ids)
            ).delete(synchronize_session=False)

        PredictionLog.query.filter_by(
            facility_id=facility_id
        ).delete(synchronize_session=False)

        # Twin history
        DigitalTwinState.query.filter_by(
            facility_id=facility_id
        ).delete(synchronize_session=False)

        # Alerts
        Alert.query.filter(
            (Alert.sensor_id.in_(sensor_ids)) |
            (Alert.sensor_id.is_(None))
        ).delete(synchronize_session=False)

        db.session.commit()

        return jsonify({
            "success": True,
            "message": "Dashboard data reset."
        })

    except Exception as e:

        db.session.rollback()

        return jsonify({
            "success": False,
            "error": "Reset failed.",
            "details": str(e)
        }), 500