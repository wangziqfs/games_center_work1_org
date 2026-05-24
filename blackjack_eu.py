import random
from playcard import make_deck

# from userlog import add_log_entry

CARD_VALUES = {
    'A': 11,
    '2': 2,
    '3': 3,
    '4': 4,
    '5': 5,
    '6': 6,
    '7': 7,
    '8': 8,
    '9': 9,
    'T': 10,
    'J': 10,
    'Q': 10,
    'K': 10,
}


def calculate_hand_value(hand):
    """Calculate the value of a hand, considering Aces as 1 or 11."""
    value, aces = 0, 0
    for card in hand:
        rank = card[0]
        value += CARD_VALUES[rank]
        aces += rank == 'A'

    # Adjust for Aces if needed.
    while value > 21 and aces:
        value -= 10
        aces -= 1

    return value


def is_natural_blackjack(hand):
    """A natural Blackjack must be made by the first two cards: A + 10-point card."""
    return len(hand) == 2 and calculate_hand_value(hand) == 21


def new_game(session):
    """Start a European Blackjack game.

    European rule implemented here:
    - The dealer receives only one face-up card at the beginning.
    - No dealer hole card is dealt before the player's actions.
    - Therefore, no initial dealer Blackjack check is performed here.
    """
    session_id = session.get('session_id', '')
    deck = make_deck()
    random.shuffle(deck)

    # Deal two cards to the player and only one card to the dealer.
    card1, card2, card3 = deck.pop(), deck.pop(), deck.pop()
    player_hand = [card1, card3]
    dealer_hand = [card2]

    dealer_value = calculate_hand_value(dealer_hand)
    player_value = calculate_hand_value(player_hand)

    # add_log_entry(session_id, 'New European Blackjack game. '
    #               f'Dealer card: [{card2}]. Player cards: [{card1}, {card3}].')

    session['game_state'] = {
        'deck': deck,
        'dealer_hand': dealer_hand,
        'player_hand': player_hand,
        'dealer_value': dealer_value,
        'player_value': player_value,
        'message': None,
        'message_class': '',
    }


def game_update(session, action):
    game_state = session.get('game_state', {})
    if not game_state:
        return new_game(session)

    # If the round is already over, ignore further actions.
    if game_state.get('message'):
        return

    session_id = session.get('session_id', '')
    deck = game_state['deck']
    dealer_hand = game_state['dealer_hand']
    player_hand = game_state['player_hand']

    if action == 'hit':
        # Deal a card to the player.
        card = deck.pop()
        player_hand.append(card)
        player_value = calculate_hand_value(player_hand)
        game_state['player_value'] = player_value
        # add_log_entry(session_id, f'Player hits and gets {card}.')

        # The player loses immediately after busting.
        if player_value > 21:
            game_state['dealer_value'] = calculate_hand_value(dealer_hand)
            game_state['message'] = '你爆牌了！庄家获胜。'
            game_state['message_class'] = 'lose-message'
            # add_log_entry(session_id, 'Player busts and loses.')

    elif action == 'stand':
        player_value = game_state['player_value']
        player_natural = is_natural_blackjack(player_hand)

        # European Blackjack: the dealer draws the second card only after
        # the player has finished all actions.
        second_card = deck.pop()
        dealer_hand.append(second_card)
        dealer_value = calculate_hand_value(dealer_hand)
        # add_log_entry(session_id, f'Player stands. Dealer gets second card {second_card}.')

        # Core European rule: if the dealer's first two cards form a natural
        # Blackjack, only a player's natural Blackjack can tie it.
        dealer_natural = is_natural_blackjack(dealer_hand)
        if dealer_natural:
            game_state['dealer_value'] = dealer_value
            if player_natural:
                game_state['message'] = '双方都是黑杰克，平局！'
                game_state['message_class'] = 'tie-message'
                # add_log_entry(session_id, 'Dealer and player tie with both natural blackjack.')
            else:
                game_state['message'] = '庄家天胡黑杰克！你输了。'
                game_state['message_class'] = 'lose-message'
                # add_log_entry(session_id, 'Dealer wins with a natural blackjack.')
            session.modified = True
            return

        # If the dealer does not have natural Blackjack, continue using
        # the original dealer rule.
        while dealer_value < 17:
            card = deck.pop()
            dealer_hand.append(card)
            dealer_value = calculate_hand_value(dealer_hand)
            # add_log_entry(session_id, f'Dealer gets {card}.')

        game_state['dealer_value'] = dealer_value

        # Determine the winner using the original comparison rules.
        if dealer_value > 21:
            game_state['message'] = '庄家爆牌！你赢了！'
            game_state['message_class'] = 'win-message'
            # add_log_entry(session_id, 'Dealer busts. Player wins.')
        elif dealer_value > player_value:
            game_state['message'] = '庄家获胜！'
            game_state['message_class'] = 'lose-message'
            # add_log_entry(session_id, f'Dealer wins by {dealer_value}:{player_value}.')
        elif dealer_value < player_value:
            game_state['message'] = '恭喜，你赢了！'
            game_state['message_class'] = 'win-message'
            # add_log_entry(session_id, f'Player wins by {player_value}:{dealer_value}.')
        else:
            game_state['message'] = '平局！'
            game_state['message_class'] = 'tie-message'
            # add_log_entry(session_id, f'Dealer and Player tie with {player_value}:{dealer_value}.')

    else:
        # add_log_entry(session_id, f'Unknown action {action}.')
        return

    session.modified = True
