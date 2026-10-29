from datetime import datetime

from flask_sqlalchemy import SQLAlchemy


# ============================================================
# DATABASE INSTANCE
# ============================================================

db = SQLAlchemy()


# ============================================================
# USER
# ============================================================

class User(db.Model):

    __tablename__ = "users"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    username = db.Column(
        db.String(100),
        unique=True,
        nullable=False
    )

    email = db.Column(
        db.String(150),
        unique=True,
        nullable=False
    )

    password_hash = db.Column(
        db.String(255),
        nullable=False
    )

    role = db.Column(
        db.String(50),
        nullable=False,
        default="Operator"
    )

    registration_date = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow
    )


# ============================================================
# FACILITY / SUSTAINABLE ENERGY ASSET
# ============================================================

class Facility(db.Model):

    __tablename__ = "facilities"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    name = db.Column(
        db.String(150),
        nullable=False
    )

    facility_type = db.Column(
        db.String(100),
        nullable=False,
        default="Solar Energy Asset"
    )

    installed_capacity_kw = db.Column(
        db.Float,
        nullable=True
    )

    location = db.Column(
        db.String(255),
        nullable=True
    )

    commission_date = db.Column(
        db.DateTime,
        nullable=True
    )


# ============================================================
# SENSOR / ESP32-CONNECTED DEVICE
# ============================================================

class Sensor(db.Model):

    __tablename__ = "sensors"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    device_id = db.Column(
        db.String(100),
        unique=True,
        nullable=False
    )

    sensor_type = db.Column(
        db.String(100),
        nullable=False
    )

    unit = db.Column(
        db.String(50),
        nullable=False
    )

    installation_date = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow
    )

    status = db.Column(
        db.String(50),
        nullable=False,
        default="Online"
    )

    facility_id = db.Column(
        db.Integer,
        db.ForeignKey("facilities.id"),
        nullable=False
    )

    registered_by = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=True
    )


# ============================================================
# SENSOR READING / TELEMETRY
# ============================================================

class SensorReading(db.Model):

    __tablename__ = "sensor_readings"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    sensor_id = db.Column(
        db.Integer,
        db.ForeignKey("sensors.id"),
        nullable=False
    )

    value = db.Column(
        db.Float,
        nullable=False
    )

    timestamp = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow
    )


# ============================================================
# SENSOR THRESHOLD
# ============================================================

class Threshold(db.Model):

    __tablename__ = "thresholds"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    facility_id = db.Column(
        db.Integer,
        db.ForeignKey("facilities.id"),
        nullable=False
    )

    sensor_id = db.Column(
        db.Integer,
        db.ForeignKey("sensors.id"),
        nullable=True
    )

    parameter_name = db.Column(
        db.String(100),
        nullable=False
    )

    minimum_value = db.Column(
        db.Float,
        nullable=True
    )

    maximum_value = db.Column(
        db.Float,
        nullable=True
    )

    effective_date = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow
    )

    severity = db.Column(
        db.String(50),
        nullable=False,
        default="Warning"
    )


# ============================================================
# ALERT
# ============================================================

class Alert(db.Model):

    __tablename__ = "alerts"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    sensor_id = db.Column(
        db.Integer,
        db.ForeignKey("sensors.id"),
        nullable=True
    )

    threshold_id = db.Column(
        db.Integer,
        db.ForeignKey("thresholds.id"),
        nullable=True
    )

    alert_type = db.Column(
        db.String(100),
        nullable=False
    )

    message = db.Column(
        db.Text,
        nullable=False
    )

    severity = db.Column(
        db.String(50),
        nullable=False,
        default="Warning"
    )

    status = db.Column(
        db.String(50),
        nullable=False,
        default="Active"
    )

    created_at = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow
    )


# ============================================================
# NOTIFICATION
# ============================================================

class Notification(db.Model):

    __tablename__ = "notifications"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=True
    )

    alert_id = db.Column(
        db.Integer,
        db.ForeignKey("alerts.id"),
        nullable=True
    )

    message = db.Column(
        db.Text,
        nullable=False
    )

    channel = db.Column(
        db.String(50),
        nullable=True
    )

    sent_timestamp = db.Column(
        db.DateTime,
        nullable=True
    )

    status = db.Column(
        db.String(50),
        nullable=False,
        default="Unread"
    )

    created_at = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow
    )


# ============================================================
# DIGITAL TWIN MODEL
# ============================================================

class DigitalTwinModel(db.Model):

    __tablename__ = "digital_twin_models"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    facility_id = db.Column(
        db.Integer,
        db.ForeignKey("facilities.id"),
        nullable=False
    )

    model_name = db.Column(
        db.String(200),
        nullable=False
    )

    model_version = db.Column(
        db.String(100),
        nullable=False,
        default="1.0"
    )

    model_path = db.Column(
        db.String(500),
        nullable=True
    )

    status = db.Column(
        db.String(50),
        nullable=False,
        default="Active"
    )

    created_at = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow
    )

    last_updated = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow
    )


# ============================================================
# DIGITAL TWIN SIMULATION RUN
# ============================================================

class SimulationRun(db.Model):

    __tablename__ = "simulation_runs"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    facility_id = db.Column(
        db.Integer,
        db.ForeignKey("facilities.id"),
        nullable=False
    )

    model_id = db.Column(
        db.Integer,
        db.ForeignKey("digital_twin_models.id"),
        nullable=False
    )

    simulation_name = db.Column(
        db.String(200),
        nullable=False
    )

    input_data = db.Column(
        db.Text,
        nullable=True
    )

    output_data = db.Column(
        db.Text,
        nullable=True
    )

    status = db.Column(
        db.String(50),
        nullable=False,
        default="Completed"
    )

    created_at = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow
    )


# ============================================================
# REPORT
# ============================================================

class Report(db.Model):

    __tablename__ = "reports"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=True
    )

    facility_id = db.Column(
        db.Integer,
        db.ForeignKey("facilities.id"),
        nullable=False
    )

    title = db.Column(
        db.String(200),
        nullable=False
    )

    report_type = db.Column(
        db.String(100),
        nullable=False
    )

    content = db.Column(
        db.Text,
        nullable=True
    )

    file_path = db.Column(
        db.String(500),
        nullable=True
    )

    created_at = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow
    )
# ============================================================
# PREDICTION LOG
# ============================================================

class PredictionLog(db.Model):

    __tablename__ = "prediction_logs"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    facility_id = db.Column(
        db.Integer,
        db.ForeignKey("facilities.id"),
        nullable=True
    )

    device_id = db.Column(
        db.String(100),
        nullable=True
    )

    prediction_timestamp = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        nullable=False
    )

    # JSON representation of the model input
    feature_vector = db.Column(
        db.Text,
        nullable=False
    )

    health_status = db.Column(
        db.String(50),
        nullable=False
    )

    health_score = db.Column(
        db.Float,
        nullable=False
    )

    failure_probability = db.Column(
        db.Float,
        nullable=False
    )

    rul = db.Column(
        db.Float,
        nullable=True
    )

    inference_time_ms = db.Column(
        db.Float,
        nullable=True
    )
# ============================================================
# XAI EXPLANATION
# ============================================================

class XAIExplanation(db.Model):

    __tablename__ = "xai_explanations"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    prediction_id = db.Column(
        db.Integer,
        db.ForeignKey(
            "prediction_logs.id"
        ),
        nullable=False,
        unique=True
    )

    explanation_json = db.Column(
        db.Text,
        nullable=False
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        nullable=False
    )
# ============================================================
# DIGITAL TWIN STATE HISTORY
# ============================================================

class DigitalTwinState(db.Model):

    __tablename__ = "digital_twin_states"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    facility_id = db.Column(
        db.Integer,
        db.ForeignKey("facilities.id"),
        nullable=False
    )

    model_id = db.Column(
        db.Integer,
        db.ForeignKey("digital_twin_models.id"),
        nullable=True
    )

    device_id = db.Column(
        db.String(100),
        nullable=True
    )

    # --------------------------------------------------------
    # TELEMETRY STATE
    # --------------------------------------------------------

    temperature = db.Column(
        db.Float,
        nullable=True
    )

    voltage = db.Column(
        db.Float,
        nullable=True
    )

    current = db.Column(
        db.Float,
        nullable=True
    )

    light_intensity = db.Column(
        db.Float,
        nullable=True
    )

    vibration = db.Column(
        db.Float,
        nullable=True
    )

    power = db.Column(
        db.Float,
        nullable=True
    )

    # --------------------------------------------------------
    # HEALTH / PREDICTION STATE
    # --------------------------------------------------------

    health_status = db.Column(
        db.String(50),
        nullable=True
    )

    health_score = db.Column(
        db.Float,
        nullable=True
    )

    failure_probability = db.Column(
        db.Float,
        nullable=True
    )

    rul = db.Column(
        db.Float,
        nullable=True
    )

    # --------------------------------------------------------
    # DIGITAL TWIN STATE
    # --------------------------------------------------------

    status = db.Column(
        db.String(50),
        nullable=False,
        default="Synchronized"
    )

    status_color = db.Column(
        db.String(20),
        nullable=False,
        default="green"
    )

    risk_level = db.Column(
        db.String(50),
        nullable=True
    )

    maintenance_recommendation = db.Column(
        db.String(100),
        nullable=True
    )

    # JSON list of active alerts / threshold breaches
    active_alerts = db.Column(
        db.Text,
        nullable=True
    )

    # Complete virtual asset snapshot
    state_snapshot = db.Column(
        db.Text,
        nullable=True
    )

    synchronized_at = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow
    )

    created_at = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow
    )