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

# Load variables from .env file
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

# Filename for custom commands
COMMANDS_FILE = "commands.json"

class MCPChatClient:
    """
    Client that connects to the MCP server, monitors the Minecraft log,
    and uses the Gemini API to process chat messages and execute commands.
    """
    def __init__(self):
        self.session: Optional[ClientSession] = None
        self.exit_stack = AsyncExitStack()
        self.client = genai.Client(api_key=GEMINI_API_KEY)
        self.extra_commands = self.load_commands_from_file(COMMANDS_FILE)

    def load_commands_from_file(self, filename: str) -> List[Dict]:
        """
        Loads additional commands from a JSON file.
        Returns a list of dictionaries, where each dictionary represents a command.
        """
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

    async def connect(self, server_path: str):
        """
        Connects to the MCP server via stdio.
        Sets up the client session for communication with the server.
        """
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
        """
        Processes the player's message, queries the Gemini API to generate a command
        or response, and executes it via MCP.
        """
        mcp_tools = (await self.session.list_tools()).tools

        # Gerar a lista de ferramentas MCP no formato {nome: descrição}
        formatted_mcp_tools = [{t.name: t.description} for t in mcp_tools]
        
        # Converter os comandos extras de dicionário para uma lista de dicionários no mesmo formato
        # Assumimos que self.extra_commands é um dicionário como {"/comando": {"description": "..."}}
        formatted_extra_commands = []
        for cmd_name, cmd_details in self.extra_commands.items():
            # A chave de t.name é apenas o nome do comando sem a barra (ex: "give" ao invés de "/give")
            # Vamos manter a barra para que o prompt veja o comando como ele é.
            formatted_extra_commands.append({cmd_name: cmd_details.get("description", "Comando personalizado.")})

        # Agora ambas são listas de dicionários, e podem ser concatenadas
        all_commands = formatted_mcp_tools + formatted_extra_commands

        # --- SEU PROMPT SEGUE AQUI, SEM ALTERAÇÕES NESTA SEÇÃO ---
        prompt = f"""
You are an AI assistant inside a Minecraft server. Your name is @ai.
The player '{player}' sent the following message: "{message}"

Your task is to interpret the player's intent and respond appropriately.
You are the server administrator and can execute Minecraft commands or reply as an NPC.
Follow these rules:

1. **Always use the /say command for NPC responses**: All replies must be sent to the in-game chat using the `/say` command.

2. **Use Minecraft commands for actions**: If the player requests something involving in-game actions, use the appropriate available commands.

3. **If the message is a command request**: Analyze the list of available commands and generate the exact Minecraft command that fits the request. Respond ONLY with the command (e.g., `/give {player} diamond 64`).

4. **If the message is general conversation or a question**: Respond in a helpful and friendly way, as an NPC would. Use the `/say` command to send your reply to the in-game chat (e.g., `/say Hello, {player}! How can I help you today?`).

Do not repeat the player's message in your response.

When using a command, output only the command — do not include any other text.
Any messages before the command may be ignored by the server.

**Available commands:**

{json.dumps(all_commands, indent=2, ensure_ascii=False)}
"""

        print(f"💬 [{player}]: {message}")
        print("🤖 Querying Gemini with improved prompt...")

        loop = asyncio.get_running_loop()
        blocking_call = functools.partial(
            self.client.models.generate_content,
            model="gemini-1.5-flash",  # Updated model
            contents=[prompt],
            config=genai.types.GenerateContentConfig(response_mime_type="text/plain")
        )
        response = await loop.run_in_executor(None, blocking_call)

        command = response.candidates[0].content.parts[0].text.strip()
        print(f"✅ Generated command: {command}")

        result = await self.session.call_tool("run_command", {"command": command})
        response_texts = [c.text for c in result.content if hasattr(c, "text")]
        print(f"🎮 Server response: {' '.join(response_texts)}")

    def process_log_line(self, line: str):
        """
        Processes a log line to extract player chat messages.
        Returns (player_name, chat_message) if it’s a chat message, otherwise None.
        """
        match = re.match(r'^\[\d{2}:\d{2}:\d{2}\] \[.*?/INFO\]: <([^>]+)> (.*)$', line)
        if match:
            return match.group(1).strip(), match.group(2).strip()
        return None

    async def monitor_log(self):
        """
        Monitors the Minecraft log and sends commands to the AI assistant
        when a message starting with "@ai" is detected.
        """
        print(f"🟡 Monitoring Minecraft log: {LOG_PATH}")
        while not os.path.exists(LOG_PATH):
            print(f"⏳ Waiting for log file: {LOG_PATH}")
            await asyncio.sleep(3)

        with open(LOG_PATH, "r", encoding="utf-8") as f:
            f.seek(0, 2)  # Move to the end of the file
            while True:
                line = f.readline()
                if not line:
                    await asyncio.sleep(0.1)
                    continue
                chat = self.process_log_line(line)
                if chat:
                    player, message = chat

                    # --- LINHAS DE DEBUGGING ---
                    print(f"DEBUG_LOG: Linha de log processada: '{line.strip()}'")
                    print(f"DEBUG_LOG: Player: '{player}', Mensagem: '{message}'")
                    print(f"DEBUG_LOG: Mensagem em minúsculas: '{message.lower()}'")
                    print(f"DEBUG_LOG: Começa com '@ai'?: {message.lower().startswith('@ai')}")
                    # --- FIM DAS LINHAS DE DEBUGGING ---

                    if message.lower().startswith("@ai"):
                        query = message[3:].strip()
                        print(f"DEBUG_LOG: Query extraída: '{query}'")
                        asyncio.create_task(self.handle_chat_command(player, query))

    async def cleanup(self):
        """Performs cleanup and closes the client session."""
        print("🔴 Shutting down client and cleaning up resources...")
        await self.exit_stack.aclose()

async def main():
    """Main function to initialize and run the MCP chat client."""
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