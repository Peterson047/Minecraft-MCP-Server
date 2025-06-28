import json
from mcp.server.fastmcp import FastMCP
from mcrcon import MCRcon

# Configurações RCON
HOST = "localhost"
PORT = 25575
PASSWORD = "minemcp"

def send_rcon(cmd: str) -> str:
    """Envia comando via RCON."""
    with MCRcon(HOST, PASSWORD, port=PORT) as mcr:
        return mcr.command(cmd)

# Inicia o servidor MCP
mcp = FastMCP("Minecraft MCP Server")

# Carrega os comandos do arquivo commands.json
commands_dict = {}
try:
    with open("commands.json", "r", encoding="utf-8") as f:
        commands_dict = json.load(f)
    print("Commands loaded successfully from commands.json.")
except FileNotFoundError:
    print("commands.json not found. The server will start without command definitions.")
except json.JSONDecodeError:
    print("Error decoding commands.json. The server will start without command definitions.")


@mcp.tool()
def run_command(command: str) -> str:
    """Executa qualquer comando no servidor via RCON."""
    # O commands_dict pode ser usado aqui para validação,
    # ou para fornecer mais contexto à LLM sobre os comandos disponíveis.
    return send_rcon(command)

if __name__ == "__main__":
    mcp.run()