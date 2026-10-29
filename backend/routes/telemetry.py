from flask import Blueprint, jsonify, request

from datetime import datetime

from backend.models.models import (
    db,
    Sensor,
    SensorReading
)

from backend.services.telemetry_importer import (
    TelemetryImporter
)


# ============================================================
# TELEMETRY BLUEPRINT
# ============================================================

telemetry_bp = Blueprint(
    "telemetry",
    __name__,
    url_prefix="/api/telemetry"
)


# ============================================================
# SOLAR TELEMETRY UNITS
# ============================================================

UNITS = {

    "ambient_temperature": "°C",

    "module_temperature": "°C",

    "voltage": "V",

    "current": "A",

    "power": "W",

    "irradiance": "W/m²",

    "vibration": "mm/s"
}


# ============================================================
# TELEMETRY PARAMETERS
# ============================================================

REQUIRED_PARAMETERS = [

    "ambient_temperature",

    "module_temperature",

    "voltage",

    "current",

    "power",

    "irradiance"
]


OPTIONAL_PARAMETERS = [

    "vibration"
]


# ============================================================
# CREATE / GET SENSOR
# ============================================================

def get_or_create_sensor(
    facility_id,
    parameter,
    device_prefix="TELEMETRY"
):

    sensor = Sensor.query.filter_by(

        facility_id=facility_id,

        sensor_type=parameter

    ).first()

    if sensor is not None:

        return sensor

    sensor = Sensor(

        device_id=(
            f"{device_prefix}-"
            f"{facility_id}-"
            f"{parameter.upper()}"
        ),

        sensor_type=parameter,

        unit=UNITS[
            parameter
        ],

        facility_id=facility_id,

        status="Active"

    )

    db.session.add(
        sensor
    )

    db.session.flush()

    return sensor


# ============================================================
# MANUAL SOLAR TELEMETRY
# ============================================================

@telemetry_bp.route(
    "/",
    methods=["POST"]
)
def store_telemetry():

    data = request.get_json(
        silent=True
    )

    if not data:

        return jsonify({

            "success": False,

            "error": (
                "JSON request body is required."
            )

        }), 400


    # --------------------------------------------------------
    # Facility
    # --------------------------------------------------------

    facility_id = data.get(
        "facility_id",
        1
    )

    try:

        facility_id = int(
            facility_id
        )

    except (
        TypeError,
        ValueError
    ):

        return jsonify({

            "success": False,

            "error": (
                "facility_id must be an integer."
            )

        }), 400


    # --------------------------------------------------------
    # Validate required solar parameters
    # --------------------------------------------------------

    for parameter in REQUIRED_PARAMETERS:

        if parameter not in data:

            return jsonify({

                "success": False,

                "error": (
                    f"Missing required field: "
                    f"{parameter}"
                )

            }), 400


    # --------------------------------------------------------
    # Convert values
    # --------------------------------------------------------

    telemetry = {}

    try:

        for parameter in REQUIRED_PARAMETERS:

            telemetry[
                parameter
            ] = float(
                data[
                    parameter
                ]
            )

        if "vibration" in data:

            telemetry[
                "vibration"
            ] = float(
                data["vibration"]
            )

    except (
        TypeError,
        ValueError
    ):

        return jsonify({

            "success": False,

            "error": (
                "Telemetry values must be numeric."
            )

        }), 400


    timestamp = datetime.utcnow()

    readings = []


    # --------------------------------------------------------
    # Store readings
    # --------------------------------------------------------

    for parameter, value in telemetry.items():

        sensor = get_or_create_sensor(

            facility_id,

            parameter,

            device_prefix="MANUAL"

        )

        reading = SensorReading(

            sensor_id=sensor.id,

            value=value,

            timestamp=timestamp

        )

        db.session.add(
            reading
        )

        readings.append({

            "parameter": parameter,

            "sensor_id": sensor.id,

            "value": value,

            "unit": UNITS[
                parameter
            ],

            "timestamp": (
                timestamp.isoformat()
            )

        })


    db.session.commit()


    # --------------------------------------------------------
    # Return response
    # --------------------------------------------------------

    return jsonify({

        "success": True,

        "message": (
            "Solar telemetry stored successfully."
        ),

        "facility_id": facility_id,

        "timestamp": (
            timestamp.isoformat()
        ),

        "telemetry": telemetry,

        "readings": readings

    })


# ============================================================
# LATEST SOLAR TELEMETRY
# ============================================================

@telemetry_bp.route(
    "/latest",
    methods=["GET"]
)
def latest_telemetry():

    facility_id = request.args.get(

        "facility_id",

        default=1,

        type=int

    )

    telemetry = {}


    # --------------------------------------------------------
    # Retrieve latest reading for every parameter
    # --------------------------------------------------------

    for parameter in UNITS:

        sensor = Sensor.query.filter_by(

            facility_id=facility_id,

            sensor_type=parameter

        ).first()


        if sensor is None:

            continue


        reading = (

            SensorReading.query

            .filter_by(
                sensor_id=sensor.id
            )

            .order_by(
                SensorReading.timestamp.desc()
            )

            .first()

        )


        if reading is None:

            continue


        telemetry[
            parameter
        ] = {

            "value": reading.value,

            "unit": sensor.unit,

            "timestamp": (
                reading.timestamp.isoformat()
            )

        }


    # --------------------------------------------------------
    # Return actual stored POWER
    # --------------------------------------------------------
    #
    # IMPORTANT:
    # POWER is imported directly from the solar dataset.
    #
    # We do NOT replace it with voltage * current.
    #
    # This preserves the external dataset exactly.
    # --------------------------------------------------------

    return jsonify({

        "success": True,

        "facility_id": facility_id,

        "telemetry": telemetry

    })


# ============================================================
# EXTERNAL CSV IMPORT
# ============================================================

@telemetry_bp.route(
    "/import",
    methods=["POST"]
)
def import_external_telemetry():

    data = request.get_json(
        silent=True
    )

    if not data:

        return jsonify({

            "success": False,

            "error": (
                "JSON request body is required."
            )

        }), 400


    # --------------------------------------------------------
    # Facility
    # --------------------------------------------------------

    facility_id = data.get(
        "facility_id",
        1
    )

    try:

        facility_id = int(
            facility_id
        )

    except (
        TypeError,
        ValueError
    ):

        return jsonify({

            "success": False,

            "error": (
                "facility_id must be an integer."
            )

        }), 400


    # --------------------------------------------------------
    # Maximum rows
    # --------------------------------------------------------

    max_rows = data.get(
        "max_rows",
        500
    )

    try:

        max_rows = int(
            max_rows
        )

    except (
        TypeError,
        ValueError
    ):

        max_rows = 500


    if max_rows < 1:

        max_rows = 1


    if max_rows > 5000:

        max_rows = 5000


    # --------------------------------------------------------
    # Import from URL
    # --------------------------------------------------------

    url = data.get(
        "url"
    )

    if url:

        try:

            dataframe = (
                TelemetryImporter
                .download_csv(
                    url
                )
            )

            result = (
                TelemetryImporter
                .import_dataframe(

                    dataframe,

                    facility_id=facility_id,

                    max_rows=max_rows

                )
            )

            return jsonify(
                result
            )

        except Exception as e:

            db.session.rollback()

            return jsonify({

                "success": False,

                "error": (
                    "External CSV import failed: "
                    f"{str(e)}"
                )

            }), 500


    # --------------------------------------------------------
    # Import local CSV
    # --------------------------------------------------------

    path = data.get(
        "path"
    )

    if path:

        try:

            dataframe = (
                TelemetryImporter
                .read_local_csv(
                    path
                )
            )

            result = (
                TelemetryImporter
                .import_dataframe(

                    dataframe,

                    facility_id=facility_id,

                    max_rows=max_rows

                )
            )

            return jsonify(
                result
            )

        except Exception as e:

            db.session.rollback()

            return jsonify({

                "success": False,

                "error": (
                    "Local CSV import failed: "
                    f"{str(e)}"
                )

            }), 500


    # --------------------------------------------------------
    # No source supplied
    # --------------------------------------------------------

    return jsonify({

        "success": False,

        "error": (
            "Provide either 'url' or 'path'."
        )

    }), 400


# ============================================================
# IMPORT PREVIEW
# ============================================================

@telemetry_bp.route(
    "/import/preview",
    methods=["POST"]
)
def preview_external_telemetry():

    data = request.get_json(
        silent=True
    )

    if not data:

        return jsonify({

            "success": False,

            "error": (
                "JSON request body is required."
            )

        }), 400


    url = data.get(
        "url"
    )

    path = data.get(
        "path"
    )


    try:

        # ----------------------------------------------------
        # Read URL
        # ----------------------------------------------------

        if url:

            dataframe = (
                TelemetryImporter
                .download_csv(
                    url
                )
            )


        # ----------------------------------------------------
        # Read local file
        # ----------------------------------------------------

        elif path:

            dataframe = (
                TelemetryImporter
                .read_local_csv(
                    path
                )
            )


        else:

            return jsonify({

                "success": False,

                "error": (
                    "Provide either "
                    "'url' or 'path'."
                )

            }), 400


        # ----------------------------------------------------
        # Column mapping
        # ----------------------------------------------------

        mapping = (
            TelemetryImporter
            .map_columns(
                dataframe
            )
        )


        # ----------------------------------------------------
        # Validation
        # ----------------------------------------------------

        validation = (
            TelemetryImporter
            .validate_dataset(

                dataframe,

                mapping

            )
        )


        # ----------------------------------------------------
        # Preview
        # ----------------------------------------------------

        preview = (

            dataframe
            .head(5)
            .fillna("")
            .to_dict(
                orient="records"
            )

        )


        return jsonify({

            "success": True,

            "rows": len(
                dataframe
            ),

            "columns": [

                str(column)

                for column in
                dataframe.columns

            ],

            "column_mapping": mapping,

            "validation": validation,

            "preview": preview

        })


    except Exception as e:

        return jsonify({

            "success": False,

            "error": (
                "Preview failed: "
                f"{str(e)}"
            )

        }), 500

    # ============================================================
# ESP32 LIVE READING (kept in memory, not in the database)
# ============================================================

esp32_latest = {
    "ambient_temperature": None,
    "humidity": None,
    "timestamp": None
}


@telemetry_bp.route(
    "/esp32",
    methods=["POST"]
)
def store_esp32_reading():

    data = request.get_json(silent=True) or {}

    try:
        esp32_latest["ambient_temperature"] = float(
            data["ambient_temperature"]
        )

        if "humidity" in data:
            esp32_latest["humidity"] = float(data["humidity"])

    except (KeyError, TypeError, ValueError):

        return jsonify({
            "success": False,
            "error": "ambient_temperature (numeric) is required."
        }), 400

    esp32_latest["timestamp"] = datetime.utcnow().isoformat()

    return jsonify({
        "success": True,
        "esp32": esp32_latest
    })


@telemetry_bp.route(
    "/esp32",
    methods=["GET"]
)
def get_esp32_reading():

    return jsonify({
        "success": True,
        "esp32": esp32_latest
    })