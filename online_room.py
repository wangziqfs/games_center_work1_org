import uuid
import time
from models import get_db

# In-memory room store
rooms = {}           # room_code (str) -> Room
user_rooms = {}      # user_id (int) -> room_code (str) -- quick lookup for disconnect


class Room:
    def __init__(self, code, host_sid, host_username, host_id):
        self.code = code
        self.host_sid = host_sid
        self.host_username = host_username
        self.host_id = host_id
        self.players = {}   # user_id -> {sid, username, player_num, connected}
        self.player_order = []  # [user_id, ...] in join order
        self.game_state = None
        self.created_at = time.time()
        # Add host as player 1
        self.players[host_id] = {
            'sid': host_sid, 'username': host_username,
            'player_num': 1, 'connected': True
        }
        self.player_order.append(host_id)

    @property
    def is_full(self):
        return len(self.player_order) >= 2

    @property
    def both_connected(self):
        return len(self.player_order) == 2 and all(
            self.players[pid]['connected'] for pid in self.player_order)

    def add_player(self, sid, username, user_id):
        if user_id in self.players:
            # Update sid on reconnect / socket join
            self.players[user_id]['sid'] = sid
            self.players[user_id]['connected'] = True
            return
        player_num = 2 if len(self.player_order) < 2 else len(self.player_order) + 1
        self.players[user_id] = {
            'sid': sid, 'username': username,
            'player_num': player_num, 'connected': True
        }
        if user_id not in self.player_order:
            self.player_order.append(user_id)

    def remove_player(self, user_id):
        if user_id in self.players:
            self.players[user_id]['connected'] = False
        if user_id in user_rooms:
            del user_rooms[user_id]

    def get_player_num(self, user_id):
        p = self.players.get(user_id)
        return p['player_num'] if p else None

    def to_json(self):
        return {
            'room_code': self.code,
            'host_username': self.host_username,
            'players': [
                {'username': self.players[pid]['username'],
                 'player_num': self.players[pid]['player_num'],
                 'connected': self.players[pid]['connected']}
                for pid in self.player_order
            ],
            'player_count': len(self.player_order),
        }


def generate_room_code():
    chars = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'  # no 0/O, 1/I to avoid confusion
    while True:
        code = ''.join(chars[ord(c) % len(chars)] for c in uuid.uuid4().hex[:4])
        if code not in rooms:
            return code


def create_room(host_sid, host_username, host_id):
    code = generate_room_code()
    rooms[code] = Room(code, host_sid, host_username, host_id)
    user_rooms[host_id] = code
    return code


def get_room(code):
    if not code:
        return None
    return rooms.get(code.upper())


def get_player_view(room, user_id):
    """Build a filtered game view for a specific player.
    Returns dict safe for emitting to that player's socket."""
    gs = room.game_state
    if not gs:
        return {'phase': 'waiting', 'message': '等待游戏开始...'}

    player_num = room.get_player_num(user_id)
    opp_num = 1 if player_num == 2 else 2
    opp_id = room.player_order[opp_num - 1] if len(room.player_order) >= opp_num else None

    p_key = f'p{player_num}'
    o_key = f'p{opp_num}'
    show_all = gs.get('show_all', False)
    phase = gs.get('phase', '')
    is_my_turn = (
        (player_num == 1 and phase == 'p1_turn') or
        (player_num == 2 and phase == 'p2_turn')
    )

    # Card visibility
    show_own = show_all or is_my_turn
    show_opp = show_all
    show_opp_count = True  # always show opponent card count

    own_hand = gs.get(f'{p_key}_hand', [])
    opp_hand = gs.get(f'{o_key}_hand', [])

    view = {
        'phase': phase,
        'current_player': gs.get('current_player', 1),
        'is_my_turn': is_my_turn,

        'own_hand': own_hand if show_own else None,
        'own_count': len(own_hand),
        'own_value': gs.get(f'{p_key}_value', 0) if (show_own or show_all) else 0,
        'own_value_visible': show_own or show_all,

        'opp_hand': opp_hand if show_opp else None,
        'opp_count': len(opp_hand),
        'opp_value': gs.get(f'{o_key}_value', 0) if show_all else 0,
        'opp_value_visible': show_all,
        'opp_username': room.players[opp_id]['username'] if opp_id else 'Opponent',

        'message': gs.get('message') if show_all or phase == 'showdown' else None,
        'message_class': gs.get('message_class', '') if show_all or phase == 'showdown' else '',
        'result': gs.get('result') if show_all else None,
        'show_all': show_all,

        'p1_status': gs.get('p1_status', ''),
        'p2_status': gs.get('p2_status', ''),
        'winning_player_num': None,
    }

    if show_all and gs.get('result'):
        if gs['result'] == 'p1_wins':
            view['winning_player_num'] = 1
        elif gs['result'] == 'p2_wins':
            view['winning_player_num'] = 2

    return view


def cleanup_stale_rooms(max_age=3600):
    """Remove rooms older than max_age seconds with no activity."""
    now = time.time()
    stale = [code for code, room in rooms.items() if now - room.created_at > max_age]
    for code in stale:
        for uid in rooms[code].player_order:
            user_rooms.pop(uid, None)
        del rooms[code]
