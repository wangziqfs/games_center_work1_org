import random
from playcard import make_deck
from online_room import rooms, get_room

CARD_VALUES = {
    'A': 11, '2': 2, '3': 3, '4': 4, '5': 5, '6': 6, '7': 7,
    '8': 8, '9': 9, 'T': 10, 'J': 10, 'Q': 10, 'K': 10,
}


def calculate_hand_value(hand):
    value, aces = 0, 0
    for card in hand:
        value += CARD_VALUES[card[0]]
        aces += card[0] == 'A'
    while value > 21 and aces:
        value -= 10
        aces -= 1
    return value


def is_natural_blackjack(hand):
    return len(hand) == 2 and calculate_hand_value(hand) == 21


def compare_hands(p1_hand, p2_hand, p1_bust, p2_bust):
    if p1_bust and p2_bust:
        return ('tie', '双方都爆牌，平局！', 'tie-message')
    if p1_bust:
        return ('p2_wins', '玩家1爆牌！玩家2获胜！', 'win-message')
    if p2_bust:
        return ('p1_wins', '玩家2爆牌！玩家1获胜！', 'win-message')
    p1_nat = is_natural_blackjack(p1_hand)
    p2_nat = is_natural_blackjack(p2_hand)
    p1_val = calculate_hand_value(p1_hand)
    p2_val = calculate_hand_value(p2_hand)
    if p1_nat and p2_nat:
        return ('tie', '双方都是黑杰克，平局！', 'tie-message')
    if p1_nat:
        return ('p1_wins', '玩家1黑杰克获胜！', 'win-message')
    if p2_nat:
        return ('p2_wins', '玩家2黑杰克获胜！', 'win-message')
    if p1_val > p2_val:
        return ('p1_wins', f'玩家1获胜！（{p1_val} : {p2_val}）', 'win-message')
    elif p2_val > p1_val:
        return ('p2_wins', f'玩家2获胜！（{p1_val} : {p2_val}）', 'win-message')
    else:
        return ('tie', f'平局！（{p1_val} : {p2_val}）', 'tie-message')


def new_game(room):
    deck = make_deck()
    random.shuffle(deck)
    p1c1, p1c2, p2c1, p2c2 = deck.pop(), deck.pop(), deck.pop(), deck.pop()
    p1_hand = [p1c1, p1c2]
    p2_hand = [p2c1, p2c2]
    p1_val = calculate_hand_value(p1_hand)
    p2_val = calculate_hand_value(p2_hand)
    p1_nat = is_natural_blackjack(p1_hand)
    p2_nat = is_natural_blackjack(p2_hand)

    if p1_nat and p2_nat:
        room.game_state = {
            'deck': deck, 'p1_hand': p1_hand, 'p2_hand': p2_hand,
            'p1_value': p1_val, 'p2_value': p2_val,
            'p1_natural': True, 'p2_natural': True,
            'phase': 'showdown', 'current_player': 1,
            'p1_status': 'blackjack', 'p2_status': 'blackjack',
            'show_all': True,
            'message': '双方都是黑杰克，平局！', 'message_class': 'tie-message',
            'result': 'tie',
        }
        return

    room.game_state = {
        'deck': deck, 'p1_hand': p1_hand, 'p2_hand': p2_hand,
        'p1_value': p1_val, 'p2_value': 0,
        'p1_natural': p1_nat, 'p2_natural': p2_nat,
        'phase': 'p1_turn', 'current_player': 1,
        'p1_status': 'playing', 'p2_status': 'playing',
        'show_all': False,
        'message': None, 'message_class': '',
        'result': None,
    }

    if p1_nat:
        # P1 natural blackjack — skip P1's turn, go directly to P2
        room.game_state['phase'] = 'p2_turn'
        room.game_state['current_player'] = 2
        room.game_state['p1_status'] = 'blackjack'
        room.game_state['p2_value'] = p2_val


def _transition_to_p2(gs):
    """Move game from P1's turn to P2's turn; auto-showdown if P2 has natural."""
    gs['phase'] = 'p2_turn'
    gs['current_player'] = 2
    gs['p2_value'] = calculate_hand_value(gs['p2_hand'])
    if gs.get('p2_natural'):
        gs['phase'] = 'showdown'
        gs['show_all'] = True
        gs['p2_status'] = 'blackjack'
        res, msg, cls = compare_hands(gs['p1_hand'], gs['p2_hand'], False, False)
        gs['result'] = res
        gs['message'] = msg
        gs['message_class'] = cls


def process_action(room, user_id, action):
    gs = room.game_state
    if not gs:
        return {'error': 'Game not started'}

    if gs.get('phase') == 'showdown':
        return {'error': 'Game is over'}

    player_num = room.get_player_num(user_id)
    phase = gs['phase']
    deck = gs['deck']

    # Validate it's this player's turn
    if (player_num == 1 and phase != 'p1_turn') or \
       (player_num == 2 and phase != 'p2_turn'):
        return {'error': 'Not your turn'}

    if player_num == 1 and phase == 'p1_turn':
        if action == 'hit':
            try:
                card = deck.pop()
            except IndexError:
                gs['phase'] = 'showdown'
                gs['show_all'] = True
                gs['message'] = '牌堆已空！'
                gs['message_class'] = 'tie-message'
                gs['result'] = 'tie'
                return None
            gs['p1_hand'].append(card)
            gs['p1_value'] = calculate_hand_value(gs['p1_hand'])
            if gs['p1_value'] > 21:
                gs['phase'] = 'showdown'
                gs['show_all'] = True
                gs['p1_status'] = 'bust'
                gs['p2_value'] = calculate_hand_value(gs['p2_hand'])
                res, msg, cls = compare_hands(gs['p1_hand'], gs['p2_hand'], True, False)
                gs['result'] = res
                gs['message'] = msg
                gs['message_class'] = cls
            elif gs['p1_value'] == 21:
                _transition_to_p2(gs)
                gs['p1_status'] = 'stood_21'
        elif action == 'stand':
            _transition_to_p2(gs)
            gs['p1_status'] = 'stood'

    elif player_num == 2 and phase == 'p2_turn':
        if action == 'hit':
            try:
                card = deck.pop()
            except IndexError:
                gs['phase'] = 'showdown'
                gs['show_all'] = True
                gs['message'] = '牌堆已空！'
                gs['message_class'] = 'tie-message'
                gs['result'] = 'tie'
                return None
            gs['p2_hand'].append(card)
            gs['p2_value'] = calculate_hand_value(gs['p2_hand'])
            if gs['p2_value'] > 21:
                gs['phase'] = 'showdown'
                gs['show_all'] = True
                gs['p2_status'] = 'bust'
                res, msg, cls = compare_hands(gs['p1_hand'], gs['p2_hand'], False, True)
                gs['result'] = res
                gs['message'] = msg
                gs['message_class'] = cls
            elif gs['p2_value'] == 21:
                gs['show_all'] = True
                gs['p2_status'] = 'stood_21'
                gs['phase'] = 'showdown'
                res, msg, cls = compare_hands(gs['p1_hand'], gs['p2_hand'], False, False)
                gs['result'] = res
                gs['message'] = msg
                gs['message_class'] = cls
        elif action == 'stand':
            gs['show_all'] = True
            gs['p2_status'] = 'stood'
            gs['phase'] = 'showdown'
            # Check if P2 had natural
            if gs.get('p2_natural'):
                gs['p2_status'] = 'blackjack'
            res, msg, cls = compare_hands(gs['p1_hand'], gs['p2_hand'], False, False)
            gs['result'] = res
            gs['message'] = msg
            gs['message_class'] = cls

    return None  # success
