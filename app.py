"""Quiz Master / Online Examination System Flask entry point."""
import os
import jinja2
from flask import Flask
from config import Config
from database import db


def create_app(test_config=None):
    base_dir = os.path.abspath(os.path.dirname(__file__))
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.config.from_object(Config)

    # Multi-path template loader to cleanly support both modular subfolders
    # (templates/auth, templates/admin, templates/user) and top-level template names.
    app.jinja_loader = jinja2.ChoiceLoader([
        jinja2.FileSystemLoader(os.path.join(base_dir, "templates")),
        jinja2.FileSystemLoader(os.path.join(base_dir, "templates", "auth")),
        jinja2.FileSystemLoader(os.path.join(base_dir, "templates", "admin")),
        jinja2.FileSystemLoader(os.path.join(base_dir, "templates", "teacher")),
        jinja2.FileSystemLoader(os.path.join(base_dir, "templates", "user")),
        jinja2.FileSystemLoader(base_dir),
    ])

    if test_config:
        app.config.update(test_config)
    db.init_app(app)
    with app.app_context():
        from models import (
            user, admin_table, subject, chapter, quiz, questions, scores,
            exam_attempt, answer_record, teacher_subject_assignment,
            audit_log, system_setting,
        )
        db.create_all()
        # Upgrade the legacy tables in-place.
        from sqlalchemy import inspect, text
        columns = {c["name"] for c in inspect(db.engine).get_columns("scores")}
        if "completed_at" not in columns:
            db.session.execute(text("ALTER TABLE scores ADD COLUMN completed_at DATETIME"))
            db.session.commit()
        user_columns = {c["name"] for c in inspect(db.engine).get_columns("user")}
        if "role" not in user_columns:
            db.session.execute(text("ALTER TABLE user ADD COLUMN role VARCHAR(20) DEFAULT 'student'"))
            db.session.commit()
        quiz_columns = {c["name"] for c in inspect(db.engine).get_columns("quiz")}
        if "published" not in quiz_columns:
            # Preserve existing exam availability; new exams are created as drafts.
            db.session.execute(text("ALTER TABLE quiz ADD COLUMN published BOOLEAN NOT NULL DEFAULT 1"))
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
