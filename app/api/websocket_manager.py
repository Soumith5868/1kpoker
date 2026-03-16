"""
WebSocket Connection Manager

Handles WebSocket connections, disconnections, and message broadcasting.
Manages connections per table (room-based).
"""

from fastapi import WebSocket
from typing import Dict, List, Optional
import json
import logging

logger = logging.getLogger(__name__)


class ConnectionManager:
    """
    Manages WebSocket connections organized by table/room.
    
    Structure:
    {
        "table_id": {
            "player_id": WebSocket
        }
    }
    """
    
    def __init__(self):
        # table_id -> {player_id -> WebSocket}
        self.active_connections: Dict[str, Dict[str, WebSocket]] = {}
        # player_id -> table_id (reverse lookup)
        self.player_tables: Dict[str, str] = {}
    
    async def connect(self, websocket: WebSocket, table_id: str, player_id: str) -> bool:
        """
        Accept a WebSocket connection and add it to a table.
        Returns True if connection successful, False otherwise.
        """
        await websocket.accept()
        
        # Initialize table if not exists
        if table_id not in self.active_connections:
            self.active_connections[table_id] = {}
        
        # Store connection
        self.active_connections[table_id][player_id] = websocket
        self.player_tables[player_id] = table_id
        
        logger.info(f"Player {player_id} connected to table {table_id}")
        return True
    
    def disconnect(self, table_id: str, player_id: str):
        """Remove a player's connection from a table."""
        if table_id in self.active_connections:
            if player_id in self.active_connections[table_id]:
                del self.active_connections[table_id][player_id]
                logger.info(f"Player {player_id} disconnected from table {table_id}")
            
            # Clean up empty tables
            if not self.active_connections[table_id]:
                del self.active_connections[table_id]
                logger.info(f"Table {table_id} removed (empty)")
        
        if player_id in self.player_tables:
            del self.player_tables[player_id]
    
    def get_table_for_player(self, player_id: str) -> Optional[str]:
        """Get the table ID for a player."""
        return self.player_tables.get(player_id)
    
    def get_connection(self, table_id: str, player_id: str) -> Optional[WebSocket]:
        """Get a specific player's WebSocket connection."""
        if table_id in self.active_connections:
            return self.active_connections[table_id].get(player_id)
        return None
    
    def get_table_connections(self, table_id: str) -> Dict[str, WebSocket]:
        """Get all connections for a table."""
        return self.active_connections.get(table_id, {})
    
    def get_connected_player_ids(self, table_id: str) -> List[str]:
        """Get list of connected player IDs for a table."""
        if table_id in self.active_connections:
            return list(self.active_connections[table_id].keys())
        return []
    
    def is_player_connected(self, table_id: str, player_id: str) -> bool:
        """Check if a player is connected to a table."""
        if table_id in self.active_connections:
            return player_id in self.active_connections[table_id]
        return False
    
    async def send_personal_message(self, message: dict, table_id: str, player_id: str):
        """Send a message to a specific player."""
        websocket = self.get_connection(table_id, player_id)
        if websocket:
            try:
                await websocket.send_json(message)
            except Exception as e:
                logger.error(f"Error sending message to {player_id}: {e}")
                self.disconnect(table_id, player_id)
    
    async def broadcast_to_table(self, message: dict, table_id: str, exclude: Optional[List[str]] = None):
        """
        Broadcast a message to all players at a table.
        
        Args:
            message: The message dict to send
            table_id: The table to broadcast to
            exclude: Optional list of player_ids to exclude from broadcast
        """
        exclude = exclude or []
        connections = self.get_table_connections(table_id)
        
        disconnected = []
        for player_id, websocket in connections.items():
            if player_id in exclude:
                continue
            try:
                await websocket.send_json(message)
            except Exception as e:
                logger.error(f"Error broadcasting to {player_id}: {e}")
                disconnected.append(player_id)
        
        # Clean up disconnected players
        for player_id in disconnected:
            self.disconnect(table_id, player_id)
    
    async def broadcast_to_all_tables(self, message: dict):
        """Broadcast a message to all connected players across all tables."""
        for table_id in list(self.active_connections.keys()):
            await self.broadcast_to_table(message, table_id)
    
    def get_table_count(self) -> int:
        """Get the number of active tables."""
        return len(self.active_connections)
    
    def get_total_connections(self) -> int:
        """Get total number of connected players across all tables."""
        return sum(len(conns) for conns in self.active_connections.values())
    
    def get_stats(self) -> dict:
        """Get connection statistics."""
        return {
            "total_tables": self.get_table_count(),
            "total_connections": self.get_total_connections(),
            "tables": {
                table_id: len(conns) 
                for table_id, conns in self.active_connections.items()
            }
        }


# Global connection manager instance
manager = ConnectionManager()
