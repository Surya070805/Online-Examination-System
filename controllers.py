"""Routes for authentication, examination delivery, and administrator workflows."""
from datetime import datetime, timedelta, timezone
from functools import wraps

from flask import abort, current_app as app, flash, redirect, render_template, request, session, url_for
from sqlalchemy import or_
from werkzeug.security import check_password_hash, generate_password_hash

from database import db
from models import (
    admin_table,
    answer_record,
    chapter,
    exam_attempt,
    questions,
    quiz,
    scores,
    subject,
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
            if role and session.get("role") != role:
                abort(403)
            return view(*args, **kwargs)
        return wrapped
    return decorate


def admin_context():
    return {"Admin": session.get("username", "Admin")}


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
        session["role"] = "student" if candidate else "admin"
        session["username"] = username
        session.permanent = True
        return redirect(url_for("student_exams" if candidate else "admin_dash"))

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
        ))
        db.session.commit()
        flash("Account created. Sign in to see available exams.")
        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/logout", methods=["GET", "POST"])
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/exams")
@login_required("student")
def student_exams():
    exams = quiz.query.order_by(quiz.id.desc()).all()
    return render_template("exam_list.html", quizzes=exams, username=session["username"])


@app.route("/exam/<int:quiz_id>/start", methods=["POST"])
@login_required("student")
def exam_start(quiz_id):
    exam = db.get_or_404(quiz, quiz_id)
    existing = exam_attempt.query.filter_by(quiz_id=quiz_id, user_id=session["user_id"]).first()
    if existing:
        flash("You have already used your attempt for this exam.")
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
    if session.get("role") != "admin" and attempt.user_id != session["user_id"]:
        abort(403)
    return render_template(
        "exam_result.html",
        attempt=attempt,
        exam=db.get_or_404(quiz, attempt.quiz_id),
    )


# Administrator dashboard and content management
@app.route("/admin_dash", methods=["GET"])
@login_required("admin")
def admin_dash():
    return render_template(
        "admin_dashbord.html",
        subjects=subject.query.order_by(subject.name).all(),
        **admin_context(),
    )


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
        db.session.add(subject(name=name, Description=description or None))
        db.session.commit()
        flash(f"Subject “{name}” was created.", "success")
        return redirect(url_for("admin_dash"))

    return render_template("new_subject.html", **admin_context())


@app.route("/new_chapter/<string:Admin>", methods=["GET", "POST"])
@login_required("admin")
def new_chapter(Admin):
    subjects = subject.query.order_by(subject.name).all()
    if request.method == "POST":
        name = request.form.get("chap_name", "").strip()
        description = request.form.get("descrip", "").strip()
        subject_id = request.form.get("subj_id", type=int)
        parent_subject = db.session.get(subject, subject_id) if subject_id else None
        if not name or not parent_subject:
            flash("Choose a subject and enter a chapter name.", "danger")
            return render_template("new_chapter.html", subjects=subjects, **admin_context()), 400
        duplicate = chapter.query.filter_by(sub_id=subject_id, name=name).first()
        if duplicate:
            flash("That chapter already exists under this subject.", "warning")
            return render_template("new_chapter.html", subjects=subjects, **admin_context()), 409
        db.session.add(chapter(
            sub_id=subject_id,
            name=name,
            Description=description or None,
        ))
        db.session.commit()
        flash(f"Chapter “{name}” was created.", "success")
        return redirect(url_for("admin_dash"))

    return render_template("new_chapter.html", subjects=subjects, **admin_context())


@app.route("/quiz_manag/<string:usern>", methods=["GET", "POST"])
@login_required("admin")
def new_quiz_manag(usern):
    exams = quiz.query.order_by(quiz.id.desc()).all()
    return render_template("quiz_management.html", quizzes=exams, **admin_context())


@app.route("/new_quiz/<string:Admin>", methods=["GET", "POST"])
@login_required("admin")
def new_quiz(Admin):
    chapters = chapter.query.order_by(chapter.name).all()
    if request.method == "POST":
        name = request.form.get("remarks", "").strip()
        chapter_id = request.form.get("chapter_id", type=int)
        duration = request.form.get("duration", type=int)
        date_of_quiz = request.form.get("date", "").strip()
        selected_chapter = db.session.get(chapter, chapter_id) if chapter_id else None

        if not selected_chapter or not name or not date_of_quiz or not duration or not 1 <= duration <= 300:
            flash("Choose a chapter, enter an exam name and date, and use a duration from 1 to 300 minutes.", "danger")
            return render_template("new_quiz.html", chapters=chapters, **admin_context()), 400

        try:
            datetime.strptime(date_of_quiz, "%Y-%m-%d")
        except ValueError:
            flash("Enter a valid exam date.", "danger")
            return render_template("new_quiz.html", chapters=chapters, **admin_context()), 400

        exam = quiz(
            chapter_id=chapter_id,
            date_of_quiz=date_of_quiz,
            time_duration=str(duration),
            remarks=name,
            quesion_id=0,
        )
        db.session.add(exam)
        db.session.commit()
        flash(f"Exam “{name}” was created. Add questions before students start it.", "success")
        return redirect(url_for("new_quiz_manag", usern=session["username"]))

    return render_template("new_quiz.html", chapters=chapters, **admin_context())


@app.route("/new_question/<string:Admin>", methods=["GET", "POST"])
@login_required("admin")
def new_question(Admin):
    exams = quiz.query.order_by(quiz.id.desc()).all()
    if request.method == "POST":
        exam_id = request.form.get("quiz_id", type=int)
        exam = db.session.get(quiz, exam_id) if exam_id else None
        statement = request.form.get("statement", "").strip()
        options = [request.form.get(f"opt{i}", "").strip() for i in range(1, 5)]
        correct = request.form.get("correct_opt", "").strip()

        if exam and exam_attempt.query.filter_by(quiz_id=exam.id).first():
            flash("Questions cannot be changed after candidates have attempted this exam.", "warning")
            return render_template("new_question.html", quizzes=exams, **admin_context()), 409
        if not exam or not statement or not all(options) or correct not in {"1", "2", "3", "4"}:
            flash("Select an exam, enter the question and all four options, and choose the correct option.", "danger")
            return render_template("new_question.html", quizzes=exams, **admin_context()), 400

        db.session.add(questions(
            quiz_id=exam.id,
            chapter_id=exam.chapter_id,
            question_statement=statement,
            option1=options[0],
            option2=options[1],
            option3=options[2],
            option4=options[3],
            correct_opt=correct,
        ))
        db.session.commit()
        flash("Question added to the exam.", "success")
        return redirect(url_for("new_quiz_manag", usern=session["username"]))

    return render_template("new_question.html", quizzes=exams, **admin_context())


@app.route("/delete_chapter/<string:Admin>/<int:chapter_id>", methods=["POST"])
@login_required("admin")
def delete_chapter(chapter_id, Admin):
    item = db.get_or_404(chapter, chapter_id)
    exams = quiz.query.filter_by(chapter_id=item.id).all()
    exam_ids = [exam.id for exam in exams]
    attempts_exist = exam_attempt.query.filter(exam_attempt.quiz_id.in_(exam_ids)).first() if exam_ids else None
    scores_exist = scores.query.filter(scores.quiz_id.in_(exam_ids)).first() if exam_ids else None
    if attempts_exist or scores_exist:
        flash("This chapter has exam history and cannot be deleted.", "warning")
        return redirect(url_for("admin_dash"))

    for exam in exams:
        _delete_quiz_records(exam)
    questions.query.filter_by(chapter_id=item.id).delete(synchronize_session=False)
    db.session.delete(item)
    db.session.commit()
    flash("Chapter and its unused exams were deleted.", "success")
    return redirect(url_for("admin_dash"))


@app.route("/delete_quiz/<string:Admin>/<int:quiz_id>", methods=["POST"])
@login_required("admin")
def delete_quiz(Admin, quiz_id):
    exam = db.get_or_404(quiz, quiz_id)
    if exam_attempt.query.filter_by(quiz_id=quiz_id).first() or scores.query.filter_by(quiz_id=quiz_id).first():
        flash("This exam has attempt history and cannot be deleted.", "warning")
        return redirect(url_for("new_quiz_manag", usern=session["username"]))
    _delete_quiz_records(exam)
    db.session.commit()
    flash("Exam deleted.", "success")
    return redirect(url_for("new_quiz_manag", usern=session["username"]))


@app.route("/delete_question/<string:Admin>/<int:question_id>", methods=["POST"])
@login_required("admin")
def delete_question(Admin, question_id):
    item = db.get_or_404(questions, question_id)
    if exam_attempt.query.filter_by(quiz_id=item.quiz_id).first():
        flash("Questions cannot be changed after candidates have attempted this exam.", "warning")
        return redirect(url_for("new_quiz_manag", usern=session["username"]))
    db.session.delete(item)
    db.session.commit()
    flash("Question deleted.", "success")
    return redirect(url_for("new_quiz_manag", usern=session["username"]))


@app.route("/scores", methods=["GET"])
@login_required("admin")
def get_scores():
    rows = (
        db.session.query(scores, user, quiz)
        .join(user, scores.user_id == user.id)
        .join(quiz, scores.quiz_id == quiz.id)
        .order_by(scores.time_stamp_of_attempt.desc())
        .all()
    )
    return render_template("scores.html", admin_scores=rows, **admin_context())


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
    exam_scores = scores.query.filter_by(user_id=user_id).order_by(scores.time_stamp_of_attempt.desc()).all()
    return render_template(
        "scores.html",
        user_score=exam_scores,
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
