from database import db


# User Table
class user(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    userName = db.Column(db.String(100), unique=True, nullable=False)  
    Password = db.Column(db.String(255), nullable=False)
    Full_Name = db.Column(db.String(150), nullable=False)
    Qualification = db.Column(db.String(100))
    DOB = db.Column(db.Integer)

    score = db.relationship('scores', backref='user')

# Admin Table 
class admin_table(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    Password = db.Column(db.String(255), nullable=False)

# Subject Table
class subject(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    Description = db.Column(db.Text)

    chapters = db.relationship('chapter', backref='subject')  

# Chapter Table
class chapter(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sub_id = db.Column(db.Integer, db.ForeignKey('subject.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    Description = db.Column(db.Text)

    Quiz = db.relationship('quiz', backref='chapter')  
    questions = db.relationship('questions', backref='chapter')  
    


class quiz(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    chapter_id= db.Column(db.Integer,db.ForeignKey('chapter.id'), nullable=False)
    date_of_quiz= db.Column(db.Text)
    time_duration= db.Column(db.String(10))  
    remarks= db.Column(db.Text)
    quesion_id=db.Column(db.Integer, nullable=False)

    questions= db.relationship('questions', backref='quiz')
    score= db.relationship('scores', backref='quiz')  

# Question Table
class questions(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    quiz_id = db.Column(db.Integer,db.ForeignKey('quiz.id'),nullable=False)
    chapter_id = db.Column(db.Integer, db.ForeignKey('chapter.id'), nullable=False)
    question_statement = db.Column(db.Text, nullable=False)
    option1 = db.Column(db.String(255), nullable=False)
    option2 = db.Column(db.String(255), nullable=False)
    option3 = db.Column(db.String(255), nullable=False)
    option4 = db.Column(db.String(255), nullable=False)
    correct_opt = db.Column(db.String(255), nullable=False)

# Score Table
class scores(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    quiz_id = db.Column(db.Integer,db.ForeignKey('quiz.id'), nullable=False)
    user_id = db.Column(db.Integer,db.ForeignKey('user.id'), nullable=False)
    time_stamp_of_attempt = db.Column(db.DateTime, default=db.func.current_timestamp())
    total_scored = db.Column(db.Integer)
    completed_at = db.Column(db.DateTime)


class exam_attempt(db.Model):
    """One immutable, server-timed examination attempt per user and quiz."""
    id = db.Column(db.Integer, primary_key=True)
    quiz_id = db.Column(db.Integer, db.ForeignKey('quiz.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    started_at = db.Column(db.DateTime, nullable=False, default=db.func.current_timestamp())
    submitted_at = db.Column(db.DateTime)
    score = db.Column(db.Integer)
    total_questions = db.Column(db.Integer, nullable=False, default=0)
    status = db.Column(db.String(20), nullable=False, default='in_progress')
    __table_args__ = (db.UniqueConstraint('quiz_id', 'user_id', name='one_attempt_per_user_quiz'),)
    answers = db.relationship('answer_record', backref='attempt', cascade='all, delete-orphan')


class answer_record(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    attempt_id = db.Column(db.Integer, db.ForeignKey('exam_attempt.id'), nullable=False, index=True)
    question_id = db.Column(db.Integer, db.ForeignKey('questions.id'), nullable=False)
    selected_option = db.Column(db.String(1))
    is_correct = db.Column(db.Boolean, nullable=False, default=False)
    __table_args__ = (db.UniqueConstraint('attempt_id', 'question_id', name='one_answer_per_question'),)
