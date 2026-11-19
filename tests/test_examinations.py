"""Functional test cases for core examination requirements (run with pytest)."""
import pytest
from werkzeug.security import generate_password_hash
from app import create_app
from database import db
from models import user, subject, chapter, quiz, questions, exam_attempt


@pytest.fixture
def client(tmp_path):
    app = create_app({"TESTING": True, "SECRET_KEY": "test-secret", "SQLALCHEMY_DATABASE_URI": "sqlite:///" + str(tmp_path / "test.db")})
    context = app.app_context(); context.push()
    db.drop_all(); db.create_all()
    db.session.add(subject(id=1, name="Test subject")); db.session.flush()
    student = user(userName="student", Password=generate_password_hash("pass"), Full_Name="Test Student")
    db.session.add(student); db.session.flush()
    ch = chapter(id=1, sub_id=1, name="Test", Description="")
    db.session.add(ch); db.session.flush()
    exam = quiz(id=1, chapter_id=ch.id, time_duration="5", remarks="Functional test", quesion_id=1)
    db.session.add(exam); db.session.flush()
    db.session.add_all([questions(id=i, quiz_id=1, chapter_id=ch.id, question_statement=f"Q{i}", option1="A", option2="B", option3="C", option4="D", correct_opt="1") for i in (1, 2)])
    db.session.commit()
    client = app.test_client()
    yield client
    db.session.remove(); db.drop_all(); context.pop()


def login(client):
    return client.post('/login', data={"username": "student", "password": "pass"})


def test_authentication_required(client):
    assert client.get('/exams').status_code == 302


def test_registration_stores_a_password_hash(client):
    response = client.post('/register', data={
        "username": "newstudent", "password": "not-plain-text",
        "name": "New Student", "qualification": "Student", "dob": "2000-01-01",
    })
    assert response.status_code == 302
    saved = user.query.filter_by(userName="newstudent").one()
    assert saved.Password != "not-plain-text"
    assert saved.Password.startswith(("pbkdf2:", "scrypt:"))


def test_student_cannot_open_admin_dashboard(client):
    login(client)
    assert client.get('/admin_dash').status_code == 403


def test_invalid_password_does_not_create_session(client):
    response = client.post('/login', data={"username": "student", "password": "wrong"})
    assert response.status_code == 401
    assert client.get('/exams').status_code == 302


def test_start_once_and_auto_evaluate(client):
    login(client)
    response = client.post('/exam/1/start')
    assert response.status_code == 302
    attempt_id = exam_attempt.query.first().id
    assert client.post('/exam/1/start').status_code == 302
    client.post(f'/exam/attempt/{attempt_id}', data={"q_1": "1", "q_2": "4", "score": "999"})
    attempt = exam_attempt.query.get(attempt_id)
    assert (attempt.score, attempt.total_questions, attempt.status) == (1, 2, 'submitted')


def test_attempt_owner_enforced(client):
    login(client)
    client.post('/exam/1/start')
    attempt_id = exam_attempt.query.first().id
    client.get('/logout')
    assert client.get(f'/exam/result/{attempt_id}').status_code in (302, 403)
