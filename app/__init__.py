from flask import Flask, redirect, url_for
from app.database import init_db
from app.routes.dashboard import dashboard_bp
from app.routes.workstation import workstation_bp
from app.routes.allocation import allocation_bp
from app.routes.waiting_queue import waiting_queue_bp
from app.routes.student import student_bp
from app.routes.semaphore import semaphore_bp
from app.routes.history import history_bp
from app.routes.analytics import analytics_bp


def create_app():
    app = Flask(__name__)

    # Initialize SQLite database and tables
    init_db()

    # Register all modular blueprints
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(workstation_bp)
    app.register_blueprint(allocation_bp)
    app.register_blueprint(waiting_queue_bp)
    app.register_blueprint(student_bp)
    app.register_blueprint(semaphore_bp)
    app.register_blueprint(history_bp)
    app.register_blueprint(analytics_bp)

    @app.route("/")
    def home():
        # Redirect root URL directly to Dashboard
        return redirect("/dashboard")

    return app
