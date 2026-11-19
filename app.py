"""Quiz Master / Online Examination System Flask entry point."""
import os
from datetime import timedelta
from flask import Flask
from database import db


def create_app(test_config=None):
    app = Flask(__name__, template_folder=".", static_folder="static")
    app.config.update(
        SECRET_KEY=os.environ.get("SECRET_KEY", "development-only-change-me"),
        SQLALCHEMY_DATABASE_URI="sqlite:///" + os.path.join(os.path.abspath(os.path.dirname(__file__)), "quizmaster.db"),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        PERMANENT_SESSION_LIFETIME=timedelta(hours=8),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
    )
    if test_config:
        app.config.update(test_config)
    db.init_app(app)
    with app.app_context():
        from models import user, admin_table, subject, chapter, quiz, questions, scores, exam_attempt, answer_record
        db.create_all()
        # Upgrade the legacy score table in-place; old quiz data remains available.
        from sqlalchemy import inspect, text
        columns = {c["name"] for c in inspect(db.engine).get_columns("scores")}
        if "completed_at" not in columns:
            db.session.execute(text("ALTER TABLE scores ADD COLUMN completed_at DATETIME"))
            db.session.commit()
        import sys
        if "controllers" not in sys.modules:
            import controllers  # noqa: F401
        else:
            # Route handlers use Flask's current_app proxy; copy their rules for
            # additional factory-created apps such as isolated functional tests.
            original = sys.modules.get("app")
            source = getattr(original, "app", None)
            if source is not None and source is not app:
                for rule in source.url_map.iter_rules():
                    if rule.endpoint not in app.view_functions:
                        app.view_functions[rule.endpoint] = source.view_functions[rule.endpoint]
                        app.url_map.add(rule.empty())
    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG") == "1")
