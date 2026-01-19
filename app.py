# -*- coding: utf-8 -*-
from flask import Flask, render_template, request, redirect, url_for
import requests
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import pymysql
import re
import os

# 1. 블루프린트 가져오기
from services import services_bp

print("YOUTUBE API 키 로드됨:", bool(os.environ.get('MY_YOUTUBE_KEY')))
print("GEMINI API 키 로드됨:", bool(os.environ.get('MY_GEMINI_KEY')))
print("STEAM API 키 로드됨:", bool(os.environ.get('MY_STEAM_KEY')))
print("DISCORD WEBHOOK 로드됨:", bool(os.environ.get('DISCORD_WEBHOOK_URL')))

app = Flask(__name__, static_folder='static', static_url_path='/static')
app.config['MAX_CONTENT_LENGTH'] = 32 * 1024 * 1024

# 2. DB 연결 설정 및 로컬 환경 자동화
database_url = os.environ.get('DATABASE_URL')

if database_url:
    # 만약 주소가 postgres://로 시작하면 postgresql://로 바꿔라
    if database_url.startswith("postgres://"):
        app.config['SQLALCHEMY_DATABASE_URI'] = database_url.replace("postgres://", "postgresql://", 1)
    else:
        app.config['SQLALCHEMY_DATABASE_URI'] = database_url
else:
    # [로컬 환경] 내 컴퓨터의 MySQL 연결
    # 로컬일 때만 DB 자동 생성 시도
    try:
        db_setup_conn = pymysql.connect(host='localhost', user='root', password='1234')
        cursor = db_setup_conn.cursor()
        cursor.execute("CREATE DATABASE IF NOT EXISTS greenplum_db")
        db_setup_conn.close()
    except Exception as e:
        print(f"로컬 DB 생성 알림: {e}")

    app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:1234@localhost:3306/greenplum_db'

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# 3. 블루프린트 등록
app.register_blueprint(services_bp)

# --- 이하 모델 정의 및 라우트(동일함) ---
# (Post, Comment 모델 정의 및 @app.route 코드들...)


# 5. 유틸리티 함수
def get_first_image(content):
    img_tag = re.search(r'<img [^>]*src="([^"]+)"', content)
    return img_tag.group(1) if img_tag else None

# [이하 모델 정의 생략 - 초록자두님의 기존 코드와 동일]
class Post(db.Model):
    __tablename__ = 'board'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    category = db.Column(db.String(50))
    category_class = db.Column(db.String(20))
    title = db.Column(db.String(100), nullable=False)
    # 💡 숫자를 지우고 그냥 db.Text만 남겨주세요. PostgreSQL에서는 이게 무제한입니다!
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

# ⭐ 바로 여기! 모델 정의가 끝난 직후에 배치하세요.
with app.app_context():
    db.create_all()

# [라우트 함수들 동일...]
@app.route('/')
def main_home(): return render_template('index.html')


@app.route('/send_discord', methods=['POST'])
def send_discord():
    # 1. HTML에서 보낸 데이터를 받습니다.
    data = request.json

    # 2. 환경변수에 숨겨둔 진짜 디스코드 주소를 가져옵니다.
    # (Render 설정창에 DISCORD_WEBHOOK_URL 이라는 이름으로 주소를 저장해두세요!)
    webhook_url = os.environ.get("DISCORD_WEBHOOK_URL")

    if not webhook_url:
        return {"status": "error", "message": "웹훅 주소가 설정되지 않았습니다."}, 500

    # 3. 서버가 대신 디스코드로 쏩니다!
    response = requests.post(webhook_url, json=data)

    return {"status": "success"}, 204

@app.route('/board')
def index():
    # ⭐ 1. 주소창에 ?mode=plum 이 있는지 확인하는 코드 추가
    is_admin = request.args.get('mode') == 'plum'

    page = request.args.get('page', 1, type=int)
    keyword = request.args.get('search', '')
    category = request.args.get('category', '')
    sort = request.args.get('sort', 'new')

    query = Post.query
    if keyword: query = query.filter(Post.title.contains(keyword))
    if category: query = query.filter(Post.category == category)

    if sort == 'views':
        query = query.order_by(Post.views.desc())
    else:
        query = query.order_by(Post.id.desc())

    pagination = query.paginate(page=page, per_page=10, error_out=False)
    posts = pagination.items
    for post in posts: post.thumbnail = get_first_image(post.content)

    # ⭐ 2. return 할 때 마지막에 is_admin=is_admin 을 꼭 넣어주세요!
    return render_template('board.html',
                           posts=posts,
                           pagination=pagination,
                           keyword=keyword,
                           current_category=category,
                           current_sort=sort,
                           is_admin=is_admin)

@app.route('/write', methods=['GET', 'POST'])
def write():
    if request.method == 'POST':
        new_post = Post(category=request.form.get('category'), category_class=request.form.get('category_class'), title=request.form.get('title'), content=request.form.get('content'), author=request.form.get('author'), date=datetime.now().strftime('%Y-%m-%d'), views=0)
        db.session.add(new_post)
        db.session.commit()
        return redirect(url_for('index'))
    return render_template('board_write.html')

@app.route('/post/<int:post_id>')
def post_detail(post_id):
    post = Post.query.get_or_404(post_id)
    post.views += 1
    db.session.commit()
    return render_template('board_detail.html', post=post)

@app.route('/post/<int:post_id>/delete', methods=['POST'])
def delete_post(post_id):
    post = Post.query.get_or_404(post_id)
    db.session.delete(post)
    db.session.commit()
    return redirect(url_for('index'))

@app.route('/post/<int:post_id>/edit', methods=['GET', 'POST'])
def edit_post(post_id):
    post = Post.query.get_or_404(post_id)
    if request.method == 'POST':
        post.title = request.form.get('title'); post.content = request.form.get('content'); post.author = request.form.get('author'); post.category = request.form.get('category'); post.category_class = request.form.get('category_class')
        db.session.commit()
        return redirect(url_for('post_detail', post_id=post.id))
    return render_template('board_edit.html', post=post)

@app.route('/post/<int:post_id>/comment', methods=['POST'])
def add_comment(post_id):
    new_comment = Comment(post_id=post_id, content=request.form.get('content'), author=request.form.get('author'), date=datetime.now().strftime('%Y-%m-%d %H:%M'))
    db.session.add(new_comment); db.session.commit()
    return redirect(url_for('post_detail', post_id=post_id))

# app.py 하단 적당한 곳에 추가
@app.route('/board/delete_all', methods=['POST'])
def delete_all_posts():
    try:
        # 1. 모든 댓글 먼저 삭제 (참조 무결성 때문!)
        Comment.query.delete()
        # 2. 모든 게시글 삭제
        Post.query.delete()
        db.session.commit()
        return redirect(url_for('index'))
    except Exception as e:
        db.session.rollback()
        return f"삭제 중 에러 발생: {e}"

@app.route('/setup-db')
def setup_db():
    try:
        db.create_all()
        return "✅ 데이터베이스 테이블 생성 완료!"
    except Exception as e:
        return f"❌ 에러 발생: {e}"

# 8. 실행
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        # 로컬(MySQL)일 때만 데이터 타입 변경 실행
        if not os.environ.get('DATABASE_URL'):
            try:
                db.session.execute(db.text("ALTER TABLE board MODIFY content LONGTEXT"))
                db.session.commit()
                print("✅ 로컬 MySQL 구조 업데이트 완료!")
            except Exception as e:
                print(f"로컬 알림: {e}")

    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port, debug=True)