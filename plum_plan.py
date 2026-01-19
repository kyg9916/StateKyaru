from flask import Blueprint, render_template, request, jsonify
from datetime import datetime
from models import db, Event, Todo

# 블루프린트 설정 (이름: calendar)
calendar_bp = Blueprint('plum_calendar', __name__)

@calendar_bp.route('/calendar')
def calendar_page():
    return render_template('calendar.html')

@calendar_bp.route('/api/events', methods=['GET'])
def get_events():
    events = Event.query.all()
    event_list = []
    for e in events:
        event_list.append({
            'id': e.id,
            'title': f"[{e.user_name}] {e.title}",
            'start': e.start_date,
            'end': e.end_date,
            'color': e.color
        })
    return jsonify(event_list)

@calendar_bp.route('/api/events', methods=['POST'])
def add_event():
    data = request.json
    new_event = Event(
        title=data['title'], start_date=data['start'], end_date=data['end'],
        user_name=data['user_name'], color=data['color'],
        password=data['password']
    )
    db.session.add(new_event)
    db.session.commit()
    return jsonify({'status': 'success'})

@calendar_bp.route('/api/events/modify/<int:event_id>', methods=['POST'])
def modify_event(event_id):
    data = request.json
    event = Event.query.get_or_404(event_id)
    if event.password != data.get('password'):
        return jsonify({'status': 'fail', 'message': '비밀번호 틀림'}), 401
    event.title = data['title']
    event.start_date = data['start']
    event.end_date = data['end']
    event.user_name = data['user_name']
    event.color = data['color']
    db.session.commit()
    return jsonify({'status': 'success'})

@calendar_bp.route('/api/events/delete/<int:event_id>', methods=['POST'])
def delete_event(event_id):
    data = request.json
    event = Event.query.get_or_404(event_id)
    if event.password != data.get('password'):
        return jsonify({'status': 'fail', 'message': '비밀번호 틀림'}), 401
    db.session.delete(event)
    db.session.commit()
    return jsonify({'status': 'success'})

# --- 투두 관련 ---
@calendar_bp.route('/api/todos/<int:event_id>', methods=['GET'])
def get_todos(event_id):
    todos = Todo.query.filter_by(event_id=event_id).all()
    return jsonify([{'id':t.id, 'content':t.content, 'is_done':t.is_done, 'completed_at':t.completed_at} for t in todos])

@calendar_bp.route('/api/todos', methods=['POST'])
def add_todo():
    data = request.json
    new_todo = Todo(event_id=data['event_id'], content=data['content'])
    db.session.add(new_todo)
    db.session.commit()
    return jsonify({'status': 'success'})

@calendar_bp.route('/api/todos/toggle/<int:todo_id>', methods=['POST'])
def toggle_todo(todo_id):
    todo = Todo.query.get_or_404(todo_id)
    todo.is_done = not todo.is_done
    todo.completed_at = datetime.now().strftime("%Y-%m-%d %H:%M") if todo.is_done else None
    db.session.commit()
    return jsonify({'status': 'success'})

@calendar_bp.route('/api/todos/edit/<int:todo_id>', methods=['POST'])
def edit_todo(todo_id):
    data = request.json
    todo = Todo.query.get_or_404(todo_id)
    todo.content = data['content']
    db.session.commit()
    return jsonify({'status': 'success'})

@calendar_bp.route('/api/todos/delete/<int:todo_id>', methods=['POST'])
def delete_todo(todo_id):
    todo = Todo.query.get_or_404(todo_id)
    db.session.delete(todo)
    db.session.commit()
    return jsonify({'status': 'success'})