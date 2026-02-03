from engine.models import Player
from engine.game import pokertable
from engine.logic import calculate_blinds, handle_betting_round

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

        # 7. Winner (Manual for now)
        print(f"\nFinal Pot: {table.pot}")
        winner_idx = int(input("Who won? Enter Player Index (0, 1, or 2): "))
        table.players[winner_idx].chips += table.pot
        
        cont = input("Play another hand? (y/n): ")
        if cont.lower() != 'y':
            break

if __name__ == "__main__":
    start_terminal_game()