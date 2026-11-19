# Quiz Master — Online Examination System

Flask and SQLite application for administering multiple-choice examinations. Students register/sign in, take one timed attempt per exam, and receive a server-calculated result. Administrators use the existing subject, chapter, quiz, and question management screens.

## Run

Install the project dependencies (`Flask`, `Flask-SQLAlchemy`) in your Python environment, then run `python app.py` and open `http://127.0.0.1:5000/login`.

Set a unique `SECRET_KEY` environment variable before deploying. The built-in fallback is for local development only. Use HTTPS in production.

## Functional test cases

`pytest` runs the examination cases in `tests/test_examinations.py`: authentication gate, single attempt and automated evaluation (including forged-score rejection), and attempt ownership. See [SRS.md](SRS.md) for requirements and acceptance criteria.
