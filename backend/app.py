from flask import Flask, jsonify, render_template
from flask_cors import CORS
import os

# ============================================================
# ECO TWIN-AI APPLICATION
# ============================================================

app = Flask(
    __name__,
    template_folder="../frontend/templates",
    static_folder="../frontend/static"
)

CORS(app)

# ============================================================
# PROJECT PATHS
# ============================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE_DIR)

DATABASE_PATH = os.path.join(
    BASE_DIR,
    "ecotwin.db"
)

# ============================================================
# ML MODEL PATHS
# ============================================================

MODEL_DIR = os.path.join(
    BASE_DIR,
    "models"
)

MODEL_PATH = os.path.join(
    MODEL_DIR,
    "ecotwin_health_model.keras"
)

TFLITE_MODEL_PATH = os.path.join(
    MODEL_DIR,
    "ecotwin_health_model.tflite"
)

INT8_MODEL_PATH = os.path.join(
    MODEL_DIR,
    "ecotwin_health_model_int8.tflite"
)

SCALER_PATH = os.path.join(
    MODEL_DIR,
    "ecotwin_scaler.pkl"
)

MODEL_METADATA_PATH = os.path.join(
    MODEL_DIR,
    "model_metadata.json"
)

# ============================================================
# DATABASE
# ============================================================

app.config["SQLALCHEMY_DATABASE_URI"] = (
    "sqlite:///" + DATABASE_PATH
)

app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = None

try:
    from backend.models.models import db

    db.init_app(app)

    print("Database models imported successfully.")

except Exception as e:

    print("ERROR: Could not initialize database.")
    print(e)

    db = None


# ============================================================
# DATABASE INITIALIZATION
# ============================================================

if db is not None:

    try:

        with app.app_context():
            db.create_all()

        print("Database initialized successfully.")

    except Exception as e:

        print("Warning: Database initialization failed:")
        print(e)


# ============================================================
# ML MODEL
# ============================================================

ml_model = None


def load_ml_model():

    global ml_model

    print()
    print("=" * 60)
    print("Loading EcoTwin-AI ML Model")
    print("=" * 60)

    print("Keras model path:")
    print(MODEL_PATH)

    print("Scaler path:")
    print(SCALER_PATH)

    if not os.path.exists(MODEL_PATH):

        print("WARNING: Keras model file not found.")

        ml_model = None

    else:

        try:

            from tensorflow import keras

            print("Loading Keras model...")

            ml_model = keras.models.load_model(
                MODEL_PATH,
                compile=False
            )

            print("ML model loaded successfully.")

        except Exception as e:

            print("WARNING: Could not load Keras model.")
            print(e)

            ml_model = None

    print(
        "Scaler available:",
        os.path.exists(SCALER_PATH)
    )

    print(
        "TFLite model available:",
        os.path.exists(TFLITE_MODEL_PATH)
    )

    print(
        "INT8 TFLite model available:",
        os.path.exists(INT8_MODEL_PATH)
    )

    print(
        "Model metadata available:",
        os.path.exists(MODEL_METADATA_PATH)
    )


load_ml_model()


# ============================================================
# ROUTE REGISTRATION
# ============================================================

def register_blueprint_safely(
    import_path,
    blueprint_name,
    display_name
):

    try:

        module = __import__(
            import_path,
            fromlist=[blueprint_name]
        )

        blueprint = getattr(
            module,
            blueprint_name
        )

        app.register_blueprint(
            blueprint
        )

        print(
            f"{display_name} routes registered successfully."
        )

        return True

    except ImportError as e:

        print(
            f"{display_name} routes not available:"
        )

        print(e)

        return False

    except Exception as e:

        print(
            f"WARNING: {display_name} routes failed:"
        )

        print(e)

        return False


# ============================================================
# TELEMETRY
# ============================================================

register_blueprint_safely(
    "backend.routes.telemetry",
    "telemetry_bp",
    "Telemetry"
)


# ============================================================
# PREDICTION
# ============================================================

register_blueprint_safely(
    "backend.routes.prediction",
    "prediction_bp",
    "Prediction"
)


# ============================================================
# DIGITAL TWIN
# ============================================================

register_blueprint_safely(
    "backend.routes.digital_twin",
    "digital_twin_bp",
    "Digital Twin"
)


# ============================================================
# ALERTS
# ============================================================

register_blueprint_safely(
    "backend.routes.alerts",
    "alerts_bp",
    "Alert"
)


# ============================================================
# REPORTS
# ============================================================

register_blueprint_safely(
    "backend.routes.reports",
    "reports_bp",
    "Report"
)


# ============================================================
# DASHBOARD
#
# IMPORTANT:
# We intentionally do NOT register the old dashboard blueprint.
# The dashboard is served directly here so there is no conflict
# between multiple /dashboard routes.
# ============================================================

@app.route(
    "/dashboard",
    methods=["GET"]
)
def dashboard():

    return render_template(
        "dashboard.html"
    )


# ============================================================
# HOME
# ============================================================

@app.route(
    "/",
    methods=["GET"]
)
def home():

    return render_template(
        "dashboard.html"
    )


# ============================================================
# HEALTH CHECK
# ============================================================

@app.route(
    "/api/health",
    methods=["GET"]
)
def health():

    return jsonify({
        "success": True,
        "service": "EcoTwin-AI API",
        "status": "healthy"
    })


# ============================================================
# MODEL STATUS
# ============================================================

@app.route(
    "/api/model-status",
    methods=["GET"]
)
def model_status():

    model_exists = os.path.exists(
        MODEL_PATH
    )

    scaler_exists = os.path.exists(
        SCALER_PATH
    )

    tflite_exists = os.path.exists(
        TFLITE_MODEL_PATH
    )

    int8_exists = os.path.exists(
        INT8_MODEL_PATH
    )

    metadata_exists = os.path.exists(
        MODEL_METADATA_PATH
    )

    return jsonify({

        "success": True,

        "model": {

            "available":
                ml_model is not None,

            "file_exists":
                model_exists,

            "path":
                MODEL_PATH,

            "size_bytes":
                (
                    os.path.getsize(MODEL_PATH)
                    if model_exists
                    else 0
                ),

            "format":
                "Keras",

            "scaler_available":
                scaler_exists,

            "scaler_path":
                SCALER_PATH,

            "tflite_available":
                tflite_exists,

            "tflite_path":
                TFLITE_MODEL_PATH,

            "int8_available":
                int8_exists,

            "int8_path":
                INT8_MODEL_PATH,

            "metadata_available":
                metadata_exists,

            "metadata_path":
                MODEL_METADATA_PATH
        }

    })


# ============================================================
# API INFORMATION
# ============================================================

@app.route(
    "/api",
    methods=["GET"]
)
def api_information():

    return jsonify({

        "success": True,

        "service":
            "EcoTwin-AI",

        "system":
            "Explainable TinyML-Based Digital Twin "
            "for Sustainable Energy Assets",

        "telemetry_parameters": [

            "temperature",
            "voltage",
            "current",
            "light_intensity",
            "vibration"

        ],

        "derived_parameter":
            "power",

        "modules": [

            "Telemetry Monitoring",
            "TinyML Prediction",
            "Explainable AI",
            "Digital Twin",
            "Maintenance Recommendation",
            "Alerts and Events",
            "Historical Replay",
            "Reports",
            "Dashboard"

        ]

    })


# ============================================================
# ERROR HANDLERS
# ============================================================

@app.errorhandler(404)
def not_found(error):

    return jsonify({

        "success": False,
        "error": "Endpoint not found."

    }), 404


@app.errorhandler(500)
def internal_error(error):

    return jsonify({

        "success": False,
        "error": "Internal server error."

    }), 500


# ============================================================
# STARTUP INFORMATION
# ============================================================

def print_application_information():

    print()
    print("=" * 60)
    print("EcoTwin-AI Backend")
    print("=" * 60)

    print(
        "Project root:",
        PROJECT_ROOT
    )

    print(
        "Database:",
        DATABASE_PATH
    )

    print(
        "Database exists:",
        os.path.exists(DATABASE_PATH)
    )

    print(
        "ML model available:",
        ml_model is not None
    )

    print(
        "ML model:",
        MODEL_PATH
    )

    print()
    print("Dashboard:")
    print(
        "http://127.0.0.1:5000/dashboard"
    )

    print()
    print("Core APIs:")
    print("GET  /api/health")
    print("GET  /api/model-status")

    print()
    print("Telemetry:")
    print("POST /api/telemetry/")
    print("GET  /api/telemetry/latest")

    print()
    print("Prediction:")
    print("POST /api/predict")

    print()
    print("Digital Twin:")
    print("GET  /api/digital-twin")
    print("POST /api/digital-twin/synchronize")
    print("POST /api/digital-twin/simulate")
    print("GET  /api/digital-twin/history")

    print()
    print("Alerts:")
    print("GET  /api/alerts")
    print("POST /api/alerts/generate")

    print()
    print("=" * 60)

# ============================================================
# ALERT ROUTES
# ============================================================

try:

    from backend.routes.alerts import alerts_bp

    app.register_blueprint(
        alerts_bp
    )

    print(
        "Alert routes registered successfully."
    )

except Exception as e:

    print(
        "Alert routes not available:"
    )

    print(e)


# ============================================================
# REPORT ROUTES
# ============================================================

try:

    from backend.routes.reports import reports_bp

    app.register_blueprint(
        reports_bp
    )

    print(
        "Report routes registered successfully."
    )

except Exception as e:

    print(
        "Report routes not available:"
    )

    print(e)
# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":

    print_application_information()

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True
    )