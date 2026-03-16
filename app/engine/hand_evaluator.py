"""
Poker Hand Evaluator

Evaluates poker hands and determines winners.
Hand rankings from highest to lowest:
1. Royal Flush (10)
2. Straight Flush (9)
3. Four of a Kind (8)
4. Full House (7)
5. Flush (6)
6. Straight (5)
7. Three of a Kind (4)
8. Two Pair (3)
9. One Pair (2)
10. High Card (1)
"""

from itertools import combinations
from typing import List, Tuple, Optional
from .models import Card, Player

# Rank values for comparison (Ace can be high or low in straights)
RANK_VALUES = {
    '2': 2, '3': 3, '4': 4, '5': 5, '6': 6, '7': 7, '8': 8,
    '9': 9, '10': 10, 'J': 11, 'Q': 12, 'K': 13, 'A': 14
}

# Hand type rankings
HAND_RANKINGS = {
    'Royal Flush': 10,
    'Straight Flush': 9,
    'Four of a Kind': 8,
    'Full House': 7,
    'Flush': 6,
    'Straight': 5,
    'Three of a Kind': 4,
    'Two Pair': 3,
    'One Pair': 2,
    'High Card': 1
}


def get_rank_value(rank: str) -> int:
    """Convert card rank to numeric value."""
    return RANK_VALUES.get(rank, 0)


def is_flush(cards: List[Card]) -> bool:
    """Check if all 5 cards are the same suit."""
    return len(set(c.suit for c in cards)) == 1


def is_straight(cards: List[Card]) -> Tuple[bool, int]:
    """
    Check if cards form a straight.
    Returns (is_straight, high_card_value)
    Handles Ace-low straight (A-2-3-4-5) as well.
    """
    values = sorted([get_rank_value(c.rank) for c in cards])
    
    # Check for Ace-low straight (A-2-3-4-5)
    if values == [2, 3, 4, 5, 14]:
        return True, 5  # 5-high straight
    
    # Check for regular straight
    for i in range(len(values) - 1):
        if values[i + 1] - values[i] != 1:
            return False, 0
    
    return True, values[-1]


def get_rank_counts(cards: List[Card]) -> dict:
    """Count occurrences of each rank."""
    counts = {}
    for card in cards:
        counts[card.rank] = counts.get(card.rank, 0) + 1
    return counts


def evaluate_hand(cards: List[Card]) -> Tuple[int, str, List[int]]:
    """
    Evaluate a 5-card poker hand.
    Returns: (hand_rank, hand_name, tiebreaker_values)
    
    tiebreaker_values is a list used to compare hands of the same type.
    """
    rank_counts = get_rank_counts(cards)
    counts_sorted = sorted(rank_counts.values(), reverse=True)
    
    # Get unique ranks sorted by count then by value (for tiebreakers)
    ranks_by_count = sorted(
        rank_counts.keys(),
        key=lambda r: (rank_counts[r], get_rank_value(r)),
        reverse=True
    )
    
    is_flush_hand = is_flush(cards)
    is_straight_hand, straight_high = is_straight(cards)
    
    # Royal Flush
    if is_flush_hand and is_straight_hand and straight_high == 14:
        values = sorted([get_rank_value(c.rank) for c in cards])
        if values == [10, 11, 12, 13, 14]:
            return HAND_RANKINGS['Royal Flush'], 'Royal Flush', [14]
    
    # Straight Flush
    if is_flush_hand and is_straight_hand:
        return HAND_RANKINGS['Straight Flush'], 'Straight Flush', [straight_high]
    
    # Four of a Kind
    if counts_sorted == [4, 1]:
        quad_rank = [r for r, c in rank_counts.items() if c == 4][0]
        kicker = [r for r, c in rank_counts.items() if c == 1][0]
        return HAND_RANKINGS['Four of a Kind'], 'Four of a Kind', [get_rank_value(quad_rank), get_rank_value(kicker)]
    
    # Full House
    if counts_sorted == [3, 2]:
        trips_rank = [r for r, c in rank_counts.items() if c == 3][0]
        pair_rank = [r for r, c in rank_counts.items() if c == 2][0]
        return HAND_RANKINGS['Full House'], 'Full House', [get_rank_value(trips_rank), get_rank_value(pair_rank)]
    
    # Flush
    if is_flush_hand:
        values = sorted([get_rank_value(c.rank) for c in cards], reverse=True)
        return HAND_RANKINGS['Flush'], 'Flush', values
    
    # Straight
    if is_straight_hand:
        return HAND_RANKINGS['Straight'], 'Straight', [straight_high]
    
    # Three of a Kind
    if counts_sorted == [3, 1, 1]:
        trips_rank = [r for r, c in rank_counts.items() if c == 3][0]
        kickers = sorted([get_rank_value(r) for r, c in rank_counts.items() if c == 1], reverse=True)
        return HAND_RANKINGS['Three of a Kind'], 'Three of a Kind', [get_rank_value(trips_rank)] + kickers
    
    # Two Pair
    if counts_sorted == [2, 2, 1]:
        pairs = sorted([get_rank_value(r) for r, c in rank_counts.items() if c == 2], reverse=True)
        kicker = [get_rank_value(r) for r, c in rank_counts.items() if c == 1][0]
        return HAND_RANKINGS['Two Pair'], 'Two Pair', pairs + [kicker]
    
    # One Pair
    if counts_sorted == [2, 1, 1, 1]:
        pair_rank = [r for r, c in rank_counts.items() if c == 2][0]
        kickers = sorted([get_rank_value(r) for r, c in rank_counts.items() if c == 1], reverse=True)
        return HAND_RANKINGS['One Pair'], 'One Pair', [get_rank_value(pair_rank)] + kickers
    
    # High Card
    values = sorted([get_rank_value(c.rank) for c in cards], reverse=True)
    return HAND_RANKINGS['High Card'], 'High Card', values


def find_best_hand(hole_cards: List[Card], community_cards: List[Card]) -> Tuple[List[Card], int, str, List[int]]:
    """
    Find the best 5-card hand from player's hole cards + community cards.
    Returns: (best_5_cards, hand_rank, hand_name, tiebreaker_values)
    """
    all_cards = hole_cards + community_cards
    
    if len(all_cards) < 5:
        # Not enough cards yet - just evaluate what we have
        if len(all_cards) == 0:
            return [], 0, 'No Cards', []
        # Pad evaluation or return current best
        return all_cards, 0, 'Incomplete Hand', [get_rank_value(c.rank) for c in all_cards]
    
    best_hand = None
    best_rank = 0
    best_name = ''
    best_tiebreakers = []
    best_cards = []
    
    # Try all combinations of 5 cards
    for combo in combinations(all_cards, 5):
        cards = list(combo)
        rank, name, tiebreakers = evaluate_hand(cards)
        
        # Compare hands: higher rank wins, or compare tiebreakers
        if rank > best_rank or (rank == best_rank and tiebreakers > best_tiebreakers):
            best_rank = rank
            best_name = name
            best_tiebreakers = tiebreakers
            best_cards = cards
    
    return best_cards, best_rank, best_name, best_tiebreakers


def get_hand_description(player: Player, community_cards: List[Card]) -> str:
    """
    Get a human-readable description of the player's best hand.
    """
    if not community_cards:
        return "Waiting for community cards..."
    
    best_cards, rank, name, tiebreakers = find_best_hand(player.current_hand, community_cards)
    
    if rank == 0:
        return "Incomplete hand"
    
    # Format the best hand cards for display
    cards_str = ", ".join([f"{c.rank}{c.suit[0]}" for c in best_cards])
    return f"{name} ({cards_str})"


def determine_winner(players: List[Player], community_cards: List[Card]) -> Tuple[List[Player], str]:
    """
    Determine the winner(s) among active players.
    Returns: (list_of_winners, winning_hand_description)
    
    Can return multiple winners in case of a tie (split pot).
    """
    active_players = [p for p in players if not p.folded and p.is_active]
    
    if len(active_players) == 0:
        return [], "No active players"
    
    if len(active_players) == 1:
        winner = active_players[0]
        _, _, hand_name, _ = find_best_hand(winner.current_hand, community_cards)
        return [winner], f"{winner.name} wins (everyone else folded)"
    
    # Evaluate all hands
    player_hands = []
    for player in active_players:
        best_cards, rank, name, tiebreakers = find_best_hand(player.current_hand, community_cards)
        player_hands.append({
            'player': player,
            'cards': best_cards,
            'rank': rank,
            'name': name,
            'tiebreakers': tiebreakers
        })
    
    # Find the best hand(s)
    best_rank = max(h['rank'] for h in player_hands)
    best_hands = [h for h in player_hands if h['rank'] == best_rank]
    
    # If multiple players have the same rank, compare tiebreakers
    if len(best_hands) > 1:
        best_tiebreakers = max(h['tiebreakers'] for h in best_hands)
        best_hands = [h for h in best_hands if h['tiebreakers'] == best_tiebreakers]
    
    winners = [h['player'] for h in best_hands]
    winning_hand = best_hands[0]['name']
    
    if len(winners) == 1:
        winner = winners[0]
        cards_str = ", ".join([f"{c.rank}{c.suit[0]}" for c in best_hands[0]['cards']])
        return winners, f"{winner.name} wins with {winning_hand} ({cards_str})"
    else:
        names = ", ".join([w.name for w in winners])
        return winners, f"Split pot! {names} tie with {winning_hand}"


def show_all_hands(players: List[Player], community_cards: List[Card]) -> None:
    """
    Display all active players' hands at showdown.
    """
    print("\n" + "=" * 40)
    print("SHOWDOWN")
    print("=" * 40)
    
    active_players = [p for p in players if not p.folded and p.is_active]
    
    for player in active_players:
        hole_cards_str = ", ".join([f"{c.rank}{c.suit[0]}" for c in player.current_hand])
        best_cards, rank, name, _ = find_best_hand(player.current_hand, community_cards)
        best_cards_str = ", ".join([f"{c.rank}{c.suit[0]}" for c in best_cards])
        
        print(f"\n{player.name}:")
        print(f"  Hole Cards: [{hole_cards_str}]")
        print(f"  Best Hand: {name} - [{best_cards_str}]")
