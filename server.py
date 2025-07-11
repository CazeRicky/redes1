# server.py

from socket import socket, AF_INET, SOCK_STREAM
from threading import Thread, Lock
from json import loads, dumps
from sqlite3 import connect, IntegrityError
from datetime import datetime
import hashlib

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def send_with_delimiter(sock, data):
    try:
        sock.sendall(dumps(data).encode('utf-8') + b'\n')
    except (ConnectionResetError, BrokenPipeError):
        pass

def init_db():
    conn = connect('chat.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password_hash TEXT NOT NULL
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS offline_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            recipient TEXT NOT NULL,
            sender TEXT NOT NULL,
            message TEXT NOT NULL,
            timestamp DATETIME NOT NULL,
            FOREIGN KEY (recipient) REFERENCES users(username)
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
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen()
        print(f"Servidor escutando em {self.host}:{self.port}")
        while True:
            client_socket, addr = self.server_socket.accept()
            print(f"Nova conexão de {addr}")
            thread = Thread(target=self.handle_client, args=(client_socket,))
            thread.start()

    def handle_client(self, client_socket):
        user = None
        buffer = ""
        try:
            while True:
                data = client_socket.recv(2048).decode('utf-8')
                if not data:
                    break
                buffer += data
                while '\n' in buffer:
                    message_str, buffer = buffer.split('\n', 1)
                    request = loads(message_str)
                    command = request.get('command')

                    if command == 'register':
                        self._register(client_socket, request)
                    elif command == 'login':
                        user = self._login(client_socket, request)
                    elif user:
                        if command == 'get_users':
                            self._send_user_list()
                        elif command == 'msg':
                            self._route_message(request)
                        elif command == 'typing':
                            self._notify_typing(request)
        except (ConnectionResetError, ValueError, ConnectionAbortedError):
            print(f"Conexão com {user if user else 'desconhecido'} perdida.")
        finally:
            if user:
                with self.lock:
                    if user in self.clients:
                        del self.clients[user]
                self._broadcast_status(user, 'offline')
                self._send_user_list()
            client_socket.close()

    def _register(self, client_socket, request):
        username = request.get('username')
        password = request.get('password')
        conn = connect('chat.db', check_same_thread=False)
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT INTO users (username, password_hash) VALUES (?, ?)", (username, hash_password(password)))
            conn.commit()
            send_with_delimiter(client_socket, {"status": "ok", "message": "Registrado com sucesso!"})
        except IntegrityError:
            send_with_delimiter(client_socket, {"status": "error", "message": "Usuário já existe."})
        finally:
            conn.close()

    def _login(self, client_socket, request):
        username = request.get('username')
        password = request.get('password')
        conn = connect('chat.db', check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE username = ? AND password_hash = ?", (username, hash_password(password)))
        user_data = cursor.fetchone()
        conn.close()

        if user_data:
            with self.lock:
                self.clients[username] = client_socket
            send_with_delimiter(client_socket, {"status": "ok", "message": "Login bem-sucedido!"})
            print(f"Usuário '{username}' logado.")
            self._broadcast_status(username, 'online')
            self._send_user_list()
            self._send_offline_messages(username)
            return username
        else:
            send_with_delimiter(client_socket, {"status": "error", "message": "Usuário ou senha inválidos."})
            return None

    def _send_user_list(self):
        conn = connect('chat.db', check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("SELECT username FROM users")
        all_users = [row[0] for row in cursor.fetchall()]
        conn.close()
        with self.lock:
            online_users = list(self.clients.keys())
            user_list_with_status = {user: ('online' if user in online_users else 'offline') for user in all_users}
            response = {"command": "user_list", "users": user_list_with_status}
            for client_sock in self.clients.values():
                send_with_delimiter(client_sock, response)

    def _route_message(self, request):
        recipient = request.get('to')
        request['timestamp'] = str(datetime.now())
        with self.lock:
            recipient_socket = self.clients.get(recipient)
        if recipient_socket:
            send_with_delimiter(recipient_socket, request)
        else:
            self._store_offline_message(request)

    def _store_offline_message(self, request):
        conn = connect('chat.db', check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO offline_messages (recipient, sender, message, timestamp) VALUES (?, ?, ?, ?)",
                       (request.get('to'), request.get('from'), request.get('body'), datetime.now()))
        conn.commit()
        conn.close()
        print(f"Mensagem de '{request.get('from')}' para '{request.get('to')}' (offline) armazenada.")

    def _send_offline_messages(self, username):
        conn = connect('chat.db', check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("SELECT sender, message, timestamp FROM offline_messages WHERE recipient = ? ORDER BY timestamp ASC", (username,))
        messages = cursor.fetchall()
        if messages:
            with self.lock:
                client_sock = self.clients.get(username)
            if client_sock:
                for sender, message, timestamp in messages:
                    msg_packet = {"command": "msg", "from": sender, "to": username, "body": message, "timestamp": str(timestamp)}
                    send_with_delimiter(client_sock, msg_packet)
                cursor.execute("DELETE FROM offline_messages WHERE recipient = ?", (username,))
                conn.commit()
        conn.close()

    def _notify_typing(self, request):
        recipient = request.get('to')
        with self.lock:
            recipient_socket = self.clients.get(recipient)
        if recipient_socket:
            send_with_delimiter(recipient_socket, request)

    def _broadcast_status(self, username, status):
        response = {"command": "status_update", "user": username, "status": status}
        with self.lock:
            for client_sock in self.clients.values():
                send_with_delimiter(client_sock, response)

if __name__ == "__main__":
    server = Server()
    server.start()