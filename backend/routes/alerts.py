from flask import Blueprint, request, jsonify
from datetime import datetime

from backend.models.models import (
    db,
    Alert,
    Notification,
    Sensor
)

alerts_bp = Blueprint(
    "alerts",
    __name__,
    url_prefix="/api/alerts"
)


# ============================================================
# GET ALERTS
# ============================================================

@alerts_bp.route("", methods=["GET"])
def get_alerts():

    try:
        facility_id = request.args.get(
            "facility_id",
            type=int
        )

        status = request.args.get("status")

        query = Alert.query

        if status:
            query = query.filter(
                Alert.status == status
            )

        alerts = query.order_by(
            Alert.created_at.desc()
        ).all()

        result = []

        for alert in alerts:

            # Optional facility filtering
            if facility_id is not None and alert.sensor_id:

                sensor = Sensor.query.get(
                    alert.sensor_id
                )

                if sensor and hasattr(
                    sensor,
                    "facility_id"
                ):

                    if sensor.facility_id != facility_id:
                        continue

            result.append({

                "id":
                    alert.id,

                "sensor_id":
                    alert.sensor_id,

                "threshold_id":
                    alert.threshold_id,

                "alert_type":
                    alert.alert_type,

                "message":
                    alert.message,

                "severity":
                    alert.severity,

                "status":
                    alert.status,

                "created_at":
                    alert.created_at.isoformat()
                    if alert.created_at
                    else None
            })

        return jsonify({

            "success": True,

            "count":
                len(result),

            "alerts":
                result
        })

    except Exception as e:

        return jsonify({

            "success": False,

            "error":
                str(e)

        }), 500


# ============================================================
# GENERATE HEALTH ALERT
# ============================================================

@alerts_bp.route(
    "/generate",
    methods=["POST"]
)
def generate_alert():

    try:

        data = request.get_json(
            silent=True
        ) or {}

        facility_id = data.get(
            "facility_id",
            1
        )

        device_id = data.get(
            "device_id",
            "SOLAR-ESP32-001"
        )

        health_status = data.get(
            "health_status",
            "Healthy"
        )

        health_score = float(
            data.get(
                "health_score",
                100
            )
        )

        failure_probability = float(
            data.get(
                "failure_probability",
                0
            )
        )

        rul = data.get("rul")

        # ====================================================
        # DETERMINE SEVERITY
        # ====================================================

        if (
            failure_probability >= 0.70
            or health_score < 40
            or health_status.lower() == "critical"
        ):

            severity = "Critical"

            message = (
                f"Critical health condition detected "
                f"for device {device_id}. "
                f"Health status: {health_status}. "
                f"Failure probability: "
                f"{failure_probability * 100:.2f}%. "
                f"Health score: {health_score:.1f}."
            )

        elif (
            failure_probability >= 0.30
            or health_score < 70
            or health_status.lower() == "warning"
        ):

            severity = "Warning"

            message = (
                f"Warning health condition detected "
                f"for device {device_id}. "
                f"Health status: {health_status}. "
                f"Failure probability: "
                f"{failure_probability * 100:.2f}%. "
                f"Health score: {health_score:.1f}."
            )

        else:

            severity = "Info"

            message = (
                f"Device {device_id} is operating normally. "
                f"Health status: {health_status}. "
                f"Health score: {health_score:.1f}."
            )

        # ====================================================
        # CHECK EXISTING ACTIVE HEALTH ALERT
        # ====================================================

        existing = Alert.query.filter_by(
            alert_type="Health Prediction Alert",
            status="Active"
        ).order_by(
            Alert.created_at.desc()
        ).first()

        if existing:

            existing.message = message
            existing.severity = severity
            existing.created_at = datetime.utcnow()

            alert = existing

        else:

            alert = Alert(

                sensor_id=None,

                threshold_id=None,

                alert_type=
                    "Health Prediction Alert",

                message=message,

                severity=severity,

                status="Active"
            )

            db.session.add(alert)

            db.session.flush()

        # ====================================================
        # CREATE NOTIFICATION
        #
        # IMPORTANT:
        # Your model uses:
        # channel
        # NOT notification_type
        # ====================================================

        notification = Notification(

            user_id=None,

            alert_id=alert.id,

            message=message,

            channel="Dashboard",

            sent_timestamp=datetime.utcnow(),

            status="Unread"
        )

        db.session.add(notification)

        db.session.commit()

        return jsonify({

            "success": True,

            "message":
                "Alert generated successfully.",

            "alert": {

                "id":
                    alert.id,

                "alert_type":
                    alert.alert_type,

                "message":
                    alert.message,

                "severity":
                    alert.severity,

                "status":
                    alert.status,

                "created_at":
                    alert.created_at.isoformat()
                    if alert.created_at
                    else None
            },

            "notification": {

                "id":
                    notification.id,

                "channel":
                    notification.channel,

                "status":
                    notification.status,

                "created_at":
                    notification.created_at.isoformat()
                    if notification.created_at
                    else None
            }
        })

    except Exception as e:

        db.session.rollback()

        return jsonify({

            "success": False,

            "error":
                str(e)

        }), 500


# ============================================================
# ACKNOWLEDGE ALERT
# ============================================================

@alerts_bp.route(
    "/<int:alert_id>/acknowledge",
    methods=["POST"]
)
def acknowledge_alert(alert_id):

    try:

        alert = Alert.query.get(
            alert_id
        )

        if not alert:

            return jsonify({

                "success": False,

                "error":
                    "Alert not found."

            }), 404

        alert.status = "Acknowledged"

        db.session.commit()

        return jsonify({

            "success": True,

            "message":
                "Alert acknowledged successfully.",

            "alert_id":
                alert.id,

            "status":
                alert.status
        })

    except Exception as e:

        db.session.rollback()

        return jsonify({

            "success": False,

            "error":
                str(e)

        }), 500


# ============================================================
# RESOLVE ALERT
# ============================================================

@alerts_bp.route(
    "/<int:alert_id>/resolve",
    methods=["POST"]
)
def resolve_alert(alert_id):

    try:

        alert = Alert.query.get(
            alert_id
        )

        if not alert:

            return jsonify({

                "success": False,

                "error":
                    "Alert not found."

            }), 404

        alert.status = "Resolved"

        db.session.commit()

        return jsonify({

            "success": True,

            "message":
                "Alert resolved successfully.",

            "alert_id":
                alert.id,

            "status":
                alert.status
        })

    except Exception as e:

        db.session.rollback()

        return jsonify({

            "success": False,

            "error":
                str(e)

        }), 500


# ============================================================
# GET NOTIFICATIONS
# ============================================================

@alerts_bp.route(
    "/notifications",
    methods=["GET"]
)
def get_notifications():

    try:

        notifications = Notification.query.order_by(
            Notification.created_at.desc()
        ).limit(50).all()

        result = []

        for notification in notifications:

            result.append({

                "id":
                    notification.id,

                "alert_id":
                    notification.alert_id,

                "message":
                    notification.message,

                "channel":
                    notification.channel,

                "sent_timestamp":
                    notification.sent_timestamp.isoformat()
                    if notification.sent_timestamp
                    else None,

                "status":
                    notification.status,

                "created_at":
                    notification.created_at.isoformat()
                    if notification.created_at
                    else None
            })

        return jsonify({

            "success": True,

            "count":
                len(result),

            "notifications":
                result
        })

    except Exception as e:

        return jsonify({

            "success": False,

            "error":
                str(e)

        }), 500


# ============================================================
# MARK NOTIFICATION AS READ
# ============================================================

@alerts_bp.route(
    "/notifications/<int:notification_id>/read",
    methods=["POST"]
)
def mark_notification_read(
    notification_id
):

    try:

        notification = Notification.query.get(
            notification_id
        )

        if not notification:

            return jsonify({

                "success": False,

                "error":
                    "Notification not found."

            }), 404

        notification.status = "Read"

        db.session.commit()

        return jsonify({

            "success": True,

            "message":
                "Notification marked as read.",

            "notification_id":
                notification.id,

            "status":
                notification.status
        })

    except Exception as e:

        db.session.rollback()

        return jsonify({

            "success": False,

            "error":
                str(e)

        }), 500