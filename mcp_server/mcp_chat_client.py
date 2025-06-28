# Arquivo: mcp_chat_client.py
import time
import re
import requests
import os

# --- CONFIGURAÇÕES ---
# O caminho completo para o arquivo de log do seu servidor Minecraft
# Exemplo: C:\Users\Peter\Desktop\mineserver\logs\latest.log
MINECRAFT_SERVER_LOG_PATH = "C:\\Users\\Peter\\Desktop\\mineserver\\logs\\latest.log" # <<<<<<<< ATUALIZE ESTE CAMINHO

# O URL do seu servidor MCP (FastAPI)
MCP_SERVER_URL = "http://localhost:8000/mcp/run"
# --- FIM DAS CONFIGURAÇÕES ---

def tail_f(filepath):
    """
    Simula o comando 'tail -f' para ler novas linhas de um arquivo de log.
    Permanece aberto e lendo continuamente.
    """
    if not os.path.exists(os.path.dirname(filepath)):
        print(f"Erro: O diretório do log não foi encontrado: {os.path.dirname(filepath)}")
        return

    # Espera até que o arquivo de log exista (útil se o servidor Minecraft ainda não iniciou)
    while not os.path.exists(filepath):
        print(f"Aguardando o arquivo de log do Minecraft em: {filepath}...")
        time.sleep(5)

    print(f"Monitorando o log do Minecraft em: {filepath}")
    with open(filepath, "r", encoding="utf-8") as f:
        # Pula para o final do arquivo para ler apenas novas linhas a partir de agora
        f.seek(0, 2)
        while True:
            line = f.readline()
            if not line:
                time.sleep(0.1) # Pequeno atraso para evitar consumo excessivo de CPU
                continue
            yield line

def process_log_line(line):
    """
    Processa uma linha do log para extrair mensagens de chat de jogadores.
    Retorna (player_name, chat_message) se for uma mensagem de chat, senão None.
    Exemplo de linha de chat: "[13:30:00 INFO]: <PlayerName> Hello world!"
    """
    # Regex para capturar o timestamp, o nível de log (INFO) e, mais importante,
    # o nome do jogador e o conteúdo da mensagem de chat.
    match = re.match(r'^\[\d{2}:\d{2}:\d{2} INFO\]: <([^>]+)> (.*)$', line)
    if match:
        player_name = match.group(1).strip()
        chat_message = match.group(2).strip()
        return player_name, chat_message
    return None

def send_to_mcp_server(tool_name: str, parameters: dict):
    """
    Envia uma requisição POST JSON para o servidor MCP.
    """
    payload = {
        "tool_name": tool_name,
        "parameters": parameters
    }
    try:
        response = requests.post(MCP_SERVER_URL, json=payload)
        response.raise_for_status() # Lança exceção para erros HTTP (4xx ou 5xx)
        print(f"Requisição MCP para '{tool_name}' enviada com sucesso. Resposta: {response.json()}")
    except requests.exceptions.ConnectionError:
        print(f"Erro: Não foi possível conectar ao servidor MCP em {MCP_SERVER_URL}. Certifique-se de que ele está rodando.")
    except requests.exceptions.HTTPError as e:
        print(f"Erro HTTP ao enviar requisição MCP: {e}. Resposta: {e.response.text}")
    except Exception as e:
        print(f"Ocorreu um erro inesperado ao enviar para o MCP: {e}")

if __name__ == "__main__":
    for line in tail_f(MINECRAFT_SERVER_LOG_PATH):
        chat_data = process_log_line(line)
        if chat_data:
            player_name, chat_message = chat_data
            print(f"[LOG] Chat detectado de {player_name}: '{chat_message}'")

            # Verifica se a mensagem começa com "@ai" (insensível a maiúsculas/minúsculas)
            if chat_message.lower().startswith("@ai"):
                # Extrai a parte do comando após "@ai"
                query = chat_message[len("@ai"):].strip()
                print(f"[CLIENT] Comando @ai detectado: '{query}' de {player_name}. Enviando para o MCP...")

                # Envia o comando para a nova tool no servidor MCP
                send_to_mcp_server(
                    tool_name="process_chat_command", # Nome da nova ferramenta no main.py
                    parameters={
                        "player_name": player_name,
                        "chat_command_text": query # Apenas a query, sem o "@ai"
                    }
                )