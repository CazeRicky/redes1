from socket import socket, AF_INET, SOCK_STREAM
from threading import Thread, Lock
from json import loads, dumps
from sqlite3 import connect, IntegrityError
from datetime import datetime

def init_db():
    """Cria as tabelas do banco de dados se não existirem."""
    conn = connect('chat.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password TEXT NOT NULL
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS offline_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            recipient TEXT NOT NULL,
            sender TEXT NOT NULL,
            message TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            FOREIGN KEY (recipient) REFERENCES users(username),
            FOREIGN KEY (sender) REFERENCES users(username)
        )
    ''')
    conn.commit()
    conn.close()

class Server:
    def __init__(self, host='localhost', port=8080):
        self.host = host
        self.port = port
        self.server_socket = socket(AF_INET, SOCK_STREAM)
        self.clients = {}
        self.lock = Lock()
        init_db()

    def start(self):
        """Inicia o servidor e aguarda por conexões."""
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen()
        print(f"Servidor escutando em {self.host}:{self.port}")

        while True:
            client_socket, addr = self.server_socket.accept()
            print(f"Nova conexão de {addr}")
            thread = Thread(target=self.handle_client, args=(client_socket,))
            thread.start()

    def handle_client(self, client_socket):
        """Gerencia a comunicação com um cliente específico."""
        user = None
        try:
            while True:
                request_data = client_socket.recv(2048).decode('utf-8')
                if not request_data:
                    break
                
                request = loads(request_data)
                command = request.get('command')

                if command == 'register':
                    self._register(client_socket, request)
                elif command == 'login':
                    user = self._login(client_socket, request)
                elif user: # A partir daqui, só comandos de quem está logado
                    if command == 'get_users':
                        self._send_user_list()
                    elif command == 'msg':
                        self._route_message(request)
                    elif command == 'typing':
                        self._notify_typing(request)

        except (ConnectionResetError, ValueError):
            print(f"Conexão com {user if user else 'desconhecido'} perdida.")
        finally:
            if user:
                with self.lock:
                    if user in self.clients:
                        del self.clients[user]
                self._broadcast_status(user, 'offline')
            client_socket.close()

    def _register(self, client_socket, request):
        """Registra um novo usuário no banco de dados."""
        username = request.get('username')
        password = request.get('password')
        conn = connect('chat.db')
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, password))
            conn.commit()
            client_socket.send(dumps({"status": "ok", "message": "Registrado com sucesso!"}).encode('utf-8'))
        except IntegrityError:
            client_socket.send(dumps({"status": "error", "message": "Usuário já existe."}).encode('utf-8'))
        finally:
            conn.close()

    def _login(self, client_socket, request):
        """Autentica um usuário."""
        username = request.get('username')
        password = request.get('password')
        conn = connect('chat.db')
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE username = ? AND password = ?", (username, password))
        user_data = cursor.fetchone()
        conn.close()

        if user_data:
            with self.lock:
                self.clients[username] = client_socket
            
            client_socket.send(dumps({"status": "ok", "message": "Login bem-sucedido!"}).encode('utf-8'))
            print(f"Usuário '{username}' logado.")
            self._broadcast_status(username, 'online')
            self._send_offline_messages(username)
            return username
        else:
            client_socket.send(dumps({"status": "error", "message": "Usuário ou senha inválidos."}).encode('utf-8'))
            return None

    def _send_user_list(self):
        """Envia a lista de usuários para todos os clientes conectados."""
        conn = connect('chat.db')
        cursor = conn.cursor()
        cursor.execute("SELECT username FROM users")
        all_users = [row[0] for row in cursor.fetchall()]
        conn.close()

        with self.lock:
            online_users = list(self.clients.keys())
            
        user_list_with_status = {user: ('online' if user in online_users else 'offline') for user in all_users}

        response = dumps({"command": "user_list", "users": user_list_with_status})
        
        with self.lock:
            for client_sock in self.clients.values():
                try:
                    client_sock.send(response.encode('utf-8'))
                except:
                    pass

    def _route_message(self, request):
        """Roteia uma mensagem para o destinatário ou a armazena se offline."""
        recipient = request.get('to')
        sender = request.get('from')
        message_text = request.get('body')
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        request['timestamp'] = timestamp
        
        with self.lock:
            recipient_socket = self.clients.get(recipient)

        if recipient_socket:
            try:
                recipient_socket.send(dumps(request).encode('utf-8'))
            except:
                self._store_offline_message(recipient, sender, message_text, timestamp)
        else:
            self._store_offline_message(recipient, sender, message_text, timestamp)

    def _store_offline_message(self, recipient, sender, message, timestamp):
        """Armazena uma mensagem no banco para um usuário offline."""
        conn = connect('chat.db')
        cursor = conn.cursor()
        cursor.execute("INSERT INTO offline_messages (recipient, sender, message, timestamp) VALUES (?, ?, ?, ?)",
                       (recipient, sender, message, timestamp))
        conn.commit()
        conn.close()
        print(f"Mensagem de '{sender}' para '{recipient}' (offline) armazenada.")

    def _send_offline_messages(self, username):
        """Envia mensagens offline para o usuário que acabou de conectar."""
        conn = connect('chat.db')
        cursor = conn.cursor()
        cursor.execute("SELECT sender, message, timestamp FROM offline_messages WHERE recipient = ?", (username,))
        messages = cursor.fetchall()

        if messages:
            client_sock = self.clients.get(username)
            for sender, message, timestamp in messages:
                msg_packet = {
                    "command": "msg", "from": sender, "to": username,
                    "body": message, "timestamp": timestamp
                }
                try:
                    client_sock.send(dumps(msg_packet).encode('utf-8'))
                except:
                    pass
            
            cursor.execute("DELETE FROM offline_messages WHERE recipient = ?", (username,))
            conn.commit()
        conn.close()

    def _notify_typing(self, request):
        """Notifica o destinatário que o remetente está digitando."""
        recipient = request.get('to')
        with self.lock:
            recipient_socket = self.clients.get(recipient)
        
        if recipient_socket:
            try:
                recipient_socket.send(dumps(request).encode('utf-8'))
            except:
                pass
    
    def _broadcast_status(self, username, status):
        """Informa a todos sobre a mudança de status de um usuário."""
        response = dumps({"command": "status_update", "user": username, "status": status})
        with self.lock:
            # Envia a lista de usuários atualizada para todos
            self._send_user_list()
            # Envia a notificação específica de status
            for client_sock in self.clients.values():
                try:
                    client_sock.send(response.encode('utf-8'))
                except:
                    pass

if __name__ == "__main__":
    server = Server()
    server.start()