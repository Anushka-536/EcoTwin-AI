from backend.models.models import db


# ============================================================
# INITIALIZE DATABASE
# ============================================================

def initialize_database(app):

    db.init_app(app)

    with app.app_context():

        db.create_all()

        print("Database initialized successfully.")
        print("Database tables verified.")


# ============================================================
# DATABASE RESET
# ============================================================

def reset_database(app):

    with app.app_context():

        db.drop_all()
        db.create_all()

        print("Database reset successfully.")