"""Functional test cases for core examination requirements (run with pytest)."""
import pytest
from datetime import datetime, timedelta, timezone
from werkzeug.security import generate_password_hash
from app import create_app
from database import db
from models import user, admin_table, subject, chapter, quiz, questions, exam_attempt, answer_record


@pytest.fixture
def client(tmp_path):
    app = create_app({"TESTING": True, "SECRET_KEY": "test-secret", "SQLALCHEMY_DATABASE_URI": "sqlite:///" + str(tmp_path / "test.db")})
    context = app.app_context(); context.push()
    db.drop_all(); db.create_all()
    db.session.add(subject(id=1, name="Test subject")); db.session.flush()
    student = user(userName="student", Password=generate_password_hash("pass"), Full_Name="Test Student")
    db.session.add(student); db.session.flush()
    db.session.add(admin_table(username="admin", Password=generate_password_hash("administrator-test-password")))
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
    attempt = db.session.get(exam_attempt, attempt_id)
    assert (attempt.score, attempt.total_questions, attempt.status) == (1, 2, 'submitted')


def test_exam_attempt_is_created_only_once(client):
    login(client)
    assert client.post('/exam/1/start').status_code == 302
    first_attempt = exam_attempt.query.filter_by(quiz_id=1, user_id=1).one()
    assert client.post('/exam/1/start').status_code == 302
    assert exam_attempt.query.filter_by(quiz_id=1, user_id=1).count() == 1
    assert first_attempt.status == 'in_progress'


def test_expired_attempt_is_submitted_without_late_answers(client):
    login(client)
    client.post('/exam/1/start')
    attempt = exam_attempt.query.filter_by(quiz_id=1, user_id=1).one()
    attempt.started_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=6)
    db.session.commit()

    response = client.post(f'/exam/attempt/{attempt.id}', data={"q_1": "1", "q_2": "1"})
    assert response.status_code == 302
    db.session.refresh(attempt)
    assert attempt.status == 'submitted'
    assert attempt.score == 0
    assert answer_record.query.filter_by(attempt_id=attempt.id).count() == 0


def test_unanswered_questions_score_zero(client):
    login(client)
    client.post('/exam/1/start')
    attempt = exam_attempt.query.filter_by(quiz_id=1, user_id=1).one()
    response = client.post(f'/exam/attempt/{attempt.id}', data={})
    assert response.status_code == 302
    db.session.refresh(attempt)
    assert attempt.score == 0
    assert answer_record.query.filter_by(attempt_id=attempt.id, is_correct=True).count() == 0


def test_submitted_result_is_immutable(client):
    login(client)
    client.post('/exam/1/start')
    attempt = exam_attempt.query.filter_by(quiz_id=1, user_id=1).one()
    client.post(f'/exam/attempt/{attempt.id}', data={"q_1": "1", "q_2": "4"})
    db.session.refresh(attempt)
    original_score = attempt.score

    response = client.post(f'/exam/attempt/{attempt.id}', data={"q_1": "1", "q_2": "1"})
    assert response.status_code == 302
    db.session.refresh(attempt)
    assert attempt.score == original_score == 1
    assert answer_record.query.filter_by(attempt_id=attempt.id).count() == 2


def test_attempt_owner_enforced(client):
    login(client)
    client.post('/exam/1/start')
    attempt_id = exam_attempt.query.first().id
    client.get('/logout')
    assert client.get(f'/exam/result/{attempt_id}').status_code in (302, 403)


def admin_login(client):
    return client.post('/login', data={
        "username": "admin",
        "password": "administrator-test-password",
    })


def test_admin_can_create_subject_chapter_exam_and_question(client):
    response = admin_login(client)
    assert response.status_code == 302
    assert response.location.endswith('/admin_dash')
    assert client.get('/admin_dash').status_code == 200

    assert client.get('/new_subject/admin').status_code == 200
    response = client.post('/new_subject/admin', data={
        "subj": "Software Engineering",
        "desc": "Lab examination subject",
    })
    assert response.status_code == 302
    created_subject = subject.query.filter_by(name="Software Engineering").one()

    assert client.get('/new_chapter/admin').status_code == 200
    response = client.post('/new_chapter/admin', data={
        "chap_name": "Incremental Models",
        "subj_id": str(created_subject.id),
        "descrip": "Process model chapter",
    })
    assert response.status_code == 302
    created_chapter = chapter.query.filter_by(name="Incremental Models").one()

    response = client.post('/new_quiz/admin', data={
        "remarks": "Admin workflow exam",
        "chapter_id": str(created_chapter.id),
        "date": "2026-12-01",
        "duration": "15",
    })
    assert response.status_code == 302
    created_exam = quiz.query.filter_by(remarks="Admin workflow exam").one()
    assert client.get('/quiz_manag/admin').status_code == 200

    response = client.post('/new_question/admin', data={
        "quiz_id": str(created_exam.id),
        "statement": "Which workflow was created?",
        "opt1": "Incremental",
        "opt2": "Random",
        "opt3": "None",
        "opt4": "Unknown",
        "correct_opt": "1",
    })
    assert response.status_code == 302
    created_question = questions.query.filter_by(quiz_id=created_exam.id).one()
    assert created_question.chapter_id == created_chapter.id
    assert created_question.correct_opt == "1"
    assert b"Admin workflow exam" in client.get('/quiz_manag/admin').data
    assert b"Software Engineering" in client.get('/admin_dash').data


def test_admin_delete_chapter_removes_unused_exam_content(client):
    admin_login(client)
    parent = subject(name="Delete subject")
    db.session.add(parent); db.session.flush()
    section = chapter(sub_id=parent.id, name="Delete chapter")
    db.session.add(section); db.session.flush()
    exam = quiz(chapter_id=section.id, time_duration="10", remarks="Delete me", quesion_id=0)
    db.session.add(exam); db.session.flush()
    question = questions(
        quiz_id=exam.id, chapter_id=section.id, question_statement="Delete question",
        option1="A", option2="B", option3="C", option4="D", correct_opt="1",
    )
    db.session.add(question); db.session.commit()

    question_id = question.id
    response = client.post(f'/delete_chapter/admin/{section.id}')
    assert response.status_code == 302
    assert db.session.get(chapter, section.id) is None
    assert db.session.get(quiz, exam.id) is None
    assert db.session.get(questions, question_id) is None


def test_admin_can_delete_question_and_exam(client):
    admin_login(client)
    exam = quiz(chapter_id=1, time_duration="10", remarks="Delete workflow exam", quesion_id=0)
    db.session.add(exam); db.session.flush()
    question = questions(
        quiz_id=exam.id, chapter_id=1, question_statement="Delete workflow question",
        option1="A", option2="B", option3="C", option4="D", correct_opt="1",
    )
    db.session.add(question); db.session.commit()
    exam_id, question_id = exam.id, question.id

    response = client.post(f'/delete_question/admin/{question_id}')
    assert response.status_code == 302
    assert db.session.get(questions, question_id) is None

    response = client.post(f'/delete_quiz/admin/{exam_id}')
    assert response.status_code == 302
    assert db.session.get(quiz, exam_id) is None

def test_admin_results_action_opens_results_page(client):
    admin_login(client)
    response = client.get('/scores')
    assert response.status_code == 200
    assert b"Exam results" in response.data
    assert b"No results yet" in response.data

def test_admin_cannot_change_question_bank_after_an_attempt(client):
    admin_login(client)
    db.session.add(exam_attempt(quiz_id=1, user_id=1, total_questions=2))
    db.session.commit()

    response = client.post('/new_question/admin', data={
        "quiz_id": "1",
        "statement": "Late question",
        "opt1": "A",
        "opt2": "B",
        "opt3": "C",
        "opt4": "D",
        "correct_opt": "1",
    })
    assert response.status_code == 409
    assert questions.query.filter_by(quiz_id=1).count() == 2
