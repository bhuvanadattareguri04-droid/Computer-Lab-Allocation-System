
from flask import Flask


def create_app():

    app = Flask(__name__)

    from app.routes.allocation import allocation_bp

    app.register_blueprint(allocation_bp)

    @app.route("/")
    def home():
        return "Computer Lab Allocation System is Running!"

    return app
