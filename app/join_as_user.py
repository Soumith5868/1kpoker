#!/usr/bin/env python3
"""
Complete Poker Terminal Client

A full-featured poker client for playing from terminal.
Run this in multiple terminals with different usernames to play multiplayer poker.

Features:
- Shows all players, their chips, bets, and status
- Shows community cards
- Shows your private cards
- Interactive gameplay (fold, check, call, raise)
- Shows showdown with all players' hands
- Real-time updates when players join/leave

Usage: python join_as_user.py [username] [chips] [table_id]
Example: python join_as_user.py soumith 10000
Example: python join_as_user.py charan 10000 default
Example: python join_as_user.py alice 5000 mytable
"""

import asyncio
import json
import sys
import uuid
import websockets
import argparse
import threading
from queue import Queue
import time


class PokerTerminalClient:
    """Complete poker terminal client with interactive gameplay."""
    
    def __init__(self, server_url: str, table_id: str, player_name: str, chips: int = 1000, player_id: str = None):
        self.server_url = server_url
        self.table_id = table_id
        self.player_name = player_name
        self.chips = chips
        self.player_id = player_id or str(uuid.uuid4())
        self.websocket = None
        self.connected = False
        self.running = False
        self.input_queue = Queue()
        self.current_table_state = None
        self.my_cards = []
        self.game_active = False
        self.my_turn = False
        self.available_actions = []
        self.to_call = 0
        self.min_raise = 0
        
    async def connect(self):
        """Connect to the poker server."""
        # Connect to WebSocket using stable player_id so the server can map actions correctly.
        ws_url = f"{self.server_url}/ws/{self.table_id}/{self.player_id}"
        
        try:
            self.websocket = await websockets.connect(ws_url)
            self.connected = True
            self.running = True
            
            # Send join message
            join_msg = {
                "type": "join_table",
                "player_name": self.player_name,
                "chips": self.chips
            }
            await self.websocket.send(json.dumps(join_msg))
            
            # Start message handler
            asyncio.create_task(self.receive_messages())
            
            return True
            
        except Exception as e:
            print(f"✗ Connection failed: {e}")
            return False
    
    async def receive_messages(self):
        """Receive and process messages from server."""
        if self.websocket is None:
            return
        try:
            async for message in self.websocket:
                if isinstance(message, bytes):
                    message = message.decode('utf-8')
                await self.handle_message(message)
        except websockets.exceptions.ConnectionClosed:
            print("\n✗ Connection closed by server")
            self.running = False
        except Exception as e:
            print(f"\n✗ Error receiving messages: {e}")
            self.running = False
    
    async def handle_message(self, message: str):
        """Handle incoming message."""
        try:
            # Ensure message is a string
            if isinstance(message, bytes):
                message = message.decode('utf-8')
            elif not isinstance(message, str):
                message = str(message)
            data = json.loads(message)
            msg_type = data.get("type")
            
            if msg_type == "connected":
                # Server may return canonical player ID
                server_player_id = data.get('player_id')
                if server_player_id and server_player_id != self.player_id:
                    self.player_id = server_player_id
                print(f"\n✓ {data.get('message')} (player_id={self.player_id})")
                
            elif msg_type == "player_joined":
                await self.handle_player_joined(data)
                
            elif msg_type == "player_left":
                await self.handle_player_left(data)
                
            elif msg_type == "table_state":
                await self.handle_table_state(data)
                
            elif msg_type == "game_started":
                await self.handle_game_started(data)
                
            elif msg_type == "cards_dealt":
                await self.handle_cards_dealt(data)
                
            elif msg_type == "action_required":
                await self.handle_action_required(data)
                
            elif msg_type == "player_acted":
                await self.handle_player_acted(data)
                
            elif msg_type == "stage_changed":
                await self.handle_stage_changed(data)
                
            elif msg_type == "showdown":
                await self.handle_showdown(data)
                
            elif msg_type == "round_ended":
                await self.handle_round_ended(data)
                
            elif msg_type == "chat_message":
                await self.handle_chat_message(data)
                
            elif msg_type == "error":
                print(f"\n✗ Error: {data.get('message')}")
                
        except json.JSONDecodeError:
            print(f"\n⚠️  Received invalid JSON")
        except Exception as e:
            print(f"\n⚠️  Error handling message: {e}")
    
    async def handle_player_joined(self, data: dict):
        """Handle player joined event."""
        player = data.get("player", {})
        print(f"\n{'='*60}")
        print(f"🎮 {data.get('message')}")
        print(f"{'='*60}")
        
        # Show all players
        players = data.get("players", [])
        print(f"\nPlayers at table ({len(players)}):")
        for i, p in enumerate(players):
            status = "👑" if p.get("player_id") == self.player_id else "  "
            status += "💤" if not p.get("is_connected") else "  "
            status += "❌" if p.get("folded") else "  "
            
            print(f"  {i+1}. {status} {p.get('name')}")
            print(f"     Chips: {p.get('chips')}, Bet: {p.get('current_bet')}")
    
    async def handle_player_left(self, data: dict):
        """Handle player left event."""
        print(f"\n{'='*60}")
        print(f"👋 {data.get('message')}")
        print(f"{'='*60}")
        
        players = data.get("players", [])
        print(f"\nPlayers left: {len(players)}")
    
    async def handle_table_state(self, data: dict):
        """Handle table state update."""
        self.current_table_state = data
        
        print(f"\n{'='*60}")
        print(f"📊 TABLE: {data.get('table_id')}")
        print(f"{'='*60}")
        
        # Display players
        players = data.get("players", [])
        print(f"\nPlayers ({len(players)}):")
        for i, player in enumerate(players):
            status = "👑" if player.get("player_id") == data.get("current_player_id") else "  "
            status += "💤" if not player.get("is_connected") else "  "
            status += "❌" if player.get("folded") else "  "
            
            print(f"  {i+1}. {status} {player.get('name')}")
            print(f"     Chips: {player.get('chips')}, Bet: {player.get('current_bet')}, Best: {player.get('best_hand', 'N/A')}")
        
        # Display community cards
        cards = data.get("community_cards", [])
        if cards:
            card_str = " ".join([f"{c['rank']}{c['suit']}" for c in cards])
            print(f"\nCommunity cards: {card_str}")
        else:
            print(f"\nCommunity cards: None yet")
        
        # Display blinds and pot
        print(f"\nSmall blind: {data.get('sb_player_id')} ({data.get('sb_amount')})")
        print(f"Big blind: {data.get('bb_player_id')} ({data.get('bb_amount')})")
        print(f"\nPot: {data.get('pot')}")
        print(f"Stage: {data.get('stage')}")
        print(f"Game active: {data.get('is_game_active')}")
        
        # Show my cards if I have them
        if self.my_cards:
            my_card_str = " ".join([f"{c['rank']}{c['suit']}" for c in self.my_cards])
            print(f"\n🃏 Your cards: {my_card_str}")
        
        print(f"{'='*60}")
    
    async def handle_game_started(self, data: dict):
        """Handle game started event."""
        self.game_active = True
        
        print(f"\n{'='*60}")
        print(f"🎲 GAME STARTED!")
        print(f"{'='*60}")
        print(f"\n{data.get('message')}")
        print(f"SB: {data.get('sb_player_id')} ({data.get('sb_amount')})")
        print(f"BB: {data.get('bb_player_id')} ({data.get('bb_amount')})")
        print(f"Pot: {data.get('pot')}")
        print(f"{'='*60}")
    
    async def handle_cards_dealt(self, data: dict):
        """Handle cards dealt event."""
        self.my_cards = data.get("your_cards", [])
        card_str = " ".join([f"{c['rank']}{c['suit']}" for c in self.my_cards])
        
        print(f"\n{'='*60}")
        print(f"🃏 YOUR CARDS: {card_str}")
        print(f"{'='*60}")
    
    async def handle_action_required(self, data: dict):
        """Handle action required event."""
        self.my_turn = True
        self.available_actions = data.get("available_actions", [])
        self.to_call = data.get("to_call", 0)
        self.min_raise = data.get("min_raise", 0)
        
        print(f"\n{'='*60}")
        print(f"🎯 YOUR TURN, {data.get('player_name')}!")
        print(f"{'='*60}")
        
        print(f"\nPot: {data.get('pot')}")
        print(f"To call: {self.to_call}")
        print(f"Min raise: {self.min_raise}")
        print(f"Available actions: {', '.join(self.available_actions)}")
        
        print(f"\nEnter action:")
        print("  fold, check, call, raise <amount>, chat <message>")
        print(f"{'='*60}")
        
        # Get user input
        await self.get_user_action()
    
    async def handle_player_acted(self, data: dict):
        """Handle player acted event."""
        print(f"\n{'='*60}")
        print(f"⚡ {data.get('message')}")
        if data.get("amount"):
            print(f"Amount: {data.get('amount')}")
        print(f"Pot: {data.get('pot')}")
        print(f"{'='*60}")
    
    async def handle_stage_changed(self, data: dict):
        """Handle stage changed event."""
        cards = data.get("community_cards", [])
        card_str = " ".join([f"{c['rank']}{c['suit']}" for c in cards])
        stage = data.get('stage', '')
        
        print(f"\n{'='*60}")
        print(f"📊 {stage.upper()} REVEALED: {card_str}")
        print(f"{'='*60}")
    
    async def handle_showdown(self, data: dict):
        """Handle showdown event."""
        print(f"\n{'='*60}")
        print(f"🎉 SHOWDOWN!")
        print(f"{'='*60}")
        
        hands = data.get("hands", [])
        winners = data.get("winners", [])
        
        print(f"\nWinning hand: {data.get('winning_hand')}")
        print(f"Pot: {data.get('pot')}")
        
        print(f"\nAll hands:")
        for hand in hands:
            player_name = hand.get("player_name")
            cards = " ".join([f"{c['rank']}{c['suit']}" for c in hand.get("cards", [])])
            hand_name = hand.get("hand_name")
            hand_cards = " ".join([f"{c['rank']}{c['suit']}" for c in hand.get("hand_cards", [])])
            is_winner = hand.get("is_winner", False)
            
            winner_mark = "🏆 " if is_winner else "   "
            print(f"\n{winner_mark}{player_name}: {cards}")
            print(f"     Best hand: {hand_name}")
            print(f"     Winning cards: {hand_cards}")
        
        print(f"{'='*60}")
    
    async def handle_round_ended(self, data: dict):
        """Handle round ended event."""
        self.game_active = False
        self.my_cards = []
        
        print(f"\n{'='*60}")
        print(f"🏁 ROUND ENDED")
        print(f"{'='*60}")
        
        winners = data.get("winners", [])
        if winners:
            print(f"\nWinners: {', '.join(winners)}")
        
        player_chips = data.get("player_chips", {})
        print(f"\nChip counts:")
        for player_id, chips in player_chips.items():
            print(f"  {player_id[:8]}: {chips}")
        
        print(f"\nPot awarded: {data.get('pot_amount')}")
        print(f"{'='*60}")
    
    async def handle_chat_message(self, data: dict):
        """Handle chat message."""
        print(f"\n💬 {data.get('player_name')}: {data.get('message')}")
    
    async def get_user_action(self):
        """Get user input for action."""
        # Get input in a separate thread
        user_input = await asyncio.get_event_loop().run_in_executor(
            None, input, "\n> "
        )
        
        if not user_input.strip():
            return
        
        command = user_input.strip().lower()
        
        if command.startswith("chat "):
            message = user_input[5:].strip()
            if message:
                await self.send_chat(message)
            else:
                print("Please provide a chat message")
                
        elif command in ["fold", "check", "call"]:
            await self.send_action(command)
            
        elif command.startswith("raise "):
            try:
                amount = int(command[6:].strip())
                await self.send_action("raise", amount)
            except ValueError:
                print("Please provide a valid raise amount")
                
        else:
            print(f"Unknown command: {command}")
            print("Available: fold, check, call, raise <amount>, chat <message>")
    
    async def send_action(self, action: str, amount: int = 0):
        """Send player action to server."""
        if not self.websocket:
            return
        
        action_msg = {
            "type": "player_action",
            "action": action
        }
        if amount > 0:
            action_msg["amount"] = str(amount)  # Convert to string for JSON
        
        await self.websocket.send(json.dumps(action_msg))
        self.my_turn = False
    
    async def send_chat(self, message: str):
        """Send chat message to server."""
        if not self.websocket:
            return
        
        chat_msg = {
            "type": "chat",
            "message": message
        }
        
        await self.websocket.send(json.dumps(chat_msg))
    
    async def send_start_game(self):
        """Send start game message."""
        if not self.websocket:
            return
        
        start_msg = {
            "type": "start_game"
        }
        
        await self.websocket.send(json.dumps(start_msg))
    
    async def disconnect(self):
        """Disconnect from server."""
        if self.websocket:
            await self.websocket.close()
        self.running = False
        self.connected = False


async def main_async(server_url: str, table_id: str, player_name: str, chips: int = 1000, player_id: str = None):
    """Main async function."""
    client = PokerTerminalClient(server_url, table_id, player_name, chips, player_id=player_id)
    
    print(f"\n{'='*60}")
    print(f"POKER TERMINAL CLIENT")
    print(f"{'='*60}")
    print(f"Table: {table_id}")
    print(f"Player: {player_name}")
    print(f"Server: {server_url}")
    print(f"{'='*60}")
    
    # Connect to server
    if not await client.connect():
        print("Failed to connect. Exiting.")
        return
    
    print("\nConnected successfully!")
    print("\nCommands:")
    print("  start - Start the game (when enough players)")
    print("  fold, check, call, raise <amount> - Game actions")
    print("  chat <message> - Send chat message")
    print("  quit - Exit")
    print(f"{'='*60}")
    
    # Main input loop
    while client.running:
        try:
            # Get user input
            user_input = await asyncio.get_event_loop().run_in_executor(
                None, input, "\n> "
            )
            
            if not user_input.strip():
                continue
            
            command = user_input.strip().lower()
            
            if command == "quit" or command == "exit":
                print("Disconnecting...")
                await client.disconnect()
                break
                
            elif command == "start":
                await client.send_start_game()
                print("Game start requested...")
                
            elif command.startswith("chat "):
                message = user_input[5:].strip()
                if message:
                    await client.send_chat(message)
                else:
                    print("Please provide a chat message")
                    
            elif command in ["fold", "check", "call"]:
                if client.my_turn:
                    await client.send_action(command)
                else:
                    print("Not your turn!")
                    
            elif command.startswith("raise "):
                if client.my_turn:
                    try:
                        amount = int(command[6:].strip())
                        await client.send_action("raise", amount)
                    except ValueError:
                        print("Please provide a valid raise amount")
                else:
                    print("Not your turn!")
                    
            else:
                print(f"Unknown command: {command}")
                print("Type 'quit' to exit")
                
        except KeyboardInterrupt:
            print("\nDisconnecting...")
            await client.disconnect()
            break
        except Exception as e:
            print(f"\nError: {e}")
    
    print("Goodbye!")


def main():
    """Parse arguments and run the client."""

    parser = argparse.ArgumentParser(description="Poker Terminal Client")
    parser.add_argument("player_name", help="Player name")
    parser.add_argument("chips", nargs="?", type=int, default=1000, help="Starting chips (default 1000)")
    parser.add_argument("table_id", nargs="?", default="default", help="Table ID (default 'default')")
    parser.add_argument("server_url", nargs="?", default="ws://localhost:8000", help="WebSocket server URL (default ws://localhost:8000)")
    parser.add_argument("--player-id", dest="player_id", default=None, help="Optional player ID for reconnecting")
    args = parser.parse_args()

    server_url = args.server_url
    if server_url.startswith("http://"):
        server_url = server_url.replace("http://", "ws://")
    elif server_url.startswith("https://"):
        server_url = server_url.replace("https://", "wss://")

    print("Starting client with:")
    print(f"  Player: {args.player_name}")
    print(f"  Chips: {args.chips}")
    print(f"  Table: {args.table_id}")
    print(f"  Server: {server_url}")
    print(f"  Player ID: {args.player_id or 'auto-generated'}")

    try:
        asyncio.run(main_async(server_url, args.table_id, args.player_name, args.chips, args.player_id))
    except KeyboardInterrupt:
        print("\n\nExiting... Goodbye!")
    except Exception as e:
        print(f"\nError: {e}")


if __name__ == "__main__":
    main()
