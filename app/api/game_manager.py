"""
Game Manager

Manages poker tables and game state, wrapping the existing game engine
for multiplayer WebSocket functionality.
"""

import uuid
import asyncio
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
import logging

from engine.models import Player as EnginePlayer, Card as EngineCard
from engine.game import pokertable
from engine.logic import calculate_blinds, handle_betting_round
from engine.hand_evaluator import determine_winner, show_all_hands, get_hand_description
from api.schemas import (
    CardSchema, PlayerPublicSchema, PlayerActionType,
    PlayerActedMessage, ActionRequiredMessage, StageChangedMessage,
    ShowdownMessage, RoundEndedMessage, GameStartedMessage, CardsDealtMessage
)
from api.websocket_manager import manager

logger = logging.getLogger(__name__)


class PokerGameManager:
    """
    Manages multiple poker tables and their game states.
    """
    
    def __init__(self):
        # table_id -> pokertable instance
        self.tables: Dict[str, pokertable] = {}
        # table_id -> game state metadata
        self.table_metadata: Dict[str, dict] = {}
        # player_id -> table_id mapping
        self.player_to_table: Dict[str, str] = {}
        # player_id -> player_name mapping
        self.player_names: Dict[str, str] = {}
    
    # ============== Table Management ==============
    
    def create_table(self, table_id: str, max_players: int = 6, sb_amount: int = 100, bb_amount: int = 200) -> pokertable:
        """Create a new poker table."""
        table = pokertable(table_id=table_id, max_players=max_players)
        table.sb_amount = sb_amount
        table.bb_amount = bb_amount
        
        self.tables[table_id] = table
        self.table_metadata[table_id] = {
            "created_at": datetime.now(),
            "max_players": max_players,
            "sb_amount": sb_amount,
            "bb_amount": bb_amount,
            "is_game_active": False,
            "current_player_turn": None,
            "game_phase": "waiting",  # waiting, preflop, flop, turn, river, showdown
            "connected_players": set(),
            "players_acted": set(),
            "last_raiser": None
        }
        
        logger.info(f"Created table {table_id}")
        return table
    
    def get_table(self, table_id: str) -> Optional[pokertable]:
        """Get a table by ID."""
        return self.tables.get(table_id)
    
    def delete_table(self, table_id: str):
        """Delete a table and all its players."""
        if table_id in self.tables:
            # Remove all players from this table
            for player_id, player_table_id in list(self.player_to_table.items()):
                if player_table_id == table_id:
                    del self.player_to_table[player_id]
                    if player_id in self.player_names:
                        del self.player_names[player_id]
            
            del self.tables[table_id]
            del self.table_metadata[table_id]
            logger.info(f"Deleted table {table_id}")
    
    # ============== Player Management ==============
    
    def add_player_to_table(self, table_id: str, player_name: str, chips: int = 1000, player_id: Optional[str] = None) -> Tuple[str, EnginePlayer]:
        """
        Add a player to a table.
        Returns (player_id, player_object)
        """
        if table_id not in self.tables:
            raise ValueError(f"Table {table_id} does not exist")

        # Use provided player_id or generate one.
        if player_id is None:
            player_id = str(uuid.uuid4())

        # If player already exists with this ID, return existing player
        existing_player = self.get_player(player_id)
        if existing_player:
            return player_id, existing_player

        # Create engine player
        player = EnginePlayer(
            playerid=player_id,
            name=player_name,
            chips=chips,
            current_bet=0,
            folded=False
        )
        
        # Add to table
        table = self.tables[table_id]
        table.add_player(player)
        
        # Update mappings
        self.player_to_table[player_id] = table_id
        self.player_names[player_id] = player_name
        
        # Update metadata
        metadata = self.table_metadata[table_id]
        metadata["connected_players"].add(player_id)
        
        logger.info(f"Added player {player_name} ({player_id}) to table {table_id}")
        return player_id, player
    
    def remove_player_from_table(self, table_id: str, player_id: str):
        """Remove a player from a table."""
        if table_id not in self.tables:
            return
        
        table = self.tables[table_id]
        
        # Find player in table
        player_to_remove = None
        for player in table.players:
            if player.playerid == player_id:
                player_to_remove = player
                break
        
        if player_to_remove:
            table.remove_player(player_to_remove)
        
        # Update mappings
        if player_id in self.player_to_table:
            del self.player_to_table[player_id]
        
        if player_id in self.player_names:
            del self.player_names[player_id]
        
        # Update metadata
        if table_id in self.table_metadata:
            metadata = self.table_metadata[table_id]
            metadata["connected_players"].discard(player_id)
        
        logger.info(f"Removed player {player_id} from table {table_id}")
    
    def get_player(self, player_id: str) -> Optional[EnginePlayer]:
        """Get a player by ID."""
        table_id = self.player_to_table.get(player_id)
        if not table_id or table_id not in self.tables:
            return None
        
        table = self.tables[table_id]
        for player in table.players:
            if player.playerid == player_id:
                return player
        return None
    
    def get_player_table(self, player_id: str) -> Optional[str]:
        """Get the table ID for a player."""
        return self.player_to_table.get(player_id)
    
    # ============== Game State Conversion ==============
    
    def engine_card_to_schema(self, card: EngineCard) -> CardSchema:
        """Convert engine Card to schema CardSchema."""
        return CardSchema(suit=card.suit, rank=card.rank)
    
    def engine_player_to_public_schema(self, player: EnginePlayer, community_cards: List[EngineCard]) -> PlayerPublicSchema:
        """Convert engine Player to public schema."""
        table_id = self.player_to_table.get(player.playerid)
        is_connected = False
        if table_id and table_id in self.table_metadata:
            is_connected = player.playerid in self.table_metadata[table_id]["connected_players"]

        best_hand = None
        if community_cards and player.current_hand:
            try:
                best_hand_info = get_hand_description(player, community_cards)
                if best_hand_info and len(best_hand_info) >= 3:
                    best_hand = best_hand_info[2]
            except Exception:
                best_hand = None

        return PlayerPublicSchema(
            player_id=player.playerid,
            name=player.name,
            chips=player.chips,
            current_bet=player.current_bet,
            folded=player.folded,
            is_active=player.is_active,
            is_connected=is_connected,
            best_hand=best_hand
        )
    
    def get_table_state(self, table_id: str) -> dict:
        """Get complete table state for broadcasting."""
        if table_id not in self.tables:
            raise ValueError(f"Table {table_id} does not exist")
        
        table = self.tables[table_id]
        metadata = self.table_metadata[table_id]
        
        # Convert community cards
        community_cards = [self.engine_card_to_schema(c) for c in table.community_cards[:table.visible_cards]]

        # Convert players
        players = [self.engine_player_to_public_schema(p, table.community_cards[:table.visible_cards]) for p in table.players]
        
        # Determine current player
        current_player_id = None
        if metadata["is_game_active"] and metadata["current_player_turn"]:
            current_player_id = metadata["current_player_turn"]

        sb_player_id = None
        bb_player_id = None
        if table.players:
            sb_index = table.sb_pos % len(table.players)
            bb_index = (table.sb_pos + 1) % len(table.players)
            sb_player_id = table.players[sb_index].playerid
            bb_player_id = table.players[bb_index].playerid

        return {
            "table_id": table_id,
            "players": players,
            "pot": table.pot,
            "stage": table.stage,
            "community_cards": community_cards,
            "visible_cards": table.visible_cards,
            "current_player_id": current_player_id,
            "sb_amount": table.sb_amount,
            "bb_amount": table.bb_amount,
            "sb_player_id": sb_player_id,
            "bb_player_id": bb_player_id,
            "is_game_active": metadata["is_game_active"]
        }
    
    # ============== Game Flow ==============
    
    async def start_game(self, table_id: str):
        """Start a new game at a table."""
        if table_id not in self.tables:
            raise ValueError(f"Table {table_id} does not exist")
        
        table = self.tables[table_id]
        metadata = self.table_metadata[table_id]
        
        # Check if enough players
        if len(table.players) < 2:
            raise ValueError("Need at least 2 players to start a game")
        
        # Reset table for new round
        table.prepare_new_round()
        
        # Post blinds
        calculate_blinds(table)
        
        # Update metadata
        metadata["is_game_active"] = True
        metadata["game_phase"] = "preflop"
        
        # Determine first player to act
        table.get_action_order()
        active_players = [p for p in table.ordered_players if not p.folded and p.is_active]
        if active_players:
            first_player = active_players[0]
            metadata["current_player_turn"] = first_player.playerid
            metadata["players_acted"] = set()
            metadata["last_raiser"] = None
        sb_player = table.players[0] if len(table.players) > 0 else None
        bb_player = table.players[1] if len(table.players) > 1 else None
        
        game_started_msg = GameStartedMessage(
            sb_pos=table.sb_pos,
            bb_pos=(table.sb_pos + 1) % len(table.players),
            sb_player_id=sb_player.playerid if sb_player else "",
            bb_player_id=bb_player.playerid if bb_player else "",
            sb_amount=table.sb_amount,
            bb_amount=table.bb_amount,
            pot=table.pot,
            message="Game started! Blinds posted."
        )
        
        await manager.broadcast_to_table(game_started_msg.dict(), table_id)
        
        # Deal private cards to each player
        await self._deal_private_cards(table_id)
        
        # Request action from first player
        await self._request_player_action(table_id)
    
    async def _deal_private_cards(self, table_id: str):
        """Send private cards to each player."""
        table = self.tables[table_id]
        
        for player in table.players:
            if player.is_active:
                cards = [self.engine_card_to_schema(c) for c in player.current_hand]
                cards_msg = CardsDealtMessage(
                    your_cards=cards,
                    message="Your cards have been dealt"
                )
                await manager.send_personal_message(cards_msg.dict(), table_id, player.playerid)
    
    async def _broadcast_table_state(self, table_id: str):
        """Broadcast current table state to all players."""
        table_state = self.get_table_state(table_id)
        from api.schemas import TableStateMessage
        table_state_msg = TableStateMessage(**table_state)
        await manager.broadcast_to_table(table_state_msg.dict(), table_id)

    async def _request_player_action(self, table_id: str):
        """Request action from the current player."""
        table = self.tables[table_id]
        metadata = self.table_metadata[table_id]

        current_player_id = metadata.get("current_player_turn")
        if not current_player_id:
            return

        # Find current player
        current_player = next((player for player in table.players if player.playerid == current_player_id), None)
        if not current_player or current_player.folded or not current_player.is_active:
            await self._advance_to_next_player(table_id)
            return

        highest_bet = max([p.current_bet for p in table.players])
        to_call = highest_bet - current_player.current_bet

        available_actions = ["fold"]
        if to_call == 0:
            available_actions.append("check")
        else:
            available_actions.append("call")

        if current_player.chips > to_call:
            available_actions.append("raise")

        min_raise = highest_bet * 2 if highest_bet > 0 else table.bb_amount * 2

        action_msg = ActionRequiredMessage(
            player_id=current_player.playerid,
            player_name=current_player.name,
            available_actions=available_actions,
            to_call=to_call,
            min_raise=min_raise,
            pot=table.pot,
            current_bet=highest_bet
        )

        await manager.send_personal_message(action_msg.dict(), table_id, current_player.playerid)
        await self._broadcast_table_state(table_id)
    
    async def _advance_to_next_player(self, table_id: str):
        """Move to the next player in turn order."""
        table = self.tables[table_id]
        metadata = self.table_metadata[table_id]
        
        # Get current order
        table.get_action_order()
        active_players = [p for p in table.ordered_players if not p.folded and p.is_active]
        
        if not active_players:
            # No active players, end round
            await self._end_betting_round(table_id)
            return
        
        current_player_id = metadata.get("current_player_turn")
        
        # Find next player
        if current_player_id:
            # Find current index
            current_index = -1
            for i, player in enumerate(active_players):
                if player.playerid == current_player_id:
                    current_index = i
                    break
            
            if current_index >= 0:
                next_index = (current_index + 1) % len(active_players)
                next_player = active_players[next_index]
            else:
                next_player = active_players[0]
        else:
            next_player = active_players[0]

        # If only one active player remains, end round
        remaining_active = [p for p in table.players if p.is_active and not p.folded]
        if len(remaining_active) <= 1:
            await self._showdown(table_id)
            return

        # Track actions for this round
        if current_player_id:
            if metadata.get("last_raiser") == current_player_id:
                metadata["players_acted"] = {current_player_id}
            else:
                metadata.setdefault("players_acted", set()).add(current_player_id)

        # Round completion checks
        active_players = [p for p in table.players if p.is_active and not p.folded]
        if len(active_players) <= 1:
            await self._showdown(table_id)
            return

        highest_bet = max(p.current_bet for p in active_players)
        all_bets_equal = all(p.current_bet == highest_bet for p in active_players)
        all_acted = all(p.playerid in metadata.get("players_acted", set()) for p in active_players)

        metadata["current_player_turn"] = next_player.playerid

        if all_bets_equal and all_acted:
            await self._end_betting_round(table_id)
            return

        await self._request_player_action(table_id)
    
    async def _end_betting_round(self, table_id: str):
        """End the current betting round and advance to next stage."""
        table = self.tables[table_id]
        metadata = self.table_metadata[table_id]
        
        # Reset current bets for next round
        for player in table.players:
            player.current_bet = 0
        
        # Advance game stage
        if metadata["game_phase"] == "preflop":
            metadata["game_phase"] = "flop"
            table.reveal_next_stage()
            
            # Broadcast flop
            await self._broadcast_stage_change(table_id)
            await self._broadcast_table_state(table_id)
            
            # Start next betting round
            await self._start_next_betting_round(table_id)
            
        elif metadata["game_phase"] == "flop":
            metadata["game_phase"] = "turn"
            table.reveal_next_stage()
            
            # Broadcast turn
            await self._broadcast_stage_change(table_id)
            await self._broadcast_table_state(table_id)
            
            # Start next betting round
            await self._start_next_betting_round(table_id)
            
        elif metadata["game_phase"] == "turn":
            metadata["game_phase"] = "river"
            table.reveal_next_stage()
            
            # Broadcast river
            await self._broadcast_stage_change(table_id)
            await self._broadcast_table_state(table_id)
            
            # Start next betting round
            await self._start_next_betting_round(table_id)
            
        elif metadata["game_phase"] == "river":
            # Showdown
            await self._showdown(table_id)
    
    async def _start_next_betting_round(self, table_id: str):
        """Start the next betting round."""
        table = self.tables[table_id]
        metadata = self.table_metadata[table_id]
        
        # Determine first player to act
        table.get_action_order()
        active_players = [p for p in table.ordered_players if not p.folded and p.is_active]
        if active_players:
            metadata["current_player_turn"] = active_players[0].playerid
            metadata["players_acted"] = set()
            metadata["last_raiser"] = None

        await self._broadcast_table_state(table_id)
        # Request action from first player
        await self._request_player_action(table_id)
    
    async def _broadcast_stage_change(self, table_id: str):
        """Broadcast stage change (flop, turn, river)."""
        table = self.tables[table_id]
        
        community_cards = [self.engine_card_to_schema(c) for c in table.community_cards[:table.visible_cards]]
        
        stage_msg = StageChangedMessage(
            stage=table.stage,
            community_cards=community_cards,
            visible_count=table.visible_cards,
            pot=table.pot,
            message=f"{table.stage} revealed"
        )
        
        await manager.broadcast_to_table(stage_msg.dict(), table_id)
        await self._broadcast_table_state(table_id)
    
    async def _showdown(self, table_id: str):
        """Handle showdown and determine winner."""
        table = self.tables[table_id]
        metadata = self.table_metadata[table_id]
        
        # Show all hands
        show_all_hands(table.players, table.community_cards)
        
        # Determine winner
        winners, description = determine_winner(table.players, table.community_cards)
        
        # Prepare hand results
        hands = []
        for player in table.players:
            if not player.folded and player.is_active:
                best_cards, rank, name, _ = get_hand_description(player, table.community_cards)
                hand_cards = [self.engine_card_to_schema(c) for c in best_cards]
                player_cards = [self.engine_card_to_schema(c) for c in player.current_hand]
                
                is_winner = player in winners
                
                hands.append({
                    "player_id": player.playerid,
                    "player_name": player.name,
                    "cards": player_cards,
                    "hand_name": name,
                    "hand_cards": hand_cards,
                    "is_winner": is_winner
                })
        
        # Award pot to winner(s)
        if len(winners) == 1:
            winners[0].chips += table.pot
        elif len(winners) > 1:
            # Split pot
            split_amount = table.pot // len(winners)
            remainder = table.pot % len(winners)
            for i, winner in enumerate(winners):
                # Give remainder to first winner (arbitrary tiebreaker)
                award = split_amount + (remainder if i == 0 else 0)
                winner.chips += award
        
        # Prepare showdown message
        showdown_msg = ShowdownMessage(
            hands=hands,
            winners=[w.playerid for w in winners],
            winning_hand=description,
            pot=table.pot,
            message=description
        )
        
        await manager.broadcast_to_table(showdown_msg.dict(), table_id)
        
        # Prepare round ended message
        player_chips = {p.playerid: p.chips for p in table.players}
        round_ended_msg = RoundEndedMessage(
            winners=[w.playerid for w in winners],
            pot_amount=table.pot,
            player_chips=player_chips,
            message="Round ended"
        )
        
        await manager.broadcast_to_table(round_ended_msg.dict(), table_id)
        
        # Reset for next round after delay
        await asyncio.sleep(5)
        
        # Reset table metadata
        metadata["is_game_active"] = False
        metadata["current_player_turn"] = None
        metadata["game_phase"] = "waiting"
        
        # Reset player states
        for player in table.players:
            player.folded = False
            player.current_bet = 0
            player.current_hand = []
        
        # Broadcast table state
        table_state = self.get_table_state(table_id)
        from api.schemas import TableStateMessage
        table_state_msg = TableStateMessage(**table_state)
        await manager.broadcast_to_table(table_state_msg.dict(), table_id)
        
        logger.info(f"Showdown completed at table {table_id}")
    
    # ============== Player Action Handling ==============
    
    async def handle_player_action(self, table_id: str, player_id: str, action: str, amount: Optional[int] = None) -> bool:
        """
        Handle a player's action.
        Returns True if action was valid and processed, False otherwise.
        """
        if table_id not in self.tables:
            return False
        
        table = self.tables[table_id]
        metadata = self.table_metadata[table_id]
        
        # Check if it's this player's turn
        if metadata.get("current_player_turn") != player_id:
            return False
        
        # Find player
        player = None
        for p in table.players:
            if p.playerid == player_id:
                player = p
                break
        
        if not player or player.folded or not player.is_active:
            return False
        
        # Process action
        highest_bet = max([p.current_bet for p in table.players])
        to_call = highest_bet - player.current_bet
        
        try:
            if action == "fold":
                player.folded = True
                action_message = f"{player.name} folds"
                amount_used = 0
                
            elif action == "check":
                if to_call > 0:
                    return False  # Can't check when there's a bet to call
                action_message = f"{player.name} checks"
                amount_used = 0
                
            elif action == "call":
                if to_call == 0:
                    return False  # Can't call when no bet to call
                if to_call > player.chips:
                    return False  # Not enough chips
                
                player.chips -= to_call
                player.current_bet += to_call
                table.pot += to_call
                action_message = f"{player.name} calls {to_call}"
                amount_used = to_call
                
            elif action == "raise":
                if amount is None:
                    return False
                
                # Validate raise amount
                min_raise = highest_bet * 2 if highest_bet > 0 else table.bb_amount * 2
                if amount < min_raise:
                    return False
                
                total_needed = amount - player.current_bet
                if total_needed > player.chips:
                    return False  # Not enough chips
                
                player.chips -= total_needed
                player.current_bet = amount
                table.pot += total_needed
                action_message = f"{player.name} raises to {amount}"
                amount_used = total_needed
                metadata["last_raiser"] = player.playerid
                if metadata.get("betting_start_player") is None:
                    metadata["betting_start_player"] = player.playerid
                
            else:
                return False
            
            # Broadcast action to all players
            player_acted_msg = PlayerActedMessage(
                player_id=player.playerid,
                player_name=player.name,
                action=action,
                amount=amount_used if action in ["call", "raise"] else None,
                pot=table.pot,
                player_chips=player.chips,
                player_current_bet=player.current_bet,
                message=action_message
            )
            
            await manager.broadcast_to_table(player_acted_msg.dict(), table_id)
            await self._broadcast_table_state(table_id)
            
            # Move to next player
            await self._advance_to_next_player(table_id)
            
            return True
            
        except Exception as e:
            logger.error(f"Error processing action for {player_id}: {e}")
            return False
    
    # ============== Connection Management ==============
    
    def mark_player_connected(self, table_id: str, player_id: str):
        """Mark a player as connected."""
        if table_id in self.table_metadata:
            self.table_metadata[table_id]["connected_players"].add(player_id)
    
    def mark_player_disconnected(self, table_id: str, player_id: str):
        """Mark a player as disconnected."""
        if table_id in self.table_metadata:
            self.table_metadata[table_id]["connected_players"].discard(player_id)
    
    def get_connected_players(self, table_id: str) -> List[str]:
        """Get list of connected player IDs for a table."""
        if table_id in self.table_metadata:
            return list(self.table_metadata[table_id]["connected_players"])
        return []
    
    def is_game_active(self, table_id: str) -> bool:
        """Check if a game is active at a table."""
        if table_id in self.table_metadata:
            return self.table_metadata[table_id]["is_game_active"]
        return False
    
    def get_current_player_turn(self, table_id: str) -> Optional[str]:
        """Get the current player whose turn it is."""
        if table_id in self.table_metadata:
            return self.table_metadata[table_id]["current_player_turn"]
        return None


# Global game manager instance
game_manager = PokerGameManager()
