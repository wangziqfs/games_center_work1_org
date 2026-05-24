import eventlet
eventlet.monkey_patch()

import os
import uuid
from flask import Flask, render_template, redirect, url_for, session, jsonify, request
from flask_socketio import SocketIO, emit, join_room as sio_join_room, leave_room as sio_leave_room
from playcard import get_card_name
import blackjack, blackjack_eu, blackjack_pvp

SUPPORTED_GAMES = {'blackjack': blackjack, 'blackjack_eu': blackjack_eu, 'blackjack_pvp': blackjack_pvp}
app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'games_center_fixed_secret_2026!@#')
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

# ── Auth Blueprint ──────────────────────────────────────────────
from auth import auth_bp
app.register_blueprint(auth_bp)

# ── Online Modules ──────────────────────────────────────────────
from online_room import rooms, user_rooms, create_room, get_room, get_player_view
from online_blackjack import new_game as online_new_game, process_action

# ── Existing Routes ─────────────────────────────────────────────

@app.route('/')
def index():
    return redirect(url_for('game'))

@app.route('/select')
def select():
    session.setdefault('session_id', uuid.uuid4().hex)
    return render_template('select.html', cur_game=session.get('cur_game', ''))

@app.route('/new_game')
def new_game():
    cur_game = session.get('cur_game', '')
    if cur_game in SUPPORTED_GAMES:
        SUPPORTED_GAMES[cur_game].new_game(session)
        session.modified = True
        return redirect(url_for('game'))
    else:
        return redirect(url_for('select'))

@app.route('/game')
def game():
    session.setdefault('session_id', uuid.uuid4().hex)
    cur_game = session.get('cur_game', '')
    game_state = session.get('game_state', {})
    if cur_game in SUPPORTED_GAMES and game_state:
        return render_template(f'{cur_game}.html', game_state=game_state)
    else:
        return redirect(url_for('select'))

@app.route('/game_update/<action>')
def game_update(action):
    cur_game = session.get('cur_game', '')
    if cur_game in SUPPORTED_GAMES:
        SUPPORTED_GAMES[cur_game].game_update(session, action)
        session.modified = True
        return redirect(url_for('game'))
    else:
        return redirect(url_for('select'))

@app.route('/game_action/<action>')
def game_action(action):
    cur_game = session.get('cur_game', '')
    if cur_game not in SUPPORTED_GAMES:
        return jsonify({'error': 'no game selected'}), 400
    game_mod = SUPPORTED_GAMES[cur_game]
    if action == 'new':
        game_mod.new_game(session)
    else:
        game_mod.game_update(session, action)
    session.modified = True
    gs = session.get('game_state', {})
    return jsonify({
        'dealer_hand': gs.get('dealer_hand', []),
        'dealer_value': gs.get('dealer_value', 0),
        'player_hand': gs.get('player_hand', []),
        'player_value': gs.get('player_value', 0),
        'message': gs.get('message'),
        'message_class': gs.get('message_class', ''),
        'p1_hand': gs.get('p1_hand', []),
        'p2_hand': gs.get('p2_hand', []),
        'p1_value': gs.get('p1_value', 0),
        'p2_value': gs.get('p2_value', 0),
        'phase': gs.get('phase', ''),
        'current_player': gs.get('current_player', 1),
        'show_all': gs.get('show_all', False),
        'p1_status': gs.get('p1_status', ''),
        'p2_status': gs.get('p2_status', ''),
        'result': gs.get('result'),
    })

@app.route('/select_game/<target_game>')
def select_game(target_game):
    if target_game in SUPPORTED_GAMES:
        session['cur_game'] = target_game
        SUPPORTED_GAMES[target_game].new_game(session)
        return redirect(url_for('game'))
    else:
        return render_template('about.html', supported=False)

@app.route('/rules')
def rules():
    return render_template('rules.html', cur_game=session.get('cur_game', ''))

@app.route('/log')
def log():
    return render_template('userlog.html', log='')

@app.route('/about')
def about():
    return render_template('about.html', supported=True)

# ── Online Lobby Routes ─────────────────────────────────────────

@app.route('/lobby')
def lobby():
    if 'user_id' not in session:
        return redirect(url_for('auth_bp.login'))
    return render_template('lobby.html', username=session['username'], room_code='')

@app.route('/lobby/<room_code>')
def lobby_room(room_code):
    if 'user_id' not in session:
        return redirect(url_for('auth_bp.login'))
    room = get_room(room_code)
    if not room:
        return render_template('lobby.html', username=session['username'], room_code='', error='房间不存在')
    return render_template('lobby.html', username=session['username'], room_code=room_code.upper())

@app.route('/online_game/<room_code>')
def online_game(room_code):
    if 'user_id' not in session:
        return redirect(url_for('auth_bp.login'))
    room = get_room(room_code)
    if not room:
        return redirect(url_for('lobby'))
    # Check user is in this room
    if session['user_id'] not in room.players:
        # Auto-join if room has space
        if room.is_full:
            return redirect(url_for('lobby'))
    return render_template('online_pvp.html', room_code=room_code.upper(), username=session['username'])

# ── API Endpoints ───────────────────────────────────────────────

@app.route('/api/create_room')
def api_create_room():
    if 'user_id' not in session:
        return jsonify({'error': 'not logged in'}), 401
    code = create_room(request.sid if hasattr(request, 'sid') else None,
                       session['username'], session['user_id'])
    return jsonify({'room_code': code})

@app.route('/api/room_exists/<code>')
def api_room_exists(code):
    room = get_room(code)
    if room and not room.is_full:
        return jsonify({'exists': True, 'host': room.host_username})
    return jsonify({'exists': False})

# ── SocketIO Event Handlers ─────────────────────────────────────

@socketio.on('connect')
def handle_connect():
    try:
        user_id = int(request.args.get('user_id', 0))
    except (ValueError, TypeError):
        user_id = 0
    if user_id:
        sid_map[request.sid] = user_id

@socketio.on('disconnect')
def handle_disconnect():
    user_id = sid_map.pop(request.sid, None)
    if not user_id:
        return
    code = user_rooms.get(user_id)
    if not code:
        return
    room = get_room(code)
    if not room:
        return
    room.remove_player(user_id)
    # Notify opponent
    for pid, pdata in room.players.items():
        if pdata['connected'] and pid != user_id:
            emit('player_left', {'username': pdata.get('username', '?'), 'player_count': len(room.player_order)},
                 room=pdata['sid'])

@socketio.on('join_room')
def handle_join_room(data):
    user_id = int(request.args.get('user_id', 0))
    if not user_id:
        emit('error', {'message': 'Not authenticated'})
        return
    code = data.get('room_code', '').upper()
    room = get_room(code)
    if not room:
        emit('error', {'message': 'Room not found'})
        return
    # Add player to room
    if user_id not in room.players:
        if room.is_full:
            emit('error', {'message': 'Room is full'})
            return
    room.add_player(request.sid, request.args.get('username', 'Player'), user_id)
    user_rooms[user_id] = code
    sio_join_room(code)
    emit('room_joined', room.to_json())
    # Notify other players
    new_player = room.players[user_id]
    for pid, pdata in room.players.items():
        if pdata['connected'] and pid != user_id:
            emit('player_joined', {'username': new_player['username']}, room=pdata['sid'])
    # If game already in progress, send current view to reconnecting player
    if room.game_state:
        view = get_player_view(room, user_id)
        emit('game_view', view)

@socketio.on('leave_room')
def handle_leave_room(data):
    code = data.get('room_code', '').upper()
    if code:
        sio_leave_room(code)
    user_id = int(request.args.get('user_id', 0))
    if user_id:
        user_rooms.pop(user_id, None)

@socketio.on('start_game')
def handle_start_game(data):
    code = data.get('room_code', '').upper()
    room = get_room(code)
    if not room:
        emit('error', {'message': 'Room not found'})
        return
    user_id = int(request.args.get('user_id', 0))
    if user_id != room.host_id:
        emit('error', {'message': 'Only host can start'})
        return
    if len(room.player_order) < 2:
        emit('error', {'message': 'Need 2 players'})
        return
    if not room.both_connected:
        emit('error', {'message': 'Both players must be connected'})
        return
    online_new_game(room)
    # Send targeted views to each player
    for pid in room.player_order:
        pdata = room.players[pid]
        if pdata['connected']:
            view = get_player_view(room, pid)
            emit('game_started', view, room=pdata['sid'])

@socketio.on('player_action')
def handle_player_action(data):
    code = data.get('room_code', '').upper()
    action = data.get('action', '')
    room = get_room(code)
    if not room:
        emit('error', {'message': 'Room not found'})
        return
    user_id = int(request.args.get('user_id', 0))
    if user_id not in room.players:
        emit('error', {'message': 'Not in room'})
        return

    # Handle play_again
    if action == 'play_again':
        online_new_game(room)
        for pid in room.player_order:
            pdata = room.players[pid]
            if pdata['connected']:
                view = get_player_view(room, pid)
                emit('game_view', view, room=pdata['sid'])
        return

    # Process game action
    err = process_action(room, user_id, action)
    if err:
        emit('error', err)
        return

    # Send targeted views to each player
    for pid in room.player_order:
        pdata = room.players[pid]
        if pdata['connected']:
            view = get_player_view(room, pid)
            emit('game_view', view, room=pdata['sid'])

# ── Context Processor ───────────────────────────────────────────

@app.context_processor
def utility_processor():
    return dict(get_card_name=get_card_name, enumerate=enumerate)

# ── Global SID Map ──────────────────────────────────────────────

sid_map = {}  # sid -> user_id

# ── Main ────────────────────────────────────────────────────────

if __name__ == '__main__':
    socketio.run(app, host='127.0.0.1', port=5000, debug=True)
