from socket import socket, AF_INET, SOCK_STREAM
from threading import Thread
from json import dumps, loads, JSONDecodeError
from time import sleep
from getpass import getpass

# --- Funções de Comunicação ---
def send_request(sock, request):
    """Envia uma requisição JSON para o servidor."""
    try:
        sock.send(dumps(request).encode('utf-8'))
    except (BrokenPipeError, ConnectionResetError):
        # A conexão pode ter sido perdida
        pass

def receive_response(sock):
    """Recebe e decodifica uma resposta JSON do servidor."""
    try:
        data = sock.recv(2048).decode('utf-8')
        return loads(data) if data else None
    except (ConnectionResetError, JSONDecodeError, ConnectionAbortedError):
        return None

# --- Thread para Receber Mensagens ---
def receive_messages(sock, username):
    """Função para escutar o servidor continuamente."""
    while True:
        message = receive_response(sock)
        if message is None:
            print("\n[Sistema] Conexão com o servidor perdida. Pressione Enter para sair.")
            break

        print("\r" + " " * 80 + "\r", end="") # Limpa a linha atual

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
            if user_status != username: # Não notificar sobre o próprio status
                print(f"[Sistema] {user_status} está agora {status}.")
        
        elif command == "typing":
            sender = message.get("from")
            status = message.get("status")
            if status == "start":
                print(f"[Sistema] {sender} está digitando...")
        
        print(f"{username}> ", end="", flush=True)

# --- Funções de Interface do Terminal ---
def show_main_menu():
    print("\n--- CHAT RURALPE ---")
    print("1. Registrar")
    print("2. Login")
    print("3. Sair")
    return input("Escolha uma opção: ")

def handle_login_or_register(option):
    username = input("Usuário: ")
    password = input("Senha: ")

    try:
        sock = socket(AF_INET, SOCK_STREAM)
        sock.connect(('localhost', 8080))
    except ConnectionRefusedError:
        print("[Erro] Não foi possível conectar ao servidor.")
        return None

    command = "register" if option == '1' else "login"
    request = {"command": command, "username": username, "password": password}
    send_request(sock, request)
    response = receive_response(sock)

    if response:
        print(f"[Servidor] {response.get('message')}")
        if command == "login" and response.get("status") == "ok":
            return sock, username
    else:
        print("[Erro] Servidor não respondeu.")

    sock.close()
    return None

def main_chat_loop(sock, username):
    print("\nBem-vindo ao chat! Digite '!ajuda' para ver os comandos.")
    
    receiver = Thread(target=receive_messages, args=(sock, username), daemon=True)
    receiver.start()

    sleep(0.1)
    send_request(sock, {"command": "get_users"})

    while receiver.is_alive():
        try:
            user_input = input(f"{username}> ")

            if user_input.startswith('@'):
                parts = user_input.split(' ', 1)
                recipient = parts[0][1:]
                if len(parts) > 1 and recipient:
                    body = parts[1]
                    send_request(sock, {"command": "typing", "from": username, "to": recipient, "status": "start"})
                    msg_req = {"command": "msg", "from": username, "to": recipient, "body": body}
                    send_request(sock, msg_req)
                else:
                    print("[Sistema] Formato inválido. Use @usuario <mensagem>")
            
            elif user_input == '!ajuda':
                print("\nComandos disponíveis:")
                print("  @usuario <mensagem> - Envia uma mensagem para um usuário.")
                print("  !usuarios         - Mostra a lista de usuários online/offline.")
                print("  !sair             - Sai do chat.")
            
            elif user_input == '!usuarios':
                send_request(sock, {"command": "get_users"})
            
            elif user_input == '!sair':
                print("Saindo...")
                break
        
        except (KeyboardInterrupt, EOFError):
            print("\nSaindo...")
            break

    sock.close()

# --- Ponto de Entrada Principal ---
if __name__ == "__main__":
    while True:
        choice = show_main_menu()
        if choice in ['1', '2']:
            session_data = handle_login_or_register(choice)
            if session_data:
                sock, username = session_data
                main_chat_loop(sock, username)
        elif choice == '3':
            break
        else:
            print("Opção inválida.")