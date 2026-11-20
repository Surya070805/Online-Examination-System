# Online Examination System

Flask and SQLite application for timed multiple-choice examinations. Students register, take published exams, and review their answer history. Faculty build courses and draft exams for assigned subjects. Administrators approve faculty, assign subjects, publish schedules, configure scoring defaults, and review institutional results and audit activity.

## Project Structure

The project follows a clean separation between backend application logic, frontend presentation layers (templates and static assets), documentation, and tests:

```text
Online-Examination-System/
├── docs/                        # Specifications, lifecycle, and validation docs
│   ├── INCREMENTS.md            # Traceability matrix across increments
│   ├── SDLC.md                  # Software development lifecycle process
│   ├── SRS.md                   # Software requirements specification
│   ├── VALIDATION.md            # Validation reports and test runs
│   └── increments/              # Increment-specific release notes
├── static/                      # Frontend assets
│   ├── css/
│   │   └── style.css            # Stylesheet with design system
│   └── images/
│       └── auth-bg.jpg          # Portal branding & background graphics
├── templates/                   # Frontend HTML views
│   ├── admin/                   # Administrative dashboards & management views
│   │   ├── admin_dashbord.html
│   │   ├── admin_audit_logs.html
│   │   ├── admin_settings.html
│   │   ├── new_chapter.html
│   │   ├── new_question.html
│   │   ├── new_quiz.html
│   │   ├── new_subject.html
│   │   ├── quiz_management.html
│   │   ├── scores.html
│   │   └── search_admin.html
│   ├── auth/                    # Authentication views
│   │   ├── login.html
│   │   └── register.html
│   ├── user/                    # Student assessment views
│       ├── exam_list.html
│       ├── exam_result.html
│       ├── exam_take.html
│       ├── search_user.html
│       ├── start_quiz.html
│       ├── user_dashboard.html
│       └── view_quiz.html
│   └── teacher/                 # Faculty assessment and analytics dashboard
│       └── teacher_dashboard.html
├── tests/                       # Automated pytest suite
│   └── test_examinations.py
├── .vscode/                     # Workspace debug configurations
│   └── launch.json
├── app.py                       # Application entrypoint & Flask factory
├── config.py                    # Environment and app configuration
├── controllers.py               # Route controllers & view handlers
├── database.py                  # SQLAlchemy instance & database setup
├── models.py                    # Database models
├── quizmaster.db                # SQLite database
├── requirements.txt             # Python package dependencies
└── README.md                    # Project documentation
```

## Run locally

1. Use Python 3.10 or later.
2. Install dependencies: `python -m pip install -r requirements.txt`.
3. Start the application: `python app.py`.
4. Open `http://127.0.0.1:5000/login` and register a student account.

The SQLite database is created in the project directory. Public registration creates student accounts only; an administrator promotes faculty accounts and assigns their subjects. Administrator accounts are provisioned separately.

Set a unique `SECRET_KEY` before deployment and serve the app over HTTPS. The default secret supports local development only.

## Validate

Run `python -m compileall -q app.py config.py controllers.py database.py models.py tests` and `pytest`. Functional cases are in `tests/test_examinations.py`; execution history and acceptance checks are in [docs/VALIDATION.md](docs/VALIDATION.md).

## Software engineering process

This lab project uses an incremental development model. See [docs/SDLC.md](docs/SDLC.md) for lifecycle and branch workflow, [docs/INCREMENTS.md](docs/INCREMENTS.md) for feature-to-requirement traceability, and [docs/SRS.md](docs/SRS.md) for product requirements. Each increment's scope and acceptance evidence are in `docs/increments/`.
