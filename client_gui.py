# client_gui.py

import tkinter as tk
from tkinter import scrolledtext, messagebox
import socket
import threading
import json
import queue
from datetime import datetime
import hashlib

# --- FUNÇÃO DE COMUNICAÇÃO ---
def send_with_delimiter(sock, data):
    """Envia dados JSON com um delimitador de nova linha."""
    try:
        sock.sendall(json.dumps(data).encode('utf-8') + b'\n')
    except (ConnectionResetError, BrokenPipeError):
        pass

# --- CLASSE PRINCIPAL DA APLICAÇÃO ---
class ChatClient:
    def __init__(self, root):
        self.root = root
        self.root.withdraw() # Esconde a janela principal até o login
        self.sock = None
        self.username = None
        self.current_chat_partner = None
        self.typing_timer = None
        self.message_queue = queue.Queue() # Fila para comunicação thread-safe com a GUI

        self.show_login_window()
        self.process_queue() # Inicia o processador de fila da GUI

    def show_login_window(self):
        """Cria e exibe a janela de login."""
        self.login_win = tk.Toplevel(self.root)
        self.login_win.title("Login")
        self.login_win.geometry("300x150")
        self.login_win.resizable(False, False)
        self.login_win.protocol("WM_DELETE_WINDOW", self.on_closing_login) # Garante que o app feche

        tk.Label(self.login_win, text="Usuário:").pack(pady=(10, 0))
        self.user_entry = tk.Entry(self.login_win)
        self.user_entry.pack(fill=tk.X, padx=10)
        tk.Label(self.login_win, text="Senha:").pack(pady=(5, 0))
        self.pass_entry = tk.Entry(self.login_win, show="*")
        self.pass_entry.pack(fill=tk.X, padx=10)

        btn_frame = tk.Frame(self.login_win)
        btn_frame.pack(pady=10)
        tk.Button(btn_frame, text="Login", command=self.login).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="Registrar", command=self.register).pack(side=tk.LEFT, padx=5)

    def on_closing_login(self):
        """Ação para quando a janela de login é fechada."""
        self.root.destroy()

    def connect_to_server(self):
        """Estabelece a conexão com o servidor, se ainda não estiver conectado."""
        if self.sock:
            return True
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.connect(('localhost', 8080))
            return True
        except ConnectionRefusedError:
            messagebox.showerror("Erro de Conexão", "Não foi possível conectar ao servidor.")
            self.sock = None
            return False

    def login(self):
        """Lida com a lógica de login."""
        if not self.connect_to_server():
            return
        
        username = self.user_entry.get()
        password = self.pass_entry.get()
        if not username or not password:
            messagebox.showwarning("Entrada Inválida", "Usuário e senha não podem ser vazios.")
            return

        request = {"command": "login", "username": username, "password": password}
        send_with_delimiter(self.sock, request)

        # A resposta do login é a primeira, então um recv simples aqui é seguro
        try:
            data = self.sock.recv(4096).decode('utf-8').strip()
            response = json.loads(data)
            if response.get("status") == "ok":
                self.username = username
                self.login_win.destroy()
                self.setup_main_window() # Monta a janela principal do chat
                threading.Thread(target=self.receive_messages, daemon=True).start()
                send_with_delimiter(self.sock, {"command": "get_users"})
            else:
                messagebox.showerror("Erro de Login", response.get("message"))
        except (IOError, json.JSONDecodeError):
            messagebox.showerror("Erro", "Falha na comunicação com o servidor.")
    
    def register(self):
        """Lida com a lógica de registro."""
        # Para registro, criamos uma conexão temporária
        try:
            temp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            temp_sock.connect(('localhost', 8080))
        except ConnectionRefusedError:
            messagebox.showerror("Erro de Conexão", "Não foi possível conectar ao servidor.")
            return

        username = self.user_entry.get()
        password = self.pass_entry.get()
        if not username or not password:
            messagebox.showwarning("Entrada Inválida", "Usuário e senha não podem ser vazios.")
            temp_sock.close()
            return
        
        request = {"command": "register", "username": username, "password": password}
        send_with_delimiter(temp_sock, request)

        try:
            data = temp_sock.recv(4096).decode('utf-8').strip()
            response = json.loads(data)
            messagebox.showinfo("Registro", response.get("message"))
        except (IOError, json.JSONDecodeError):
            messagebox.showerror("Erro", "Falha na comunicação com o servidor.")
        finally:
            temp_sock.close()

    def setup_main_window(self):
        """Cria os widgets da janela principal do chat."""
        self.root.deiconify() # Mostra a janela principal
        self.root.title(f"Chat - {self.username}")
        self.root.geometry("700x500")
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing_main)

        main_frame = tk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Frame da Lista de Contatos [cite: 16]
        contacts_frame = tk.Frame(main_frame, bd=2, relief=tk.GROOVE)
        contacts_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
        tk.Label(contacts_frame, text="Contatos").pack()
        self.contacts_list = tk.Listbox(contacts_frame, width=25)
        self.contacts_list.pack(fill=tk.Y, expand=True)
        self.contacts_list.bind('<<ListboxSelect>>', self.on_contact_select)

        # Frame da Conversa
        chat_frame = tk.Frame(main_frame)
        chat_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.status_label = tk.Label(chat_frame, text="Selecione um contato para conversar", anchor='w')
        self.status_label.pack(fill=tk.X)
        self.chat_display = scrolledtext.ScrolledText(chat_frame, state='disabled', wrap=tk.WORD, bd=2, relief=tk.GROOVE)
        self.chat_display.pack(fill=tk.BOTH, expand=True)
        
        # Frame de Entrada de Mensagem
        msg_frame = tk.Frame(chat_frame)
        msg_frame.pack(fill=tk.X, pady=5)
        self.msg_entry = tk.Entry(msg_frame, bd=2, relief=tk.GROOVE)
        self.msg_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.msg_entry.bind("<KeyPress>", self.on_typing)
        self.msg_entry.bind("<Return>", self.send_message)
        send_button = tk.Button(msg_frame, text="Enviar", command=self.send_message)
        send_button.pack(side=tk.RIGHT, padx=5)

    def process_queue(self):
        """Processa mensagens da fila para atualizar a GUI com segurança."""
        try:
            while True:
                message = self.message_queue.get_nowait()
                self.handle_server_message(message)
        except queue.Empty:
            pass
        finally:
            self.root.after(100, self.process_queue)

    def receive_messages(self):
        """Escuta o servidor em uma thread separada e coloca mensagens na fila."""
        buffer = ""
        while self.sock:
            try:
                data = self.sock.recv(2048).decode('utf-8')
                if not data:
                    self.message_queue.put({"command": "server_shutdown"})
                    break
                buffer += data
                while '\n' in buffer:
                    message_str, buffer = buffer.split('\n', 1)
                    self.message_queue.put(json.loads(message_str))
            except (ConnectionError, json.JSONDecodeError):
                self.message_queue.put({"command": "server_shutdown"})
                break

    def handle_server_message(self, message):
        """Interpreta a mensagem do servidor e atualiza a GUI."""
        command = message.get("command")
        if command == "user_list":
            self.update_contacts_list(message.get("users", {}))
        elif command == "status_update":
            self.update_user_status(message.get("user"), message.get("status"))
        elif command == "msg": # Recebimento de mensagens em tempo real [cite: 17]
            # Também recebe mensagens offline ao logar [cite: 20]
            if self.current_chat_partner == message.get("from"):
                self.display_message(message)
        elif command == "typing" and self.current_chat_partner == message.get("from"):
            self.display_typing_status(message.get("status"))
        elif command == "server_shutdown":
            if self.sock:
                self.sock.close()
                self.sock = None
            messagebox.showerror("Conexão Perdida", "O servidor encerrou a conexão.")
            self.on_closing_main()

    def update_contacts_list(self, users):
        """Atualiza a Listbox de contatos com nomes e status."""
        self.contacts_list.delete(0, tk.END)
        for user, status in sorted(users.items()):
            if user != self.username:
                # Exibe o status online/offline na lista de contatos [cite: 19]
                self.contacts_list.insert(tk.END, f"{user} ({status})")

    def update_user_status(self, user, status):
        """Atualiza o status de um único usuário na lista."""
        for i, item in enumerate(self.contacts_list.get(0, tk.END)):
            if item.startswith(f"{user} "):
                self.contacts_list.delete(i)
                self.contacts_list.insert(i, f"{user} ({status})")
                return

    def display_message(self, message):
        """Adiciona uma mensagem recebida à janela de chat."""
        sender = message.get("from")
        body = message.get("body")
        timestamp = datetime.fromisoformat(message.get("timestamp").split('.')[0]).strftime('%H:%M:%S')
        formatted_message = f"[{timestamp}] {sender}: {body}\n"
        
        self.chat_display.config(state='normal')
        self.chat_display.insert(tk.END, formatted_message)
        self.chat_display.config(state='disabled')
        self.chat_display.see(tk.END) # Rola para o final

    def display_typing_status(self, status):
        """Mostra ou esconde a notificação 'digitando...'."""
        if status == "start":
            self.status_label.config(text=f"{self.current_chat_partner} está digitando...")
        else: # stop
            self.status_label.config(text=f"Conversando com {self.current_chat_partner}")

    def on_contact_select(self, event):
        """Ação para quando um contato é selecionado na lista."""
        selection = event.widget.curselection()
        if selection:
            index = selection[0]
            contact_info = event.widget.get(index)
            self.current_chat_partner = contact_info.split(' ')[0]
            self.status_label.config(text=f"Conversando com {self.current_chat_partner}")
            self.chat_display.config(state='normal')
            self.chat_display.delete(1.0, tk.END)
            self.chat_display.config(state='disabled')

    def send_message(self, event=None):
        """Envia o conteúdo da caixa de entrada para o contato selecionado."""
        msg_body = self.msg_entry.get()
        if msg_body and self.current_chat_partner:
            # Envia o pacote com remetente, destinatário, etc. [cite: 31]
            msg_packet = {"command": "msg", "from": self.username, "to": self.current_chat_partner, "body": msg_body}
            send_with_delimiter(self.sock, msg_packet)
            
            # Exibe a própria mensagem na tela
            timestamp = datetime.now().strftime('%H:%M:%S')
            formatted_message = f"[{timestamp}] Você: {msg_body}\n"
            self.chat_display.config(state='normal')
            self.chat_display.insert(tk.END, formatted_message)
            self.chat_display.config(state='disabled')
            self.chat_display.see(tk.END)
            self.msg_entry.delete(0, tk.END)
            self.stop_typing()

    def on_typing(self, event=None):
        """Envia o evento 'digitando' e agenda o evento 'parou de digitar'."""
        if self.current_chat_partner:
            # Envia "evento de digitação" [cite: 36]
            send_with_delimiter(self.sock, {"command": "typing", "from": self.username, "to": self.current_chat_partner, "status": "start"})
            if self.typing_timer:
                self.root.after_cancel(self.typing_timer)
            # Agenda o envio do "parou de digitar" após 2 segundos [cite: 39]
            self.typing_timer = self.root.after(2000, self.stop_typing)

    def stop_typing(self):
        """Envia o evento 'parou de digitar'."""
        if self.current_chat_partner:
            send_with_delimiter(self.sock, {"command": "typing", "from": self.username, "to": self.current_chat_partner, "status": "stop"})
            if self.typing_timer:
                self.root.after_cancel(self.typing_timer)
                self.typing_timer = None

    def on_closing_main(self):
        """Ação para quando a janela principal é fechada."""
        if self.sock:
            self.sock.close()
            self.sock = None
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = ChatClient(root)
    root.mainloop()