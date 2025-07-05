import asyncio
import os
import re
import json
import functools
from typing import Optional, List, Dict
from contextlib import AsyncExitStack

from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from google import genai

# Load environment variables from .env file
load_dotenv()

# Path to the Minecraft log file
LOG_PATH = os.getenv("MINECRAFT_LOG_PATH")

# Path to the MCP server script (server.py)
MCP_SERVER_PATH = os.getenv("MCP_SERVER_PATH")
if not MCP_SERVER_PATH or not os.path.exists(MCP_SERVER_PATH):
    raise ValueError("❌ Error: Invalid or undefined MCP_SERVER_PATH")

# Gemini API key
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("❌ Error: GEMINI_API_KEY variable not found in .env")

# Files for extra commands and chat history
COMMANDS_FILE = "commands.json"
CHAT_HISTORY_FILE = "chat_history.json"

class MCPChatClient:
    def __init__(self):
        self.session: Optional[ClientSession] = None
        self.exit_stack = AsyncExitStack()
        self.client = genai.Client(api_key=GEMINI_API_KEY)
        self.extra_commands = self.load_commands_from_file(COMMANDS_FILE)
        self.chat_history: Dict[str, List[str]] = self.load_chat_history()

    def load_commands_from_file(self, filename: str) -> List[Dict]:
        if os.path.exists(filename):
            try:
                with open(filename, "r", encoding="utf-8") as f:
                    print(f"✅ Custom commands loaded from {filename}")
                    return json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                print(f"⚠️ Warning: Could not load or decode {filename}: {e}")
        else:
            print(f"ℹ️ Info: File {filename} not found. No extra commands will be loaded.")
        return []

    def load_chat_history(self) -> Dict[str, List[str]]:
        if os.path.exists(CHAT_HISTORY_FILE):
            try:
                with open(CHAT_HISTORY_FILE, "r", encoding="utf-8") as f:
                    print(f"🟢 Chat history loaded from {CHAT_HISTORY_FILE}")
                    return json.load(f)
            except Exception as e:
                print(f"⚠️ Failed to load chat history: {e}")
        return {}

    def save_chat_history(self):
        try:
            with open(CHAT_HISTORY_FILE, "w", encoding="utf-8") as f:
                json.dump(self.chat_history, f, indent=2, ensure_ascii=False)
            print("💾 Chat history saved.")
        except Exception as e:
            print(f"⚠️ Failed to save chat history: {e}")

    async def connect(self, server_path: str):
        stdio_ctx = stdio_client(
            StdioServerParameters(command="python", args=[server_path])
        )
        self.stdio, self.write = await self.exit_stack.enter_async_context(stdio_ctx)

        self.session = await self.exit_stack.enter_async_context(
            ClientSession(self.stdio, self.write)
        )
        await self.session.initialize()
        print("✅ Connected to MCP")

    async def handle_chat_command(self, player: str, message: str):
        mcp_tools = (await self.session.list_tools()).tools
        formatted_mcp_tools = [{t.name: t.description} for t in mcp_tools]

        formatted_extra_commands = []
        for cmd_name, cmd_details in self.extra_commands.items():
            formatted_extra_commands.append({cmd_name: cmd_details.get("description", "Custom command.")})

        all_commands = formatted_mcp_tools + formatted_extra_commands

        # 🧠 Update history
        history = self.chat_history.get(player, [])
        history.append(f"Player: {message}")
        history = history[-10:]  # Keep the last 10 entries
        self.chat_history[player] = history
        formatted_history = "\n".join(history)

        prompt = f"""
You are an AI assistant inside a Minecraft server. Your name is @ai. You speak Brazilian Portuguese and act as a friendly NPC.

Recent chat history with player '{player}':
{formatted_history}

The player '{player}' sent the following message: "{message}"

Your task is to interpret the player's intent and respond appropriately.
You are the server administrator and can execute Minecraft commands or reply as an NPC.
Follow these rules:

1. **Always use `/say` for NPC responses**: All replies must go to the chat using `/say`.

2. **Use Minecraft commands for actions**: If the player asks for something involving in-game actions, use the appropriate commands.

3. **If it's a command request**:
   * Analyze the list of available commands and generate the exact Minecraft command.
   * Respond ONLY with the command (e.g., `/give {player} diamond 64`).
   * **Do NOT include any extra text before or after.**

4. **If it's general conversation or a question**:
   * Reply in a friendly manner, like a helpful NPC.
   * Use `/say` to send your response (e.g., `/say Hello, {player}! How can I help you today?`).

5. **Restrictions for standard players**:
   * **Giving items (`/give`) is forbidden**.
   * **Teleporting players (`/tp`, `/teleport`) is not allowed**.
   * **Changing gamemode, summoning mobs, killing entities, changing weather/time and other admin commands are also forbidden.**
   * Forbidden requests must be politely refused using `/say`.

Do not repeat the player's message in your response.
When using commands, send only the command — with no additional text.

**Available commands**:
{json.dumps(all_commands, indent=2, ensure_ascii=False)}
"""

        print(f"💬 [{player}]: {message}")
        print("🤖 Querying Gemini with chat history...")

        loop = asyncio.get_running_loop()
        blocking_call = functools.partial(
            self.client.models.generate_content,
            model="gemini-1.5-flash",
            contents=[prompt],
            config=genai.types.GenerateContentConfig(response_mime_type="text/plain")
        )
        response = await loop.run_in_executor(None, blocking_call)
        command = response.candidates[0].content.parts[0].text.strip()

        print(f"✅ Generated command: {command}")

        # Update and save chat history
        self.chat_history[player].append(f"@ai: {command}")
        self.save_chat_history()

        result = await self.session.call_tool("run_command", {"command": command})
        response_texts = [c.text for c in result.content if hasattr(c, "text")]
        print(f"🎮 Server response: {' '.join(response_texts)}")

    def process_log_line(self, line: str):
        match = re.match(r'^\[\d{2}:\d{2}:\d{2}\] \[.*?/INFO\]: <([^>]+)> (.*)$', line)
        if match:
            return match.group(1).strip(), match.group(2).strip()
        return None

    async def monitor_log(self):
        print(f"🟡 Monitoring Minecraft log: {LOG_PATH}")
        while not os.path.exists(LOG_PATH):
            print(f"⏳ Waiting for log file: {LOG_PATH}")
            await asyncio.sleep(3)

        with open(LOG_PATH, "r", encoding="utf-8") as f:
            f.seek(0, 2)
            while True:
                line = f.readline()
                if not line:
                    await asyncio.sleep(0.1)
                    continue
                chat = self.process_log_line(line)
                if chat:
                    player, message = chat
                    print(f"DEBUG_LOG: {player} said: {message}")
                    if message.lower().startswith("@ai"):
                        query = message[3:].strip()
                        asyncio.create_task(self.handle_chat_command(player, query))

    async def cleanup(self):
        print("🔴 Shutting down client and cleaning up resources...")
        self.save_chat_history()
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
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🟡 Program interrupted by user.")
