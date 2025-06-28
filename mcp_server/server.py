# Arquivo: main.py
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

# Carrega os comandos do arquivo commands.json (funcionalidade existente)
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
    return send_rcon(command)

@mcp.tool()
def process_chat_command(player_name: str, chat_command_text: str) -> str:
    """
    Processa um comando em linguagem natural recebido via chat do Minecraft
    e o traduz para um comando RCON.

    Args:
        player_name (str): O nome do jogador que digitou o comando.
        chat_command_text (str): O texto do comando digitado pelo jogador (após "@ai").

    Returns:
        str: Uma mensagem de confirmação de que a informação foi enviada ao jogador.
    """
    translated_command = None
    response_to_player = "Desculpe, não entendi o que você quis dizer. Tente algo como 'deixe de dia'."

    # --- Lógica Simples de Mapeamento de Comandos ---
    # Futuramente, esta lógica será o ponto de integração com uma LLM (como o Gemini)
    # para interpretar comandos em linguagem natural de forma mais avançada.
    # Por enquanto, usamos mapeamentos diretos para testar o fluxo.
    
    lower_chat_command = chat_command_text.lower()

    if "deixe de dia" in lower_chat_command:
        translated_command = "time set day"
        response_to_player = "O tempo foi definido para dia!"
    elif "deixe de noite" in lower_chat_command:
        translated_command = "time set night"
        response_to_player = "O tempo foi definido para noite!"
    elif "chover" in lower_chat_command or "chuva" in lower_chat_command:
        translated_command = "weather rain"
        response_to_player = "Chuva ativada no mundo!"
    elif "tempo limpo" in lower_chat_command or "parar chuva" in lower_chat_command:
        translated_command = "weather clear"
        response_to_player = "O tempo está limpo agora!"
    elif "explodir" in lower_chat_command or "explosao" in lower_chat_command:
        # Exemplo de comando que normalmente precisaria de coordenadas.
        # Por enquanto, apenas informamos ao jogador a limitação.
        response_to_player = f"Desculpe {player_name}, para causar uma explosão preciso saber onde. Atualmente, a IA não consegue pegar sua localização automaticamente."
    # Você pode adicionar mais mapeamentos simples aqui para testar:
    # elif "me teleporte para" in lower_chat_command and "x:" in lower_chat_command:
    #     # Lógica para extrair X Y Z e usar /tp
    #     pass
    # --- Fim da Lógica de Mapeamento ---

    if translated_command:
        try:
            print(f"[MCP Server] Traduzindo '{chat_command_text}' para RCON: '{translated_command}'")
            rcon_output = send_rcon(translated_command)
            print(f"[MCP Server] Saída RCON: {rcon_output}")
            
            # Ajuste a resposta ao jogador se o comando RCON falhar
            if rcon_output and "Unknown command" in rcon_output:
                response_to_player = f"Erro Minecraft: Não reconheci o comando '{translated_command}'. Verifique a sintaxe."
            elif rcon_output and "Usage:" in rcon_output:
                 response_to_player = f"Erro de uso no Minecraft para '{translated_command}'. Verifique a sintaxe. ({rcon_output})"


        except Exception as e:
            response_to_player = f"Ocorreu um erro interno ao executar o comando RCON: {e}"
            print(f"[MCP Server] Erro ao enviar RCON: {e}")
    
    # Envia a resposta final de volta ao jogador no chat do Minecraft
    # Isso garante que o jogador sempre receba um feedback.
    send_rcon(f"tell {player_name} {response_to_player}")
    
    return f"Comando '{chat_command_text}' processado para {player_name}. Resposta enviada."

if __name__ == "__main__":
    mcp.run()
     