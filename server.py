import socket
import time
import sys
import json

class VoiceServer:
    def __init__(self, name="Default Server", ip='0.0.0.0', port=5555):
        self.server_name = name
        self.ip = ip
        self.port = port
        self.chunk = 1024
        self.timeout = 30
        
        self.clients = []
        self.message_history = [] # Массив словарей {"id": ..., "message": ...}
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def start(self):
        try:
            self.server_socket.bind((self.ip, self.port))
            self.server_socket.settimeout(0.5)
            print("-" * 30)
            print(f"СЕРВЕР: {self.server_name} ЗАПУЩЕН")
            print("-" * 30)
        except Exception as e:
            print(f"Ошибка: {e}")
            return

        while True:
            try:
                try:
                    data, addr = self.server_socket.recvfrom(self.chunk * 8)
                except socket.timeout:
                    self._check_timeouts()
                    continue

                if not data: continue
                self._handle_packet(data, addr)
                self._check_timeouts()

            except KeyboardInterrupt:
                break
        self.server_socket.close()

    def _handle_packet(self, data, addr):
        packet_type = data[0]
        payload = data[1:]
        client_id = str(addr)

        client = next((c for c in self.clients if c["id"] == client_id), None)

        # 0 - ПОДКЛЮЧЕНИЕ
        if packet_type == 0:
            if not client:
                name = payload.decode('utf-8') if payload else "Anonymous"
                new_client = {
                    "id": client_id, "ip": addr[0], "port": addr[1],
                    "name": name, "last_seen": time.time()
                }
                self.clients.append(new_client)
                
                # 1. Отправляем имя сервера
                welcome = f"SERVER_NAME|{self.server_name}".encode('utf-8')
                self.server_socket.sendto(bytes([0]) + welcome, addr)
                
                # 2. Отправляем историю сообщений (API тип 3)
                self.send_history(addr)
                
                # 3. Рассылаем всем обновленный список участников (API тип 3)
                self.broadcast_user_list()
            else:
                client["last_seen"] = time.time()

        # 1 - ЗВУК (без изменений)
        elif packet_type == 1:
            if client:
                client["last_seen"] = time.time()
                for c in self.clients:
                    if c["id"] != client_id:
                        try: self.server_socket.sendto(data, (c["ip"], c["port"]))
                        except: pass

        # 2 - ТЕКСТ
        elif packet_type == 2:
            if client:
                client["last_seen"] = time.time()
                msg_text = payload.decode('utf-8')
                
                # Сохраняем в историю (для API)
                history_entry = {"id": client["name"], "message": msg_text}
                self.message_history.append(history_entry)
                
                # Рассылаем само сообщение (тип 2)
                broadcast = f"{client['name']}: {msg_text}".encode('utf-8')
                for c in self.clients:
                    try: self.server_socket.sendto(bytes([2]) + broadcast, (c["ip"], c["port"]))
                    except: pass

    # --- API МЕТОДЫ ---

    def broadcast_user_list(self):
        """Отправляет всем клиентам список участников (Тип 3)"""
        user_data = {
            "action": "users",
            "objects": [{"id": c["id"], "name": c["name"]} for c in self.clients]
        }
        self._send_api_json(user_data)

    def send_history(self, addr):
        """Отправляет конкретному клиенту историю сообщений (Тип 3)"""
        history_data = {
            "action": "messages",
            "objects": self.message_history[-20:] # Последние 20 сообщений
        }
        self._send_api_json(history_data, addr)

    def _send_api_json(self, data_dict, target_addr=None):
        """Вспомогательный метод для упаковки JSON в пакет типа 3"""
        json_payload = json.dumps(data_dict, ensure_ascii=False).encode('utf-8')
        packet = bytes([3]) + json_payload
        
        if target_addr:
            self.server_socket.sendto(packet, target_addr)
        else:
            # Рассылка всем
            for c in self.clients:
                try: self.server_socket.sendto(packet, (c["ip"], c["port"]))
                except: pass

    def _check_timeouts(self):
        now = time.time()
        initial_len = len(self.clients)
        self.clients = [c for c in self.clients if now - c["last_seen"] < self.timeout]
        
        if len(self.clients) < initial_len:
            print("[INFO] Клиент отключился по таймауту. Обновляю список...")
            self.broadcast_user_list()

if __name__ == "__main__":
    name = sys.argv[1] if len(sys.argv) > 1 else "Voce Chat"
    server = VoiceServer(name=name)
    server.start()