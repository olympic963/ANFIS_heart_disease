import os

from flask import Flask, redirect, session, url_for

from webapp import AuthManager, PredictionManager, RuleManager


def create_app() -> Flask:
    app = Flask(__name__)
    app.secret_key = os.environ.get("ANFIS_WEB_SECRET", "dev-secret-change-me")

    auth_manager = AuthManager()
    prediction_manager = PredictionManager()
    rule_manager = RuleManager()
    auth_manager.init_user_table()
    auth_manager.register_routes(app)
    prediction_manager.register_routes(app, auth_manager.login_required, auth_manager.role_required)
    rule_manager.register_routes(app, auth_manager.login_required, auth_manager.role_required)

    @app.route("/")
    def index():
        if "user_id" not in session:
            return redirect(url_for("login"))
        if session.get("role") == "admin":
            return redirect(url_for("admin_rules"))
        return redirect(url_for("doctor_dashboard"))

    return app


app = create_app()


if __name__ == "__main__":
    app.run(debug=True)

