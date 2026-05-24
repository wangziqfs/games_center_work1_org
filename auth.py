from flask import Blueprint, render_template, request, redirect, url_for, session
from werkzeug.security import generate_password_hash, check_password_hash
from models import get_db

auth_bp = Blueprint('auth_bp', __name__)


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        if not username or not password:
            return render_template('login.html', error='请输入用户名和密码')
        db = get_db()
        user = db.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
        db.close()
        if not user or not check_password_hash(user['password_hash'], password):
            return render_template('login.html', error='用户名或密码错误')
        session['user_id'] = user['id']
        session['username'] = user['username']
        session.modified = True
        return redirect(url_for('lobby'))
    return render_template('login.html', error=None)


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        confirm = request.form.get('confirm', '')
        if not username or not password:
            return render_template('register.html', error='请填写所有字段')
        if len(username) < 2 or len(username) > 20:
            return render_template('register.html', error='用户名需 2-20 个字符')
        if len(password) < 4:
            return render_template('register.html', error='密码至少 4 个字符')
        if password != confirm:
            return render_template('register.html', error='两次密码不一致')
        db = get_db()
        existing = db.execute('SELECT id FROM users WHERE username = ?', (username,)).fetchone()
        if existing:
            db.close()
            return render_template('register.html', error='用户名已存在')
        pw_hash = generate_password_hash(password)
        db.execute('INSERT INTO users (username, password_hash) VALUES (?, ?)', (username, pw_hash))
        db.commit()
        user = db.execute('SELECT id FROM users WHERE username = ?', (username,)).fetchone()
        db.close()
        session['user_id'] = user['id']
        session['username'] = username
        session.modified = True
        return redirect(url_for('lobby'))
    return render_template('register.html', error=None)


@auth_bp.route('/logout')
def logout():
    session.pop('user_id', None)
    session.pop('username', None)
    return redirect(url_for('select'))
