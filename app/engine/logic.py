from .exceptions import PokerError, InsufficientChipsError, InvalidActionError
from .hand_evaluator import get_hand_description
def calculate_blinds(table):
    """Takes chips from the first two active players and adds to pot."""
    # Simplified: Player 0 is SB, Player 1 is BB
    sb_amount = table.sb_amount
    bb_amount = table.bb_amount
    sb_player = table.players[0]
    bb_player = table.players[1]
    
    # Small Blind
    sb_player.chips -= sb_amount
    sb_player.current_bet = sb_amount
    
    # Big Blind
    bb_player.chips -= bb_amount
    bb_player.current_bet = bb_amount
    
    table.pot += (sb_amount + bb_amount)
    print(f"Blinds posted: {sb_player.name} ({sb_amount}), {bb_player.name} ({bb_amount})")

def handle_betting_round(table):
    """
    Handle a betting round with proper raise/re-raise logic.
    
    When a player raises, they become the "last aggressor". The action continues
    around the table until it returns to the last aggressor AND everyone has
    either matched the bet or folded. If someone re-raises, they become the new
    last aggressor and the raiser gets another chance to act.
    """
    table.get_action_order()
    
    # Get active (non-folded) players in action order
    active_players = [p for p in table.ordered_players if not p.folded and p.is_active]
    
    if len(active_players) <= 1:
        return table
    
    # Track the last player who raised/bet - action ends when it comes back to them
    # Initially set to None so everyone must act at least once
    last_aggressor = None
    
    # Track which players have acted since the last raise
    # Using player IDs to track who has acted
    players_acted_since_last_raise = set()
    
    # Current position in the ordered_players list
    current_index = 0
    
    highest_bet = max([p.current_bet for p in table.players])
    
    while True:
        # Get current player from ordered list
        p = table.ordered_players[current_index]
        
        # Skip folded or inactive players
        if p.folded or not p.is_active:
            current_index = (current_index + 1) % len(table.ordered_players)
            continue
        
        # Check termination conditions BEFORE player acts:
        # 1. Only one player left (everyone else folded)
        active_count = len([pl for pl in table.players if not pl.folded and pl.is_active])
        if active_count <= 1:
            break
        
        # 2. Action has returned to the last aggressor AND all active players have acted
        #    AND everyone's bet matches the highest bet
        if last_aggressor is not None:
            all_bets_matched = all(
                pl.current_bet == highest_bet 
                for pl in table.players 
                if not pl.folded and pl.is_active
            )
            # If we've come back to the last aggressor and all bets are matched, round is over
            if p.playerid == last_aggressor and all_bets_matched:
                break
        else:
            # No one has bet/raised yet - check if everyone has checked (all acted, all bets equal)
            all_have_acted = all(
                pl.playerid in players_acted_since_last_raise 
                for pl in table.players 
                if not pl.folded and pl.is_active
            )
            all_bets_matched = all(
                pl.current_bet == highest_bet 
                for pl in table.players 
                if not pl.folded and pl.is_active
            )
            if all_have_acted and all_bets_matched:
                break

        print(f"\n--- {p.name}'s Turn ---")
        print(f"Hand: {p.current_hand} | Chips: {p.chips}")
        # Show best hand if community cards are available
        if table.visible_cards > 0:
            visible_community = table.community_cards[:table.visible_cards]
            best_hand = get_hand_description(p, visible_community)
            print(f"Best Hand: {best_hand}")
        print(f"Pot: {table.pot} | To Call: {highest_bet - p.current_bet}")

        try:
            # Determine available options to show user
            options = "(f)old, (r)aise"
            if p.current_bet == highest_bet:
                options += ", (c)heck"
            else:
                options += ", (c)all"
            
            action = input(f"Action {options}: ").strip().lower()

            if action in ("fold", "f"):
                p.folded = True
                print(f"{p.name} folds.")
                players_acted_since_last_raise.add(p.playerid)
            
            elif action in ("check", "c") and p.current_bet == highest_bet:
                print(f"{p.name} checks.")
                players_acted_since_last_raise.add(p.playerid)

            elif action in ("call", "c") and p.current_bet < highest_bet:
                amount_to_call = highest_bet - p.current_bet
                if amount_to_call > p.chips:
                    raise InsufficientChipsError("Not enough chips to call.")
                
                p.chips -= amount_to_call
                p.current_bet += amount_to_call
                table.pot += amount_to_call
                print(f"{p.name} calls {amount_to_call}.")
                players_acted_since_last_raise.add(p.playerid)

            elif action in ("raise", "r"):
                raise_amt = int(input(f"Enter TOTAL bet (must be > {highest_bet}): "))
                if raise_amt <= highest_bet:
                    raise InvalidActionError(f"Raise must be more than {highest_bet}")
                
                total_contribution = raise_amt - p.current_bet
                if total_contribution > p.chips:
                    raise InsufficientChipsError(f"Needs {total_contribution}, has {p.chips}")
                
                p.chips -= total_contribution
                p.current_bet = raise_amt
                table.pot += total_contribution
                highest_bet = raise_amt
                print(f"{p.name} raises to {raise_amt}.")
                
                # This player is now the last aggressor
                # Reset the acted set - everyone else needs to act again
                last_aggressor = p.playerid
                players_acted_since_last_raise = {p.playerid}
            
            else:
                raise InvalidActionError("Invalid command.")

            # Move to next player
            current_index = (current_index + 1) % len(table.ordered_players)

        except (InsufficientChipsError, InvalidActionError, ValueError) as e:
            print(f"❌ {e}")
            # Don't move to next player - let the same player try again
            continue

    # Reset current_bet for all players at the end of the round
    for p in table.players:
        p.current_bet = 0
        
    return table
