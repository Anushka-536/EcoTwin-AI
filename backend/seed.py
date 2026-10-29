from datetime import datetime

from werkzeug.security import generate_password_hash

from backend.app import app
from backend.models.models import (
    db,
    User,
    Facility
)


# ============================================================
# SEED DATABASE
# ============================================================

def seed_database():

    with app.app_context():

        # ----------------------------------------------------
        # USERS
        # ----------------------------------------------------

        admin = User.query.filter_by(
            username="admin"
        ).first()

        if admin is None:

            admin = User(

                username="admin",

                email="admin@ecotwin.ai",

                password_hash=generate_password_hash(
                    "admin123"
                ),

                role="Admin",

                registration_date=datetime.utcnow()

            )

            db.session.add(
                admin
            )

        # ----------------------------------------------------

        operator = User.query.filter_by(
            username="operator"
        ).first()

        if operator is None:

            operator = User(

                username="operator",

                email="operator@ecotwin.ai",

                password_hash=generate_password_hash(
                    "operator123"
                ),

                role="Operator",

                registration_date=datetime.utcnow()

            )

            db.session.add(
                operator
            )

        # ----------------------------------------------------

        viewer = User.query.filter_by(
            username="viewer"
        ).first()

        if viewer is None:

            viewer = User(

                username="viewer",

                email="viewer@ecotwin.ai",

                password_hash=generate_password_hash(
                    "viewer123"
                ),

                role="Viewer",

                registration_date=datetime.utcnow()

            )

            db.session.add(
                viewer
            )

        # ----------------------------------------------------
        # FACILITY
        # ----------------------------------------------------

        facility = Facility.query.first()

        if facility is None:

            facility = Facility(

                name=(
                    "EcoTwin-AI "
                    "Solar Energy Facility"
                ),

                facility_type=(
                    "Solar Energy Asset"
                ),

                installed_capacity_kw=100.0,

                location=(
                    "EcoTwin-AI Demonstration Facility"
                )

            )

            db.session.add(
                facility
            )

        # ----------------------------------------------------
        # SAVE
        # ----------------------------------------------------

        db.session.commit()

        print()
        print("=" * 60)
        print("EcoTwin-AI Database Seeded")
        print("=" * 60)

        print(
            "Users created: "
            "Admin / Operator / Viewer"
        )

        print(
            "Facility created: "
            "EcoTwin-AI Solar Energy Facility"
        )

        print("=" * 60)


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":

    seed_database()