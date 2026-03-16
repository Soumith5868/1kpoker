"""
WebSocket Event Handlers

Handles incoming WebSocket messages and dispatches them to appropriate handlers.
"""

import json
import logging
from typing import Dict, Any, Optional

from fastapi import WebSocket, WebSocketDisconnect

from api.schemas import (
    parse_client_message, JoinTableMessage, LeaveTableMessage, StartGameMessage,
    PlayerActionMessage, ChatMessage, ErrorMessage, PlayerJoinedMessage,
    PlayerLeftMessage, TableStateMessage, ConnectedMessage, ChatBroadcastMessage
)
from api.websocket_manager import manager
from api.game_manager import game_manager

logger = logging.getLogger(__name__)


class WebSocketEventHandler:
    """
    Handles WebSocket events and messages.
    """
    
    def __init__(self):
        self.handlers = {
            "join_table": self.handle_join_table,
            "leave_table": self.handle_leave_table,
            "start_game": self.handle_start_game,
            "player_action": self.handle_player_action,
            "chat": self.handle_chat,
        }
    
    async def handle_connection(self, websocket: WebSocket, table_id: str, player_id: str):
        """
        Handle a new WebSocket connection.
        """
        try:
            # Accept connection
            await manager.connect(websocket, table_id, player_id)
            
            # Mark player as connected in game manager
            game_manager.mark_player_connected(table_id, player_id)
            
            # Send connection confirmation
            connected_msg = ConnectedMessage(
                player_id=player_id,
                table_id=table_id,
                message=f"Connected to table {table_id}"
            )
            await websocket.send_json(connected_msg.dict())
            
            # Send current table state
            await self._send_table_state(table_id, player_id)
            
            # Broadcast player joined (if player exists in game)
            player = game_manager.get_player(player_id)
            if player:
                await self._broadcast_player_joined(table_id, player)
            
            # Handle incoming messages
            await self._handle_messages(websocket, table_id, player_id)
            
        except WebSocketDisconnect:
            logger.info(f"Player {player_id} disconnected from table {table_id}")
        except Exception as e:
            logger.error(f"Error handling connection for {player_id}: {e}")
        finally:
            # Clean up on disconnect
            await self._handle_disconnect(table_id, player_id)
    
    async def _handle_messages(self, websocket: WebSocket, table_id: str, player_id: str):
        """
        Handle incoming WebSocket messages.
        """
        try:
            while True:
                # Receive message
                data = await websocket.receive_json()
                logger.debug(f"Received message from {player_id}: {data}")
                
                # Parse and handle message
                await self._handle_message(data, table_id, player_id)
                
        except WebSocketDisconnect:
            raise
        except json.JSONDecodeError:
            error_msg = ErrorMessage(message="Invalid JSON message")
            await websocket.send_json(error_msg.dict())
        except Exception as e:
            logger.error(f"Error handling message from {player_id}: {e}")
            error_msg = ErrorMessage(message=f"Error processing message: {str(e)}")
            await websocket.send_json(error_msg.dict())
    
    async def _handle_message(self, data: Dict[str, Any], table_id: str, player_id: str):
        """
        Parse and dispatch a message to the appropriate handler.
        """
        try:
            # Parse message
            message = parse_client_message(data)
            
            # Get handler
            handler = self.handlers.get(message.type)
            if not handler:
                error_msg = ErrorMessage(message=f"Unknown message type: {message.type}")
                await manager.send_personal_message(error_msg.dict(), table_id, player_id)
                return
            
            # Call handler
            await handler(message, table_id, player_id)
            
        except ValueError as e:
            error_msg = ErrorMessage(message=f"Invalid message format: {str(e)}")
            await manager.send_personal_message(error_msg.dict(), table_id, player_id)
        except Exception as e:
            logger.error(f"Error in message handler for {player_id}: {e}")
            error_msg = ErrorMessage(message=f"Internal server error: {str(e)}")
            await manager.send_personal_message(error_msg.dict(), table_id, player_id)
    
    async def _handle_disconnect(self, table_id: str, player_id: str):
        """
        Handle player disconnection.
        """
        # Mark player as disconnected in game manager
        game_manager.mark_player_disconnected(table_id, player_id)
        
        # Remove connection from manager
        manager.disconnect(table_id, player_id)
        
        # Broadcast player left (if player exists in game)
        player = game_manager.get_player(player_id)
        if player:
            await self._broadcast_player_left(table_id, player)
        
        # Remove player from table if they're not in an active game
        if not game_manager.is_game_active(table_id):
            game_manager.remove_player_from_table(table_id, player_id)
    
    # ============== Message Handlers ==============
    
    async def handle_join_table(self, message: JoinTableMessage, table_id: str, player_id: str):
        """
        Handle player joining a table.
        """
        try:
            # Check if table exists, create if not
            table = game_manager.get_table(table_id)
            if not table:
                table = game_manager.create_table(table_id)
            
            # Check if player already exists at this table
            existing_player = game_manager.get_player(player_id)
            if existing_player:
                # Player already exists, just update connection status
                logger.info(f"Player {player_id} reconnected to table {table_id}")
                return
            
            # Add player to table using websocket path player_id so actions are authorized correctly.
            chips_amount = message.chips if message.chips is not None else 1000
            new_player_id, player = game_manager.add_player_to_table(
                table_id,
                message.player_name,
                chips=chips_amount,
                player_id=player_id
            )

            # Broadcast player joined
            await self._broadcast_player_joined(table_id, player)

            # Send success message (use the actual player id)
            success_msg = ConnectedMessage(
                player_id=player.playerid,
                table_id=table_id,
                message=f"Joined table {table_id} as {message.player_name}"
            )
            await manager.send_personal_message(success_msg.dict(), table_id, player_id)
            
        except Exception as e:
            logger.error(f"Error joining table: {e}")
            error_msg = ErrorMessage(message=f"Failed to join table: {str(e)}")
            await manager.send_personal_message(error_msg.dict(), table_id, player_id)
    
    async def handle_leave_table(self, message: LeaveTableMessage, table_id: str, player_id: str):
        """
        Handle player leaving a table.
        """
        try:
            # Get player
            player = game_manager.get_player(player_id)
            if not player:
                return
            
            # Broadcast player left
            await self._broadcast_player_left(table_id, player)
            
            # Remove player from table
            game_manager.remove_player_from_table(table_id, player_id)
            
            # Send confirmation
            success_msg = ConnectedMessage(
                player_id=player_id,
                table_id=table_id,
                message="Left table successfully"
            )
            await manager.send_personal_message(success_msg.dict(), table_id, player_id)
            
        except Exception as e:
            logger.error(f"Error leaving table: {e}")
            error_msg = ErrorMessage(message=f"Failed to leave table: {str(e)}")
            await manager.send_personal_message(error_msg.dict(), table_id, player_id)
    
    async def handle_start_game(self, message: StartGameMessage, table_id: str, player_id: str):
        """
        Handle starting a game.
        """
        try:
            # Check if player is at the table
            player = game_manager.get_player(player_id)
            if not player:
                error_msg = ErrorMessage(message="You are not at this table")
                await manager.send_personal_message(error_msg.dict(), table_id, player_id)
                return
            
            # Check if game is already active
            if game_manager.is_game_active(table_id):
                error_msg = ErrorMessage(message="Game is already in progress")
                await manager.send_personal_message(error_msg.dict(), table_id, player_id)
                return
            
            # Start game
            await game_manager.start_game(table_id)
            
        except ValueError as e:
            error_msg = ErrorMessage(message=str(e))
            await manager.send_personal_message(error_msg.dict(), table_id, player_id)
        except Exception as e:
            logger.error(f"Error starting game: {e}")
            error_msg = ErrorMessage(message=f"Failed to start game: {str(e)}")
            await manager.send_personal_message(error_msg.dict(), table_id, player_id)
    
    async def handle_player_action(self, message: PlayerActionMessage, table_id: str, player_id: str):
        """
        Handle player action (fold, check, call, raise).
        """
        try:
            # Validate game is active
            if not game_manager.is_game_active(table_id):
                error_msg = ErrorMessage(message="No game in progress")
                await manager.send_personal_message(error_msg.dict(), table_id, player_id)
                return
            
            # Process action
            success = await game_manager.handle_player_action(
                table_id, player_id, message.action.value, message.amount
            )
            
            if not success:
                error_msg = ErrorMessage(message="Invalid action or not your turn")
                await manager.send_personal_message(error_msg.dict(), table_id, player_id)
            
        except Exception as e:
            logger.error(f"Error handling player action: {e}")
            error_msg = ErrorMessage(message=f"Failed to process action: {str(e)}")
            await manager.send_personal_message(error_msg.dict(), table_id, player_id)
    
    async def handle_chat(self, message: ChatMessage, table_id: str, player_id: str):
        """
        Handle chat message.
        """
        try:
            # Get player
            player = game_manager.get_player(player_id)
            if not player:
                return
            
            # Broadcast chat message
            chat_msg = ChatBroadcastMessage(
                player_id=player_id,
                player_name=player.name,
                message=message.message
            )
            
            await manager.broadcast_to_table(chat_msg.dict(), table_id)
            
        except Exception as e:
            logger.error(f"Error handling chat: {e}")
            error_msg = ErrorMessage(message=f"Failed to send chat: {str(e)}")
            await manager.send_personal_message(error_msg.dict(), table_id, player_id)
    
    # ============== Helper Methods ==============
    
    async def _send_table_state(self, table_id: str, player_id: str):
        """
        Send current table state to a player.
        """
        try:
            table_state = game_manager.get_table_state(table_id)
            table_state_msg = TableStateMessage(**table_state)
            await manager.send_personal_message(table_state_msg.dict(), table_id, player_id)
        except Exception as e:
            logger.error(f"Error sending table state to {player_id}: {e}")
    
    async def _broadcast_player_joined(self, table_id: str, player):
        """
        Broadcast player joined event.
        """
        try:
            # Get table state
            table_state = game_manager.get_table_state(table_id)
            
            # Create player joined message
            player_joined_msg = PlayerJoinedMessage(
                player=table_state["players"][-1],  # Last player is the new one
                players=table_state["players"],
                message=f"{player.name} joined the table"
            )
            
            # Broadcast to all except the new player
            await manager.broadcast_to_table(
                player_joined_msg.dict(), table_id, exclude=[player.playerid]
            )
            
        except Exception as e:
            logger.error(f"Error broadcasting player joined: {e}")
    
    async def _broadcast_player_left(self, table_id: str, player):
        """
        Broadcast player left event.
        """
        try:
            # Get updated table state (without the leaving player)
            table_state = game_manager.get_table_state(table_id)
            
            # Create player left message
            player_left_msg = PlayerLeftMessage(
                player_id=player.playerid,
                player_name=player.name,
                players=table_state["players"],
                message=f"{player.name} left the table"
            )
            
            # Broadcast to all
            await manager.broadcast_to_table(player_left_msg.dict(), table_id)
            
        except Exception as e:
            logger.error(f"Error broadcasting player left: {e}")


# Global event handler instance
event_handler = WebSocketEventHandler()
