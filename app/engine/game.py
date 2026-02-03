import random 
from typing import List, Optional
from .models import Card, Player

class pokertable:
    def __init__(self, table_id: str, max_players: int = 6):
        self.table_id = table_id
        self.players: List[Player] = [] 
        self.deck: List[Card] = self.generate_deck()
        self.pot: int = 0
        self.stage = "PRE FLOP"
        self.sb_amount = 100
        self.bb_amount = 200
        self.sb_pos:int = -1 #postion of small blind
        # All 5 cards dealt for the round (hidden from players initially)
        self.community_cards: List[Card] = [] 
        self.visible_cards: int = 0
        self.ordered_players: List[Player] = self.players

    def generate_deck(self) -> List[Card]:
        suits = ["heart", "diamond", "club", "spade"]
        numbers = ["A", "2", "3", "4", "5", "6", "7", "8", "9","10", "J","Q", "K"]
        deck = []
        for s in suits:
            for n in numbers:
                c = Card(suit=s, rank=n)
                deck.append(c)

        random.shuffle(deck)

        return deck
    
    def add_player(self,  Player: Player):
        self.players.append(Player)
    
    def remove_player(self, Player: Player):
        self.players.remove(Player)

    def deal_cards(self):
        self.get_action_order()
        for _ in range(2):
            for p in self.ordered_players:
                if p.is_active:
                    p.current_hand.append(self.deck.pop())

    def deal_community_cards(self):
        self.deck.pop() #first burn
        for _ in range(3):
            self.community_cards.append(self.deck.pop())
        self.deck.pop()
        self.community_cards.append(self.deck.pop())
        self.deck.pop()
        self.community_cards.append(self.deck.pop())
    
    def get_action_order(self):
        """Returns the list of players in the order they should act."""
        num_players = len(self.players)
        
        # Calculate BB position (usually SB + 1)
        bb_pos = (self.sb_pos + 1) % num_players
        
        if self.stage == "PRE-FLOP":
            # Start from the person to the left of the Big Blind (UTG)
            start_index = (bb_pos + 1) % num_players
        else:
            # Start from the Small Blind (or first active player to their left)
            start_index = self.sb_pos
            
        # Rotate the list: everything from start_index to end + everything from start to start_index
        self.ordered_players = self.players[start_index:] + self.players[:start_index]

    def prepare_new_round(self):
        self.deck = self.generate_deck()
        self.pot = 0
        self.stage = "PRE-FLOP"
        self.visible_cards = 0
        self.sb_pos  = (self.sb_pos+1) % len(self.players)

        for p in self.players:
            p.current_bet = 0
            p.current_hand = []
            p.folded = False
            p.is_active = True if p.chips > 0 else False

        self.deal_cards()
        self.deal_community_cards()

    def reveal_next_stage(self):
        """Progresses the game stage and updates the number of visible cards."""
        if self.stage == "PRE-FLOP":
            self.visible_cards = 3
            self.stage = "FLOP"
        elif self.stage == "FLOP":
            self.visible_cards = 4
            self.stage = "TURN"
        elif self.stage == "TURN":
            self.visible_cards = 5
            self.stage = "RIVER"
        elif self.stage == "RIVER":
            self.stage = "SHOWDOWN"
        
        # Unified print logic to avoid repetition
        self._print_board()

    def _print_board(self):
        """Helper to display only what is currently visible."""
        if self.visible_cards > 0:
            # Slice the list based on the integer value
            current_board = self.community_cards[:self.visible_cards]
            print(f"\n--- {self.stage} ---")
            print(f"Board: {current_board}")
        


        





    



        


    