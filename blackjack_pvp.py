import random
from playcard import make_deck

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
    """Return (result, message, message_class). result: 'p1_wins' | 'p2_wins' | 'tie'."""
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


def new_game(session):
    deck = make_deck()
    random.shuffle(deck)
    p1c1, p1c2, p2c1, p2c2 = deck.pop(), deck.pop(), deck.pop(), deck.pop()
    p1_hand = [p1c1, p1c2]
    p2_hand = [p2c1, p2c2]
    p1_val = calculate_hand_value(p1_hand)
    p2_val = calculate_hand_value(p2_hand)
    p1_nat = is_natural_blackjack(p1_hand)
    p2_nat = is_natural_blackjack(p2_hand)

    # Both have natural blackjack → immediate tie
    if p1_nat and p2_nat:
        session['game_state'] = {
            'deck': deck, 'p1_hand': p1_hand, 'p2_hand': p2_hand,
            'p1_value': p1_val, 'p2_value': p2_val,
            'p1_natural': p1_nat, 'p2_natural': p2_nat,
            'phase': 'showdown', 'current_player': 1,
            'p1_status': 'blackjack', 'p2_status': 'blackjack',
            'show_all': True,
            'message': '双方都是黑杰克，平局！', 'message_class': 'tie-message',
            'result': 'tie',
        }
        return

    # P1 natural → skip to wait_p2
    if p1_nat:
        session['game_state'] = {
            'deck': deck, 'p1_hand': p1_hand, 'p2_hand': p2_hand,
            'p1_value': p1_val, 'p2_value': 0,
            'p1_natural': p1_nat, 'p2_natural': p2_nat,
            'phase': 'wait_p2', 'current_player': 1,
            'p1_status': 'blackjack', 'p2_status': 'playing',
            'show_all': False,
            'message': '玩家1黑杰克！请将设备交给玩家2。', 'message_class': '',
            'result': None,
        }
        return

    # P2 natural → P2 has natural waiting; P1 plays normally
    phase = 'p1_turn'
    message = None
    # Normal start: P1's turn
    session['game_state'] = {
        'deck': deck, 'p1_hand': p1_hand, 'p2_hand': p2_hand,
        'p1_value': p1_val, 'p2_value': 0,
        'p1_natural': p1_nat, 'p2_natural': p2_nat,
        'phase': phase, 'current_player': 1,
        'p1_status': 'playing', 'p2_status': 'playing',
        'show_all': False,
        'message': message, 'message_class': '',
        'result': None,
    }


def game_update(session, action):
    gs = session.get('game_state', {})
    if not gs:
        return new_game(session)

    if gs.get('message') and gs.get('phase') == 'showdown':
        return

    phase = gs['phase']
    deck = gs['deck']

    # ── p1_turn ──
    if phase == 'p1_turn':
        if action == 'hit':
            try:
                card = deck.pop()
            except IndexError:
                gs['phase'] = 'showdown'
                gs['show_all'] = True
                gs['message'] = '牌堆已空！'
                gs['message_class'] = 'tie-message'
                gs['result'] = 'tie'
                session.modified = True
                return
            gs['p1_hand'].append(card)
            gs['p1_value'] = calculate_hand_value(gs['p1_hand'])
            if gs['p1_value'] > 21:
                gs['phase'] = 'showdown'
                gs['show_all'] = True
                gs['p1_status'] = 'bust'
                gs['p2_value'] = calculate_hand_value(gs['p2_hand'])
                res, msg, cls = compare_hands(
                    gs['p1_hand'], gs['p2_hand'], True, False)
                gs['result'] = res
                gs['message'] = msg
                gs['message_class'] = cls
            elif gs['p1_value'] == 21:
                gs['phase'] = 'wait_p2'
                gs['p1_status'] = 'stood_21'
                gs['message'] = '玩家1达到21点！请将设备交给玩家2。'
                gs['message_class'] = ''

        elif action == 'stand':
            gs['phase'] = 'wait_p2'
            gs['p1_status'] = 'stood'
            gs['message'] = '请将设备交给玩家2。'
            gs['message_class'] = ''

    # ── wait_p2 ──
    elif phase == 'wait_p2':
        if action == 'pass_device':
            gs['current_player'] = 2
            if gs.get('p2_natural'):
                # P2 had natural from the start
                gs['phase'] = 'showdown'
                gs['show_all'] = True
                gs['p2_value'] = calculate_hand_value(gs['p2_hand'])
                gs['p2_status'] = 'blackjack'
                res, msg, cls = compare_hands(
                    gs['p1_hand'], gs['p2_hand'],
                    gs['p1_status'] == 'bust', False)
                gs['result'] = res
                gs['message'] = msg
                gs['message_class'] = cls
            else:
                gs['phase'] = 'p2_turn'
                gs['p2_value'] = calculate_hand_value(gs['p2_hand'])
                gs['message'] = None
                gs['message_class'] = ''

    # ── p2_turn ──
    elif phase == 'p2_turn':
        if action == 'hit':
            try:
                card = deck.pop()
            except IndexError:
                gs['phase'] = 'showdown'
                gs['show_all'] = True
                gs['message'] = '牌堆已空！'
                gs['message_class'] = 'tie-message'
                gs['result'] = 'tie'
                session.modified = True
                return
            gs['p2_hand'].append(card)
            gs['p2_value'] = calculate_hand_value(gs['p2_hand'])
            if gs['p2_value'] > 21:
                gs['phase'] = 'showdown'
                gs['show_all'] = True
                gs['p2_status'] = 'bust'
                res, msg, cls = compare_hands(
                    gs['p1_hand'], gs['p2_hand'], False, True)
                gs['result'] = res
                gs['message'] = msg
                gs['message_class'] = cls
            elif gs['p2_value'] == 21:
                gs['show_all'] = True
                gs['p2_status'] = 'stood_21'
                gs['phase'] = 'showdown'
                res, msg, cls = compare_hands(
                    gs['p1_hand'], gs['p2_hand'], False, False)
                gs['result'] = res
                gs['message'] = msg
                gs['message_class'] = cls

        elif action == 'stand':
            gs['show_all'] = True
            gs['p2_status'] = 'stood'
            gs['phase'] = 'showdown'
            res, msg, cls = compare_hands(
                gs['p1_hand'], gs['p2_hand'], False, False)
            gs['result'] = res
            gs['message'] = msg
            gs['message_class'] = cls

    session.modified = True
