# Online Examination System

Flask and SQLite application for administering multiple-choice exams. Students register and sign in, take one timed attempt per exam, and receive an automatically calculated result. Administrators use the subject, chapter, quiz, and question management screens.

## Run locally

1. Use Python 3.10 or later.
2. Install dependencies: `python -m pip install -r requirements.txt`.
3. Start the application: `python app.py`.
4. Open `http://127.0.0.1:5000/login` and register a student account.

The SQLite database is created in the project directory. Administrator accounts must be provisioned by the project owner; public administrator registration is not enabled.

Set a unique `SECRET_KEY` before deployment and serve the app over HTTPS. The default secret supports local development only.

## Validate

Run `python -m compileall -q app.py controllers.py models.py tests` and `pytest`. Functional cases are in `tests/test_examinations.py`; execution history and acceptance checks are in [VALIDATION.md](VALIDATION.md).

## Software engineering process

This lab project uses an incremental development model. See [SDLC.md](SDLC.md) for lifecycle and branch workflow, [INCREMENTS.md](INCREMENTS.md) for feature-to-requirement traceability, and [SRS.md](SRS.md) for product requirements. Each increment's scope and acceptance evidence are in `docs/increments/`.
