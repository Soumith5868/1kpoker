"""
WebSocket Message Schemas

Defines all message types for client-server communication over WebSocket.
"""

from pydantic import BaseModel
from typing import List, Optional, Literal, Any, Dict
from enum import Enum


# ============== Enums ==============

class ClientMessageType(str, Enum):
    JOIN_TABLE = "join_table"
    LEAVE_TABLE = "leave_table"
    START_GAME = "start_game"
    PLAYER_ACTION = "player_action"
    CHAT = "chat"


class ServerMessageType(str, Enum):
    # Connection events
    CONNECTED = "connected"
    ERROR = "error"
    
    # Table events
    PLAYER_JOINED = "player_joined"
    PLAYER_LEFT = "player_left"
    TABLE_STATE = "table_state"
    
    # Game events
    GAME_STARTED = "game_started"
    CARDS_DEALT = "cards_dealt"
    ACTION_REQUIRED = "action_required"
    PLAYER_ACTED = "player_acted"
    STAGE_CHANGED = "stage_changed"
    POT_UPDATED = "pot_updated"
    SHOWDOWN = "showdown"
    ROUND_ENDED = "round_ended"
    GAME_ENDED = "game_ended"
    
    # Chat
    CHAT_MESSAGE = "chat_message"


class PlayerActionType(str, Enum):
    FOLD = "fold"
    CHECK = "check"
    CALL = "call"
    RAISE = "raise"
    ALL_IN = "all_in"


# ============== Client Messages ==============

class JoinTableMessage(BaseModel):
    type: Literal[ClientMessageType.JOIN_TABLE] = ClientMessageType.JOIN_TABLE
    player_name: str
    chips: Optional[int] = 1000


class LeaveTableMessage(BaseModel):
    type: Literal[ClientMessageType.LEAVE_TABLE] = ClientMessageType.LEAVE_TABLE


class StartGameMessage(BaseModel):
    type: Literal[ClientMessageType.START_GAME] = ClientMessageType.START_GAME


class PlayerActionMessage(BaseModel):
    type: Literal[ClientMessageType.PLAYER_ACTION] = ClientMessageType.PLAYER_ACTION
    action: PlayerActionType
    amount: Optional[int] = None  # Only for raise


class ChatMessage(BaseModel):
    type: Literal[ClientMessageType.CHAT] = ClientMessageType.CHAT
    message: str


# ============== Server Messages ==============

class CardSchema(BaseModel):
    suit: str
    rank: str


class PlayerPublicSchema(BaseModel):
    """Public player info visible to all"""
    player_id: str
    name: str
    chips: int
    current_bet: int
    folded: bool
    is_active: bool
    is_connected: bool = True
    best_hand: Optional[str] = None


class ConnectedMessage(BaseModel):
    type: Literal[ServerMessageType.CONNECTED] = ServerMessageType.CONNECTED
    player_id: str
    table_id: str
    message: str = "Connected to table"


class ErrorMessage(BaseModel):
    type: Literal[ServerMessageType.ERROR] = ServerMessageType.ERROR
    message: str
    code: Optional[str] = None


class PlayerJoinedMessage(BaseModel):
    type: Literal[ServerMessageType.PLAYER_JOINED] = ServerMessageType.PLAYER_JOINED
    player: PlayerPublicSchema
    players: List[PlayerPublicSchema]
    message: str


class PlayerLeftMessage(BaseModel):
    type: Literal[ServerMessageType.PLAYER_LEFT] = ServerMessageType.PLAYER_LEFT
    player_id: str
    player_name: str
    players: List[PlayerPublicSchema]
    message: str


class TableStateMessage(BaseModel):
    """Full table state sync"""
    type: Literal[ServerMessageType.TABLE_STATE] = ServerMessageType.TABLE_STATE
    table_id: str
    players: List[PlayerPublicSchema]
    pot: int
    stage: str
    community_cards: List[CardSchema]
    visible_cards: int
    current_player_id: Optional[str] = None
    sb_amount: int
    bb_amount: int
    sb_player_id: Optional[str] = None
    bb_player_id: Optional[str] = None
    is_game_active: bool = False


class GameStartedMessage(BaseModel):
    type: Literal[ServerMessageType.GAME_STARTED] = ServerMessageType.GAME_STARTED
    sb_pos: int
    bb_pos: int
    sb_player_id: str
    bb_player_id: str
    sb_amount: int
    bb_amount: int
    pot: int
    message: str


class CardsDealtMessage(BaseModel):
    """Private message - only sent to the specific player"""
    type: Literal[ServerMessageType.CARDS_DEALT] = ServerMessageType.CARDS_DEALT
    your_cards: List[CardSchema]
    message: str = "Cards dealt"


class ActionRequiredMessage(BaseModel):
    type: Literal[ServerMessageType.ACTION_REQUIRED] = ServerMessageType.ACTION_REQUIRED
    player_id: str
    player_name: str
    available_actions: List[str]
    to_call: int
    min_raise: int
    pot: int
    current_bet: int  # Highest bet on the table


class PlayerActedMessage(BaseModel):
    type: Literal[ServerMessageType.PLAYER_ACTED] = ServerMessageType.PLAYER_ACTED
    player_id: str
    player_name: str
    action: str
    amount: Optional[int] = None
    pot: int
    player_chips: int
    player_current_bet: int
    message: str


class StageChangedMessage(BaseModel):
    type: Literal[ServerMessageType.STAGE_CHANGED] = ServerMessageType.STAGE_CHANGED
    stage: str
    community_cards: List[CardSchema]
    visible_count: int
    pot: int
    message: str


class PotUpdatedMessage(BaseModel):
    type: Literal[ServerMessageType.POT_UPDATED] = ServerMessageType.POT_UPDATED
    pot: int


class PlayerHandResult(BaseModel):
    player_id: str
    player_name: str
    cards: List[CardSchema]
    hand_name: str
    hand_cards: List[CardSchema]
    is_winner: bool


class ShowdownMessage(BaseModel):
    type: Literal[ServerMessageType.SHOWDOWN] = ServerMessageType.SHOWDOWN
    hands: List[PlayerHandResult]
    winners: List[str]  # player_ids
    winning_hand: str
    pot: int
    message: str


class RoundEndedMessage(BaseModel):
    type: Literal[ServerMessageType.ROUND_ENDED] = ServerMessageType.ROUND_ENDED
    winners: List[str]
    pot_amount: int
    player_chips: Dict[str, int]  # player_id -> chips
    message: str
    next_round_in: int = 5  # seconds


class ChatBroadcastMessage(BaseModel):
    type: Literal[ServerMessageType.CHAT_MESSAGE] = ServerMessageType.CHAT_MESSAGE
    player_id: str
    player_name: str
    message: str


# ============== Utility Functions ==============

def parse_client_message(data: dict) -> Any:
    """Parse incoming client message based on type"""
    msg_type = data.get("type")
    
    if msg_type == ClientMessageType.JOIN_TABLE:
        return JoinTableMessage(**data)
    elif msg_type == ClientMessageType.LEAVE_TABLE:
        return LeaveTableMessage(**data)
    elif msg_type == ClientMessageType.START_GAME:
        return StartGameMessage(**data)
    elif msg_type == ClientMessageType.PLAYER_ACTION:
        return PlayerActionMessage(**data)
    elif msg_type == ClientMessageType.CHAT:
        return ChatMessage(**data)
    else:
        raise ValueError(f"Unknown message type: {msg_type}")
