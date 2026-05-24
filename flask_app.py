import os
import uuid
from flask import Flask, render_template, redirect, url_for, session, jsonify
from playcard import get_card_name
import blackjack, blackjack_eu

SUPPORTED_GAMES = {'blackjack': blackjack, 'blackjack_eu': blackjack_eu}
app = Flask(__name__)
# Generate a random secret key for the session
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'games_center_fixed_secret_2026!@#')

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
        return render_template(f'{cur_game}.html',
                               game_state=game_state)
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
    })


@app.route('/select_game/<target_game>')
def select_game(target_game):
    if target_game in SUPPORTED_GAMES:
        session['cur_game'] = target_game
        session_id = session.get('session_id', '')
        #add_log_entry(session_id, f'Select {target_game}.')
        SUPPORTED_GAMES[target_game].new_game(session)
        return redirect(url_for('game'))
    else:
        return render_template('about.html', supported=False)


@app.route('/rules')
def rules():
    return render_template('rules.html',
                           cur_game=session.get('cur_game', ''))

@app.route('/log')
def log():
    return render_template('userlog.html', log='')


@app.route('/about')
def about():
    return render_template('about.html', supported=True)


@app.context_processor
def utility_processor():
    # Make the `get_card_name` function available in all templates
    return dict(get_card_name=get_card_name, enumerate=enumerate)


if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5000, debug=True)