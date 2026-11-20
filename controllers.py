"""Routes for authentication, examination delivery, and administrator workflows."""
from datetime import datetime, timedelta, timezone
from functools import wraps

from flask import abort, current_app as app, flash, redirect, render_template, request, session, url_for
from sqlalchemy import func, or_
from werkzeug.security import check_password_hash, generate_password_hash

from database import db
from models import (
    admin_table,
    answer_record,
    audit_log,
    chapter,
    exam_attempt,
    questions,
    quiz,
    scores,
    subject,
    system_setting,
    teacher_subject_assignment,
    user,
)


def utc_now():
    """Use UTC while keeping SQLite-compatible naive datetime values."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def login_required(role=None):
    def decorate(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if not session.get("user_id"):
                return redirect(url_for("login"))
            session_role = session.get("role")
            if session_role in {"student", "teacher"}:
                account = db.session.get(user, session["user_id"])
                account_role = getattr(account, "role", "student") if account else None
                account_role = account_role if account_role in {"student", "teacher"} else "student"
                if account is None or account_role != session_role:
                    session.clear()
                    flash("Your account permissions changed. Sign in again to continue.", "warning")
                    return redirect(url_for("login"))
            elif session_role == "admin":
                account = db.session.get(admin_table, session["user_id"])
                if account is None or account.username != session.get("username"):
                    session.clear()
                    return redirect(url_for("login"))
            if role:
                allowed = [role] if isinstance(role, str) else list(role)
                if session.get("role") not in allowed:
                    abort(403)
            return view(*args, **kwargs)
        return wrapped
    return decorate


def admin_context():
    return {
        "Admin": session.get("username", "Admin"),
        "role": session.get("role", "admin"),
        "full_name": session.get("full_name", session.get("username", "Admin")),
    }


def _teacher_subject_ids(teacher_id=None):
    teacher_id = teacher_id or session.get("user_id")
    return [row[0] for row in db.session.query(teacher_subject_assignment.subject_id)
            .filter_by(teacher_id=teacher_id).all()]


def _teacher_chapter_ids(teacher_id=None):
    subject_ids = _teacher_subject_ids(teacher_id)
    if not subject_ids:
        return []
    return [row[0] for row in db.session.query(chapter.id).filter(chapter.sub_id.in_(subject_ids)).all()]


def _teacher_exam_ids(teacher_id=None):
    chapter_ids = _teacher_chapter_ids(teacher_id)
    if not chapter_ids:
        return []
    return [row[0] for row in db.session.query(quiz.id).filter(quiz.chapter_id.in_(chapter_ids)).all()]


def _require_teacher_exam_access(exam):
    if session.get("role") == "teacher" and exam.chapter.sub_id not in _teacher_subject_ids():
        abort(403)


def _exam_scheduled_for_later(exam):
    if not exam.date_of_quiz:
        return False
    try:
        scheduled_date = datetime.strptime(exam.date_of_quiz, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return False
    return scheduled_date > datetime.now().date()


def _audit(action, entity_type, entity_id=None, details=None):
    db.session.add(audit_log(
        actor_username=session.get("username", "system"),
        actor_role=session.get("role", "system"),
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        details=details,
    ))


def _delete_quiz_records(exam):
    """Delete an unattempted quiz and its dependent questions safely."""
    attempt_ids = [
        row[0] for row in db.session.query(exam_attempt.id)
        .filter_by(quiz_id=exam.id).all()
    ]
    if attempt_ids:
        answer_record.query.filter(answer_record.attempt_id.in_(attempt_ids)).delete(synchronize_session=False)
        exam_attempt.query.filter(exam_attempt.id.in_(attempt_ids)).delete(synchronize_session=False)
    scores.query.filter_by(quiz_id=exam.id).delete(synchronize_session=False)
    questions.query.filter_by(quiz_id=exam.id).delete(synchronize_session=False)
    db.session.delete(exam)


@app.route("/")
def index():
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        candidate = user.query.filter_by(userName=username).first()
        administrator = admin_table.query.filter_by(username=username).first()

        account = candidate or administrator
        if account is None:
            return render_template("login.html", message="Invalid username or password"), 401

        stored_password = account.Password
        if stored_password.startswith(("pbkdf2:", "scrypt:")):
            valid = check_password_hash(stored_password, password)
        else:
            # Upgrade legacy plaintext accounts only after a valid login.
            valid = stored_password == password
            if valid:
                account.Password = generate_password_hash(password)
                db.session.commit()

        if not valid:
            return render_template("login.html", message="Invalid username or password"), 401

        session.clear()
        session["user_id"] = account.id
        if candidate:
            role = getattr(candidate, "role", "student") or "student"
            session["role"] = role if role in {"student", "teacher"} else "student"
            session["full_name"] = candidate.Full_Name
        else:
            session["role"] = "admin"
            session["full_name"] = "Dean / Administrator"
        session["username"] = username
        session.permanent = True

        if session["role"] == "admin":
            return redirect(url_for("admin_dash"))
        elif session["role"] == "teacher":
            return redirect(url_for("teacher_dash"))
        else:
            return redirect(url_for("student_exams"))

    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        fullname = request.form.get("name", "").strip()
        qualification = request.form.get("qualification", "").strip()
        dob = request.form.get("dob", "")

        if not all((username, password, fullname, dob)):
            return render_template("register.html", message="Complete all required fields."), 400
        if user.query.filter_by(userName=username).first() or admin_table.query.filter_by(username=username).first():
            return render_template("register.html", message="That username is already in use."), 409
        if len(password) < 8:
            return render_template("register.html", message="Use a password with at least 8 characters."), 400

        db.session.add(user(
            userName=username,
            Password=generate_password_hash(password),
            Full_Name=fullname,
            Qualification=qualification or None,
            DOB=dob,
            role="student",
        ))
        db.session.commit()
        flash("Student account created. An administrator can approve faculty access.")
        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/logout", methods=["GET", "POST"])
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/exams")
@login_required("student")
def student_exams():
    exams = quiz.query.filter_by(published=True).order_by(quiz.id.desc()).all()
    attempts = {item.quiz_id: item for item in exam_attempt.query.filter_by(user_id=session["user_id"]).all()}
    future_exam_ids = {item.id for item in exams if _exam_scheduled_for_later(item)}
    return render_template("exam_list.html", quizzes=exams, attempts=attempts, future_exam_ids=future_exam_ids, username=session["username"])


@app.route("/exam/<int:quiz_id>/start", methods=["POST"])
@login_required("student")
def exam_start(quiz_id):
    exam = db.get_or_404(quiz, quiz_id)
    if not exam.published:
        abort(404)
    existing = exam_attempt.query.filter_by(quiz_id=quiz_id, user_id=session["user_id"]).first()
    if existing:
        if existing.status == "in_progress":
            return redirect(url_for("exam_take", attempt_id=existing.id))
        return redirect(url_for("exam_result", attempt_id=existing.id))
    if _exam_scheduled_for_later(exam):
        flash(f"This exam opens on {exam.date_of_quiz}.", "info")
        return redirect(url_for("student_exams"))
    if not exam.questions:
        flash("This exam has no questions yet.")
        return redirect(url_for("student_exams"))

    attempt = exam_attempt(
        quiz_id=quiz_id,
        user_id=session["user_id"],
        total_questions=len(exam.questions),
    )
    db.session.add(attempt)
    db.session.commit()
    return redirect(url_for("exam_take", attempt_id=attempt.id))


@app.route("/exam/attempt/<int:attempt_id>", methods=["GET", "POST"])
@login_required("student")
def exam_take(attempt_id):
    attempt = exam_attempt.query.filter_by(
        id=attempt_id, user_id=session["user_id"]
    ).first_or_404()
    exam = db.get_or_404(quiz, attempt.quiz_id)
    if attempt.status != "in_progress":
        return redirect(url_for("exam_result", attempt_id=attempt.id))

    duration = max(1, int(exam.time_duration or 30))
    expires = attempt.started_at + timedelta(minutes=duration)
    if utc_now() >= expires:
        attempt.score = 0
        attempt.submitted_at = utc_now()
        attempt.status = "submitted"
        db.session.add(scores(
            quiz_id=attempt.quiz_id,
            user_id=attempt.user_id,
            total_scored=0,
            completed_at=attempt.submitted_at,
        ))
        db.session.commit()
        return redirect(url_for("exam_result", attempt_id=attempt.id))

    if request.method == "POST":
        now = utc_now()
        for question in exam.questions:
            selected = request.form.get(f"q_{question.id}", "")
            if selected not in {"1", "2", "3", "4"}:
                selected = None
            db.session.add(answer_record(
                attempt_id=attempt.id,
                question_id=question.id,
                selected_option=selected,
                is_correct=bool(selected and selected == str(question.correct_opt)),
            ))
        db.session.flush()
        attempt.score = answer_record.query.filter_by(
            attempt_id=attempt.id, is_correct=True
        ).count()
        attempt.submitted_at = now
        attempt.status = "submitted"
        db.session.add(scores(
            quiz_id=attempt.quiz_id,
            user_id=attempt.user_id,
            total_scored=attempt.score,
            completed_at=now,
        ))
        db.session.commit()
        return redirect(url_for("exam_result", attempt_id=attempt.id))

    return render_template(
        "exam_take.html",
        attempt=attempt,
        exam=exam,
        questions=exam.questions,
        expires_at=expires.isoformat() + "Z",
    )


@app.route("/exam/result/<int:attempt_id>")
@login_required()
def exam_result(attempt_id):
    attempt = db.get_or_404(exam_attempt, attempt_id)
    role = session.get("role")
    if role == "student" and attempt.user_id != session["user_id"]:
        abort(403)
    if role == "teacher":
        _require_teacher_exam_access(db.get_or_404(quiz, attempt.quiz_id))
    if attempt.status != "submitted":
        if role == "student":
            return redirect(url_for("exam_take", attempt_id=attempt.id))
        abort(409)
    answers = {row.question_id: row for row in answer_record.query.filter_by(attempt_id=attempt.id).all()}
    return render_template(
        "exam_result.html",
        attempt=attempt,
        exam=db.get_or_404(quiz, attempt.quiz_id),
        answers=answers,
        role=role,
    )


# Administrator and Teacher dashboards
@app.route("/admin_dash", methods=["GET"])
@login_required("admin")
def admin_dash():
    users_list = user.query.order_by(user.id.desc()).all()
    students_count = user.query.filter_by(role="student").count()
    teachers_count = user.query.filter_by(role="teacher").count()
    exams_count = quiz.query.count()
    assignment_map = {member.id: set() for member in users_list if member.role == "teacher"}
    for assignment in teacher_subject_assignment.query.all():
        assignment_map.setdefault(assignment.teacher_id, set()).add(assignment.subject_id)
    pass_mark_setting = system_setting.query.filter_by(key="pass_mark_percent").first()
    pass_mark = int(pass_mark_setting.value) if pass_mark_setting else 50
    submissions = db.session.query(scores.total_scored, quiz.id).join(quiz, scores.quiz_id == quiz.id).filter(scores.total_scored.is_not(None)).all()
    pass_count = 0
    for score_value, exam_id in submissions:
        exam_question_count = len(db.session.get(quiz, exam_id).questions)
        if exam_question_count and 100 * score_value / exam_question_count >= pass_mark:
            pass_count += 1
    return render_template(
        "admin_dashbord.html",
        subjects=subject.query.order_by(subject.name).all(),
        users=users_list,
        students_count=students_count,
        teachers_count=teachers_count,
        exams_count=exams_count,
        total_submissions=len(submissions),
        pass_count=pass_count,
        fail_count=len(submissions) - pass_count,
        pass_mark=pass_mark,
        assigned_subject_ids=assignment_map,
        draft_exams=(quiz.query.filter_by(published=False).order_by(quiz.id.desc()).all()),
        recent_audit_logs=audit_log.query.order_by(audit_log.created_at.desc()).limit(8).all(),
        **admin_context(),
    )


@app.route("/teacher_dash", methods=["GET"])
@login_required("teacher")
def teacher_dash():
    subject_ids = _teacher_subject_ids()
    chapter_ids = _teacher_chapter_ids()
    exam_ids = _teacher_exam_ids()
    subjects = subject.query.filter(subject.id.in_(subject_ids)).order_by(subject.name).all() if subject_ids else []
    exams = quiz.query.filter(quiz.id.in_(exam_ids)).order_by(quiz.id.desc()).all() if exam_ids else []
    recent_scores = scores.query.filter(scores.quiz_id.in_(exam_ids)).order_by(scores.id.desc()).limit(10).all() if exam_ids else []
    total_questions = questions.query.filter(questions.quiz_id.in_(exam_ids)).count() if exam_ids else 0
    total_chapters = len(chapter_ids)
    score_rows = db.session.query(scores.total_scored, quiz.id).join(quiz, scores.quiz_id == quiz.id).filter(quiz.id.in_(exam_ids), scores.total_scored.is_not(None)).all() if exam_ids else []
    percentages = [100 * score / max(1, len(db.session.get(quiz, quiz_id).questions)) for score, quiz_id in score_rows]
    average_score = round(sum(percentages) / len(percentages), 1) if percentages else None
    response_rows = []
    if exam_ids:
        response_rows = (
            db.session.query(answer_record.question_id, func.count(answer_record.id), func.sum(answer_record.is_correct))
            .join(exam_attempt, answer_record.attempt_id == exam_attempt.id)
            .filter(exam_attempt.quiz_id.in_(exam_ids))
            .group_by(answer_record.question_id)
            .all()
        )
    response_map = {question_id: (responses, correct or 0) for question_id, responses, correct in response_rows}
    question_difficulty = []
    if exam_ids:
        for item in questions.query.filter(questions.quiz_id.in_(exam_ids)).all():
            responses, correct = response_map.get(item.id, (0, 0))
            if responses:
                question_difficulty.append({"question": item, "responses": responses, "correct_rate": round(100 * correct / responses)})
        question_difficulty.sort(key=lambda item: item["correct_rate"])
    return render_template(
        "teacher_dashboard.html",
        subjects=subjects,
        quizzes=exams,
        recent_scores=recent_scores,
        total_questions=total_questions,
        total_chapters=total_chapters,
        average_score=average_score,
        question_difficulty=question_difficulty[:5],
        **admin_context(),
    )


@app.route("/admin/user/<int:user_id>/toggle_role", methods=["POST"])
@login_required("admin")
def toggle_user_role(user_id):
    target_user = db.get_or_404(user, user_id)
    new_role = request.form.get("role")
    if new_role not in {"student", "teacher"}:
        abort(400)
    if target_user.role == new_role:
        return redirect(url_for("admin_dash"))
    previous_role = target_user.role
    target_user.role = new_role
    if new_role == "student":
        teacher_subject_assignment.query.filter_by(teacher_id=target_user.id).delete()
    _audit("role_changed", "user", target_user.id, f"{previous_role} -> {new_role}")
    db.session.commit()
    flash(f"Updated {target_user.Full_Name}'s role to {target_user.role.capitalize()}.", "success")
    return redirect(url_for("admin_dash"))


@app.route("/admin/teacher/<int:teacher_id>/subjects", methods=["POST"])
@login_required("admin")
def assign_teacher_subjects(teacher_id):
    teacher = db.get_or_404(user, teacher_id)
    if teacher.role != "teacher":
        abort(409)
    selected_ids = {int(value) for value in request.form.getlist("subject_ids") if value.isdigit()}
    available_ids = {row[0] for row in db.session.query(subject.id).all()}
    if not selected_ids.issubset(available_ids):
        abort(400)
    teacher_subject_assignment.query.filter_by(teacher_id=teacher.id).delete()
    for subject_id in sorted(selected_ids):
        db.session.add(teacher_subject_assignment(teacher_id=teacher.id, subject_id=subject_id))
    _audit("subjects_assigned", "user", teacher.id, ",".join(map(str, sorted(selected_ids))))
    db.session.commit()
    flash(f"Subject access updated for {teacher.Full_Name}.", "success")
    return redirect(url_for("admin_dash"))


@app.route("/admin_dash/<string:Admin>", methods=["GET", "POST"])
@login_required("admin")
def new_admin_dash(Admin):
    return redirect(url_for("admin_dash"))


@app.route("/new_subject/<string:Admin>", methods=["GET", "POST"])
@login_required("admin")
def new_subject(Admin):
    if request.method == "POST":
        name = request.form.get("subj", "").strip()
        description = request.form.get("desc", "").strip()
        if not name:
            flash("Enter a subject name.", "danger")
            return render_template("new_subject.html", **admin_context()), 400
        duplicate = subject.query.filter(db.func.lower(subject.name) == name.lower()).first()
        if duplicate:
            flash("A subject with that name already exists.", "warning")
            return render_template("new_subject.html", **admin_context()), 409
        created = subject(name=name, Description=description or None)
        db.session.add(created)
        db.session.flush()
        _audit("subject_created", "subject", created.id, name)
        db.session.commit()
        flash(f"Subject “{name}” was created.", "success")
        return redirect(url_for("admin_dash"))

    return render_template("new_subject.html", **admin_context())


@app.route("/new_chapter/<string:Admin>", methods=["GET", "POST"])
@login_required("teacher")
def new_chapter(Admin):
    subject_ids = _teacher_subject_ids()
    subjects = subject.query.filter(subject.id.in_(subject_ids)).order_by(subject.name).all() if subject_ids else []
    if request.method == "POST":
        name = request.form.get("chap_name", "").strip()
        description = request.form.get("descrip", "").strip()
        subject_id = request.form.get("subj_id", type=int)
        parent_subject = db.session.get(subject, subject_id) if subject_id else None
        if not name or not parent_subject or parent_subject.id not in subject_ids:
            if parent_subject and parent_subject.id not in subject_ids:
                abort(403)
            flash("Choose a subject and enter a chapter name.", "danger")
            return render_template("new_chapter.html", subjects=subjects, **admin_context()), 400
        duplicate = chapter.query.filter_by(sub_id=subject_id, name=name).first()
        if duplicate:
            flash("That chapter already exists under this subject.", "warning")
            return render_template("new_chapter.html", subjects=subjects, **admin_context()), 409
        created = chapter(
            sub_id=subject_id,
            name=name,
            Description=description or None,
        )
        db.session.add(created)
        db.session.flush()
        _audit("chapter_created", "chapter", created.id, name)
        db.session.commit()
        flash(f"Chapter “{name}” was created.", "success")
        return redirect(url_for("teacher_dash"))

    return render_template("new_chapter.html", subjects=subjects, **admin_context())


@app.route("/quiz_manag/<string:usern>", methods=["GET", "POST"])
@login_required(["teacher", "admin"])
def new_quiz_manag(usern):
    if session.get("role") == "teacher":
        exam_ids = _teacher_exam_ids()
        exams = quiz.query.filter(quiz.id.in_(exam_ids)).order_by(quiz.id.desc()).all() if exam_ids else []
    else:
        exams = quiz.query.order_by(quiz.id.desc()).all()
    return render_template("quiz_management.html", quizzes=exams, **admin_context())


@app.route("/new_quiz/<string:Admin>", methods=["GET", "POST"])
@login_required("teacher")
def new_quiz(Admin):
    chapter_ids = _teacher_chapter_ids()
    chapters = chapter.query.filter(chapter.id.in_(chapter_ids)).order_by(chapter.name).all() if chapter_ids else []
    setting = system_setting.query.filter_by(key="default_exam_duration").first()
    default_duration = setting.value if setting else "30"
    if request.method == "POST":
        name = request.form.get("remarks", "").strip()
        chapter_id = request.form.get("chapter_id", type=int)
        duration = request.form.get("duration", type=int)
        date_of_quiz = request.form.get("date", "").strip()
        selected_chapter = db.session.get(chapter, chapter_id) if chapter_id else None

        if not selected_chapter or not name or not date_of_quiz or not duration or not 1 <= duration <= 300:
            flash("Choose a chapter, enter an exam name and date, and use a duration from 1 to 300 minutes.", "danger")
            return render_template("new_quiz.html", chapters=chapters, default_duration=default_duration, **admin_context()), 400
        if selected_chapter.id not in chapter_ids:
            abort(403)

        try:
            datetime.strptime(date_of_quiz, "%Y-%m-%d")
        except ValueError:
            flash("Enter a valid exam date.", "danger")
            return render_template("new_quiz.html", chapters=chapters, default_duration=default_duration, **admin_context()), 400

        exam = quiz(
            chapter_id=chapter_id,
            date_of_quiz=date_of_quiz,
            time_duration=str(duration),
            remarks=name,
            quesion_id=0,
            published=False,
        )
        db.session.add(exam)
        db.session.flush()
        _audit("exam_created", "quiz", exam.id, name)
        db.session.commit()
        flash(f"Exam “{name}” was created as a draft. Add questions and submit it for dean review.", "success")
        return redirect(url_for("new_quiz_manag", usern=session["username"]))

    return render_template("new_quiz.html", chapters=chapters, default_duration=default_duration, **admin_context())


@app.route("/new_question/<string:Admin>", methods=["GET", "POST"])
@login_required("teacher")
def new_question(Admin):
    exam_ids = _teacher_exam_ids()
    exams = quiz.query.filter(quiz.id.in_(exam_ids), quiz.published.is_(False)).order_by(quiz.id.desc()).all() if exam_ids else []
    if request.method == "POST":
        exam_id = request.form.get("quiz_id", type=int)
        exam = db.session.get(quiz, exam_id) if exam_id else None
        statement = request.form.get("statement", "").strip()
        options = [request.form.get(f"opt{i}", "").strip() for i in range(1, 5)]
        correct = request.form.get("correct_opt", "").strip()

        if exam and exam.id not in exam_ids:
            abort(403)
        if exam and (exam.published or exam_attempt.query.filter_by(quiz_id=exam.id).first()):
            flash("Unpublish the exam before changing questions. Exams with attempt history are locked.", "warning")
            return render_template("new_question.html", quizzes=exams, **admin_context()), 409
        if not exam or not statement or not all(options) or correct not in {"1", "2", "3", "4"}:
            flash("Select an exam, enter the question and all four options, and choose the correct option.", "danger")
            return render_template("new_question.html", quizzes=exams, **admin_context()), 400

        created = questions(
            quiz_id=exam.id,
            chapter_id=exam.chapter_id,
            question_statement=statement,
            option1=options[0],
            option2=options[1],
            option3=options[2],
            option4=options[3],
            correct_opt=correct,
        )
        db.session.add(created)
        db.session.flush()
        _audit("question_created", "question", created.id, f"quiz={exam.id}")
        db.session.commit()
        flash("Question added to the exam.", "success")
        return redirect(url_for("new_quiz_manag", usern=session["username"]))

    return render_template("new_question.html", quizzes=exams, **admin_context())


@app.route("/delete_chapter/<string:Admin>/<int:chapter_id>", methods=["POST"])
@login_required("teacher")
def delete_chapter(chapter_id, Admin):
    item = db.get_or_404(chapter, chapter_id)
    if item.sub_id not in _teacher_subject_ids():
        abort(403)
    exams = quiz.query.filter_by(chapter_id=item.id).all()
    exam_ids = [exam.id for exam in exams]
    attempts_exist = exam_attempt.query.filter(exam_attempt.quiz_id.in_(exam_ids)).first() if exam_ids else None
    scores_exist = scores.query.filter(scores.quiz_id.in_(exam_ids)).first() if exam_ids else None
    published_exam = quiz.query.filter(quiz.id.in_(exam_ids), quiz.published.is_(True)).first() if exam_ids else None
    if attempts_exist or scores_exist or published_exam:
        flash("Unpublish its exams first; chapters with student history cannot be deleted.", "warning")
        return redirect(url_for("teacher_dash"))

    for exam in exams:
        _delete_quiz_records(exam)
    questions.query.filter_by(chapter_id=item.id).delete(synchronize_session=False)
    db.session.delete(item)
    _audit("chapter_deleted", "chapter", item.id, item.name)
    db.session.commit()
    flash("Chapter and its unused exams were deleted.", "success")
    return redirect(url_for("teacher_dash"))


@app.route("/delete_quiz/<string:Admin>/<int:quiz_id>", methods=["POST"])
@login_required("teacher")
def delete_quiz(Admin, quiz_id):
    exam = db.get_or_404(quiz, quiz_id)
    _require_teacher_exam_access(exam)
    if exam.published:
        flash("Ask the administrator to unpublish this exam before deleting it.", "warning")
        return redirect(url_for("new_quiz_manag", usern=session["username"]))
    if exam_attempt.query.filter_by(quiz_id=quiz_id).first() or scores.query.filter_by(quiz_id=quiz_id).first():
        flash("This exam has attempt history and cannot be deleted.", "warning")
        return redirect(url_for("new_quiz_manag", usern=session["username"]))
    exam_name = exam.remarks or str(exam.id)
    _delete_quiz_records(exam)
    _audit("exam_deleted", "quiz", quiz_id, exam_name)
    db.session.commit()
    flash("Exam deleted.", "success")
    return redirect(url_for("new_quiz_manag", usern=session["username"]))


@app.route("/delete_question/<string:Admin>/<int:question_id>", methods=["POST"])
@login_required("teacher")
def delete_question(Admin, question_id):
    item = db.get_or_404(questions, question_id)
    _require_teacher_exam_access(db.get_or_404(quiz, item.quiz_id))
    if db.session.get(quiz, item.quiz_id).published:
        flash("Ask an administrator to unpublish the exam before changing its questions.", "warning")
        return redirect(url_for("new_quiz_manag", usern=session["username"]))
    if exam_attempt.query.filter_by(quiz_id=item.quiz_id).first():
        flash("Questions cannot be changed after candidates have attempted this exam.", "warning")
        return redirect(url_for("new_quiz_manag", usern=session["username"]))
    question_id = item.id
    db.session.delete(item)
    _audit("question_deleted", "question", question_id)
    db.session.commit()
    flash("Question deleted.", "success")
    return redirect(url_for("new_quiz_manag", usern=session["username"]))


@app.route("/scores", methods=["GET"])
@login_required(["teacher", "admin"])
def get_scores():
    query = (
        db.session.query(scores, user, quiz)
        .join(user, scores.user_id == user.id)
        .join(quiz, scores.quiz_id == quiz.id)
        .order_by(scores.time_stamp_of_attempt.desc())
    )
    if session.get("role") == "teacher":
        exam_ids = _teacher_exam_ids()
        query = query.filter(quiz.id.in_(exam_ids)) if exam_ids else query.filter(db.false())
    rows = query.all()
    attempt_ids = {
        (item.user_id, item.quiz_id): item.id
        for item in exam_attempt.query.filter_by(status="submitted").all()
    }
    return render_template("scores.html", admin_scores=rows, attempt_ids=attempt_ids, **admin_context())


@app.route("/admin/exams/<int:quiz_id>/publish", methods=["POST"])
@login_required("admin")
def publish_exam(quiz_id):
    exam = db.get_or_404(quiz, quiz_id)
    if not exam.questions:
        flash("Add at least one question before publishing this exam.", "warning")
        return redirect(url_for("new_quiz_manag", usern=session["username"]))
    exam.published = True
    _audit("exam_published", "quiz", exam.id, exam.remarks)
    db.session.commit()
    flash(f"{exam.remarks or 'Exam'} is now available to students.", "success")
    return redirect(url_for("admin_dash"))


@app.route("/admin/exams/<int:quiz_id>/unpublish", methods=["POST"])
@login_required("admin")
def unpublish_exam(quiz_id):
    exam = db.get_or_404(quiz, quiz_id)
    if exam_attempt.query.filter_by(quiz_id=exam.id).first() or scores.query.filter_by(quiz_id=exam.id).first():
        flash("An exam with student history cannot be unpublished.", "warning")
        return redirect(url_for("admin_dash"))
    exam.published = False
    _audit("exam_unpublished", "quiz", exam.id, exam.remarks)
    db.session.commit()
    flash("Exam removed from the student examination list.", "success")
    return redirect(url_for("admin_dash"))


@app.route("/admin/settings", methods=["GET", "POST"])
@login_required("admin")
def admin_settings():
    setting = system_setting.query.filter_by(key="default_exam_duration").first()
    pass_setting = system_setting.query.filter_by(key="pass_mark_percent").first()
    default_duration = setting.value if setting else "30"
    pass_mark = pass_setting.value if pass_setting else "50"
    if request.method == "POST":
        duration = request.form.get("default_exam_duration", type=int)
        submitted_pass_mark = request.form.get("pass_mark_percent", type=int)
        submitted_pass_mark = int(pass_mark) if submitted_pass_mark is None else submitted_pass_mark
        if duration is None or not 1 <= duration <= 300 or not 1 <= submitted_pass_mark <= 100:
            flash("Duration must be 1–300 minutes and passing score must be 1–100 percent.", "danger")
            return render_template("admin_settings.html", default_duration=default_duration, pass_mark=pass_mark, **admin_context()), 400
        if setting is None:
            setting = system_setting(key="default_exam_duration", value=str(duration), updated_by=session["username"])
            db.session.add(setting)
        else:
            setting.value = str(duration)
            setting.updated_by = session["username"]
        if pass_setting is None:
            pass_setting = system_setting(key="pass_mark_percent", value=str(submitted_pass_mark), updated_by=session["username"])
            db.session.add(pass_setting)
        else:
            pass_setting.value = str(submitted_pass_mark)
            pass_setting.updated_by = session["username"]
        _audit("setting_changed", "system_setting", None, f"duration={duration}; pass_mark={submitted_pass_mark}")
        db.session.commit()
        flash("System setting saved.", "success")
        return redirect(url_for("admin_settings"))
    return render_template("admin_settings.html", default_duration=default_duration, pass_mark=pass_mark, **admin_context())


@app.route("/admin/audit-logs")
@login_required("admin")
def admin_audit_logs():
    logs = audit_log.query.order_by(audit_log.created_at.desc()).limit(250).all()
    return render_template("admin_audit_logs.html", logs=logs, **admin_context())


# Student compatibility routes
@app.route("/user_dash", methods=["GET", "POST"])
@login_required("student")
def new_user_dash():
    return redirect(url_for("student_exams"))


@app.route("/user_dash/<int:user_id>", methods=["GET", "POST"])
@login_required("student")
def user_dash(user_id):
    if user_id != session["user_id"]:
        abort(403)
    return redirect(url_for("student_exams"))


@app.route("/user_dash/<string:usern>", methods=["GET", "POST"])
@login_required("student")
def user_dashb(usern):
    return redirect(url_for("student_exams"))


@app.route("/user_dash/<string:usern>/<int:user_id>", methods=["GET", "POST"])
@login_required("student")
def users_dashb(usern, user_id):
    if user_id != session["user_id"]:
        abort(403)
    return redirect(url_for("student_exams"))


@app.route("/view_quiz/<string:usern>/<int:user_id>/<int:quiz_id>")
@login_required("student")
def view_quiz(usern, user_id, quiz_id):
    if user_id != session["user_id"]:
        abort(403)
    exam = db.get_or_404(quiz, quiz_id)
    if not exam.published:
        abort(404)
    return render_template("view_quiz.html", quiz=exam, usern=session["username"], user_id=user_id)


@app.route("/start_quiz/<int:user_id>/<string:usern>/<int:quiz_id>/<int:question_id>", methods=["GET", "POST"])
@login_required("student")
def start_quiz(user_id, usern, quiz_id, question_id):
    if user_id != session["user_id"]:
        abort(403)
    return redirect(url_for("student_exams"))


@app.route("/scores/<string:usern>/<int:user_id>")
@login_required("student")
def show_scores(usern, user_id):
    if user_id != session["user_id"]:
        abort(403)
    attempts = exam_attempt.query.filter_by(user_id=user_id).order_by(exam_attempt.started_at.desc()).all()
    attempted_quiz_ids = {item.quiz_id for item in attempts}
    legacy_scores = [
        item for item in scores.query.filter_by(user_id=user_id).order_by(scores.time_stamp_of_attempt.desc()).all()
        if item.quiz_id not in attempted_quiz_ids
    ]
    return render_template(
        "scores.html",
        attempts=attempts,
        user_score=legacy_scores,
        attempt_quiz_ids=attempted_quiz_ids,
        quizzes=quiz.query.all(),
        usern=session["username"],
        user_id=user_id,
    )


@app.route("/search_admin/<string:Admin>")
@login_required("admin")
def search_admin(Admin):
    term = request.args.get("query", "").strip()
    results = {}
    if term:
        pattern = f"%{term}%"
        results["users"] = user.query.filter(user.Full_Name.ilike(pattern)).all()
        results["subjects"] = subject.query.filter(subject.name.ilike(pattern)).all()
        results["quizzes"] = quiz.query.filter(
            or_(quiz.remarks.ilike(pattern), quiz.date_of_quiz.ilike(pattern))
        ).all()
        results["questions"] = questions.query.filter(questions.question_statement.ilike(pattern)).all()
    else:
        results = {"users": [], "subjects": [], "quizzes": [], "questions": []}
    return render_template("search_admin.html", results=results, query=term, **admin_context())


@app.route("/search_user/<string:usern>")
@login_required("student")
def search_user(usern):
    term = request.args.get("query", "").strip()
    pattern = f"%{term}%"
    results = {
        "subjects": subject.query.filter(subject.name.ilike(pattern)).all() if term else [],
        "quizzes": quiz.query.filter(
            or_(quiz.remarks.ilike(pattern), quiz.date_of_quiz.ilike(pattern))
        ).all() if term else [],
    }
    return render_template("search_user.html", results=results, query=term, usern=session["username"])
