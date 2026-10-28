
from flask import Flask, request, jsonify, session
from flask_cors import CORS
import sqlite3
import hashlib
import math
import os
from datetime import date, timedelta

app = Flask(__name__, static_folder='.', static_url_path='')
app.secret_key = 'habitquest_sqlite_secret_2024'
CORS(app, supports_credentials=True)

DB_PATH = os.path.join(os.path.dirname(__file__), 'habit_quest.db')

def get_db():

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():

    conn = get_db()
    cur  = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            name       TEXT    NOT NULL,
            email      TEXT    UNIQUE NOT NULL,
            password   TEXT    NOT NULL,
            bio        TEXT    DEFAULT '',
            avatar     TEXT    DEFAULT '',
            total_xp   INTEGER DEFAULT 0,
            created_at TEXT    DEFAULT (date('now'))
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS habits (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL,
            title       TEXT    NOT NULL,
            description TEXT    DEFAULT '',
            category    TEXT    DEFAULT 'other',
            color       TEXT    DEFAULT '#FF6B6B',
            streak      INTEGER DEFAULT 0,
            best_streak INTEGER DEFAULT 0,
            created_at  TEXT    DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS task_completions (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            habit_id  INTEGER NOT NULL,
            user_id   INTEGER NOT NULL,
            done_date TEXT    NOT NULL,
            UNIQUE(habit_id, done_date),
            FOREIGN KEY (habit_id) REFERENCES habits(id) ON DELETE CASCADE,
            FOREIGN KEY (user_id)  REFERENCES users(id)  ON DELETE CASCADE
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS notifications (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    INTEGER NOT NULL,
            message    TEXT    NOT NULL,
            icon       TEXT    DEFAULT '🔔',
            is_read    INTEGER DEFAULT 0,
            created_at TEXT    DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)

    conn.commit()
    conn.close()
    print("SQLite database ready:", DB_PATH)

def hash_password(password):

    return hashlib.sha256(password.encode()).hexdigest()

def calc_level(total_xp):

    level      = 1
    xp_to_next = 100
    remaining  = total_xp

    while remaining >= xp_to_next:
        remaining  -= xp_to_next
        level      += 1
        xp_to_next  = math.ceil(xp_to_next * 1.35)

    return level, remaining, xp_to_next

def user_to_dict(row):

    level, xp_current, xp_to_next = calc_level(row['total_xp'])
    return {
        'id':       row['id'],
        'name':     row['name'],
        'email':    row['email'],
        'bio':      row['bio']    or '',
        'avatar':   row['avatar'] or '',
        'level':    level,
        'xp':       xp_current,
        'xpToNext': xp_to_next,
        'total_xp': row['total_xp'],
    }

def habit_to_dict(row, completed_dates):

    return {
        'id':             row['id'],
        'title':          row['title'],
        'description':    row['description'] or '',
        'category':       row['category'],
        'color':          row['color'],
        'streak':         row['streak'],
        'bestStreak':     row['best_streak'],
        'completedDates': completed_dates,
        'createdAt':      row['created_at'],
    }

@app.route('/')
def index():

    return app.send_static_file('index.html')

@app.route('/api/register', methods=['POST'])
def register():

    data     = request.get_json()
    name     = (data.get('name')     or '').strip()
    email    = (data.get('email')    or '').strip().lower()
    password = (data.get('password') or '')

    if not name or not email or not password:
        return jsonify({'ok': False, 'msg': 'All fields are required.'}), 400
    if len(password) < 6:
        return jsonify({'ok': False, 'msg': 'Password must be at least 6 characters.'}), 400

    conn = get_db()
    cur  = conn.cursor()

    cur.execute("SELECT id FROM users WHERE email = ?", (email,))
    if cur.fetchone():
        conn.close()
        return jsonify({'ok': False, 'msg': 'Email already registered.'}), 409

    hashed = hash_password(password)
    cur.execute(
        "INSERT INTO users (name, email, password) VALUES (?, ?, ?)",
        (name, email, hashed)
    )
    conn.commit()
    user_id = cur.lastrowid

    cur.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    user = cur.fetchone()
    conn.close()

    session['user_id'] = user_id

    return jsonify({'ok': True, 'user': user_to_dict(user)})

@app.route('/api/login', methods=['POST'])
def login():

    data     = request.get_json()
    email    = (data.get('email')    or '').strip().lower()
    password = (data.get('password') or '')

    conn   = get_db()
    cur    = conn.cursor()
    hashed = hash_password(password)

    cur.execute(
        "SELECT * FROM users WHERE email = ? AND password = ?",
        (email, hashed)
    )
    user = cur.fetchone()
    conn.close()

    if not user:
        return jsonify({'ok': False, 'msg': 'Invalid email or password.'}), 401

    session['user_id'] = user['id']
    return jsonify({'ok': True, 'user': user_to_dict(user)})

@app.route('/api/logout', methods=['POST'])
def logout():

    session.clear()
    return jsonify({'ok': True})

@app.route('/api/me', methods=['GET'])
def get_me():

    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'ok': False, 'msg': 'Not logged in.'}), 401

    conn = get_db()
    cur  = conn.cursor()
    cur.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    user = cur.fetchone()
    conn.close()

    if not user:
        session.clear()
        return jsonify({'ok': False, 'msg': 'User not found.'}), 404

    return jsonify({'ok': True, 'user': user_to_dict(user)})

@app.route('/api/profile', methods=['PUT'])
def update_profile():

    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'ok': False, 'msg': 'Not logged in.'}), 401

    data   = request.get_json()
    name   = (data.get('name')  or '').strip()
    email  = (data.get('email') or '').strip().lower()
    bio    = data.get('bio',    '')
    avatar = data.get('avatar', None)

    if not name or not email:
        return jsonify({'ok': False, 'msg': 'Name and email are required.'}), 400

    conn = get_db()
    cur  = conn.cursor()

    cur.execute("SELECT id FROM users WHERE email = ? AND id != ?", (email, user_id))
    if cur.fetchone():
        conn.close()
        return jsonify({'ok': False, 'msg': 'Email already in use.'}), 409

    if avatar is not None:
        cur.execute(
            "UPDATE users SET name=?, email=?, bio=?, avatar=? WHERE id=?",
            (name, email, bio, avatar, user_id)
        )
    else:
        cur.execute(
            "UPDATE users SET name=?, email=?, bio=? WHERE id=?",
            (name, email, bio, user_id)
        )

    add_notification(conn, user_id, 'Your profile was updated ✨', '👤')

    conn.commit()
    cur.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    user = cur.fetchone()
    conn.close()

    return jsonify({'ok': True, 'user': user_to_dict(user)})

@app.route('/api/habits', methods=['GET'])
def get_habits():

    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'ok': False, 'msg': 'Not logged in.'}), 401

    conn = get_db()
    cur  = conn.cursor()

    cur.execute(
        "SELECT * FROM habits WHERE user_id = ? ORDER BY created_at ASC",
        (user_id,)
    )
    habits = cur.fetchall()

    result = []
    for h in habits:

        cur.execute(
            "SELECT done_date FROM task_completions WHERE habit_id = ? ORDER BY done_date ASC",
            (h['id'],)
        )
        dates = [row['done_date'] for row in cur.fetchall()]
        result.append(habit_to_dict(h, dates))

    conn.close()
    return jsonify({'ok': True, 'habits': result})

@app.route('/api/habits', methods=['POST'])
def create_habit():

    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'ok': False, 'msg': 'Not logged in.'}), 401

    data  = request.get_json()
    title = (data.get('title') or '').strip()
    if not title:
        return jsonify({'ok': False, 'msg': 'Title is required.'}), 400

    description = data.get('description', '')
    category    = data.get('category',    'other')
    color       = data.get('color',       '#FF6B6B')

    conn = get_db()
    cur  = conn.cursor()

    cur.execute(
        "INSERT INTO habits (user_id, title, description, category, color) VALUES (?,?,?,?,?)",
        (user_id, title, description, category, color)
    )
    habit_id = cur.lastrowid

    cur.execute("UPDATE users SET total_xp = total_xp + 50 WHERE id = ?", (user_id,))

    add_notification(conn, user_id,
        f'New habit "{title}" created! +50 XP ✨', '🎯')

    conn.commit()

    cur.execute("SELECT * FROM habits WHERE id = ?", (habit_id,))
    habit = cur.fetchone()
    conn.close()

    return jsonify({'ok': True, 'habit': habit_to_dict(habit, [])})

@app.route('/api/habits/<int:habit_id>', methods=['PUT'])
def update_habit(habit_id):

    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'ok': False, 'msg': 'Not logged in.'}), 401

    data        = request.get_json()
    title       = (data.get('title') or '').strip()
    description = data.get('description', '')
    category    = data.get('category',    'other')
    color       = data.get('color',       '#FF6B6B')

    if not title:
        return jsonify({'ok': False, 'msg': 'Title is required.'}), 400

    conn = get_db()
    cur  = conn.cursor()

    cur.execute("SELECT id FROM habits WHERE id = ? AND user_id = ?", (habit_id, user_id))
    if not cur.fetchone():
        conn.close()
        return jsonify({'ok': False, 'msg': 'Habit not found.'}), 404

    cur.execute(
        "UPDATE habits SET title=?, description=?, category=?, color=? WHERE id=?",
        (title, description, category, color, habit_id)
    )
    conn.commit()

    cur.execute("SELECT * FROM habits WHERE id = ?", (habit_id,))
    habit = cur.fetchone()
    cur.execute(
        "SELECT done_date FROM task_completions WHERE habit_id = ? ORDER BY done_date ASC",
        (habit_id,)
    )
    dates = [row['done_date'] for row in cur.fetchall()]
    conn.close()

    return jsonify({'ok': True, 'habit': habit_to_dict(habit, dates)})

@app.route('/api/habits/<int:habit_id>', methods=['DELETE'])
def delete_habit(habit_id):

    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'ok': False, 'msg': 'Not logged in.'}), 401

    conn = get_db()
    cur  = conn.cursor()

    cur.execute("SELECT id FROM habits WHERE id = ? AND user_id = ?", (habit_id, user_id))
    if not cur.fetchone():
        conn.close()
        return jsonify({'ok': False, 'msg': 'Habit not found.'}), 404

    cur.execute("DELETE FROM habits WHERE id = ?", (habit_id,))

    add_notification(conn, user_id, 'A habit was deleted 🗑️', '🗑️')

    conn.commit()
    conn.close()

    return jsonify({'ok': True})

@app.route('/api/habits/<int:habit_id>/toggle', methods=['POST'])
def toggle_habit(habit_id):

    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'ok': False, 'msg': 'Not logged in.'}), 401

    today = date.today().isoformat()

    conn = get_db()
    cur  = conn.cursor()

    cur.execute("SELECT * FROM habits WHERE id = ? AND user_id = ?", (habit_id, user_id))
    habit = cur.fetchone()
    if not habit:
        conn.close()
        return jsonify({'ok': False, 'msg': 'Habit not found.'}), 404

    cur.execute(
        "SELECT id FROM task_completions WHERE habit_id = ? AND done_date = ?",
        (habit_id, today)
    )
    existing = cur.fetchone()

    if existing:

        cur.execute(
            "DELETE FROM task_completions WHERE habit_id = ? AND done_date = ?",
            (habit_id, today)
        )

        cur.execute(
            "UPDATE users SET total_xp = MAX(0, total_xp - 25) WHERE id = ?",
            (user_id,)
        )
        completed = False
    else:

        cur.execute(
            "INSERT INTO task_completions (habit_id, user_id, done_date) VALUES (?,?,?)",
            (habit_id, user_id, today)
        )
        cur.execute(
            "UPDATE users SET total_xp = total_xp + 25 WHERE id = ?",
            (user_id,)
        )
        completed = True

    conn.commit()

    cur.execute(
        "SELECT done_date FROM task_completions WHERE habit_id = ? ORDER BY done_date DESC",
        (habit_id,)
    )
    all_date_strs = [row['done_date'] for row in cur.fetchall()]

    all_dates = [date.fromisoformat(d) for d in all_date_strs]

    streak = 0
    check  = date.today()
    for i in range(400):
        if check in all_dates:
            streak += 1
            check  -= timedelta(days=1)
        elif i == 0:

            check -= timedelta(days=1)
            if check in all_dates:
                streak += 1
                check  -= timedelta(days=1)
            else:
                break
        else:
            break

    best_streak = max(habit['best_streak'], streak)

    cur.execute(
        "UPDATE habits SET streak = ?, best_streak = ? WHERE id = ?",
        (streak, best_streak, habit_id)
    )

    if completed:

        add_notification(conn, user_id,
            f'"{habit["title"]}" completed! +25 XP ⚡', '✅')

        if streak in (3, 7, 14, 30, 60, 100):
            add_notification(conn, user_id,
                f'🔥 {streak}-day streak on "{habit["title"]}"! Keep it up!', '🔥')
    else:

        add_notification(conn, user_id,
            f'"{habit["title"]}" marked incomplete. -25 XP', '↩️')

    conn.commit()

    cur.execute("SELECT total_xp FROM users WHERE id = ?", (user_id,))
    user_row = cur.fetchone()
    level, xp_current, xp_to_next = calc_level(user_row['total_xp'])

    conn.close()

    return jsonify({
        'ok':             True,
        'completed':      completed,
        'streak':         streak,
        'bestStreak':     best_streak,
        'completedDates': all_date_strs,
        'user': {
            'level':    level,
            'xp':       xp_current,
            'xpToNext': xp_to_next,
            'total_xp': user_row['total_xp'],
        }
    })

@app.route('/api/leaderboard', methods=['GET'])
def leaderboard():

    user_id = session.get('user_id')

    conn = get_db()
    cur  = conn.cursor()

    cur.execute(
        """SELECT id, name, avatar, total_xp, created_at
           FROM users
           ORDER BY total_xp DESC, created_at ASC"""
    )
    users = cur.fetchall()
    conn.close()

    result = []
    for u in users:
        level, _, _ = calc_level(u['total_xp'])
        result.append({
            'name':   u['name'],
            'avatar': u['avatar'] or '',
            'level':  level,
            'xp':     u['total_xp'],
            'isMe':   (u['id'] == user_id),
        })

    result = [r for r in result if r['xp'] > 0 or r['isMe']]

    return jsonify({'ok': True, 'leaderboard': result})

@app.route('/api/weekly', methods=['GET'])
def weekly_activity():

    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'ok': False, 'msg': 'Not logged in.'}), 401

    conn = get_db()
    cur  = conn.cursor()

    days   = []
    counts = []

    for i in range(6, -1, -1):
        d = date.today() - timedelta(days=i)
        d_str = d.isoformat()

        cur.execute(
            """SELECT COUNT(*) AS cnt
               FROM task_completions tc
               JOIN habits h ON h.id = tc.habit_id
               WHERE h.user_id = ? AND tc.done_date = ?""",
            (user_id, d_str)
        )
        row = cur.fetchone()
        days.append(d.strftime('%a'))
        counts.append(row['cnt'])

    conn.close()
    return jsonify({'ok': True, 'days': days, 'counts': counts})

def add_notification(conn, user_id, message, icon='🔔'):

    conn.execute(
        "INSERT INTO notifications (user_id, message, icon) VALUES (?, ?, ?)",
        (user_id, message, icon)
    )

@app.route('/api/notifications', methods=['GET'])
def get_notifications():

    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'ok': False, 'msg': 'Not logged in.'}), 401

    conn = get_db()
    cur  = conn.cursor()

    cur.execute(
        """SELECT id, message, icon, is_read, created_at
           FROM notifications
           WHERE user_id = ?
           ORDER BY created_at DESC
           LIMIT 30""",
        (user_id,)
    )
    rows = cur.fetchall()

    cur.execute(
        "SELECT COUNT(*) AS cnt FROM notifications WHERE user_id = ? AND is_read = 0",
        (user_id,)
    )
    unread_count = cur.fetchone()['cnt']
    conn.close()

    notifications = [
        {
            'id':         row['id'],
            'message':    row['message'],
            'icon':       row['icon'],
            'is_read':    bool(row['is_read']),
            'created_at': row['created_at'],
        }
        for row in rows
    ]

    return jsonify({
        'ok':             True,
        'notifications':  notifications,
        'unread_count':   unread_count,
    })

@app.route('/api/notifications/<int:notif_id>/read', methods=['PUT'])
def mark_notification_read(notif_id):

    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'ok': False, 'msg': 'Not logged in.'}), 401

    conn = get_db()
    conn.execute(
        "UPDATE notifications SET is_read = 1 WHERE id = ? AND user_id = ?",
        (notif_id, user_id)
    )
    conn.commit()
    conn.close()
    return jsonify({'ok': True})

@app.route('/api/notifications/read-all', methods=['PUT'])
def mark_all_read():

    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'ok': False, 'msg': 'Not logged in.'}), 401

    conn = get_db()
    conn.execute(
        "UPDATE notifications SET is_read = 1 WHERE user_id = ?",
        (user_id,)
    )
    conn.commit()
    conn.close()
    return jsonify({'ok': True})

@app.route('/api/notifications/clear', methods=['DELETE'])
def clear_notifications():

    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'ok': False, 'msg': 'Not logged in.'}), 401

    conn = get_db()
    conn.execute("DELETE FROM notifications WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()
    return jsonify({'ok': True})

init_db()

if __name__ == '__main__':
    print("Habit Quest running at http://localhost:5000")
    app.run(debug=True, port=5000)
