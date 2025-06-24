from mcrcon import MCRcon
import json
from pathlib import Path
from mcp.server.fastmcp import FastMCP

# --- Loads command dictionary from JSON file ---
commands_path = Path(__file__).parent / "commands.json"
commands_dict = json.loads(commands_path.read_text(encoding="utf-8"))

# --- Utility function to send commands via RCON to Minecraft ---
def rcon_command(cmd: str, host="localhost", port=25575, pwd="minemcp") -> str:
    with MCRcon(host=host, password=pwd, port=port) as mcr:
        return mcr.command(cmd)

# --- Initializes the MCP server ---
mcp = FastMCP("Minecraft Controller")

# --- Resource: makes the command dictionary available to the LLM ---
@mcp.resource("minecraft://commands", title="Minecraft Commands")
def get_commands() -> dict:
    """This resource provides the complete dictionary of commands and examples."""
    return commands_dict

# --- Tool: executes command on the server via RCON ---
@mcp.tool(title="run_minecraft_command", description="Executes a command on the Minecraft server via RCON.")
def run_minecraft_command(command: str) -> str:
    """Sends an RCON command and returns the response."""
    return rcon_command(command)

# --- Main script ---
if __name__ == "__main__":