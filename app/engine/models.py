from pydantic import BaseModel, ConfigDict
from typing import List, Optional

class Card(BaseModel):
    model_config = ConfigDict(frozen=True)
    suit: str 
    rank: str 

    def __repr__(self):
        return f"{self.rank}{self.suit[0].lower()}"

class Player(BaseModel):
    playerid: str
    name: str
    chips: int
    folded: bool = True
    current_hand: List[Card] = []
    current_bet: int
    is_active: bool = True
