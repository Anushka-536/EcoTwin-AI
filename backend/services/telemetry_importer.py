import io
import requests
import pandas as pd

from datetime import datetime

from backend.models.models import (
    db,
    Sensor,
    SensorReading
)


# ============================================================
# ECO TWIN-AI SOLAR TELEMETRY IMPORTER
# ============================================================
#
# This importer is designed for the solar telemetry dataset
# used by EcoTwin-AI.
#
# Supported solar parameters:
#
#   AMBIENT_TEMP       -> ambient_temperature
#   MODULE_TEMP        -> module_temperature
#   VOLTAGE            -> voltage
#   CURRENT            -> current
#   POWER              -> power
#   IR                 -> irradiance
#
# Vibration is optional and is NOT artificially generated.
#
# ============================================================


class TelemetryImporter:

    # ========================================================
    # REQUIRED SOLAR TELEMETRY PARAMETERS
    # ========================================================

    REQUIRED_PARAMETERS = [
        "ambient_temperature",
        "module_temperature",
        "voltage",
        "current",
        "power",
        "irradiance"
    ]

    # ========================================================
    # OPTIONAL TELEMETRY PARAMETERS
    # ========================================================

    OPTIONAL_PARAMETERS = [
        "vibration"
    ]

    # ========================================================
    # EXTERNAL DATASET COLUMN ALIASES
    # ========================================================

    COLUMN_ALIASES = {

        # ----------------------------------------------------
        # Ambient temperature
        # ----------------------------------------------------

        "ambient_temperature": [
            "ambient_temp",
            "ambient temperature",
            "ambient_temperature",
            "ambient",
            "air_temperature",
            "air temperature",
            "air_temp"
        ],

        # ----------------------------------------------------
        # Module / panel temperature
        # ----------------------------------------------------

        "module_temperature": [
            "module_temp",
            "module temperature",
            "module_temperature",
            "panel_temp",
            "panel temperature",
            "panel_temperature",
            "cell_temp",
            "cell temperature"
        ],

        # ----------------------------------------------------
        # Voltage
        # ----------------------------------------------------

        "voltage": [
            "voltage",
            "volt",
            "v"
        ],

        # ----------------------------------------------------
        # Current
        # ----------------------------------------------------

        "current": [
            "current",
            "ampere",
            "amps",
            "amp",
            "i"
        ],

        # ----------------------------------------------------
        # Generated power
        # ----------------------------------------------------

        "power": [
            "power",
            "generated power",
            "generated_power",
            "output power",
            "output_power",
            "ac power",
            "ac_power",
            "dc power",
            "dc_power"
        ],

        # ----------------------------------------------------
        # Solar irradiance
        # ----------------------------------------------------

        "irradiance": [
            "irradiance",
            "ir",
            "solar irradiance",
            "solar_irradiance",
            "irradiation",
            "ghi",
            "global horizontal irradiance"
        ],

        # ----------------------------------------------------
        # Optional vibration
        # ----------------------------------------------------

        "vibration": [
            "vibration",
            "vibration level",
            "vibration_level"
        ],

        # ----------------------------------------------------
        # Timestamp
        # ----------------------------------------------------

        "timestamp": [
            "timestamp",
            "datetime",
            "date time",
            "date_time",
            "time",
            "date"
        ],

        # ----------------------------------------------------
        # Record identifier
        # ----------------------------------------------------

        "record_id": [
            "sr_no",
            "sr no",
            "serial number",
            "serial_number",
            "record_id",
            "id"
        ]
    }

    # ========================================================
    # SENSOR UNITS
    # ========================================================

    SENSOR_UNITS = {

        "ambient_temperature": "°C",

        "module_temperature": "°C",

        "voltage": "V",

        "current": "A",

        "power": "W",

        "irradiance": "W/m²",

        "vibration": "mm/s"
    }

    # ========================================================
    # SENSOR DISPLAY NAMES
    # ========================================================

    SENSOR_NAMES = {

        "ambient_temperature": "Ambient Temperature",

        "module_temperature": "Module Temperature",

        "voltage": "Voltage",

        "current": "Current",

        "power": "Power",

        "irradiance": "Irradiance",

        "vibration": "Vibration"
    }

    # ========================================================
    # NORMALIZE COLUMN NAME
    # ========================================================

    @staticmethod
    def normalize_column_name(name):

        return (
            str(name)
            .strip()
            .lower()
            .replace("-", " ")
            .replace("_", " ")
        )

    # ========================================================
    # FIND COLUMN
    # ========================================================

    @classmethod
    def find_column(
        cls,
        dataframe,
        parameter
    ):

        aliases = cls.COLUMN_ALIASES.get(
            parameter,
            []
        )

        normalized_columns = {}

        for column in dataframe.columns:

            normalized = (
                cls.normalize_column_name(
                    column
                )
            )

            normalized_columns[
                normalized
            ] = column

        for alias in aliases:

            alias_normalized = (
                cls.normalize_column_name(
                    alias
                )
            )

            if (
                alias_normalized
                in normalized_columns
            ):

                return normalized_columns[
                    alias_normalized
                ]

        return None

    # ========================================================
    # MAP DATASET COLUMNS
    # ========================================================

    @classmethod
    def map_columns(
        cls,
        dataframe
    ):

        mapping = {}

        parameters = (
            cls.REQUIRED_PARAMETERS
            + cls.OPTIONAL_PARAMETERS
            + [
                "timestamp",
                "record_id"
            ]
        )

        for parameter in parameters:

            column = cls.find_column(
                dataframe,
                parameter
            )

            if column is not None:

                mapping[
                    parameter
                ] = column

        return mapping

    # ========================================================
    # DOWNLOAD CSV FROM URL
    # ========================================================

    @staticmethod
    def download_csv(url):

        response = requests.get(
            url,
            timeout=60
        )

        response.raise_for_status()

        return pd.read_csv(
            io.BytesIO(
                response.content
            )
        )

    # ========================================================
    # READ LOCAL CSV
    # ========================================================

    @staticmethod
    def read_local_csv(path):

        return pd.read_csv(
            path
        )

    # ========================================================
    # VALIDATE DATASET
    # ========================================================

    @classmethod
    def validate_dataset(
        cls,
        dataframe,
        mapping
    ):

        # ----------------------------------------------------
        # Check required parameters
        # ----------------------------------------------------

        missing = []

        for parameter in (
            cls.REQUIRED_PARAMETERS
        ):

            if parameter not in mapping:

                missing.append(
                    parameter
                )

        if missing:

            return {

                "valid": False,

                "error": (
                    "Missing required solar "
                    "telemetry parameters: "
                    + ", ".join(
                        missing
                    )
                )

            }

        # ----------------------------------------------------
        # Check empty dataset
        # ----------------------------------------------------

        if dataframe.empty:

            return {

                "valid": False,

                "error": (
                    "The external dataset "
                    "contains no records."
                )

            }

        # ----------------------------------------------------
        # Dataset is valid
        # ----------------------------------------------------

        return {

            "valid": True,

            "error": None

        }

    # ========================================================
    # GET OR CREATE SENSOR
    # ========================================================

    @classmethod
    def get_or_create_sensor(
        cls,
        facility_id,
        parameter
    ):

        sensor = Sensor.query.filter_by(
            facility_id=facility_id,
            sensor_type=parameter
        ).first()

        if sensor:

            return sensor

        sensor = Sensor(

            device_id=(
                f"EXT-{facility_id}-"
                f"{parameter.upper()}"
            ),

            sensor_type=parameter,

            unit=cls.SENSOR_UNITS.get(
                parameter,
                ""
            ),

            facility_id=facility_id,

            status="Active"

        )

        db.session.add(
            sensor
        )

        db.session.flush()

        return sensor

    # ========================================================
    # IMPORT DATAFRAME
    # ========================================================

    @classmethod
    def import_dataframe(
        cls,
        dataframe,
        facility_id=1,
        max_rows=500
    ):

        # ----------------------------------------------------
        # Map columns
        # ----------------------------------------------------

        mapping = cls.map_columns(
            dataframe
        )

        # ----------------------------------------------------
        # Validate dataset
        # ----------------------------------------------------

        validation = cls.validate_dataset(
            dataframe,
            mapping
        )

        if not validation["valid"]:

            return {

                "success": False,

                "error": validation[
                    "error"
                ],

                "column_mapping": mapping

            }

        # ----------------------------------------------------
        # Limit rows
        # ----------------------------------------------------

        dataframe = (
            dataframe
            .head(max_rows)
            .copy()
        )

        # ----------------------------------------------------
        # Timestamp
        # ----------------------------------------------------

        if "timestamp" in mapping:

            timestamps = pd.to_datetime(

                dataframe[
                    mapping["timestamp"]
                ],

                errors="coerce"

            )

        else:

            timestamps = pd.Series(

                [
                    datetime.utcnow()
                    for _ in range(
                        len(dataframe)
                    )
                ],

                index=dataframe.index

            )

        # ----------------------------------------------------
        # Create sensors
        # ----------------------------------------------------

        sensors = {}

        all_parameters = (
            cls.REQUIRED_PARAMETERS
            + cls.OPTIONAL_PARAMETERS
        )

        for parameter in all_parameters:

            if parameter in mapping:

                sensors[
                    parameter
                ] = cls.get_or_create_sensor(

                    facility_id,

                    parameter

                )

        # ----------------------------------------------------
        # Counters
        # ----------------------------------------------------

        imported_rows = 0

        skipped_rows = 0

        reading_counts = {}

        # ====================================================
        # PROCESS ROWS
        # ====================================================

        for index, row in dataframe.iterrows():

            # ------------------------------------------------
            # Timestamp
            # ------------------------------------------------

            timestamp = timestamps.loc[
                index
            ]

            if pd.isna(timestamp):

                timestamp = datetime.utcnow()

            elif hasattr(
                timestamp,
                "to_pydatetime"
            ):

                timestamp = (
                    timestamp.to_pydatetime()
                )

            # ------------------------------------------------
            # Extract telemetry values
            # ------------------------------------------------

            values = {}

            row_valid = True

            for parameter in all_parameters:

                if parameter not in mapping:

                    continue

                raw_value = row[
                    mapping[parameter]
                ]

                value = pd.to_numeric(
                    raw_value,
                    errors="coerce"
                )

                # ------------------------------------------------
                # Required parameter missing/invalid
                # ------------------------------------------------

                if pd.isna(value):

                    if parameter in (
                        cls.REQUIRED_PARAMETERS
                    ):

                        row_valid = False

                        break

                    # Optional parameter
                    # can be absent.

                    continue

                values[
                    parameter
                ] = float(value)

            # ------------------------------------------------
            # Skip invalid row
            # ------------------------------------------------

            if not row_valid:

                skipped_rows += 1

                continue

            # ------------------------------------------------
            # Store sensor readings
            # ------------------------------------------------

            for parameter, value in (
                values.items()
            ):

                reading = SensorReading(

                    sensor_id=(
                        sensors[
                            parameter
                        ].id
                    ),

                    value=value,

                    timestamp=timestamp

                )

                db.session.add(
                    reading
                )

                reading_counts[
                    parameter
                ] = (
                    reading_counts.get(
                        parameter,
                        0
                    ) + 1
                )

            imported_rows += 1

        # ----------------------------------------------------
        # Commit
        # ----------------------------------------------------

        db.session.commit()

        # ----------------------------------------------------
        # Return result
        # ----------------------------------------------------

        return {

            "success": True,

            "facility_id": facility_id,

            "rows_processed": len(
                dataframe
            ),

            "rows_imported": imported_rows,

            "rows_skipped": skipped_rows,

            "parameters_imported": (
                reading_counts
            ),

            "column_mapping": mapping,

            "vibration_available": (
                "vibration" in mapping
            )

        }


# ============================================================
# IMPORT EXTERNAL CSV
# ============================================================

def import_external_csv(
    url,
    facility_id=1,
    max_rows=500
):

    dataframe = (
        TelemetryImporter.download_csv(
            url
        )
    )

    return (
        TelemetryImporter.import_dataframe(
            dataframe,
            facility_id=facility_id,
            max_rows=max_rows
        )
    )


# ============================================================
# IMPORT LOCAL CSV
# ============================================================

def import_local_csv(
    path,
    facility_id=1,
    max_rows=500
):

    dataframe = (
        TelemetryImporter.read_local_csv(
            path
        )
    )

    return (
        TelemetryImporter.import_dataframe(
            dataframe,
            facility_id=facility_id,
            max_rows=max_rows
        )
    )