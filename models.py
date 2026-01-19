# models.py
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

# --- [게시판 설계도] ---
class Post(db.Model):
    __tablename__ = 'board'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    category = db.Column(db.String(50))
    category_class = db.Column(db.String(20))
    title = db.Column(db.String(100), nullable=False)
    content = db.Column(db.Text)
    author = db.Column(db.String(50))
    date = db.Column(db.String(20))
    views = db.Column(db.Integer, default=0)
    comments = db.relationship('Comment', backref='post', cascade='all, delete-orphan')

class Comment(db.Model):
    __tablename__ = 'comments'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    post_id = db.Column(db.Integer, db.ForeignKey('board.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    author = db.Column(db.String(50))
    date = db.Column(db.String(20))

# --- [캘린더 설계도] ---
class Event(db.Model):
    __tablename__ = 'calendar_events'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    start_date = db.Column(db.String(20), nullable=False)
    end_date = db.Column(db.String(20))
    user_name = db.Column(db.String(20))
    color = db.Column(db.String(10))
    password = db.Column(db.String(100), nullable=False)
    todos = db.relationship('Todo', backref='event', cascade='all, delete-orphan')

class Todo(db.Model):
    __tablename__ = 'calendar_todos'
    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey('calendar_events.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    is_done = db.Column(db.Boolean, default=False)
    completed_at = db.Column(db.String(30))