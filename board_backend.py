from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import pymysql
import re

app = Flask(__name__)

app.config['MAX_CONTENT_LENGTH'] = 32 * 1024 * 1024

db_setup_conn = pymysql.connect(host='localhost', user='root', password='1234')
cursor = db_setup_conn.cursor()
cursor.execute("CREATE DATABASE IF NOT EXISTS greenplum_db")
db_setup_conn.close()

# [1] DB 연결 설정 (나중에 배포 시 이 부분만 수정하면 돼요!)
# 만약 특수문자가 비번에 있다면 인코딩이 필요하지만, 1234라면 아래대로 가셔도 됩니다.
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:1234@localhost:3306/greenplum_db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

def get_first_image(content):
    # 내용에서 첫 번째 img 태그의 src 주소를 찾아옵니다.
    img_tag = re.search(r'<img [^>]*src="([^"]+)"', content)
    if img_tag:
        return img_tag.group(1)
    return None


# [2] DB 모델
class Post(db.Model):
    __tablename__ = 'board'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    category = db.Column(db.String(20))
    category_class = db.Column(db.String(20))
    title = db.Column(db.String(100), nullable=False)
    content = db.Column(db.Text(4294967295))
    author = db.Column(db.String(50))
    date = db.Column(db.String(20))
    views = db.Column(db.Integer, default=0)
    # [추가] 이 게시글에 달린 댓글들을 가져오는 연결고리 (자바의 @OneToMany 느낌)
    comments = db.relationship('Comment', backref='post', cascade='all, delete-orphan')

class Comment(db.Model):
    __tablename__ = 'comments'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    post_id = db.Column(db.Integer, db.ForeignKey('board.id'), nullable=False) # 어느 글의 댓글인가?
    content = db.Column(db.Text, nullable=False)
    author = db.Column(db.String(50))
    date = db.Column(db.String(20))


# [3] 테이블 자동 생성
with app.app_context():
    db.create_all()


# [4] 라우트: 게시판 목록 (페이징 기능 추가)
@app.route('/')
def index():
    page = request.args.get('page', 1, type=int)
    keyword = request.args.get('search', '')
    category = request.args.get('category', '')  # 카테고리 파라미터 추가

    query = Post.query.order_by(Post.id.desc())

    # 검색어가 있으면 필터링
    if keyword:
        query = query.filter(Post.title.contains(keyword))

    # [추가] 카테고리가 선택되었다면 해당 카테고리 글만 필터링
    if category:
        query = query.filter(Post.category == category)

    pagination = query.paginate(page=page, per_page=10, error_out=False)
    posts = pagination.items

    for post in posts:
        post.thumbnail = get_first_image(post.content)

    return render_template('board.html',
                           posts=posts,
                           pagination=pagination,
                           keyword=keyword,
                           current_category=category)  # 현재 선택된 카테고리 정보 전달

# [5] 라우트: 글쓰기 페이지 이동 및 저장
@app.route('/write', methods=['GET', 'POST'])
def write():
    if request.method == 'POST':
        new_post = Post(
            category=request.form.get('category'),
            category_class=request.form.get('category_class'),
            title=request.form.get('title'),
            content=request.form.get('content'),
            author=request.form.get('author'),
            date=datetime.now().strftime('%Y-%m-%d'),
            views=0
        )
        db.session.add(new_post)
        db.session.commit()
        return redirect(url_for('index'))

    return render_template('board_write.html')


@app.route('/post/<int:post_id>')
def post_detail(post_id):
    post = Post.query.get_or_404(post_id)

    # [추가] 조회수 1 증가
    post.views += 1
    db.session.commit()  # 변경된 값을 DB에 저장

    return render_template('board_detail.html', post=post)


# [7] 라우트: 글 삭제하기 (Delete)
@app.route('/post/<int:post_id>/delete', methods=['POST'])
def delete_post(post_id):
    post = Post.query.get_or_404(post_id)
    db.session.delete(post)
    db.session.commit()
    return redirect(url_for('index'))


# [8] 라우트: 글 수정하기 (Update)
@app.route('/post/<int:post_id>/edit', methods=['GET', 'POST'])
def edit_post(post_id):
    post = Post.query.get_or_404(post_id)

    if request.method == 'POST':
        # 기존 데이터를 사용자가 입력한 데이터로 덮어씁니다.
        post.title = request.form.get('title')
        post.content = request.form.get('content')
        post.author = request.form.get('author')
        post.category = request.form.get('category')
        post.category_class = request.form.get('category_class')

        db.session.commit()  # save() 대신 commit()만 하면 반영됩니다!
        return redirect(url_for('post_detail', post_id=post.id))

    # 수정 화면으로 이동할 때는 기존 데이터를 채워서 보여줍니다.
    return render_template('board_edit.html', post=post)

# [9] 라우트: 댓글 작성 (Create Comment)
@app.route('/post/<int:post_id>/comment', methods=['POST'])
def add_comment(post_id):
    new_comment = Comment(
        post_id=post_id,
        content=request.form.get('content'),
        author=request.form.get('author'),
        date=datetime.now().strftime('%Y-%m-%d %H:%M')
    )
    db.session.add(new_comment)
    db.session.commit()
    return redirect(url_for('post_detail', post_id=post_id))


if __name__ == '__main__':
    # [임시 코드] 딱 한 번만 실행해서 DB 구조를 바꿉니다!
    with app.app_context():
        # 직접 SQL 명령어를 날려서 content 타입을 LONGTEXT로 변경합니다.
        db.session.execute(db.text("ALTER TABLE board MODIFY content LONGTEXT"))
        db.session.commit()
        print("✅ DB 구조가 성공적으로 변경되었습니다!")

    app.run(debug=True)