from flask import Blueprint, request, jsonify, make_response
from datetime import datetime
import json

from backend.models.models import (
    db,
    Report,
    Facility,
    PredictionLog,
    Alert,
    SimulationRun
)

reports_bp = Blueprint(
    "reports",
    __name__,
    url_prefix="/api/reports"
)


# ============================================================
# BUILD REPORT DATA
# ============================================================

def build_report_data(facility_id):

    facility = Facility.query.get(facility_id)

    if not facility:
        return None

    predictions = PredictionLog.query.filter_by(
        facility_id=facility_id
    ).order_by(
        PredictionLog.prediction_timestamp.desc()
    ).limit(20).all()

    alerts = Alert.query.order_by(
        Alert.created_at.desc()
    ).limit(20).all()

    simulations = []

    # SimulationRun may not exist in every version of the project.
    try:
        simulations = SimulationRun.query.filter_by(
            facility_id=facility_id
        ).order_by(
            SimulationRun.created_at.desc()
        ).limit(20).all()
    except Exception:
        simulations = []

    latest_prediction = (
        predictions[0]
        if predictions
        else None
    )

    return {

        "generated_at":
            datetime.utcnow().isoformat(),

        "facility": {

            "id":
                facility.id,

            "name":
                facility.name,

            "facility_type":
                getattr(
                    facility,
                    "facility_type",
                    "Solar Energy Asset"
                ),

            "installed_capacity_kw":
                facility.installed_capacity_kw,

            "location":
                facility.location
        },

        "health": {

            "status":
                getattr(
                    latest_prediction,
                    "health_status",
                    "Unknown"
                )
                if latest_prediction
                else "Unknown",

            "health_score":
                getattr(
                    latest_prediction,
                    "health_score",
                    None
                )
                if latest_prediction
                else None,

            "failure_probability":
                getattr(
                    latest_prediction,
                    "failure_probability",
                    None
                )
                if latest_prediction
                else None,

            "rul":
                getattr(
                    latest_prediction,
                    "rul",
                    None
                )
                if latest_prediction
                else None
        },

        "predictions": [

            {
                "timestamp":
                    p.prediction_timestamp.isoformat()
                    if p.prediction_timestamp
                    else None,

                "health_status":
                    getattr(
                        p,
                        "health_status",
                        None
                    ),

                "health_score":
                    getattr(
                        p,
                        "health_score",
                        None
                    ),

                "failure_probability":
                    getattr(
                        p,
                        "failure_probability",
                        None
                    ),

                "rul":
                    getattr(
                        p,
                        "rul",
                        None
                    ),

                "inference_time_ms":
                    getattr(
                        p,
                        "inference_time_ms",
                        None
                    )
            }

            for p in predictions
        ],

        "alerts": [

            {
                "id":
                    a.id,

                "type":
                    a.alert_type,

                "message":
                    a.message,

                "severity":
                    a.severity,

                "status":
                    a.status,

                "created_at":
                    a.created_at.isoformat()
                    if a.created_at
                    else None
            }

            for a in alerts
        ],

        "simulations": [

            {
                "id":
                    s.id,

                "name":
                    getattr(
                        s,
                        "simulation_name",
                        "Simulation"
                    ),

                "status":
                    getattr(
                        s,
                        "status",
                        "Completed"
                    ),

                "created_at":
                    s.created_at.isoformat()
                    if getattr(
                        s,
                        "created_at",
                        None
                    )
                    else None
            }

            for s in simulations
        ]
    }


# ============================================================
# GENERATE REPORT
# ============================================================

@reports_bp.route(
    "/generate",
    methods=["POST"]
)
def generate_report():

    try:

        data = request.get_json(
            silent=True
        ) or {}

        facility_id = data.get(
            "facility_id",
            1
        )

        report_data = build_report_data(
            facility_id
        )

        if report_data is None:

            return jsonify({

                "success": False,

                "error":
                    "Facility not found."
            }), 404

        report = Report(

            user_id=None,

            facility_id=facility_id,

            title=
                "EcoTwin-AI Solar Asset Health Report",

            report_type=
                "Digital Twin Health Report",

            content=json.dumps(
                report_data,
                indent=2
            ),

            file_path=None

        )

        db.session.add(report)

        db.session.commit()

        return jsonify({

            "success": True,

            "message":
                "Report generated successfully.",

            "report": {

                "id":
                    report.id,

                "title":
                    report.title,

                "report_type":
                    report.report_type,

                "facility_id":
                    report.facility_id,

                "created_at":
                    report.created_at.isoformat()
                    if report.created_at
                    else None,

                "data":
                    report_data
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
# GET ALL REPORTS
# ============================================================

@reports_bp.route(
    "",
    methods=["GET"]
)
def get_reports():

    try:

        facility_id = request.args.get(
            "facility_id",
            type=int
        )

        query = Report.query

        if facility_id is not None:

            query = query.filter(
                Report.facility_id == facility_id
            )

        reports = query.order_by(
            Report.created_at.desc()
        ).limit(50).all()

        result = []

        for report in reports:

            result.append({

                "id":
                    report.id,

                "facility_id":
                    report.facility_id,

                "title":
                    report.title,

                "report_type":
                    report.report_type,

                "created_at":
                    report.created_at.isoformat()
                    if report.created_at
                    else None
            })

        return jsonify({

            "success": True,

            "count":
                len(result),

            "reports":
                result
        })

    except Exception as e:

        return jsonify({

            "success": False,

            "error":
                str(e)

        }), 500


# ============================================================
# GET SINGLE REPORT
# ============================================================

@reports_bp.route(
    "/<int:report_id>",
    methods=["GET"]
)
def get_report(report_id):

    try:

        report = Report.query.get(
            report_id
        )

        if not report:

            return jsonify({

                "success": False,

                "error":
                    "Report not found."

            }), 404

        try:

            content = json.loads(
                report.content
            )

        except Exception:

            content = report.content

        return jsonify({

            "success": True,

            "report": {

                "id":
                    report.id,

                "facility_id":
                    report.facility_id,

                "title":
                    report.title,

                "report_type":
                    report.report_type,

                "created_at":
                    report.created_at.isoformat()
                    if report.created_at
                    else None,

                "file_path":
                    report.file_path,

                "content":
                    content
            }
        })

    except Exception as e:

        return jsonify({

            "success": False,

            "error":
                str(e)

        }), 500


# ============================================================
# DOWNLOAD REPORT AS JSON
# ============================================================

@reports_bp.route(
    "/<int:report_id>/download",
    methods=["GET"]
)
def download_report(report_id):

    try:

        report = Report.query.get(
            report_id
        )

        if not report:

            return jsonify({

                "success": False,

                "error":
                    "Report not found."

            }), 404

        filename = (
            f"ecotwin_report_{report.id}.json"
        )

        response = make_response(
            report.content or "{}"
        )

        response.headers[
            "Content-Type"
        ] = "application/json"

        response.headers[
            "Content-Disposition"
        ] = (
            f'attachment; filename="{filename}"'
        )

        return response

    except Exception as e:

        return jsonify({

            "success": False,

            "error":
                str(e)

        }), 500