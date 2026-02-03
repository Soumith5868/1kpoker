from .exceptions import PokerError, InsufficientChipsError, InvalidActionError
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
    round_active = True
    table.get_action_order()
    while round_active:
        # Reset this count for each loop iteration to ensure everyone acts
        players_acted = 0
        highest_bet = max([p.current_bet for p in table.players])
        
        # In Poker, if the highest bet is 0, 'Check' is possible.
        # If someone bets, 'Check' is no longer an option.
        
        for p in table.ordered_players:
            if p.folded or not p.is_active:
                continue

            # Termination condition:
            # Everyone has acted AND everyone's bet matches the highest bet

            print(f"\n--- {p.name}'s Turn ---")
            print(f"Hand: {p.current_hand} | Chips: {p.chips}")
            print(f"Pot: {table.pot} | To Call: {highest_bet - p.current_bet}")

            try:
                # Determine available options to show user
                options = "(f)old, (r)aise"
                if p.current_bet == highest_bet:
                    options += ", (c)heck"
                else:
                    options += ", (c)all"
                
                action = input(f"Action {options}: ").strip().lower()

                if action == "fold":
                    p.folded = True
                
                elif action == "check":
                    if p.current_bet < highest_bet:
                        raise InvalidActionError("Cannot check. You must call or fold.")
                    # Checking does nothing to the pot or chips
                    print(f"{p.name} checks.")

                elif action == "call":
                    amount_to_call = highest_bet - p.current_bet
                    if amount_to_call > p.chips:
                        raise InsufficientChipsError("Not enough chips to call.")
                    
                    p.chips -= amount_to_call
                    p.current_bet += amount_to_call
                    table.pot += amount_to_call
                    print(f"{p.name} calls {amount_to_call}.")

                elif action == "raise":
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
                
                else:
                    raise InvalidActionError("Invalid command.")

                players_acted += 1

            except (InsufficientChipsError, InvalidActionError, ValueError) as e:
                print(f"❌ {e}")
                continue # Let the same player try again
        if (players_acted >= len([pl for pl in table.players if not pl.folded])) and \
        all(pl.current_bet == highest_bet for pl in table.players if not pl.folded):
            round_active = False      
        # Quick check: If only one person left, stop the round
        if len([pl for pl in table.players if not pl.folded]) <= 1:
            round_active = False

    # Reset current_bet for all players at the end of the round
    for p in table.players:
        p.current_bet = 0
        
    return table