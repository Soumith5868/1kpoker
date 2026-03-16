"""
FastAPI Poker WebSocket Server

Main entry point for the poker WebSocket server.
Provides WebSocket endpoints for real-time poker gameplay.
"""

import uuid
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn

from api.events import event_handler
from api.game_manager import game_manager
from api.websocket_manager import manager

# Create FastAPI app
app = FastAPI(
    title="Poker WebSocket Server",
    description="Real-time multiplayer poker game server with WebSocket support",
    version="1.0.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict to your frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============== REST Endpoints ==============

@app.get("/")
async def root():
    """Root endpoint with server info."""
    return {
        "message": "Poker WebSocket Server",
        "version": "1.0.0",
        "endpoints": {
            "websocket": "/ws/{table_id}/{player_id}",
            "health": "/health",
            "tables": "/tables",
            "create_table": "/tables/{table_id} (POST)",
            "table_info": "/tables/{table_id}"
        }
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    stats = manager.get_stats()
    return {
        "status": "healthy",
        "connections": stats["total_connections"],
        "tables": stats["total_tables"],
        "table_details": stats["tables"]
    }


@app.get("/tables")
async def list_tables():
    """List all active tables."""
    tables = []
    for table_id, table in game_manager.tables.items():
        metadata = game_manager.table_metadata.get(table_id, {})
        tables.append({
            "table_id": table_id,
            "player_count": len(table.players),
            "max_players": metadata.get("max_players", 6),
            "is_game_active": metadata.get("is_game_active", False),
            "connected_players": len(game_manager.get_connected_players(table_id)),
            "created_at": metadata.get("created_at"),
            "sb_amount": table.sb_amount,
            "bb_amount": table.bb_amount
        })
    
    return {"tables": tables}


@app.post("/tables/{table_id}")
async def create_table(
    table_id: str,
    max_players: int = 6,
    sb_amount: int = 100,
    bb_amount: int = 200
):
    """Create a new poker table."""
    # Check if table already exists
    if game_manager.get_table(table_id):
        raise HTTPException(status_code=400, detail=f"Table {table_id} already exists")
    
    # Create table
    table = game_manager.create_table(
        table_id=table_id,
        max_players=max_players,
        sb_amount=sb_amount,
        bb_amount=bb_amount
    )
    
    return {
        "message": f"Table {table_id} created",
        "table_id": table_id,
        "max_players": max_players,
        "sb_amount": sb_amount,
        "bb_amount": bb_amount
    }


@app.get("/tables/{table_id}")
async def get_table_info(table_id: str):
    """Get information about a specific table."""
    table = game_manager.get_table(table_id)
    if not table:
        raise HTTPException(status_code=404, detail=f"Table {table_id} not found")
    
    metadata = game_manager.table_metadata.get(table_id, {})
    
    # Convert players to public info
    players = []
    for player in table.players:
        players.append({
            "player_id": player.playerid,
            "name": player.name,
            "chips": player.chips,
            "current_bet": player.current_bet,
            "folded": player.folded,
            "is_active": player.is_active,
            "is_connected": player.playerid in game_manager.get_connected_players(table_id)
        })
    
    return {
        "table_id": table_id,
        "players": players,
        "player_count": len(table.players),
        "max_players": metadata.get("max_players", 6),
        "pot": table.pot,
        "stage": table.stage,
        "community_cards": [
            {"suit": card.suit, "rank": card.rank}
            for card in table.community_cards[:table.visible_cards]
        ],
        "visible_cards": table.visible_cards,
        "is_game_active": metadata.get("is_game_active", False),
        "current_player_turn": metadata.get("current_player_turn"),
        "game_phase": metadata.get("game_phase", "waiting"),
        "sb_amount": table.sb_amount,
        "bb_amount": table.bb_amount,
        "connected_players": len(game_manager.get_connected_players(table_id))
    }


@app.delete("/tables/{table_id}")
async def delete_table(table_id: str):
    """Delete a table."""
    table = game_manager.get_table(table_id)
    if not table:
        raise HTTPException(status_code=404, detail=f"Table {table_id} not found")
    
    game_manager.delete_table(table_id)
    return {"message": f"Table {table_id} deleted"}


# ============== WebSocket Endpoints ==============

@app.websocket("/ws/{table_id}/{player_id}")
async def websocket_endpoint(websocket: WebSocket, table_id: str, player_id: str):
    """
    WebSocket endpoint for real-time poker gameplay.
    
    Parameters:
    - table_id: The ID of the poker table to join
    - player_id: The ID of the player connecting
    
    The player_id can be:
    - An existing player ID (for reconnection)
    - "new" to create a new player (will be prompted for name via join_table message)
    - A specific ID if the frontend has stored it
    
    All game communication happens through this WebSocket connection.
    """
    try:
        # Handle the WebSocket connection
        await event_handler.handle_connection(websocket, table_id, player_id)
        
    except WebSocketDisconnect:
        # Connection closed normally
        pass
    except Exception as e:
        # Log unexpected errors
        print(f"WebSocket error for {player_id} at table {table_id}: {e}")
        try:
            await websocket.close(code=1011, reason=str(e))
        except:
            pass


@app.websocket("/ws/join/{table_id}")
async def websocket_join_table(websocket: WebSocket, table_id: str):
    """
    Alternative WebSocket endpoint that generates a player ID automatically.
    Useful for new players who don't have a stored player ID.
    """
    # Generate a new player ID
    player_id = str(uuid.uuid4())
    
    try:
        # Handle the WebSocket connection
        await event_handler.handle_connection(websocket, table_id, player_id)
        
    except WebSocketDisconnect:
        # Connection closed normally
        pass
    except Exception as e:
        # Log unexpected errors
        print(f"WebSocket error for {player_id} at table {table_id}: {e}")
        try:
            await websocket.close(code=1011, reason=str(e))
        except:
            pass


# ============== Error Handlers ==============

@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """Handle HTTP exceptions."""
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail}
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    """Handle general exceptions."""
    return JSONResponse(
        status_code=500,
        content={"detail": f"Internal server error: {str(exc)}"}
    )


# ============== Startup/Shutdown Events ==============

@app.on_event("startup")
async def startup_event():
    """Initialize on startup."""
    print("Poker WebSocket Server starting up...")
    # Create a default table for testing
    try:
        game_manager.create_table("default", max_players=6, sb_amount=100, bb_amount=200)
        print("Created default table: 'default'")
    except Exception as e:
        print(f"Error creating default table: {e}")


@app.on_event("shutdown")
async def shutdown_event():
    """Clean up on shutdown."""
    print("Poker WebSocket Server shutting down...")
    # Clean up all tables
    for table_id in list(game_manager.tables.keys()):
        game_manager.delete_table(table_id)
    print("Cleaned up all tables")


# ============== Main Entry Point ==============

if __name__ == "__main__":
    # Run the server
    uvicorn.run(
        "api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,  # Auto-reload on code changes
        log_level="info"
    )
