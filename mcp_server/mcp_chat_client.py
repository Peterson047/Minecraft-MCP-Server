# File: mcp_chat_client.py

import asyncio
import os
import re
import time
import json
from dotenv import load_dotenv
from typing import Optional
from contextlib import AsyncExitStack

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from google import genai

# Load variables from .env file
load_dotenv()

# Path to the Minecraft log file
LOG_PATH = os.getenv("MINECRAFT_LOG_PATH", "PATH_TO_YOUR_MINECRAFT_LOG_FILE")

# Path to the MCP server script (server.py)
MCP_SERVER_PATH = os.getenv("MCP_SERVER_PATH")
if not MCP_SERVER_PATH or not os.path.exists(MCP_SERVER_PATH):
    raise ValueError("❌ Error: Invalid or undefined MCP_SERVER_PATH")

# Gemini API key
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("❌ Error: GEMINI_API_KEY variable not found in .env")


class MCPChatClient:
    def __init__(self):
        self.session: Optional[ClientSession] = None
        self.exit_stack = AsyncExitStack()
        self.client = genai.Client(api_key=GEMINI_API_KEY)

    async def connect(self, server_path: str):
        """Connects to the MCP server via stdio"""
        stdio_ctx = stdio_client(
            StdioServerParameters(command="python", args=[server_path])
        )
        stdio = await self.exit_stack.enter_async_context(stdio_ctx)
        self.stdio, self.write = stdio

        self.session = await self.exit_stack.enter_async_context(
            ClientSession(self.stdio, self.write)
        )
        await self.session.initialize()
        print("✅ Connected to MCP")

    async def handle_chat_command(self, player: str, message: str):
        """Processes the player’s message and executes it via Gemini + MCP"""
        tools = (await self.session.list_tools()).tools
        prompt = f"""Minecraft player message: "{message}"
The goal is to generate the correct Minecraft command for this intention.
Respond only with the command, nothing else.

Available commands:
{json.dumps([{t.name: t.description} for t in tools], indent=2)}

Return a valid command (e.g., /time set day)
"""

        print(f"💬 [{player}]: {message}")
        print("🤖 Querying Gemini...")

        response = self.client.models.generate_content(
            model="gemini-2.5-pro",
            contents=[prompt],
            config=genai.types.GenerateContentConfig(response_mime_type="text/plain")
        )

        command = response.candidates[0].content.parts[0].text.strip()
        print(f"✅ Command generated: {command}")

        result = await self.session.call_tool("run_command", {"command": command})
        response_texts = [c.text for c in result.content if hasattr(c, "text")]
        print(f"🎮 Server response: {' '.join(response_texts)}")

    def process_log_line(self, line: str):
        """
        Processes a log line to extract player chat messages.
        Returns (player_name, chat_message) if it's a chat message, otherwise None.
        """
        match = re.match(r'^\[\d{2}:\d{2}:\d{2}\] \[.*?/INFO\]: <([^>]+)> (.*)$', line)
        if match:
            player_name = match.group(1).strip()
            chat_message = match.group(2).strip()
            return player_name, chat_message
        return None

    async def monitor_log(self):
        """Monitors the Minecraft log and sends commands with @ai"""
        print(f"🟡 Monitoring Minecraft log: {LOG_PATH}")
        while not os.path.exists(LOG_PATH):
            print(f"⏳ Waiting for log file: {LOG_PATH}")
            time.sleep(3)

        with open(LOG_PATH, "r", encoding="utf-8") as f:
            f.seek(0, 2)  # Go to the end of the file
            while True:
                line = f.readline()
                if not line:
                    await asyncio.sleep(0.1)
                    continue
                chat = self.process_log_line(line)
                if chat:
                    player, message = chat
                    if message.lower().startswith("@ai"):
                        query = message[3:].strip()
                        print(f"🚨 Command detected from {player}: {query}")
                        await self.handle_chat_command(player, query)

    async def cleanup(self):
        await self.exit_stack.aclose()


async def main():
    client = MCPChatClient()
    try:
        await client.connect(MCP_SERVER_PATH)
        await client.monitor_log()
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        await client.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
