"""Functional test cases for core examination requirements (run with pytest)."""
import pytest
import sqlite3
from datetime import datetime, timedelta, timezone
from werkzeug.security import generate_password_hash
from app import create_app
from database import db
from models import (
    user, admin_table, subject, chapter, quiz, questions, exam_attempt,
    answer_record, scores, teacher_subject_assignment, audit_log, system_setting,
)


@pytest.fixture
def client(tmp_path):
    app = create_app({"TESTING": True, "SECRET_KEY": "test-secret", "SQLALCHEMY_DATABASE_URI": "sqlite:///" + str(tmp_path / "test.db")})
    context = app.app_context(); context.push()
    db.drop_all(); db.create_all()
    db.session.add(subject(id=1, name="Test subject")); db.session.flush()
    student = user(userName="student", Password=generate_password_hash("pass"), Full_Name="Test Student")
    db.session.add(student); db.session.flush()
    db.session.add(user(
        userName="faculty", Password=generate_password_hash("faculty-test-password"),
        Full_Name="Faculty Candidate", role="student",
    ))
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


def test_public_registration_cannot_self_assign_faculty_role(client):
    response = client.post('/register', data={
        "username": "self-promoted", "password": "not-plain-text",
        "name": "Self Promoted", "dob": "2000-01-01", "role": "teacher",
    })
    assert response.status_code == 302
    assert user.query.filter_by(userName="self-promoted").one().role == "student"


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


def test_student_can_resume_attempt_and_review_own_answers(client):
    login(client)
    started = client.post('/exam/1/start')
    attempt = exam_attempt.query.filter_by(quiz_id=1, user_id=1).one()
    assert started.headers['Location'].endswith(f'/exam/attempt/{attempt.id}')
    assert b"Resume examination" in client.get('/exams').data
    resumed = client.post('/exam/1/start')
    assert resumed.headers['Location'].endswith(f'/exam/attempt/{attempt.id}')

    client.post(f'/exam/attempt/{attempt.id}', data={"q_1": "1", "q_2": "4"})
    result = client.get(f'/exam/result/{attempt.id}')
    assert result.status_code == 200
    assert b"Your answer review" in result.data
    assert b"Correct answer: A" in result.data
    assert b"View result and answers" in client.get('/exams').data


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


def faculty_login(client):
    return client.post('/login', data={
        "username": "faculty",
        "password": "faculty-test-password",
    })


def admin_promote_and_assign(client, subject_id):
    admin_login(client)
    response = client.post('/admin/user/2/toggle_role', data={"role": "teacher"})
    assert response.status_code == 302
    response = client.post('/admin/teacher/2/subjects', data={"subject_ids": [str(subject_id)]})
    assert response.status_code == 302
    client.post('/logout')
    assert faculty_login(client).status_code == 302


def test_admin_assigns_subject_teacher_builds_draft_and_admin_publishes(client):
    scheduled_date = (datetime.now().date() + timedelta(days=10)).isoformat()
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

    assert client.get('/new_chapter/admin').status_code == 403
    admin_promote_and_assign(client, created_subject.id)
    assert teacher_subject_assignment.query.filter_by(teacher_id=2, subject_id=created_subject.id).count() == 1
    assert client.get('/teacher_dash').status_code == 200
    unassigned_subject = subject(name="Unassigned subject")
    db.session.add(unassigned_subject); db.session.commit()
    assert client.post('/new_chapter/faculty', data={
        "chap_name": "Forbidden chapter", "subj_id": str(unassigned_subject.id),
    }).status_code == 403

    assert client.get('/new_subject/faculty').status_code == 403
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
        "date": scheduled_date,
        "duration": "15",
    })
    assert response.status_code == 302
    created_exam = quiz.query.filter_by(remarks="Admin workflow exam").one()
    assert created_exam.published is False
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
    client.post('/logout')
    admin_login(client)
    assert client.post('/new_question/admin', data={
        "quiz_id": str(created_exam.id), "statement": "Dean should not author this",
        "opt1": "A", "opt2": "B", "opt3": "C", "opt4": "D", "correct_opt": "1",
    }).status_code == 403

    client.post('/logout')
    login(client)
    assert b"Admin workflow exam" not in client.get('/exams').data
    assert client.post(f'/exam/{created_exam.id}/start').status_code == 404

    client.post('/logout')
    admin_login(client)
    response = client.post(f'/admin/exams/{created_exam.id}/publish')
    assert response.status_code == 302
    db.session.refresh(created_exam)
    assert created_exam.published is True
    assert audit_log.query.filter_by(action="exam_published", entity_id=created_exam.id).count() == 1
    assert b"Admin workflow exam" in client.get('/quiz_manag/admin').data
    admin_dashboard = client.get('/admin_dash')
    assert admin_dashboard.status_code == 200
    assert b"Software Engineering" in admin_dashboard.data

    client.post('/logout')
    login(client)
    assert b"Admin workflow exam" in client.get('/exams').data
    assert f"Available {scheduled_date}".encode() in client.get('/exams').data
    assert client.post(f'/exam/{created_exam.id}/start').status_code == 302
    assert exam_attempt.query.filter_by(quiz_id=created_exam.id, user_id=1).first() is None


def test_teacher_delete_chapter_removes_unused_exam_content(client):
    admin_login(client)
    parent = subject(name="Delete subject")
    db.session.add(parent); db.session.flush()
    section = chapter(sub_id=parent.id, name="Delete chapter")
    db.session.add(section); db.session.flush()
    exam = quiz(chapter_id=section.id, time_duration="10", remarks="Delete me", quesion_id=0, published=False)
    db.session.add(exam); db.session.flush()
    question = questions(
        quiz_id=exam.id, chapter_id=section.id, question_statement="Delete question",
        option1="A", option2="B", option3="C", option4="D", correct_opt="1",
    )
    db.session.add(question); db.session.commit()

    admin_promote_and_assign(client, parent.id)
    question_id = question.id
    response = client.post(f'/delete_chapter/admin/{section.id}')
    assert response.status_code == 302
    assert db.session.get(chapter, section.id) is None
    assert db.session.get(quiz, exam.id) is None
    assert db.session.get(questions, question_id) is None


def test_teacher_can_delete_question_and_draft_exam(client):
    exam = quiz(chapter_id=1, time_duration="10", remarks="Delete workflow exam", quesion_id=0, published=False)
    db.session.add(exam); db.session.flush()
    question = questions(
        quiz_id=exam.id, chapter_id=1, question_statement="Delete workflow question",
        option1="A", option2="B", option3="C", option4="D", correct_opt="1",
    )
    db.session.add(question); db.session.commit()
    admin_promote_and_assign(client, 1)
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

def test_teacher_cannot_change_question_bank_after_an_attempt(client):
    db.session.add(exam_attempt(quiz_id=1, user_id=1, total_questions=2))
    db.session.commit()
    admin_promote_and_assign(client, 1)

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


def test_admin_role_demotion_revokes_existing_teacher_session(client):
    admin_login(client)
    client.post('/admin/user/2/toggle_role', data={"role": "teacher"})
    client.post('/admin/teacher/2/subjects', data={"subject_ids": ["1"]})
    teacher_client = client.application.test_client()
    assert faculty_login(teacher_client).status_code == 302
    assert teacher_client.get('/teacher_dash').status_code == 200

    client.post('/admin/user/2/toggle_role', data={"role": "student"})
    response = teacher_client.get('/teacher_dash')
    assert response.status_code == 302
    assert response.location.endswith('/login')


def test_teacher_only_sees_and_manages_assigned_subjects(client):
    other_subject = subject(name="Private other subject")
    db.session.add(other_subject); db.session.flush()
    other_chapter = chapter(sub_id=other_subject.id, name="Other chapter")
    db.session.add(other_chapter); db.session.flush()
    other_exam = quiz(chapter_id=other_chapter.id, time_duration="10", remarks="Private other exam", quesion_id=0)
    db.session.add(other_exam); db.session.flush()
    question = questions(
        quiz_id=other_exam.id, chapter_id=other_chapter.id, question_statement="Private question",
        option1="A", option2="B", option3="C", option4="D", correct_opt="1",
    )
    db.session.add(question); db.session.flush()
    attempt = exam_attempt(quiz_id=other_exam.id, user_id=1, total_questions=1, status="submitted", score=0)
    db.session.add(attempt)
    db.session.add(scores(quiz_id=other_exam.id, user_id=1, total_scored=0))
    db.session.commit()

    admin_promote_and_assign(client, 1)
    listing = client.get('/quiz_manag/faculty')
    assert b"Private other exam" not in listing.data
    assert client.get('/exam/result/' + str(attempt.id)).status_code == 403
    assert b"Private other exam" not in client.get('/scores').data
    assert client.post('/new_question/faculty', data={
        "quiz_id": str(other_exam.id), "statement": "Unauthorized question",
        "opt1": "A", "opt2": "B", "opt3": "C", "opt4": "D", "correct_opt": "1",
    }).status_code == 403


def test_admin_settings_are_validated_and_audited(client):
    admin_login(client)
    assert client.get('/admin/settings').status_code == 200
    assert client.post('/admin/settings', data={"default_exam_duration": "0"}).status_code == 400
    assert client.post('/admin/settings', data={"default_exam_duration": "45"}).status_code == 302
    assert system_setting.query.filter_by(key="default_exam_duration").one().value == "45"
    assert audit_log.query.filter_by(action="setting_changed").count() == 1
    assert client.get('/admin/audit-logs').status_code == 200


def test_admin_pass_fail_metrics_follow_system_threshold(client):
    admin_login(client)
    client.post('/admin/settings', data={"default_exam_duration": "30", "pass_mark_percent": "75"})
    db.session.add_all([
        scores(quiz_id=1, user_id=1, total_scored=2),
        scores(quiz_id=1, user_id=2, total_scored=1),
    ])
    db.session.commit()
    response = client.get('/admin_dash')
    assert b"Passes \xc2\xb7 \xe2\x89\xa5 75%" in response.data
    assert b"Submitted Attempts</div><div class=\"display-6 fw-bold text-primary mt-1\">2" in response.data
    assert b"Passes \xc2\xb7 \xe2\x89\xa5 75%</div><div class=\"display-6 fw-bold text-success mt-1\">1" in response.data
    assert b"Below Passing Threshold</div><div class=\"display-6 fw-bold text-warning mt-1\">1" in response.data


def test_existing_database_schema_migrates_roles_assignments_and_exam_publish_state(tmp_path):
    database_path = tmp_path / "legacy.db"
    connection = sqlite3.connect(str(database_path))
    connection.executescript("""
        CREATE TABLE user (id INTEGER PRIMARY KEY, userName VARCHAR(100), Password VARCHAR(255), Full_Name VARCHAR(150), Qualification VARCHAR(100), DOB INTEGER);
        INSERT INTO user VALUES (1, 'legacy-student', 'hash', 'Legacy Student', NULL, NULL);
        CREATE TABLE subject (id INTEGER PRIMARY KEY, name VARCHAR(100), Description TEXT);
        INSERT INTO subject VALUES (1, 'Legacy Subject', NULL);
        CREATE TABLE chapter (id INTEGER PRIMARY KEY, sub_id INTEGER, name VARCHAR(100), Description TEXT);
        INSERT INTO chapter VALUES (1, 1, 'Legacy Chapter', NULL);
        CREATE TABLE quiz (id INTEGER PRIMARY KEY, chapter_id INTEGER, date_of_quiz TEXT, time_duration VARCHAR(10), remarks TEXT, quesion_id INTEGER);
        INSERT INTO quiz VALUES (1, 1, '2025-01-01', '30', 'Legacy exam', 0);
        CREATE TABLE scores (id INTEGER PRIMARY KEY, quiz_id INTEGER, user_id INTEGER, time_stamp_of_attempt DATETIME, total_scored INTEGER);
    """)
    connection.commit(); connection.close()

    legacy_app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": f"sqlite:///{database_path}"})
    with legacy_app.app_context():
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        assert "role" in {column["name"] for column in inspector.get_columns("user")}
        assert "published" in {column["name"] for column in inspector.get_columns("quiz")}
        assert "completed_at" in {column["name"] for column in inspector.get_columns("scores")}
        assert {"teacher_subject_assignment", "audit_log", "system_setting"}.issubset(set(inspector.get_table_names()))
        assert db.session.get(user, 1).role == "student"
        assert db.session.get(quiz, 1).published is True
        db.session.remove()
