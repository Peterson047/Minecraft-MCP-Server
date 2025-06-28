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

@mcp.tool()
def run_command(command: str) -> str:
    """Executa qualquer comando no servidor via RCON."""
    return send_rcon(command)

if __name__ == "__main__":
    mcp.run()
