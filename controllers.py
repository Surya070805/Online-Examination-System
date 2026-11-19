from flask import Flask, render_template, request, redirect,url_for,session, abort, flash
from flask import current_app as app
from sqlalchemy import func
import os
from datetime import datetime, timedelta, timezone
from functools import wraps
from werkzeug.security import check_password_hash, generate_password_hash

from models import *


def utc_now():
    # SQLite stores these UTC timestamps without timezone metadata.
    return datetime.now(timezone.utc).replace(tzinfo=None)


def login_required(role=None):
    def decorate(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if not session.get('user_id'):
                return redirect(url_for('login'))
            if role and session.get('role') != role:
                abort(403)
            return view(*args, **kwargs)
        return wrapped
    return decorate


@app.route('/')
def index():
    return redirect(url_for('login'))
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        founder_user = user.query.filter_by(userName=username).first()
        admin=admin_table.query.filter_by(username=username).first()
        if founder_user:
            if founder_user.Password.startswith(('pbkdf2:', 'scrypt:')):
                valid = check_password_hash(founder_user.Password, password)
            else:  # Upgrade existing plaintext accounts after a successful login.
                valid = founder_user.Password == password
                if valid:
                    founder_user.Password = generate_password_hash(password)
                    db.session.commit()
            if valid:
                session.clear(); session['user_id'] = founder_user.id; session['role'] = 'student'; session['username'] = username; session.permanent = True
                return redirect(url_for('student_exams'))
            return render_template('login.html', message='Invalid username or password'), 401
        else:
            if admin:
                if admin.Password.startswith(('pbkdf2:', 'scrypt:')):
                    valid = check_password_hash(admin.Password, password)
                else:
                    valid = admin.Password == password
                    if valid:
                        admin.Password = generate_password_hash(password); db.session.commit()
                if valid:
                    session.clear(); session['user_id'] = admin.id; session['role'] = 'admin'; session['username'] = username; session.permanent = True
                    return redirect(url_for('admin_dash'))
            return render_template('login.html', message='Invalid username or password'), 401
    return render_template('login.html')
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        fullname= request.form['name']
        qualification= request.form['qualification']
        dob=request.form['dob']
        exist_user=user.query.filter_by(userName=username).first()
        print("hell")
        if exist_user:
            return render_template("login.html", message="Username already exists")
        else:
            print("hello")
            new_user = user(userName=username, Password=generate_password_hash(password), Full_Name=fullname, Qualification=qualification, DOB=dob)
            db.session.add(new_user)
            db.session.commit()
            return redirect("/login")
    return render_template('register.html')


@app.route('/logout', methods=['POST', 'GET'])
def logout():
    session.clear()
    return redirect(url_for('login'))


@app.route('/exams')
@login_required('student')
def student_exams():
    return render_template('exam_list.html', quizzes=quiz.query.order_by(quiz.id.desc()).all(), username=session['username'])


@app.route('/exam/<int:quiz_id>/start', methods=['POST'])
@login_required('student')
def exam_start(quiz_id):
    exam = db.get_or_404(quiz, quiz_id)
    if exam_attempt.query.filter_by(quiz_id=quiz_id, user_id=session['user_id']).first():
        flash('An attempt has already been started or submitted for this exam.')
        return redirect(url_for('student_exams'))
    if not exam.questions:
        flash('This exam has no questions yet.')
        return redirect(url_for('student_exams'))
    duration = max(1, int(exam.time_duration or 30))
    attempt = exam_attempt(quiz_id=quiz_id, user_id=session['user_id'], total_questions=len(exam.questions))
    db.session.add(attempt); db.session.commit()
    return redirect(url_for('exam_take', attempt_id=attempt.id))


@app.route('/exam/attempt/<int:attempt_id>', methods=['GET', 'POST'])
@login_required('student')
def exam_take(attempt_id):
    attempt = exam_attempt.query.filter_by(id=attempt_id, user_id=session['user_id']).first_or_404()
    exam = db.get_or_404(quiz, attempt.quiz_id)
    if attempt.status != 'in_progress':
        return redirect(url_for('exam_result', attempt_id=attempt.id))
    duration = max(1, int(exam.time_duration or 30))
    expires = attempt.started_at + timedelta(minutes=duration)
    if utc_now() >= expires:
        attempt.score = 0; attempt.submitted_at = utc_now(); attempt.status = 'submitted'
        db.session.add(scores(quiz_id=attempt.quiz_id, user_id=attempt.user_id, total_scored=0, completed_at=attempt.submitted_at))
        db.session.commit()
        return redirect(url_for('exam_result', attempt_id=attempt.id))
    if request.method == 'POST':
        now = utc_now()
        # Accept only option indexes from the posted form; compute every point on the server.
        posted = request.form
        for question in exam.questions:
            selected = posted.get(f'q_{question.id}', '')
            if selected not in ('1', '2', '3', '4'):
                selected = None
            db.session.add(answer_record(attempt_id=attempt.id, question_id=question.id,
                                         selected_option=selected,
                                         is_correct=bool(selected and selected == str(question.correct_opt))))
        attempt.score = sum(1 for a in answer_record.query.filter_by(attempt_id=attempt.id).all() if a.is_correct)
        attempt.submitted_at = now; attempt.status = 'submitted'
        score = scores(quiz_id=attempt.quiz_id, user_id=attempt.user_id, total_scored=attempt.score, completed_at=now)
        db.session.add(score); db.session.commit()
        return redirect(url_for('exam_result', attempt_id=attempt.id))
    return render_template('exam_take.html', attempt=attempt, exam=exam, questions=exam.questions,
                           expires_at=expires.isoformat() + 'Z')


@app.route('/exam/result/<int:attempt_id>')
@login_required()
def exam_result(attempt_id):
    attempt = db.get_or_404(exam_attempt, attempt_id)
    if session.get('role') != 'admin' and attempt.user_id != session['user_id']:
        abort(403)
    return render_template('exam_result.html', attempt=attempt, exam=db.get_or_404(quiz, attempt.quiz_id))

@app.route('/new_chapter/<string:Admin>', methods=['GET', 'POST'])
@login_required('admin')
def new_chapter(Admin):
    if request.method == 'POST':
        Admin=Admin
        subjects = subject.query.all()
        chapter_name = request.form['chap_name']
        chap_id=request.form["chapter_id"]
        subj_id=request.form["subj_id"]
        descript=request.form.get("descrip")
        new_chap=chapter(name=chapter_name,sub_id=subj_id,id=chap_id,Description=descript)
        db.session.add(new_chap)
        db.session.commit()
        
        return render_template("admin_dashbord.html",Admin=Admin,subjects=subjects)
         
    return render_template('new_chapter.html',Admin=Admin)

@app.route('/new_subject/<string:Admin>', methods=['GET', 'POST'])
@login_required('admin')
def new_subject(Admin):
    if request.method == 'POST':
        Admin=Admin
        subjects = subject.query.all()
        sub_id=request.form["subj_id"]
        subj_name = request.form['subj']
        description=request.form.get("desc")
        new_chap=subject(name=subj_name,id=sub_id,Description=description)
        db.session.add(new_chap)
        db.session.commit()
        return render_template("admin_dashbord.html",Admin=Admin,subjects=subjects)
    return render_template('new_subject.html',Admin=Admin)

    
@app.route('/admin_dash/<string:Admin>', methods=['GET', 'POST'])
@login_required('admin')
def new_admin_dash(Admin):
    if request.method == 'POST':
        subjects = subject.query.all()  
        return render_template('admin_dashbord.html', subjects=subjects,Admin=Admin)    
    elif request.method == 'GET':
        subjects = subject.query.all()  
        return render_template('admin_dashbord.html', subjects=subjects,Admin=Admin)  
    else:
        subjects = subject.query.all()  
        return render_template('admin_dashbord.html', subjects=subjects,Admin=Admin) 
    
@app.route('/admin_dash', methods=['GET', 'POST'])
@login_required('admin')
def admin_dash():
    if request.method == 'POST':
        subjects = subject.query.all()  
        return render_template('admin_dashbord.html', subjects=subjects)    
    elif request.method == 'GET':
        subjects = subject.query.all()  
        return render_template('admin_dashbord.html', subjects=subjects)  
    else:
        subjects = subject.query.all()  
        return render_template('admin_dashbord.html', subjects=subjects) 
@app.route('/user_dash', methods=['GET', 'POST'])
@login_required('student')
def new_user_dash():
    if request.method == 'POST':
        quizzes = quiz.query.all()  
        return render_template('user_dashboard.html', quizzes=quizzes) 
    elif request.method == 'GET':
        quizzes = quiz.query.all()  
        return render_template('user_dashboard.html', quizzes=quizzes)
    else:
        quizzes = quiz.query.all()  
        return render_template('user_dashboard.html', quizzes=quizzes)
@app.route('/user_dash/<int:user_id>', methods=['GET', 'POST'])
@login_required('student')
def user_dash(user_id):
    if user_id != session['user_id']:
        abort(403)
    if request.method == 'POST':
        user_id=user_id
        quizzes = quiz.query.all()  
        return render_template('user_dashboard.html', quizzes=quizzes,user_id=user_id) 
    elif request.method == 'GET':
        quizzes = quiz.query.all()  
        return render_template('user_dashboard.html', quizzes=quizzes,user_id=user_id)
    else:
        quizzes = quiz.query.all()  
        return render_template('user_dashboard.html', quizzes=quizzes,user_id=user_id)
@app.route('/user_dash/<string:usern>', methods=['GET', 'POST'])
@login_required('student')
def user_dashb(usern):
    if request.method == 'POST':
        quizzes = quiz.query.all()  
        return render_template('user_dashboard.html', quizzes=quizzes,usern=usern) 
    elif request.method == 'GET':
        quizzes = quiz.query.all()  
        return render_template('user_dashboard.html', quizzes=quizzes,usern=usern)
    else:
        quizzes = quiz.query.all()  
        return render_template('user_dashboard.html', quizzes=quizzes,userm=usern)
     
@app.route('/user_dash/<string:usern>/<int:user_id>', methods=['GET', 'POST'])
@login_required('student')
def users_dashb(usern,user_id):
    if user_id != session['user_id']:
        abort(403)
    
    if request.method == 'POST':
        quizzes = quiz.query.all()  
        return render_template('user_dashboard.html', quizzes=quizzes,usern=usern,user_id=user_id) 
    elif request.method == 'GET':
        quizzes = quiz.query.all()
        return render_template('user_dashboard.html', quizzes=quizzes,usern=usern,user_id=user_id)
    else:
        quizzes = quiz.query.all()  
        return render_template('user_dashboard.html', quizzes=quizzes,userm=usern,user_id=user_id)
     
@app.route('/quiz_manag/<string:usern>', methods=['GET', 'POST'])
@login_required('admin')
def new_quiz_manag(usern):
    if request.method == 'get':
        quizzes = quiz.query.all()  
        return render_template('quiz_management.html', quizzes=quizzes,Admin=usern)
    elif request.method=="post":
        quizzes = quiz.query.all()  
        return render_template('quiz_management.html', quizzes=quizzes,Admin=usern)
    else:
        quizzes = quiz.query.all()  
        return render_template('quiz_management.html', quizzes=quizzes,Admin=usern)
    
@app.route('/new_quiz/<string:Admin>', methods=['GET', 'POST'])
@login_required('admin')
def new_quiz(Admin):
    if request.method == 'POST':
        Admin=Admin
        quizzes = quiz.query.all()
        chap_id=request.form["chapter_id"]
        quiz_id=request.form["quiz_id"]
        date=request.form["date"]
        duriation=request.form["duration"]
        question_id=request.form["quest_id"]
        new_quiz=quiz(id=quiz_id,chapter_id=chap_id,date_of_quiz=date,time_duration=duriation,quesion_id=question_id)
        db.session.add(new_quiz)
        db.session.commit()
        return render_template("quiz_management.html",quizzes=quizzes,Admin=Admin)
        
    return render_template('new_quiz.html',Admin=Admin)
@app.route('/new_question/<string:Admin>', methods=['GET', 'POST'])
@login_required('admin')
def new_question(Admin):
    Admin=Admin
    if request.method == 'POST':
        quizzes = quiz.query.all()
        quest_id=request.form["ques_id"]
        chap_id=request.form["chapter_id"]
        quiz_id=request.form["quiz_id"]
        quest_titl=request.form["title"]
        quest_opt1=request.form["opt1"]
        quest_opt2=request.form["opt2"]
        quest_opt3=request.form["opt3"]
        quest_opt4=request.form["opt4"]
        quest_correct_opt=request.form["correct_opt"]
        
        new_ques=questions(id=quest_id,quiz_id=quiz_id,chapter_id=chap_id,question_statement=quest_titl,option1=quest_opt1,option2=quest_opt2,option3=quest_opt3,option4=quest_opt4,correct_opt=quest_correct_opt)
        db.session.add(new_ques)
        db.session.commit()
        return render_template("quiz_management.html",quizzes=quizzes,Admin=Admin)
    return render_template('new_question.html',Admin=Admin)

@app.route('/view_quiz/<string:usern>/<int:user_id>/<int:quiz_id>')
@login_required('student')
def view_quiz(quiz_id,usern,user_id):
    if user_id != session['user_id']:
        abort(403)
    usern=usern
    users_id=user_id
    q = db.session.get(quiz, quiz_id)
    subj=subject.query.all()
    return render_template("view_quiz.html", quiz=q,sub=subj,usern=usern,user_id=users_id)

@app.route('/start_quiz/<int:user_id>/<string:usern>/<int:quiz_id>/<int:question_id>', methods=['GET', 'POST'])
@login_required('student')
def start_quiz(user_id, usern,quiz_id, question_id):
    # Legacy incremental scoring endpoint is retired; use atomic exam attempts.
    if user_id != session['user_id']:
        abort(403)
    return redirect(url_for('student_exams'))
    question = questions.query.filter_by(id=question_id, quiz_id=quiz_id).first()
    total_questions = questions.query.filter_by(quiz_id=quiz_id).count()
    quizs = db.session.get(quiz, quiz_id)
    
    if not question:
        return redirect(f'/view_quiz/{usern}/{user_id}/{quiz_id}')  


    if request.method == 'POST':
        selected_option = request.form.get("option")
        if selected_option:
            correct_answer = question.correct_opt  
            score_entry = scores.query.filter_by(quiz_id=quiz_id, user_id=user_id).first()
            
            if  (not score_entry):
                score_entry = scores(quiz_id=quiz_id, user_id=user_id, total_scored=0)
                db.session.add(score_entry)
                db.session.commit()

            if (selected_option) == (correct_answer) :
                score_entry.total_scored += 1
                db.session.add(score_entry)
                db.session.commit()


        question_id_str = str(question_id)
        third_digit = int(question_id_str[2]) if len(question_id_str) > 2 else 0


        if total_questions > third_digit:
            next_question = questions.query.filter(
                questions.id > question_id,
                questions.quiz_id == quiz_id
            ).order_by(questions.id).first()
        else:
            next_question = None  

        
        if next_question:
            return redirect(f"/start_quiz/{user_id}/{usern}/{quiz_id}/{next_question.id}")
        else:
            return redirect(f'/scores/{usern}/{user_id}')
    
    return render_template("start_quiz.html", question=question,user_id=user_id,quiz_id=quiz_id, total_questions=total_questions,quiz=quizs,usern=usern)




@app.route('/scores', methods=['GET', 'POST'])
@login_required('admin')
def get_scores():
    quizzes = quiz.query.all()  
    ques = questions.query.all()  
    return render_template('scores.html', quizzes=quizzes, questions=ques)

@app.route('/scores/<string:usern>/<int:user_id>')
@login_required('student')
def show_scores(user_id,usern):
    if user_id != session['user_id']:
        abort(403)
    usern=usern
    quizs = quiz.query.all()
    user_score = scores.query.filter_by(user_id=user_id).all()
    return render_template("scores.html", quizzes=quizs, user_score=user_score,usern=usern,user_id=user_id)

@app.route('/search/<string:Admin>',methods=['GET', 'POST'])
def search_admin(Admin):
    if session.get('role') != 'admin':
        abort(403)
    Admin=Admin
    query = request.args.get('query', '').strip()
    if not query:
        return render_template('search_admin.html', results={}, query=query,Admin=Admin)

    results = {}

    results["users"] = user.query.filter(user.Full_Name.ilike(f"%{query}%")).all()
    results["subjects"] = subject.query.filter(subject.name.ilike(f"%{query}%")).all()
    results["quizzes"] = quiz.query.filter(quiz.date_of_quiz.ilike(f"%{query}%")).all()
    results["questions"] = questions.query.filter(questions.question_statement.ilike(f"%{query}%")).all()

   
    results["subjects"] = subject.query.filter(subject.name.ilike(f"%{query}%")).all()
    results["quizzes"] = quiz.query.filter(quiz.date_of_quiz.ilike(f"%{query}%")).all()
    return render_template('search_admin.html', results={}, query=query,Admin=Admin)

@app.route('/search/<string:usern>',methods=['GET', 'POST'])
def search_user(usern):
    if session.get('role') != 'student':
        abort(403)
    usern=usern
    query = request.args.get('query', '').strip()
    if not query:
        return render_template('search_user.html', results={}, query=query,usern=usern)

    results = {}

    results["users"] = user.query.filter(user.Full_Name.ilike(f"%{query}%")).all()
    results["subjects"] = subject.query.filter(subject.name.ilike(f"%{query}%")).all()
    results["quizzes"] = quiz.query.filter(quiz.date_of_quiz.ilike(f"%{query}%")).all()
    results["questions"] = questions.query.filter(questions.question_statement.ilike(f"%{query}%")).all()

   
    results["subjects"] = subject.query.filter(subject.name.ilike(f"%{query}%")).all()
    results["quizzes"] = quiz.query.filter(quiz.date_of_quiz.ilike(f"%{query}%")).all()
    return render_template('search_user.html', results={}, query=query,usern=usern)


@app.route('/delete_chapter/<string:Admin>/<int:chapter_id>',methods=["post"])
@login_required('admin')
def delete_chapter(chapter_id,Admin):
    Admin=Admin
    chapters = db.session.get(chapter, chapter_id)
    question = db.session.get(questions, chapter_id)
    quiz.query.filter_by(chapter_id=chapter_id).delete()
    db.session.delete(chapters)
    db.session.delete(question)
    db.session.commit()
    subjects = subject.query.all()
    return render_template('admin_dashbord.html', subjects=subjects)


