# Minecraft-MCP-Server

Python MCP Server to control a Minecraft server via RCON, using FastMCP.

---

## 🔧 Features

* Exposes a set of commands (dictionary) to contextualize the LLM
* Executes commands on the Minecraft server via RCON
* Integration with Claude Desktop or any MCP client
* Simple structure: `stdio` (local development) or HTTP/SSE (production)

---

## 📦 Project Structure

```
mcp_server/
├── commands.json         # Commands dictionary and examples  
├── server.py             # Main MCP server  
├── commands.json         # Minecraft commands for context  
└── (venv/)               # Virtual environment (optional)  
```

---

## ⚙️ Installation

1. Clone the repository:

   ```bash
     cd Minecraft-MCP-Server/mcp_server
   ```

2. Create an environment and install dependencies:

   ```bash
   python -m venv venv
   venv\Scripts\activate
   pip install mcp[cli] mcrcon
   ```

---

## 📝 Setup

In the `commands.json` file, you will have a list of commands like `/give`, `/weather`, `/gamemode`, etc., with descriptions and examples.

Don’t forget to enable RCON in the Minecraft `server.properties` file:

```
enable-rcon=true
rcon.password=minemcp
rcon.port=25575
```

---

## 🚀 Running

Activate the virtual environment and run:

```bash
venv\Scripts\activate
python server.py
```

Monkey patch: starts MCP server in STDIO by default ([apidog.com][1], [reddit.com][2], [github.com][3])

---

## ⚙️ Integration with Claude Desktop

In `claude_desktop_config.json` (e.g., `%APPDATA%\Claude\`):

```json
{
  "mcpServers": {
    "minecraft-controller": {
      "type": "stdio",
      "command": "C:\\...\\venv\\Scripts\\python.exe",
      "args": ["C:\\...\\mcp_server\\server.py"],
      "env": {"PATH": "%PATH%"}
    }
  }
}
```

Then restart Claude — the ‘minecraft-controller’ server will appear.

---

## 🧪 Local Test with Python

```python
from fastmcp import Client
import asyncio

async def test():
    client = Client("mcp_server/server.py")
    async with client:
        res = await client.call_tool("run_minecraft_command", {"command": "/list"})
        print("Players:", res)
        cmds = await client.read_resource("minecraft://commands")
        print("Commands:", list(cmds.keys())[:5])

asyncio.run(test())
```

---

## 🧰 How It Works

* 🎯 `FastMCP` automatically loads tools and resources ([medium.com][4], [github.com][5])
* Resource `minecraft://commands` provides the commands dictionary
* Tool `run_minecraft_command` uses `mcrcon` to send commands to Minecraft

---

## 📚 References

* \[FastMCP v2 – Sample README] ([pypi.org][6])
* \[mcrcon – Python RCON client] ([pypi.org][6])

---

## 🛠 Next Steps

* Support for HTTP/SSE transport with Docker
* Argument validation/autocomplete via commands dictionary
* Logging extra actions: `/start`, `/stop`, `/backup`, `/whitelist`

---

**Ready to make your server smart!** 🚀

[1]: https://apidog.com/blog/fastmcp/?utm_source=chatgpt.com "A Beginner's Guide to Use FastMCP - Apidog"
[2]: https://www.reddit.com/r/mcp/comments/1hrq0au/how_to_build_mcp_servers_with_fastmcp_stepbystep/?utm_source=chatgpt.com "How to Build MCP Servers with FastMCP: Step-by-Step Tutorial for ..."
[3]: https://github.com/GanonUchiha/My-FastMCP-Example?utm_source=chatgpt.com "My example of setting up a MCP server - GitHub"
[4]: https://medium.com/data-engineering-with-dremio/building-a-basic-mcp-server-with-python-4c34c41031ed?utm_source=chatgpt.com "Building a Basic MCP Server with Python | by Alex Merced - Medium"
[5]: https://github.com/jlowin/fastmcp?utm_source=chatgpt.com "jlowin/fastmcp: The fast, Pythonic way to build MCP servers and clients"
[6]: https://pypi.org/project/mcrcon/?utm_source=chatgpt.com "mcrcon - PyPI"

---

