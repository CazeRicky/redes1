from socket import socket, AF_INET, SOCK_STREAM
from threading import Thread
from json import dumps, loads, JSONDecodeError
from time import sleep
from getpass import getpass

# Função para enviar dados com um delimitador de nova linha
def send_with_delimiter(sock, data):
    """Envia dados JSON seguidos por um caractere de nova linha."""
    try:
        sock.sendall(dumps(data).encode('utf-8') + b'\n')
    except (BrokenPipeError, ConnectionResetError):
        pass

# --- Thread para Receber Mensagens ---
def receive_messages(sock, username, client_app):
    """Função para escutar o servidor continuamente."""
    buffer = ""
    while client_app['is_running']:
        try:
            data = sock.recv(2048).decode('utf-8')
            if not data:
                print("\n[Sistema] O servidor encerrou a conexão.")
                break
            
            buffer += data
            while '\n' in buffer:
                message_str, buffer = buffer.split('\n', 1)
                message = loads(message_str)

                # Limpa a linha atual para não bagunçar a entrada do usuário
                print("\r" + " " * 80 + "\r", end="")

                command = message.get("command")
                if command == "msg":
                    sender = message.get("from")
                    body = message.get("body")
                    timestamp_str = message.get("timestamp", "").split(" ")[1][:5]
                    print(f"[{timestamp_str}] {sender}: {body}")

                elif command == "user_list":
                    users = message.get("users", {})
                    online = [u for u, s in users.items() if s == 'online' and u != username]
                    offline = [u for u, s in users.items() if s == 'offline' and u != username]
                    print("[Sistema] Usuários Online: " + (", ".join(online) if online else "Nenhum"))
                    print("[Sistema] Usuários Offline: " + (", ".join(offline) if offline else "Nenhum"))

                elif command == "status_update":
                    user_status = message.get("user")
                    status = message.get("status")
                    if user_status != username:
                        print(f"[Sistema] {user_status} está agora {status}.")

                elif command == "typing":
                    sender = message.get("from")
                    status = message.get("status")
                    if status == "start":
                        print(f"[Sistema] {sender} está digitando...")
                
                # Re-exibe o prompt de entrada do usuário
                print(f"{username}> ", end="", flush=True)

        except (ConnectionResetError, ConnectionAbortedError):
            print("\n[Sistema] Conexão com o servidor perdida.")
            break
        except (JSONDecodeError, ValueError):
            # Ignora mensagens malformadas e continua
            continue
        except Exception:
            break
            
    client_app['is_running'] = False # Sinaliza para a thread principal que deve parar

# --- Funções de Interface do Terminal ---
def show_main_menu():
    print("\n--- CHAT RURALPE ---")
    print("1. Registrar")
    print("2. Login")
    print("3. Sair")
    return input("Escolha uma opção: ")

def handle_login_or_register(option):
    username = input("Usuário: ")
    password = getpass("Senha: ")

    try:
        sock = socket(AF_INET, SOCK_STREAM)
        sock.connect(('localhost', 8080))
    except ConnectionRefusedError:
        print("[Erro] Não foi possível conectar ao servidor.")
        return None, None

    command = "register" if option == '1' else "login"
    request = {"command": command, "username": username, "password": password}
    send_with_delimiter(sock, request)

    # Para login/register, esperamos apenas uma resposta, então um recv simples funciona
    try:
        data = sock.recv(2048).decode('utf-8').strip()
        response = loads(data)
    except (IOError, JSONDecodeError):
        print("[Erro] Servidor não respondeu corretamente.")
        sock.close()
        return None, None
        
    print(f"[Servidor] {response.get('message')}")
    if command == "login" and response.get("status") == "ok":
        return sock, username # Retorna o socket e usuário para a sessão de chat
    
    sock.close()
    return None, None

def main_chat_loop(sock, username):
    print("\nBem-vindo ao chat! Digite '!ajuda' para ver os comandos.")
    
    client_app = {'is_running': True}
    receiver = Thread(target=receive_messages, args=(sock, username, client_app), daemon=True)
    receiver.start()

    sleep(0.1)
    send_with_delimiter(sock, {"command": "get_users"})

    while client_app['is_running']:
        try:
            user_input = input(f"{username}> ")
            if not client_app['is_running']:
                break

            if user_input.startswith('@'):
                parts = user_input.split(' ', 1)
                recipient = parts[0][1:]
                if len(parts) > 1 and recipient:
                    body = parts[1]
                    send_with_delimiter(sock, {"command": "typing", "from": username, "to": recipient, "status": "start"})
                    msg_req = {"command": "msg", "from": username, "to": recipient, "body": body}
                    send_with_delimiter(sock, msg_req)
                else:
                    print("[Sistema] Formato inválido. Use @usuario <mensagem>")
            
            elif user_input == '!ajuda':
                print("\nComandos disponíveis:")
                print("  @usuario <mensagem> - Envia uma mensagem para um usuário.")
                print("  !usuarios         - Mostra a lista de usuários online/offline.")
                print("  !sair             - Sai do chat.")
            
            elif user_input == '!usuarios':
                send_with_delimiter(sock, {"command": "get_users"})
            
            elif user_input == '!sair':
                break
        
        except (KeyboardInterrupt, EOFError):
            break
            
    client_app['is_running'] = False
    print("\nSaindo...")
    sock.close()

# --- Ponto de Entrada Principal ---
if __name__ == "__main__":
    while True:
        choice = show_main_menu()
        if choice in ['1', '2']:
            sock, username = handle_login_or_register(choice)
            if sock and username:
                main_chat_loop(sock, username)
        elif choice == '3':
            break
        else:
            print("Opção inválida.")