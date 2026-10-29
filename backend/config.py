import os


# ============================================================
# PROJECT PATHS
# ============================================================

BASE_DIR = os.path.abspath(
    os.path.dirname(__file__)
)

DATABASE_PATH = os.path.join(
    BASE_DIR,
    "ecotwin.db"
)


# ============================================================
# FLASK CONFIGURATION
# ============================================================

class Config:

    SECRET_KEY = os.environ.get(
        "SECRET_KEY",
        "ecotwin-ai-development-key"
    )

    SQLALCHEMY_DATABASE_URI = (
        "sqlite:///"
        + DATABASE_PATH
    )

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    JSON_SORT_KEYS = False