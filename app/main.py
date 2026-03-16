from engine.models import Player
from engine.game import pokertable
from engine.logic import calculate_blinds, handle_betting_round
from engine.hand_evaluator import determine_winner, show_all_hands

def start_terminal_game():
    # 1. Setup
    table = pokertable(table_id="dev-room")
    names = ["Alice", "Bob", "Charlie"]
    for i, name in enumerate(names):
        table.add_player(Player(playerid=str(i), name=name, chips=1000, current_bet=0, folded=False))

    print("Welcome to the Poker Engine Terminal")
    
    while True:
        # 2. Reset Table for a new hand
        table.prepare_new_round() 
        print("\n" + "="*30)
        print("NEW HAND DEALT")
        print("="*30)

        # 3. Pre-Flop
        calculate_blinds(table)
        handle_betting_round(table)

        # 4. Flop (Reveal 3)
        table.reveal_next_stage()
        handle_betting_round(table)

        # 5. Turn (Reveal 1)
        table.reveal_next_stage()
        handle_betting_round(table)

        # 6. River (Reveal 1)
        table.reveal_next_stage()
        handle_betting_round(table)

        # 7. Showdown and Winner Determination
        print(f"\nFinal Pot: {table.pot}")
        
        # Show all hands at showdown
        show_all_hands(table.players, table.community_cards)
        
        # Determine winner(s)
        winners, description = determine_winner(table.players, table.community_cards)
        
        print("\n" + "=" * 40)
        print(description)
        print("=" * 40)
        
        # Award pot to winner(s)
        if len(winners) == 1:
            winners[0].chips += table.pot
            print(f"{winners[0].name} wins {table.pot} chips!")
        elif len(winners) > 1:
            # Split pot
            split_amount = table.pot // len(winners)
            remainder = table.pot % len(winners)
            for i, winner in enumerate(winners):
                # Give remainder to first winner (arbitrary tiebreaker)
                award = split_amount + (remainder if i == 0 else 0)
                winner.chips += award
            print(f"Pot split: {split_amount} chips each!")
        
        # Show chip counts
        print("\nChip Counts:")
        for p in table.players:
            print(f"  {p.name}: {p.chips}")
        
        cont = input("Play another hand? (y/n): ")
        if cont.lower() != 'y':
            break

if __name__ == "__main__":
    start_terminal_game()
