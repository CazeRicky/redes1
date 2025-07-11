# client.py

from socket import socket, AF_INET, SOCK_STREAM
from threading import Thread
from json import dumps, loads, JSONDecodeError
from time import sleep
from getpass import getpass

def send_with_delimiter(sock, data):
    """Envia dados JSON seguidos por um caractere de nova linha."""
    try:
        if sock:
            sock.sendall(dumps(data).encode('utf-8') + b'\n')
    except (OSError, ConnectionResetError, BrokenPipeError):
        pass

def receive_messages(sock, username, client_app):
    """Função para escutar o servidor continuamente."""
    buffer = ""
    while client_app['is_running']:
        try:
            data = sock.recv(2048).decode('utf-8')
            if not data:
                break
            
            buffer += data
            while '\n' in buffer:
                message_str, buffer = buffer.split('\n', 1)
                message = loads(message_str)

                print("\r" + " " * 80 + "\r", end="")

                command = message.get("command")
                if command == "msg":
                    sender = message.get("from")
                    body = message.get("body")
                    timestamp_str = message.get("timestamp", " ").split(" ")[1][:5]
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
                    if message.get("status") == "start":
                        print(f"[Sistema] {sender} está digitando...")
                
                print(f"{username}> ", end="", flush=True)

        except (ConnectionAbortedError, ConnectionResetError):
            break 
        except (JSONDecodeError, ValueError):
            continue
        except OSError:
            break
            
    client_app['is_running'] = False
    print("\n[Sistema] Conexão com o servidor perdida. Voltando ao menu principal...")

def main_chat_loop(sock, username):
    """Loop principal do chat, onde o usuário envia mensagens."""
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
    print("\nSaindo do chat...")
    sock.close()

# --- Bloco Principal da Aplicação ---
if __name__ == "__main__":
    while True: # Loop que mantém a aplicação rodando e mostrando o menu
        print("\n--- CHAT RURALPE ---")
        print("1. Registrar")
        print("2. Login")
        print("3. Sair")
        choice = input("Escolha uma opção: ")

        if choice == '1':
            u = input("Usuário para registrar: ")
            p = getpass("Senha: ")
            try:
                temp_sock = socket(AF_INET, SOCK_STREAM)
                temp_sock.connect(('localhost', 8080))
                send_with_delimiter(temp_sock, {"command": "register", "username": u, "password": p})
                response_str = temp_sock.recv(1024).decode('utf-8').strip()
                response = loads(response_str)
                print(f"[Servidor] {response.get('message')}")
            except Exception as e:
                print(f"Erro no registro: {e}")
            finally:
                if 'temp_sock' in locals():
                    temp_sock.close()
            sleep(2)

        elif choice == '2':
            u = input("Usuário: ")
            p = getpass("Senha: ")
            try:
                sock = socket(AF_INET, SOCK_STREAM)
                sock.connect(('localhost', 8080))
                send_with_delimiter(sock, {"command": "login", "username": u, "password": p})
                response_str = sock.recv(1024).decode('utf-8').strip()
                response = loads(response_str)

                if response.get("status") == "ok":
                    print(f"[Servidor] {response.get('message')}")
                    main_chat_loop(sock, u)
                else:
                    print(f"[Servidor] {response.get('message')}")
                    sock.close()
                    sleep(2)
            except Exception as e:
                print(f"Erro no login: {e}")
                if 'sock' in locals():
                    sock.close()
                sleep(2)

        elif choice == '3':
            print("Saindo do programa.")
            break
        
        else:
            print("Opção inválida.")
            sleep(1)